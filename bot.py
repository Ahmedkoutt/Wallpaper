import streamlit as st
import logging
import httpx
import sqlite3
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# =============================
# 🔐 تحميل المفاتيح من Streamlit Secrets
# =============================
required_secrets = [
    "PEXELS_API_KEY",
    "TELEGRAM_TOKEN",
    "OWNER_ID",
    "DEVELOPER_USER"
]

for key in required_secrets:
    if key not in st.secrets:
        st.error(f"❌ Missing secret: {key}")
        st.stop()

PEXELS_API_KEY = st.secrets["PEXELS_API_KEY"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
OWNER_ID = int(st.secrets["OWNER_ID"])
DEVELOPER_USER = st.secrets["DEVELOPER_USER"]

st.success("🔐 Secrets Loaded Successfully")

# =============================
# 🗄 قاعدة البيانات
# =============================
DB_NAME = "pexels_v5.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            join_date TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            category TEXT PRIMARY KEY,
            downloads INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def log_user(user):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?)",
        (user.id, user.first_name, user.username, datetime.now().strftime("%Y-%m-%d"))
    )
    conn.commit()
    conn.close()

def track_download(category):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO stats VALUES (?, 0)", (category,))
    c.execute("UPDATE stats SET downloads = downloads + 1 WHERE category = ?", (category,))
    conn.commit()
    conn.close()

# =============================
# 📂 الفئات
# =============================
CATEGORIES = [
    ("🌍 شخصيات عالمية", "Influential People Celebrity"),
    ("📚 دراسة وتحفيز", "Study Motivation Library"),
    ("👦 بروفايل شباب", "Men Portrait Fashion"),
    ("👧 بروفايل بنات", "Women Portrait Aesthetic"),
    ("💻 برمجة وهكر", "Coding Cybersecurity"),
    ("🎮 جيمنج", "Gaming Setup 4k"),
    ("🌆 سيبيربانك", "Cyberpunk Futuristic City"),
    ("🌌 فضاء 8K", "Deep Space Nebula"),
    ("🏎 سيارات فارهة", "Luxury Supercars"),
    ("💎 حياة الأثرياء", "Luxury Lifestyle"),
    ("🌑 دارك / غامض", "Dark Moody Aesthetic"),
    ("🍃 هدوء ومينيمال", "Minimalist Zen"),
    ("🌸 طبيعة خلابة", "Breathtaking Nature"),
    ("🌊 محيطات", "Ocean Blue Undersea"),
    ("🍂 خريف وشجن", "Moody Autumn"),
    ("⛩ أنمي ياباني", "Anime Style Scenery"),
    ("🐱 حيوانات أليفة", "Cute Pets"),
    ("🍎 طعام شهي", "Gourmet Food Photography"),
    ("🏛 معمار هندسي", "Modern Architecture"),
    ("🎨 فن تجريدي", "Abstract Fluid Art")
]

# =============================
# ⌨️ لوحة المفاتيح
# =============================
def main_menu(user_id):
    keyboard = [
        [
            InlineKeyboardButton("📱 Phone", callback_data="setdev_mobile"),
            InlineKeyboardButton("🖥 Laptop", callback_data="setdev_laptop")
        ],
        [
            InlineKeyboardButton("👨‍💻 المطور", url=f"https://t.me/{DEVELOPER_USER[1:]}")
        ]
    ]
    if user_id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("👑 لوحة الإدارة", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

# =============================
# 🚀 أوامر البوت
# =============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user(user)
    await update.message.reply_text(
        f"مرحباً {user.first_name} ✨\nاختر نوع جهازك:",
        reply_markup=main_menu(user.id)
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("setdev_"):
        dev = data.split("_")[1]
        kb = []
        for i in range(0, len(CATEGORIES), 2):
            row = [
                InlineKeyboardButton(
                    CATEGORIES[i][0],
                    callback_data=f"get_{dev}_{CATEGORIES[i][1]}_1"
                )
            ]
            if i + 1 < len(CATEGORIES):
                row.append(
                    InlineKeyboardButton(
                        CATEGORIES[i + 1][0],
                        callback_data=f"get_{dev}_{CATEGORIES[i + 1][1]}_1"
                    )
                )
            kb.append(row)
        kb.append([InlineKeyboardButton("🔙 عودة", callback_data="start_back")])
        await query.edit_message_text("اختر فئة:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("get_"):
        _, dev, cat, page = data.split("_")
        track_download(cat)

        params = {
            "query": cat,
            "per_page": 1,
            "page": page,
            "orientation": "portrait" if dev == "mobile" else "landscape"
        }

        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_API_KEY},
                params=params
            )
            res = r.json()

        if res.get("photos"):
            p = res["photos"][0]
            photo_url = p["src"]["large2x"]
            caption = f"🖼 {cat}\n📸 {p['photographer']}"
            kb = [[
                InlineKeyboardButton("🔄 صورة أخرى", callback_data=f"get_{dev}_{cat}_{int(page)+1}"),
                InlineKeyboardButton("💎 4K", url=p["src"]["original"])
            ]]
            await context.bot.send_photo(
                chat_id=user_id,
                photo=photo_url,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(kb)
            )

# =============================
# ▶️ تشغيل البوت (تحذير: تجريبي على Streamlit)
# =============================
init_db()

if st.button("▶️ تشغيل البوت"):
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))

    st.info("🚀 البوت يعمل الآن (وضع Streamlit)")
    app.run_polling()
