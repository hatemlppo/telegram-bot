import os
import subprocess
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# قراءة التوكن من Environment Variable
TOKEN = os.environ.get("BOT_TOKEN")

# إعدادات الاشتراك الإجباري
CHANNEL_USERNAME = "THTOMI"  # معرف القناة (بدون @)
CHANNEL_LINK = "https://t.me/THTOMI"

# التحقق من وجود ffmpeg
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except:
        return False

async def check_subscription(user_id, context):
    """التحقق من اشتراك المستخدم في القناة"""
    try:
        member = await context.bot.get_chat_member(chat_id=f"@{CHANNEL_USERNAME}", user_id=user_id)
        return member.status not in ['left', 'kicked']
    except Exception as e:
        logging.error(f"خطأ في التحقق من الاشتراك: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # التحقق من الاشتراك
    is_subscribed = await check_subscription(user_id, context)
    
    if not is_subscribed:
        await update.message.reply_text(
            f"⚠️ *عذراً، يجب الاشتراك في القناة أولاً*\n\n"
            f"🔗 [{CHANNEL_USERNAME}]({CHANNEL_LINK})\n\n"
            f"✅ بعد الاشتراك، أرسل /start مرة أخرى",
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        return
    
    await update.message.reply_text(
        "🎵 *بوت تعديل الميتاداتا*\n\n"
        "✅ تم التحقق من اشتراكك في القناة\n"
        "ارسل ملف MP3 او فيديو 🎵📹\n"
        "وسأطلب منك اسم الاغنية ثم اسم المغني بالترتيب.",
        parse_mode='Markdown'
    )

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # التحقق من الاشتراك
    is_subscribed = await check_subscription(user_id, context)
    
    if not is_subscribed:
        await update.message.reply_text(
            f"⚠️ *عذراً، يجب الاشتراك في القناة أولاً*\n\n"
            f"🔗 [{CHANNEL_USERNAME}]({CHANNEL_LINK})\n\n"
            f"✅ بعد الاشتراك، أرسل /start مرة أخرى",
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        return
    
    try:
        file = await update.message.audio.get_file()
        file_path = f"input_{update.message.from_user.id}.mp3"
        await file.download_to_drive(file_path)

        context.user_data["file_path"] = file_path
        context.user_data["file_type"] = "audio"
        context.user_data["step"] = "waiting_for_title"  # ننتظر اسم الاغنية أولاً
        
        await update.message.reply_text("✅ تم استلام الملف\n📝 أرسل اسم الاغنية:")
    except Exception as e:
        logging.error(f"خطأ في معالجة الصوت: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة الملف")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # التحقق من الاشتراك
    is_subscribed = await check_subscription(user_id, context)
    
    if not is_subscribed:
        await update.message.reply_text(
            f"⚠️ *عذراً، يجب الاشتراك في القناة أولاً*\n\n"
            f"🔗 [{CHANNEL_USERNAME}]({CHANNEL_LINK})\n\n"
            f"✅ بعد الاشتراك، أرسل /start مرة أخرى",
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        return
    
    if not check_ffmpeg():
        await update.message.reply_text("❌ استخراج الصوت من الفيديو غير متاح حالياً")
        return

    try:
        file = await update.message.video.get_file()
        video_path = f"input_video_{update.message.from_user.id}.mp4"
        audio_path = f"extracted_{update.message.from_user.id}.mp3"

        await file.download_to_drive(video_path)
        
        # رسالة انتظار
        await update.message.reply_text("⏳ جاري استخراج الصوت من الفيديو...")

        # استخراج الصوت من الفيديو
        result = subprocess.run([
            "ffmpeg", "-i", video_path,
            "-q:a", "0", "-map", "a",
            audio_path, "-y"
        ], capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"FFmpeg error: {result.stderr}")

        os.remove(video_path)

        context.user_data["file_path"] = audio_path
        context.user_data["file_type"] = "video"
        context.user_data["step"] = "waiting_for_title"  # ننتظر اسم الاغنية أولاً
        
        await update.message.reply_text("✅ تم استخراج الصوت\n📝 أرسل اسم الاغنية:")
        
    except Exception as e:
        logging.error(f"خطأ في معالجة الفيديو: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة الفيديو")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # التحقق من الاشتراك
    is_subscribed = await check_subscription(user_id, context)
    
    if not is_subscribed:
        await update.message.reply_text(
            f"⚠️ *عذراً، يجب الاشتراك في القناة أولاً*\n\n"
            f"🔗 [{CHANNEL_USERNAME}]({CHANNEL_LINK})\n\n"
            f"✅ بعد الاشتراك، أرسل /start مرة أخرى",
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        return
    
    # التحقق من وجود ملف
    if "file_path" not in context.user_data:
        await update.message.reply_text("❌ أرسل ملف أولاً")
        return
    
    file_path = context.user_data["file_path"]
    current_step = context.user_data.get("step")
    
    # الخطوة 1: استلام اسم الاغنية
    if current_step == "waiting_for_title":
        song_title = update.message.text
        context.user_data["song_title"] = song_title
        context.user_data["step"] = "waiting_for_artist"  # ننتظر اسم المغني بعدين
        await update.message.reply_text("✅ تم حفظ اسم الاغنية\n🎤 الآن أرسل اسم المغني:")
    
    # الخطوة 2: استلام اسم المغني وتعديل الملف
    elif current_step == "waiting_for_artist":
        artist_name = update.message.text
        song_title = context.user_data.get("song_title", "غير معروف")

        try:
            # التحقق من وجود الملف
            if not os.path.exists(file_path):
                await update.message.reply_text("❌ الملف غير موجود")
                return

            # تعديل الميتاداتا
            try:
                audio = MP3(file_path, ID3=EasyID3)
            except:
                audio = MP3(file_path)
                audio.add_tags()

            audio["title"] = song_title
            audio["artist"] = artist_name
            audio.save()

            # إرسال الملف المعدل
            await update.message.reply_text("⏳ جاري رفع الملف المعدل...")
            
            with open(file_path, "rb") as f:
                await update.message.reply_audio(
                    audio=f,
                    title=song_title,
                    performer=artist_name,
                    caption=f"✅ تم التعديل بنجاح\n🎵 {song_title} - {artist_name}\n\n🔗 اشترك في قناتنا: {CHANNEL_LINK}"
                )

            # تنظيف الملفات
            os.remove(file_path)
            context.user_data.clear()
            
        except Exception as e:
            logging.error(f"خطأ في تعديل الميتاداتا: {e}")
            await update.message.reply_text("❌ حدث خطأ في تعديل الملف")

def main():
    if not TOKEN:
        logging.error("لم يتم تعيين BOT_TOKEN في متغيرات البيئة")
        return

    # إنشاء التطبيق
    app = Application.builder().token(TOKEN).build()

    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logging.info("✅ البوت بدأ العمل...")

    # بدء البوت
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"خطأ عام: {e}")