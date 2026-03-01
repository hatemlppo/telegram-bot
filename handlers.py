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
    if context.user_data.get('admin_step') == 'broadcasting':
        if user_id != OWNER_ID:
            context.user_data['admin_step'] = None
            return
        
        conn = sqlite3.connect(DB_FILE)
        users = conn.execute("SELECT user_id FROM users").fetchall()
        conn.close()
        
        success_count = 0
        for u in users:
            try: 
                await context.bot.send_message(chat_id=u[0], text=user_text)
                success_count += 1
            except: 
                pass
        
        context.user_data['admin_step'] = None
        await update.message.reply_text(f"✅ تمت الإذاعة بنجاح لـ {success_count} مستخدم.")
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
    
    # زر أغنيتي - إضافة صورة مخصصة (جديد)
    elif user_text == "🖼️ أغنيتي (إضافة صورة مخصصة)":
        context.user_data['custom_cover_mode'] = True
        context.user_data['step'] = 'waiting_for_audio_with_cover'
        await update.message.reply_text(
            "🖼️ **إضافة صورة مخصصة للأغنية**\n\n"
            "أرسل لي الآن:\n"
            "1️⃣ أولاً: الملف الصوتي (MP3)\n"
            "2️⃣ ثم: الصورة التي تريد استخدامها كغلاف\n\n"
            "✅ سأقوم بدمج الصورة مع الأغنية وإرسالها لك."
        )
        return
    
    elif user_text == "🔙 الرجوع إلى البداية":
        await start_handler(update, context)
        return

    # معالج استقبال الملف الصوتي للصورة المخصصة (جديد)
    if context.user_data.get('custom_cover_mode'):
        if context.user_data.get('step') == 'waiting_for_audio_with_cover':
            # استقبال الملف الصوتي
            if update.message.audio or (update.message.document and update.message.document.mime_type == 'audio/mpeg'):
                file_obj = update.message.audio or update.message.document
                
                if file_obj.file_size > MAX_FILE_SIZE:
                    await update.message.reply_text("❌ حجم الملف كبير جداً (الحد الأقصى 70MB).")
                    return
                
                # تحميل الملف الصوتي
                wait_msg = await update.message.reply_text("⏳ جاري تحميل الملف الصوتي...")
                tg_file = await file_obj.get_file()
                audio_path = f"custom_audio_{user_id}_{file_obj.file_id[:5]}.mp3"
                await tg_file.download_to_drive(audio_path)
                
                # حفظ المسار في user_data
                context.user_data['custom_audio_path'] = audio_path
                context.user_data['step'] = 'waiting_for_cover_image'
                
                await wait_msg.edit_text(
                    "🖼️ **تم تحميل الملف الصوتي**\n\n"
                    "الآن أرسل الصورة التي تريد استخدامها كغلاف (JPG أو PNG)\n"
                    "✅ سيتم دمجها مع الأغنية تلقائياً"
                )
            else:
                await update.message.reply_text("❌ من فضلك أرسل ملف صوتي بصيغة MP3")
            return
        
        elif context.user_data.get('step') == 'waiting_for_cover_image':
            # استقبال الصورة
            if update.message.photo:
                # المستخدم أرسل صورة
                photo = update.message.photo[-1]  # أفضل جودة
                
                wait_msg = await update.message.reply_text("⏳ جاري معالجة الصورة ودمجها مع الأغنية...")
                
                # تحميل الصورة
                tg_photo = await photo.get_file()
                cover_path = f"custom_cover_{user_id}.jpg"
                await tg_photo.download_to_drive(cover_path)
                
                # الحصول على مسار الملف الصوتي
                audio_path = context.user_data.get('custom_audio_path')
                
                if audio_path and os.path.exists(audio_path):
                    # دمج الصورة مع الأغنية
                    output_path = f"final_with_cover_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp3"
                    
                    try:
                        # نسخ الملف الصوتي إلى ملف جديد
                        import shutil
                        shutil.copy2(audio_path, output_path)
                        
                        # إضافة الصورة إلى الملف الصوتي باستخدام mutagen
                        audio = ID3(output_path)
                        
                        with open(cover_path, "rb") as img:
                            # إزالة أي غلاف قديم
                            if "APIC" in audio:
                                del audio["APIC"]
                            
                            # إضافة الغلاف الجديد
                            audio["APIC"] = APIC(
                                encoding=3, 
                                mime="image/jpeg", 
                                type=3, 
                                desc="Cover", 
                                data=img.read()
                            )
                        audio.save()
                        
                        # إرسال الملف النهائي
                        with open(output_path, "rb") as f:
                            await update.message.reply_audio(
                                audio=f,
                                title=os.path.basename(audio_path).replace('.mp3', ''),
                                performer="غير معروف"
                            )
                        
                        # تنظيف الملفات المؤقتة
                        for file in [audio_path, cover_path, output_path]:
                            if os.path.exists(file):
                                os.remove(file)
                        
                        # إنهاء الوضع
                        context.user_data.clear()
                        
                    except Exception as e:
                        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
                        # تنظيف في حالة الخطأ
                        for file in [audio_path, cover_path, output_path]:
                            if os.path.exists(file):
                                os.remove(file)
                else:
                    await update.message.reply_text("❌ حدث خطأ: لا يوجد ملف صوتي")
                
                await wait_msg.delete()
            else:
                await update.message.reply_text("❌ من فضلك أرسل صورة بصيغة JPG أو PNG")
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

            # تسجيل العملية في قاعدة البيانات
            conn = sqlite3.connect(DB_FILE)
            conn.execute(
                "INSERT INTO files (user_id, title, artist, date) VALUES (?, ?, ?, ?)",
                (user_id, title, artist, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            conn.commit()
            conn.close()

            if os.path.exists(file_path): os.remove(file_path)
            context.user_data.clear()
            global processing_now
            processing_now -= 1