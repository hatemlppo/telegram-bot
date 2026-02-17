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
TOKEN = os.environ.get("BOT_TOKEN")  # غيرت الاسم إلى BOT_TOKEN ليكون واضحاً
ARTIST_NAME = "HATEM_F2"

# التحقق من وجود ffmpeg
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 *بوت تعديل الميتاداتا*\n\n"
        "ارسل ملف MP3 او فيديو 🎵📹\n"
        "وبعدها راح اكلك اكتب اسم الاغنية.\n\n"
        "مطور البوت @HATEM_F2" 
    )

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        file = await update.message.audio.get_file()
        file_path = f"input_{update.message.from_user.id}.mp3"
        await file.download_to_drive(file_path)

        context.user_data["file_path"] = file_path
        context.user_data["file_type"] = "audio"
        await update.message.reply_text("✅ تم استلام الملف\nادخل اسم الاغنية:")
    except Exception as e:
        logging.error(f"خطأ في معالجة الصوت: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة الملف")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_ffmpeg():
        await update.message.reply_text("❌ استخراج الصوت من الفيديو غير متاح حالياً")
        return
        
    try:
        file = await update.message.video.get_file()
        video_path = f"input_video_{update.message.from_user.id}.mp4"
        audio_path = f"extracted_{update.message.from_user.id}.mp3"

        await file.download_to_drive(video_path)

        # استخراج الصوت من الفيديو
        result = subprocess.run([
            "ffmpeg", "-i", video_path,
            "-q:a", "0", "-map", "a",
            audio_path, "-y"  # -y للتجاوز بدون تأكيد
        ], capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"FFmpeg error: {result.stderr}")

        os.remove(video_path)

        context.user_data["file_path"] = audio_path
        context.user_data["file_type"] = "video"
        await update.message.reply_text("✅ تم استخراج الصوت\nادخل اسم الاغنية:")
    except Exception as e:
        logging.error(f"خطأ في معالجة الفيديو: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة الفيديو")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "file_path" not in context.user_data:
        await update.message.reply_text("❌ أرسل ملف أولاً")
        return

    file_path = context.user_data["file_path"]
    new_title = update.message.text

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

        audio["title"] = new_title
        audio["artist"] = ARTIST_NAME
        audio.save()

        # إرسال الملف المعدل
        with open(file_path, "rb") as f:
            await update.message.reply_audio(
                audio=f,
                title=new_title,
                performer=ARTIST_NAME
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
