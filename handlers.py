import os
import subprocess
import sqlite3
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from mutagen.id3 import ID3, TIT2, TPE1, APIC

from utils import check_subscription, is_maintenance, DB_FILE, OWNER_ID, MAX_FILE_SIZE, get_channel_cover

# متغيرات للتحكم في الطابور
processing_now = 0
queue = []

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_maintenance(update, context): return
    from keyboards import main_menu_keyboard
    
    user = update.effective_user
    if not await check_subscription(user.id, context):
        await update.message.reply_text("⚠️ اشترك بالقناة أولاً: @THTOMI")
        return

    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO users(user_id, first_name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🚀 أهلاً بك {user.first_name} في بوت الخدمات الصوتية.\nإختر ماذا تريد أن تفعل الآن:",
        reply_markup=main_menu_keyboard()
    )

async def quality_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_maintenance(update, context): return
    from keyboards import quality_keyboard
    await update.message.reply_text("اختر الجودة المطلوبة:", reply_markup=quality_keyboard("edit"))

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data.startswith("q_"):
        parts = data.split("_")
        quality = parts[1] + "k"
        action = parts[2]
        context.user_data['selected_quality'] = quality
        context.user_data['action_type'] = action
        
        msg = "🎵 أرسل الآن الملف الصوتي (MP3) لتعديله:" if action == "edit" else "🎬 أرسل الآن ملف الفيديو لاستخراج الصوت منه:"
        await query.edit_message_text(f"✅ تم اختيار جودة {quality}.\n\n{msg}")
    
    elif data == "cancel_action":
        await query.edit_message_text("❌ تم إلغاء العملية.")
        context.user_data.clear()

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_maintenance(update, context): return
    global processing_now
    
    user_id = update.effective_user.id
    action = context.user_data.get('action_type')
    quality = context.user_data.get('selected_quality', "192k")

    if not action:
        await update.message.reply_text("❌ من فضلك اختر نوع العملية أولاً (تعديل أغنية أو استخراج من فيديو) من القائمة.")
        return

    # التحقق من نوع الملف المرسل
    file_obj = None
    if action == "edit" and update.message.audio:
        file_obj = update.message.audio
    elif action == "extract" and update.message.video:
        file_obj = update.message.video
    elif update.message.document:
        file_obj = update.message.document

    if not file_obj:
        await update.message.reply_text("❌ الملف المرسل لا يتوافق مع العملية المختارة.")
        return

    if file_obj.file_size > MAX_FILE_SIZE:
        await update.message.reply_text("❌ حجم الملف كبير جداً (الحد الأقصى 70MB).")
        return

    processing_now += 1
    wait_msg = await update.message.reply_text("⏳ جاري التحميل والمعالجة...")
    
    tg_file = await file_obj.get_file()
    input_path = f"input_{user_id}_{file_obj.file_id[:5]}"
    output_path = f"output_{user_id}_{file_obj.file_id[:5]}.mp3"
    
    await tg_file.download_to_drive(input_path)

    # تشغيل FFmpeg بناءً على العملية
    cmd = [
        "ffmpeg", "-i", input_path, "-vn", "-acodec", "libmp3lame",
        "-ac", "2", "-b:a", quality, output_path, "-y"
    ]
    
    process = subprocess.run(cmd, capture_output=True)

    if os.path.exists(input_path): os.remove(input_path)

    if process.returncode != 0:
        await wait_msg.edit_text("❌ حدث خطأ أثناء المعالجة.")
        processing_now -= 1
        return

    context.user_data["file_path"] = output_path
    context.user_data["step"] = "title"
    await wait_msg.edit_text("📝 تمت المعالجة! الآن أرسل (اسم الأغنية) الجديد:")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id

    # الإذاعة للأدمن
    if context.user_data.get('admin_step') == 'broadcasting' and user_id == OWNER_ID:
        conn = sqlite3.connect(DB_FILE)
        users = conn.execute("SELECT user_id FROM users").fetchall()
        conn.close()
        for u in users:
            try: await context.bot.send_message(chat_id=u[0], text=user_text)
            except: pass
        context.user_data['admin_step'] = None
        await update.message.reply_text("✅ تمت الإذاعة بنجاح.")
        return

    # أزرار القائمة الرئيسية
    if user_text == "🎵 تعديل الأغاني":
        from keyboards import quality_keyboard
        await update.message.reply_text("اختر الجودة المطلوبة للتعديل:", reply_markup=quality_keyboard("edit"))
        return
    elif user_text == "🎬 استخراج من الفيديو":
        from keyboards import quality_keyboard
        await update.message.reply_text("اختر الجودة المطلوبة للاستخراج:", reply_markup=quality_keyboard("extract"))
        return
    elif user_text == "🔙 الرجوع إلى البداية":
        await start_handler(update, context)
        return

    # إكمال عملية التعديل (الميتادات)
    if "file_path" in context.user_data:
        step = context.user_data.get("step")
        file_path = context.user_data["file_path"]

        if step == "title":
            context.user_data["title"] = user_text
            context.user_data["step"] = "artist"
            await update.message.reply_text("🎤 الآن أرسل (اسم الفنان):")
        
        elif step == "artist":
            title = context.user_data["title"]
            artist = user_text
            
            try:
                audio = ID3(file_path)
            except:
                audio = ID3()
            
            audio["TIT2"] = TIT2(encoding=3, text=title)
            audio["TPE1"] = TPE1(encoding=3, text=artist)
            
            cover = await get_channel_cover(context)
            if cover:
                with open(cover, "rb") as img:
                    audio["APIC"] = APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=img.read())
            audio.save(file_path)

            with open(file_path, "rb") as f:
                await update.message.reply_audio(audio=f, title=title, performer=artist)

            if os.path.exists(file_path): os.remove(file_path)
            context.user_data.clear()
            global processing_now
            processing_now -= 1
