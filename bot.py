import streamlit as st
import threading
import logging
import httpx
import sqlite3
import asyncio
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ==================================================
# Streamlit UI
# ==================================================
st.set_page_config(page_title="Telegram Bot Runner", layout="centered")
st.title("🤖 Telegram Bot Running")
st.caption("Optimized • Cached • Stable")

# ==================================================
# Secrets
# ==================================================
PEXELS_API_KEY = st.secrets["PEXELS_API_KEY"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
OWNER_ID = int(st.secrets["OWNER_ID"])
DEVELOPER_USER = st.secrets["DEVELOPER_USER"]

# ==================================================
# Logging
# ==================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ==================================================
# Database (Singleton Connection)
# ==================================================
DB_CONN = sqlite3.connect(
    "pexels_v5.db",
    check_same_thread=False
)
DB_CURSOR = DB_CONN.cursor()

def init_db():
    DB_CURSOR.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            join_date TEXT
        )
    """)
    DB_CURSOR.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            category TEXT PRIMARY KEY,
            downloads INTEGER DEFAULT 0
        )
    """)
    DB_CONN.commit()

def log_user(user):
    DB_CURSOR.execute(
        "INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?)",
        (
            user.id,
            user.first_name,
            user.username,
            datetime.now().strftime("%Y-%m-%d")
        )
    )
    DB_CONN.commit()

def track_download(category):
    DB_CURSOR.execute(
        "INSERT OR IGNORE INTO stats VALUES (?, 0)",
        (category,)
    )
    DB_CURSOR.execute(
        "UPDATE stats SET downloads = downloads + 1 WHERE category = ?",
        (category,)
    )
    DB_CONN.commit()

# ==================================================
# Performance Layer
# ==================================================
HTTP_CLIENT = httpx.AsyncClient(timeout=10)

IMAGE_CACHE = {}
CACHE_TTL = 300  # seconds

USER_LAST_ACTION = {}

def can_proceed(user_id, cooldown=1.5):
    now = time.time()
    last = USER_LAST_ACTION.get(user_id, 0)
    if now - last < cooldown:
        return False
    USER_LAST_ACTION[user_id] = now
    return True

def get_cached(key):
    data = IMAGE_CACHE.get(key)
    if not data:
        return None
    if time.time() - data["time"] > CACHE_TTL:
        del IMAGE_CACHE[key]
        return None
    return data["value"]

def set_cached(key, value):
    IMAGE_CACHE[key] = {
        "value": value,
        "time": time.time()
    }

# ==================================================
# Categories
# ==================================================
CATEGORIES = [
    ("🌍 شخصيات عالمية", "Influential People Celebrity"),
    ("📚 دراسة وتحفيز", "Study Motivation Library"),
    ("👦 بروفايل شباب", "Men Portrait Fashion"),
    ("👧 بروفايل بنات", "Women Portrait Aesthetic"),
    ("💻 برمجة وهكر", "Coding Cybersecurity"),
    ("🎮 جيمنج", "Gaming Setup 4k"),
    ("🌆 سيبيربانك", "Cyberpunk Futuristic City"),
    ("🌌 فضاء", "Deep Space Nebula"),
    ("🏎 سيارات", "Luxury Supercars"),
    ("💎 حياة الأثرياء", "Luxury Lifestyle"),
    ("🌑 دارك", "Dark Moody Aesthetic"),
    ("🍃 مينيمال", "Minimalist Zen"),
    ("🌸 طبيعة", "Breathtaking Nature"),
    ("🌊 محيطات", "Ocean Blue"),
    ("🍂 خريف", "Moody Autumn"),
    ("⛩ أنمي", "Anime Scenery"),
    ("🐱 حيوانات", "Cute Pets"),
    ("🍎 طعام", "Gourmet Food"),
    ("🏛 معمار", "Modern Architecture"),
    ("🎨 فن", "Abstract Art"),
]

# ==================================================
# Keyboards
# ==================================================
def main_menu(user_id):
    keyboard = [
        [
            InlineKeyboardButton("📱 Phone", callback_data="setdev_mobile"),
            InlineKeyboardButton("💻 Laptop", callback_data="setdev_laptop")
        ],
        [
            InlineKeyboardButton(
                "👨‍💻 المطور",
                url=f"https://t.me/{DEVELOPER_USER[1:]}"
            )
        ]
    ]
    if user_id == OWNER_ID:
        keyboard.append(
            [InlineKeyboardButton("👑 لوحة الإدارة", callback_data="admin_panel")]
        )
    return InlineKeyboardMarkup(keyboard)

# ==================================================
# Handlers
# ==================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user(update.effective_user)
    await update.message.reply_text(
        "✨ مرحباً بك في بوت الخلفيات الاحترافي",
        reply_markup=main_menu(update.effective_user.id)
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if not can_proceed(user_id):
        return

    data = query.data

    if data == "start_back":
        await query.edit_message_text(
            "اختر نوع جهازك:",
            reply_markup=main_menu(user_id)
        )

    elif data.startswith("setdev_"):
        dev = data.split("_")[1]
        keyboard = []
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
            keyboard.append(row)

        keyboard.append(
            [InlineKeyboardButton("🔙 عودة", callback_data="start_back")]
        )

        await query.edit_message_text(
            "🔥 اختر فئة الخلفيات:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("get_"):
        _, dev, cat, page = data.split("_")
        page = int(page)
        track_download(cat)

        cache_key = f"{cat}_{dev}_{page}"
        photo_data = get_cached(cache_key)

        if not photo_data:
            params = {
                "query": cat,
                "per_page": 1,
                "page": page,
                "orientation": "portrait" if dev == "mobile" else "landscape"
            }

            r = await HTTP_CLIENT.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_API_KEY},
                params=params
            )
            res = r.json()
            if not res.get("photos"):
                return

            photo_data = res["photos"][0]
            set_cached(cache_key, photo_data)

        photo_url = photo_data["src"]["large2x"]
        caption = (
            f"🖼 الفئة: {cat}\n"
            f"📸 المصور: {photo_data['photographer']}"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 صورة أخرى",
                    callback_data=f"get_{dev}_{cat}_{page + 1}"
                ),
                InlineKeyboardButton(
                    "💎 الدقة الأصلية",
                    url=photo_data["src"]["original"]
                )
            ]
        ]

        await context.bot.send_photo(
            chat_id=user_id,
            photo=photo_url,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ==================================================
# Bot Runner
# ==================================================
BOT_LOCK = threading.Lock()

def start_bot():
    with BOT_LOCK:
        init_db()
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(callback_handler))
        app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), lambda *_: None)
        )
        app.run_polling()

# ==================================================
# Streamlit Safe Start
# ==================================================
if "bot_started" not in st.session_state:
    thread = threading.Thread(target=start_bot, daemon=True)
    thread.start()
    st.session_state.bot_started = True
    st.success("✅ البوت يعمل بكفاءة عالية")
else:
    st.info("🟢 البوت يعمل بالفعل")
