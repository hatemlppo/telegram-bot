import os
import subprocess
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from mutagen.id3 import ID3, TIT2, TPE1, APIC

from utils import check_subscription, get_channel_cover, DB_FILE, MAX_FILE_SIZE, DEFAULT_AUDIO_QUALITY
from keyboards import quality_keyboard

# متغيرات عالمية بسيطة (للتوضيح)
processing_now = 0
queue = []

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not await check_subscription(user.id, context):
        await update.message.reply_text(f"⚠️ يجب الاشتراك في القناة أولاً: @THTOMI")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id, first_name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit()
    conn.close()

    context.user_data["audio_quality"] = DEFAULT_AUDIO_QUALITY
    await update.message.reply_text(
        f"🎵 مرحباً {user.first_name}!\n"
        f"🎧 أرسل ملف صوت أو فيديو وسيتم تعديل الاسم والفنان تلقائياً.\n"
        f"🎚 للتحكم في جودة الصوت اضغط /quality"
    )

async def quality_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اختر جودة الصوت المطلوبة:", reply_markup=quality_keyboard())

async def panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    OWNER_ID = 8460454874 # تأكد من رقم الايدي الخاص بك
    if update.message.from_user.id != OWNER_ID:
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM files")
    total_files = c.fetchone()[0]
    conn.close()

    await update.message.reply_text(
        f"📊 لوحة التحكم\n\n"
        f"👥 عدد المستخدمين: {total_users}\n"
        f"📁 عدد الملفات المعالجة: {total_files}\n"
        f"⚙ المعالجة الحالية: {processing_now}\n"
        f"⏳ في الطابور: {len(queue)}"
    )

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global processing_now
    user_id = update.message.from_user.id

    if not await check_subscription(user_id, context):
        await update.message.reply_text("⚠️ اشترك بالقناة أولاً @THTOMI")
        return

    if processing_now >= 3:
        queue.append(update)
        await update.message.reply_text("⏳ يوجد ضغط عالي، تم إدخالك في الطابور...")
        return

    processing_now += 1
    
    file_obj = None
    if update.message.audio:
        file_obj = update.message.audio
    elif update.message.video:
        file_obj = update.message.video
    elif update.message.document:
        file_obj = update.message.document

    if not file_obj or file_obj.file_size > MAX_FILE_SIZE:
        await update.message.reply_text("❌ فشل التحميل أو تجاوز الحد 70MB")
        processing_now -= 1
        return

    wait_msg = await update.message.reply_text("⏳ جاري تحميل ومعالجة الملف...")
    
    tg_file = await file_obj.get_file()
    input_path = f"input_{user_id}_{file_obj.file_id[:5]}"
    output_path = f"output_{user_id}_{file_obj.file_id[:5]}.mp3"
    
    await tg_file.download_to_drive(input_path)

    audio_quality = context.user_data.get("audio_quality", DEFAULT_AUDIO_QUALITY)
    
    # تشغيل ffmpeg
    process = subprocess.run([
        "ffmpeg", "-i", input_path, "-vn", "-acodec", "libmp3lame",
        "-ac", "2", "-b:a", audio_quality, output_path, "-y"
    ], capture_output=True)

    if os.path.exists(input_path): os.remove(input_path)

    if process.returncode != 0:
        await wait_msg.edit_text("❌ فشل التحويل عبر FFmpeg")
        processing_now -= 1
        return

    context.user_data["file_path"] = output_path
    context.user_data["step"] = "title"
    await wait_msg.edit_text("📝 تم التحويل! الآن أرسل اسم الأغنية (Title):")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global processing_now
    if "file_path" not in context.user_data:
        return # تجاهل النصوص العادية إذا لم يكن هناك ملف قيد المعالجة

    file_path = context.user_data["file_path"]
    step = context.user_data.get("step")
    user_id = update.message.from_user.id

    if step == "title":
        context.user_data["title"] = update.message.text
        context.user_data["step"] = "artist"
        await update.message.reply_text("🎤 ارسل اسم المغني (Artist):")
        return

    if step == "artist":
        title = context.user_data["title"]
        artist = update.message.text
        
        # تعديل الميتادات
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

        # حفظ الإحصائيات
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO files(user_id, title, artist, date) VALUES (?, ?, ?, ?)",
                  (user_id, title, artist, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

        if os.path.exists(file_path): os.remove(file_path)
        context.user_data.clear()
        processing_now -= 1
        
        # معالجة الملف التالي في الطابور إذا وجد
        if queue:
            next_update = queue.pop(0)
            await media_handler(next_update, context)
