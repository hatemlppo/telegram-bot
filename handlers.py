import os
import subprocess
import sqlite3
import asyncio
import shutil
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from mutagen.id3 import ID3, TIT2, TPE1, APIC, error as MutagenError

from utils import check_subscription, is_maintenance, DB_FILE, OWNER_ID, MAX_FILE_SIZE, get_channel_cover

# متغيرات للتحكم في الطابور
processing_now = 0
queue = []

# ============================================
# دالة البداية
# ============================================
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

# ============================================
# معالج الكولباك (الأزرار)
# ============================================
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    # ===== أزرار أغنيتي الجديدة =====
    if data == "mysong_edit":
        context.user_data.clear()
        context.user_data['mysong_mode'] = 'edit'
        context.user_data['step'] = 'waiting_for_audio'
        await query.edit_message_text(
            "🎵 **تعديل أغنية موجودة**\n\n"
            "أرسل لي الآن الملف الصوتي (MP3) الذي تريد تعديل اسمه وإضافة صورة له."
        )
    
    elif data == "mysong_extract":
        context.user_data.clear()
        context.user_data['mysong_mode'] = 'extract'
        context.user_data['step'] = 'waiting_for_video'
        await query.edit_message_text(
            "🎬 **استخراج صوت من فيديو + إضافة صورة**\n\n"
            "أرسل لي الآن ملف الفيديو لاستخراج الصوت منه، ثم سنضيف الاسم والصورة."
        )
    
    elif data == "mysong_new":
        context.user_data.clear()
        context.user_data['mysong_mode'] = 'new'
        context.user_data['step'] = 'waiting_for_audio'
        await query.edit_message_text(
            "🆕 **رفع ملف صوتي + صورة جديدة**\n\n"
            "أرسل لي الآن الملف الصوتي (MP3) وسأطلب منك الاسم والفنان والصورة."
        )
    
    # ===== أزرار الجودة القديمة =====
    elif data.startswith("q_"):
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

# ============================================
# معالج الملفات (الصوت والفيديو)
# ============================================
async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_maintenance(update, context): return
    
    user_id = update.effective_user.id
    
    # ===== معالج وضع أغنيتي =====
    if context.user_data.get('mysong_mode'):
        mysong_mode = context.user_data.get('mysong_mode')
        step = context.user_data.get('step')
        
        # استقبال الملف الصوتي (للوضعين edit و new)
        if step == 'waiting_for_audio' and mysong_mode in ['edit', 'new']:
            # التحقق من أن الملف صوتي
            file_obj = None
            if update.message.audio:
                file_obj = update.message.audio
            elif update.message.document and update.message.document.mime_type and 'audio' in update.message.document.mime_type:
                file_obj = update.message.document
            elif update.message.document and update.message.document.file_name and update.message.document.file_name.endswith('.mp3'):
                file_obj = update.message.document
            
            if not file_obj:
                await update.message.reply_text("❌ من فضلك أرسل ملف صوتي بصيغة MP3")
                return
            
            if file_obj.file_size > MAX_FILE_SIZE:
                await update.message.reply_text("❌ حجم الملف كبير جداً (الحد الأقصى 70MB).")
                return
            
            # تحميل الملف
            wait_msg = await update.message.reply_text("⏳ جاري تحميل الملف الصوتي...")
            tg_file = await file_obj.get_file()
            audio_path = f"audio_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp3"
            await tg_file.download_to_drive(audio_path)
            
            context.user_data['audio_path'] = audio_path
            context.user_data['step'] = 'waiting_for_title'
            await wait_msg.edit_text("📝 أرسل الآن **اسم الأغنية**:")
            return
        
        # استقبال ملف الفيديو (لوضع extract)
        elif step == 'waiting_for_video' and mysong_mode == 'extract':
            if not update.message.video:
                await update.message.reply_text("❌ من فضلك أرسل ملف فيديو")
                return
            
            file_obj = update.message.video
            if file_obj.file_size > MAX_FILE_SIZE:
                await update.message.reply_text("❌ حجم الملف كبير جداً (الحد الأقصى 70MB).")
                return
            
            # تحميل الفيديو واستخراج الصوت
            wait_msg = await update.message.reply_text("⏳ جاري تحميل الفيديو واستخراج الصوت...")
            tg_file = await file_obj.get_file()
            video_path = f"video_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
            await tg_file.download_to_drive(video_path)
            
            # استخراج الصوت باستخدام ffmpeg
            audio_path = f"extracted_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp3"
            quality = context.user_data.get('selected_quality', '192k')
            
            cmd = [
                "ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame",
                "-ac", "2", "-b:a", quality, audio_path, "-y"
            ]
            
            process = subprocess.run(cmd, capture_output=True)
            
            # حذف الفيديو بعد الاستخراج
            if os.path.exists(video_path):
                os.remove(video_path)
            
            if process.returncode != 0:
                await wait_msg.edit_text("❌ حدث خطأ أثناء استخراج الصوت.")
                return
            
            context.user_data['audio_path'] = audio_path
            context.user_data['step'] = 'waiting_for_title'
            await wait_msg.edit_text("📝 تم استخراج الصوت بنجاح!\nأرسل الآن **اسم الأغنية**:")
            return
        
        # إذا وصلنا هنا، يعني أن المستخدم أرسل ملف ولكننا لا ننتظره
        else:
            # تجاهل الملف في هذه الحالة
            return
    
    # ===== المعالج القديم (للوضع العادي) =====
    global processing_now
    action = context.user_data.get('action_type')
    quality = context.user_data.get('selected_quality', "192k")

    if not action:
        await update.message.reply_text("❌ من فضلك اختر نوع العملية أولاً (تعديل أغنية أو استخراج من فيديو) من القائمة.")
        return

    # التحقق من نوع الملف المرسل
    file_obj = None
    if action == "edit" and (update.message.audio or (update.message.document and update.message.document.mime_type == 'audio/mpeg')):
        file_obj = update.message.audio or update.message.document
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

    # تشغيل FFmpeg
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

# ============================================
# معالج الصور (مخصص لوضع أغنيتي)
# ============================================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الصور المرسلة من المستخدم"""
    if await is_maintenance(update, context): return
    
    user_id = update.effective_user.id
    
    # التحقق من أن المستخدم في وضع أغنيتي وينتظر صورة
    if context.user_data.get('mysong_mode') and context.user_data.get('step') == 'waiting_for_cover':
        
        wait_msg = await update.message.reply_text("⏳ جاري معالجة الصورة ودمجها مع الأغنية...")
        
        # تحميل الصورة
        photo = update.message.photo[-1]  # أفضل جودة
        tg_photo = await photo.get_file()
        cover_path = f"cover_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        await tg_photo.download_to_drive(cover_path)
        
        # الحصول على البيانات
        audio_path = context.user_data.get('audio_path')
        title = context.user_data.get('title', 'غير معروف')
        artist = context.user_data.get('artist', 'غير معروف')
        
        if not audio_path or not os.path.exists(audio_path):
            await wait_msg.edit_text("❌ حدث خطأ: الملف الصوتي غير موجود")
            return
        
        try:
            # إضافة الميتاداتا والصورة للملف الصوتي
            audio = ID3(audio_path)
            
            # تعديل الاسم والفنان
            audio["TIT2"] = TIT2(encoding=3, text=title)
            audio["TPE1"] = TPE1(encoding=3, text=artist)
            
            # إضافة الصورة
            with open(cover_path, "rb") as img:
                if "APIC" in audio:
                    del audio["APIC"]
                audio["APIC"] = APIC(
                    encoding=3, 
                    mime="image/jpeg", 
                    type=3, 
                    desc="Cover", 
                    data=img.read()
                )
            audio.save()
            
            # إرسال الملف النهائي
            with open(audio_path, "rb") as f:
                await update.message.reply_audio(
                    audio=f,
                    title=title,
                    performer=artist
                )
            
            # تسجيل العملية في قاعدة البيانات
            conn = sqlite3.connect(DB_FILE)
            conn.execute(
                "INSERT INTO files (user_id, title, artist, date) VALUES (?, ?, ?, ?)",
                (user_id, title, artist, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            conn.commit()
            conn.close()
            
            await wait_msg.delete()
            
        except Exception as e:
            await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        
        # تنظيف الملفات المؤقتة
        for file in [audio_path, cover_path]:
            if os.path.exists(file):
                os.remove(file)
        
        context.user_data.clear()
        return
    
    # إذا لم يكن المستخدم في الوضع المناسب
    else:
        await update.message.reply_text("❌ لست في وضع إضافة صورة حالياً. اختر '🖼️ أغنيتي' أولاً.")

# ============================================
# معالج النصوص (معدل مع زر تشغيل البوت)
# ============================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id

    # ===== الإذاعة للأدمن =====
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

    # ===== أزرار القائمة الرئيسية (معدلة مع زر تشغيل البوت) =====
    
    # زر تعديل الأغاني
    if user_text == "🎵 تعديل الأغاني":
        from keyboards import quality_keyboard
        await update.message.reply_text("اختر الجودة المطلوبة للتعديل:", reply_markup=quality_keyboard("edit"))
        return
    
    # زر استخراج من الفيديو
    elif user_text == "🎬 استخراج من الفيديو":
        from keyboards import quality_keyboard
        await update.message.reply_text("اختر الجودة المطلوبة للاستخراج:", reply_markup=quality_keyboard("extract"))
        return
    
    # زر أغنيتي (القائمة المتكاملة)
    elif user_text == "🖼️ أغنيتي (القائمة المتكاملة)":
        from keyboards import my_song_menu_keyboard
        await update.message.reply_text(
            "🖼️ **قائمة أغنيتي المتكاملة**\n\n"
            "اختر ما تريد فعله:",
            reply_markup=my_song_menu_keyboard()
        )
        return
    
    # ✅ زر تشغيل البوت (الجديد)
    elif user_text == "▶️ تشغيل البوت":
        await start_handler(update, context)  # نفس دالة البداية
        return
    
    # زر الرجوع إلى البداية
    elif user_text == "🔙 الرجوع إلى البداية":
        await start_handler(update, context)
        return

    # ===== معالج وضع أغنيتي (إدخال النصوص) =====
    if context.user_data.get('mysong_mode'):
        step = context.user_data.get('step')
        audio_path = context.user_data.get('audio_path')
        
        # استقبال اسم الأغنية
        if step == 'waiting_for_title':
            context.user_data['title'] = user_text
            context.user_data['step'] = 'waiting_for_artist'
            await update.message.reply_text("🎤 أرسل الآن **اسم الفنان**:")
            return
        
        # استقبال اسم الفنان
        elif step == 'waiting_for_artist':
            context.user_data['artist'] = user_text
            context.user_data['step'] = 'waiting_for_cover'
            await update.message.reply_text(
                "🖼️ أرسل الآن **الصورة** التي تريد استخدامها كغلاف للأغنية\n"
                "(JPG أو PNG)"
            )
            return
        
        # إذا كان ينتظر صورة وأرسل نص
        elif step == 'waiting_for_cover':
            await update.message.reply_text("❌ أنا في انتظار صورة وليس نص. أرسل صورة من فضلك.")
            return
        
        # إذا وصلنا هنا، نكمل
        return

    # ===== إكمال عملية التعديل القديمة =====
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

            # تسجيل العملية
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