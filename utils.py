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

# تنظيف الكاش
async def auto_clear_cache():
    for file in os.listdir():
        if file.endswith(".mp3"):
            os.remove(file)
    logging.info("🧹 تم تنظيف الملفات المؤقتة")

# التحقق من الاشتراك
async def check_subscription(user_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status not in ["left", "kicked"]
    except:
        return False

# جلب صورة القناة
async def get_channel_cover(context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(COVER_CACHE):
        return COVER_CACHE
    try:
        chat = await context.bot.get_chat(f"@{CHANNEL_USERNAME}")
        if chat.photo:
            photo = await chat.get_file(chat.photo.big_file_id)
            await photo.download_to_drive(COVER_CACHE)
            return COVER_CACHE
    except Exception as e:
        logging.error(f"خطأ جلب صورة القناة: {e}")
    return None