import os
import subprocess
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from mutagen.id3 import ID3, TIT2, TPE1, APIC

from utils import check_subscription, get_channel_cover, auto_clear_cache, DB_FILE, MAX_FILE_SIZE, DEFAULT_AUDIO_QUALITY, processing_now, queue
from keyboards import quality_keyboard

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
🎧 أرسل ملف صوت أو فيديو وسيتم تعديل الاسم والفنان تلقائياً.
🎚 للتحكم في جودة الصوت اضغط /quality
""")

# لوحة تحكم المالك
async def panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    OWNER_ID = 8460454874
    global processing_now, queue

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

# التعامل مع الملفات (صوت/فيديو)
async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global processing_now, queue
    user_id = update.message.from_user.id

    if not await check_subscription(user_id, context):
        await update.message.reply_text("⚠️ اشترك بالقناة أولاً")
        return

    if processing_now >= 3:
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

    if not file or size > MAX_FILE_SIZE:
        await update.message.reply_text("❌ فشل التحميل أو تجاوز الحد 70MB")
        processing_now -= 1
        return

    input_path = f"input_{user_id}"
    output_path = f"output_{user_id}.mp3"
    await file.download_to_drive(input_path)
    await update.message.reply_text("⏳ جاري التحويل...")

    audio_quality = context.user_data.get("audio_quality", DEFAULT_AUDIO_QUALITY)
    result = subprocess.run([
        "ffmpeg", "-i", input_path, "-vn", "-map_metadata", "-1",
        "-ac", "2", "-b:a", audio_quality, "-preset", "ultrafast", "-threads", "2",
        output_path, "-y"
    ], capture_output=True)
    os.remove(input_path)

    if result.returncode != 0:
        await update.message.reply_text("❌ فشل التحويل")
        processing_now -= 1
        return

    context.user_data["file_path"] = output_path
    context.user_data["step"] = "title"
    await update.message.reply_text("📝 ارسل اسم الأغنية:")

# التعامل مع النصوص (عنوان وفنان)
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            audio = ID3(file_path)
        except:
            audio = ID3()
        audio["TIT2"] = TIT2(encoding=3, text=title)
        audio["TPE1"] = TPE1(encoding=3, text=artist)

        cover_path = await get_channel_cover(context)
        if cover_path and os.path.exists(cover_path):
            with open(cover_path, "rb") as img:
                audio["APIC"] = APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=img.read())
        audio.save(file_path)

        with open(file_path, "rb") as f:
            await update.message.reply_audio(audio=f, title=title, performer=artist)

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
            await media_handler(next_update, context)