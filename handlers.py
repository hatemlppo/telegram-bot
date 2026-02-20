import os
import subprocess
import sqlite3
import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from mutagen.id3 import ID3, TIT2, TPE1, APIC

# استيراد الأدوات المساعدة
from utils import check_subscription, get_channel_cover, DB_FILE, MAX_FILE_SIZE, DEFAULT_AUDIO_QUALITY, is_maintenance

# تعريف الايدي الخاص بالمالك (تأكد من مطابقته لما في admin_panel)
OWNER_ID = 8460454874 

# متغيرات عالمية مؤقتة للتحكم في الضغط
processing_now = 0
queue = []

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_maintenance(update, context): return
    
    user = update.message.from_user
    if not await check_subscription(user.id, context):
        await update.message.reply_text(f"⚠️ يجب الاشتراك في القناة أولاً: @THTOMI")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id, first_name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🎵 مرحباً {user.first_name}!\n"
        f"🎧 أرسل ملف صوت أو فيديو وسيتم تعديل الاسم والفنان تلقائياً.\n"
        f"🎚 للتحكم في جودة الصوت اضغط /quality"
    )

async def quality_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_maintenance(update, context): return
    from keyboards import quality_keyboard
    await update.message.reply_text("اختر جودة الصوت المطلوبة:", reply_markup=quality_keyboard())

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_maintenance(update, context): return
    
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
    
    file_obj = update.message.audio or update.message.video or update.message.document
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
    
    process = subprocess.run([
        "ffmpeg", "-i", input_path, "-vn", "-acodec", "libmp3lame",
        "-ac", "2", "-b:a", audio_quality, output_path, "-y"
    ], capture_output=True)

    if os.path.exists(input_path): os.remove(input_path)

    if process.returncode != 0:
        await wait_msg.edit_text("❌ فشل التحويل")
        processing_now -= 1
        return

    context.user_data["file_path"] = output_path
    context.user_data["step"] = "title"
    await wait_msg.edit_text("📝 تم التحويل! الآن أرسل اسم الأغنية (Title):")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # 1. ميزة الإذاعة للمالك (تُفحص أولاً)
    if context.user_data.get('admin_step') == 'broadcasting' and user_id == OWNER_ID:
        msg = update.message.text
        conn = sqlite3.connect(DB_FILE)
        users = conn.execute("SELECT user_id FROM users").fetchall()
        conn.close()
        
        count = 0
        status_msg = await update.message.reply_text(f"🚀 جاري الإذاعة لـ {len(users)} مستخدم...")
        
        for user in users:
            try:
                await context.bot.send_message(chat_id=user[0], text=msg)
                count += 1
                await asyncio.sleep(0.05) # حماية من الـ Flood
            except Exception:
                continue
        
        await status_msg.edit_text(f"✅ تم الانتهاء! استلم الرسالة {count} مستخدم بنجاح.")
        context.user_data['admin_step'] = None
        return

    # 2. منطق تعديل الميتادات (العنوان والفنان)
    if "file_path" not in context.user_data:
        return 

    file_path = context.user_data["file_path"]
    step = context.user_data.get("step")

    if step == "title":
        context.user_data["title"] = update.message.text
        context.user_data["step"] = "artist"
        await update.message.reply_text("🎤 ارسل اسم المغني (Artist):")
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

        # حفظ إحصائيات الملف في قاعدة البيانات
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO files(user_id, title, artist, date) VALUES (?, ?, ?, ?)",
                  (user_id, title, artist, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

        if os.path.exists(file_path): os.remove(file_path)
        context.user_data.clear()
        
        global processing_now
        processing_now -= 1
        
        # معالجة الملف التالي في الطابور
        if queue:
            next_update = queue.pop(0)
            await media_handler(next_update, context)
