import streamlit as st
import logging
import httpx
import sqlite3
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler,
    filters, ContextTypes
)

# ----------------- Streamlit Config -----------------
st.set_page_config(page_title="Telegram Bot Runner", layout="centered")
st.title("🤖 Telegram Bot is Running")

# ----------------- Secrets -----------------
PEXELS_API_KEY = st.secrets["PEXELS_API_KEY"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
OWNER_ID = int(st.secrets["OWNER_ID"])
DEVELOPER_USER = st.secrets["DEVELOPER_USER"]

# ----------------- Database -----------------
def init_db():
    conn = sqlite3.connect('pexels_v5.db')
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users
        (user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT, join_date TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS stats
        (category TEXT PRIMARY KEY, downloads INTEGER DEFAULT 0)""")
    conn.commit()
    conn.close()

def log_user(user):
    conn = sqlite3.connect('pexels_v5.db')
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?)",
        (user.id, user.first_name, user.username,
         datetime.now().strftime("%Y-%m-%d"))
    )
    conn.commit()
    conn.close()

def track_download(category):
    conn = sqlite3.connect('pexels_v5.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO stats VALUES (?, 0)", (category,))
    c.execute("UPDATE stats SET downloads = downloads + 1 WHERE category = ?", (category,))
    conn.commit()
    conn.close()

# ----------------- Categories -----------------
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
    ("🍃 مينيمال", "Minimalist Zen"),
    ("🌸 طبيعة", "Breathtaking Nature"),
    ("🌊 محيطات", "Ocean Blue"),
    ("🍂 خريف", "Moody Autumn"),
    ("⛩ أنمي", "Anime Scenery"),
    ("🐱 حيوانات", "Cute Pets"),
    ("🍎 طعام", "Gourmet Food"),
    ("🏛 معمار", "Modern Architecture"),
    ("🎨 فن", "Abstract Art")
]

# ----------------- Bot Logic -----------------
def main_menu(user_id):
    kb = [
        [InlineKeyboardButton("📱 Phone", callback_data="setdev_mobile"),
         InlineKeyboardButton("💻 Laptop", callback_data="setdev_laptop")],
        [InlineKeyboardButton("👨‍💻 المطور", url=f"https://t.me/{DEVELOPER_USER[1:]}")]
    ]
    if user_id == OWNER_ID:
        kb.append([InlineKeyboardButton("👑 الإدارة", callback_data="admin_panel")])
    return InlineKeyboardMarkup(kb)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_user(update.effective_user)
    await update.message.reply_text(
        "✨ مرحباً بك في بوت الخلفيات الاحترافي V5",
        reply_markup=main_menu(update.effective_user.id)
    )

# ----------------- Run Bot Once -----------------
async def run_bot():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(lambda u, c: None))
    await app.initialize()
    await app.start()
    await app.bot.initialize()
    await app.updater.start_polling()

# ----------------- Streamlit Safe Runner -----------------
if "bot_started" not in st.session_state:
    st.session_state.bot_started = True
    asyncio.run(run_bot())
    st.success("✅ Telegram Bot Started Successfully")
else:
    st.info("🟢 Bot already running")
