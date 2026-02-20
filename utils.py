import os
import sqlite3
import logging
from telegram.ext import ContextTypes

DB_FILE = "bot_stats.db"
MAX_FILE_SIZE = 70 * 1024 * 1024
DEFAULT_AUDIO_QUALITY = "192k"
processing_now = 0
queue = []
COVER_CACHE = "channel_cover_cached.jpg"
CHANNEL_USERNAME = "THTOMI"

# دالة لتهيئة قاعدة البيانات عند التشغيل
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, first_name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS files 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, artist TEXT, date TEXT)''')
    conn.commit()
    conn.close()

init_db()

async def auto_clear_cache():
    for file in os.listdir():
        if file.endswith(".mp3") or file.startswith("input_") or file.startswith("output_"):
            try:
                os.remove(file)
            except:
                pass
    logging.info("🧹 تم تنظيف الملفات المؤقتة")

async def check_subscription(user_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status not in ["left", "kicked"]
    except Exception as e:
        logging.error(f"خطأ في فحص الاشتراك: {e}")
        return False

async def get_channel_cover(context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(COVER_CACHE):
        return COVER_CACHE
    try:
        chat = await context.bot.get_chat(f"@{CHANNEL_USERNAME}")
        if chat.photo:
            photo_file = await context.bot.get_file(chat.photo.big_file_id)
            await photo_file.download_to_drive(COVER_CACHE)
            return COVER_CACHE
    except Exception as e:
        logging.error(f"خطأ جلب صورة القناة: {e}")
    return None
