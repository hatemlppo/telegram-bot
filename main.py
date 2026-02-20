import os
import subprocess
import logging
import sqlite3
from datetime import datetime
import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from mutagen.id3 import ID3, TIT2, TPE1, APIC

logging.basicConfig(level=logging.INFO)

# ====== إعدادات البوت ======
TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_USERNAME = "THTOMI"
MAX_FILE_SIZE = 70 * 1024 * 1024  # 70MB
MAX_CONCURRENT = 3
OWNER_ID = 123456789
COVER_CACHE = "channel_cover_cached.jpg"
DEFAULT_AUDIO_QUALITY = "192k"

# ====== قاعدة بيانات SQLite ======
DB_FILE = "bot_stats.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT,
                    artist TEXT,
                    date TIMESTAMP
                )''')
    conn.commit()
    conn.close()

init_db()

# ====== متغيرات التشغيل ======
processing_now = 0
queue = []

# ====== تنظيف الكاش ======
async def auto_clear_cache():
    for file in os.listdir():
        if file.endswith(".mp3"):
            os.remove(file)
    logging.info("🧹 تم تنظيف الملفات المؤقتة")

# ====== التحقق من الاشتراك ======
async def check_subscription(user_id, context):
    try:
        member = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status not in ["left", "kicked"]
    except:
        return False

# ====== جلب صورة القناة ======
async def get_channel_cover(context):
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

# ====== رسالة ترحيب ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id

    if not await check_subscription(user_id, context):
        await update.message.reply_text("⚠️ يجب الاشتراك في القناة أولاً")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id, first_name) VALUES (?, ?)", (user_id, user.first_name))
    conn.commit()
    conn.close()

    context.user_data["audio_quality"] = DEFAULT_AUDIO_QUALITY

    await update.message.reply_text(f"""
🎵 مرحباً {user.first_name}!

🤖 بوت تعديل الميتاداتا الاحترافي

━━━━━━━━━━━━━━
📦 الحد الأقصى للملف: 70MB
⏳ أقصى ملفات معالجة بنفس الوقت: 3
🎚 يمكنك اختيار جودة الصوت: /quality 128k | 192k | 256k
━━━━━━━━━━━━━━

🎧 أرسل ملف صوت أو فيديو
✔ سيتم تعديل الاسم والفنان
✔ إضافة صورة القناة تلقائياً
✔ سرعة معالجة عالية
✔ تنظيف تلقائي للكاش كل 10 دقائق
""")

# ====== تعيين جودة الصوت ======
async def set_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("❌ استخدم: /quality 128k | 192k | 256k")
        return

    quality = context.args[0]
    if quality not in ["128k", "192k", "256k"]:
        await update.message.reply_text("❌ الجودة غير صالحة! اختر: 128k, 192k, 256k")
        return

    context.user_data["audio_quality"] = quality
    await update.message.reply_text(f"✅ تم تعيين جودة الصوت: {quality}")

# ====== لوحة التحكم ======
async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM files")
    total_files = c.fetchone()[0]
    conn.close()

    await update.message.reply_text(f"""
📊 لوحة التحكم

👥 عدد المستخدمين: {total_users}
📁 عدد الملفات المعالجة: {total_files}
⚙ المعالجة الحالية: {processing_now}
⏳ في الطابور: {len(queue)}
""")

# ====== التعامل مع الملفات ======
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global processing_now, queue

    user_id = update.message.from_user.id

    if not await check_subscription(user_id, context):
        await update.message.reply_text("⚠️ اشترك بالقناة أولاً")
        return

    if processing_now >= MAX_CONCURRENT:
        queue.append(update)
        await update.message.reply_text("⏳ يوجد ضغط عالي، تم إدخالك في الطابور...")
        return

    processing_now += 1

    file = None
    size = 0
    if update.message.audio:
        file = await update.message.audio.get_file()
        size = update.message.audio.file_size
    elif update.message.video:
        file = await update.message.video.get_file()
        size = update.message.video.file_size
    elif update.message.document:
        file = await update.message.document.get_file()
        size = update.message.document.file_size

    if not file:
        processing_now -= 1
        return

    if size > MAX_FILE_SIZE:
        await update.message.reply_text("❌ تجاوز الحد المسموح 70MB")
        processing_now -= 1
        return

    input_path = f"input_{user_id}"
    output_path = f"output_{user_id}.mp3"

    await file.download_to_drive(input_path)
    await update.message.reply_text("⏳ جاري التحويل...")

    audio_quality = context.user_data.get("audio_quality", DEFAULT_AUDIO_QUALITY)

    result = subprocess.run([
        "ffmpeg",
        "-i", input_path,
        "-vn",
        "-map_metadata", "-1",
        "-ac", "2",
        "-b:a", audio_quality,
        "-preset", "ultrafast",
        "-threads", "2",
        output_path,
        "-y"
    ], capture_output=True)
    os.remove(input_path)

    if result.returncode != 0:
        await update.message.reply_text("❌ فشل التحويل")
        processing_now -= 1
        return

    context.user_data["file_path"] = output_path
    context.user_data["step"] = "title"
    await update.message.reply_text("📝 ارسل اسم الأغنية:")

# ====== التعامل مع النص ======
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global processing_now, queue

    if "file_path" not in context.user_data:
        return

    file_path = context.user_data["file_path"]
    step = context.user_data.get("step")
    user_id = update.message.from_user.id

    if step == "title":
        context.user_data["title"] = update.message.text
        context.user_data["step"] = "artist"
        await update.message.reply_text("🎤 ارسل اسم المغني:")
        return

    if step == "artist":
        title = context.user_data["title"]
        artist = update.message.text

        try:
            try:
                audio = ID3(file_path)
            except:
                audio = ID3()

            audio["TIT2"] = TIT2(encoding=3, text=title)
            audio["TPE1"] = TPE1(encoding=3, text=artist)

            cover_path = await get_channel_cover(context)
            if cover_path and os.path.exists(cover_path):
                with open(cover_path, "rb") as img:
                    audio["APIC"] = APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=img.read()
                    )

            audio.save(file_path)

            with open(file_path, "rb") as f:
                await update.message.reply_audio(
                    audio=f,
                    title=title,
                    performer=artist
                )

            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO files(user_id, title, artist, date) VALUES (?, ?, ?, ?)",
                      (user_id, title, artist, datetime.now()))
            conn.commit()
            conn.close()

            os.remove(file_path)
            context.user_data.clear()
            processing_now -= 1

            if queue:
                next_update = queue.pop(0)
                await handle_media(next_update, context)

        except Exception as e:
            logging.error(e)
            await update.message.reply_text("❌ حدث خطأ أثناء التعديل")
            processing_now -= 1
            if queue:
                next_update = queue.pop(0)
                await handle_media(next_update, context)

# ====== تشغيل البوت ======
def main():
    app = Application.builder().token(TOKEN).build()

    # شغل تنظيف الكاش كل 10 دقائق بشكل آمن
    app.job_queue.run_repeating(lambda _: asyncio.create_task(auto_clear_cache()), interval=600, first=10)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quality", set_quality))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.Document.ALL, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()