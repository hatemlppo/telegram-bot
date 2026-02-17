
import os
import subprocess
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# قراءة التوكن من Environment Variable
TOKEN = os.environ.get("TOKEN")
DEFAULT_ARTIST = "اغنيتي"  # اسم افتراضي

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("تعيين اسم مغني جديد", callback_data='set_artist')],
        [InlineKeyboardButton("استخدام الاسم الافتراضي", callback_data='default_artist')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎵 *مرحباً بك في بوت تعديل الميتاداتا*\n\n"
        "أولاً: اختر اسم المغني:\n"
        "📝 بعدها أرسل ملف MP3 أو فيديو",
        reply_markup=reply_markup
   " تم تطوير بواسطه @HATEM_F2"
 )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'set_artist':
        await query.edit_message_text("أرسل اسم المغني الجديد:")
        context.user_data['waiting_for_artist'] = True
    elif query.data == 'default_artist':
        context.user_data['artist_name'] = DEFAULT_ARTIST
        await query.edit_message_text(f"✅ تم اختيار الاسم الافتراضي: {DEFAULT_ARTIST}\nأرسل الملف الآن:")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إذا كان المستخدم يريد تعيين اسم مغني جديد
    if context.user_data.get('waiting_for_artist'):
        artist_name = update.message.text
        context.user_data['artist_name'] = artist_name
        context.user_data['waiting_for_artist'] = False
        await update.message.reply_text(f"✅ تم تعيين اسم المغني: {artist_name}\nأرسل الملف الآن:")
        return
    
    # إذا كان في ملف بانتظار اسم الأغنية
    if "file_path" in context.user_data:
        file_path = context.user_data["file_path"]
        new_title = update.message.text
        artist_name = context.user_data.get('artist_name', DEFAULT_ARTIST)

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
            audio["artist"] = artist_name
            audio.save()

            # إرسال الملف المعدل
            with open(file_path, "rb") as f:
                await update.message.reply_audio(
                    audio=f,
                    title=new_title,
                    performer=artist_name
                )

            # تنظيف الملفات
            os.remove(file_path)
            context.user_data.clear()
            
        except Exception as e:
            logging.error(f"خطأ في تعديل الميتاداتا: {e}")
            await update.message.reply_text("❌ حدث خطأ في تعديل الملف")
    else:
        await update.message.reply_text("❌ أرسل ملف أولاً")

# باقي الدوال (handle_audio, handle_video) نفس ما هي...

def main():
    if not TOKEN:
        logging.error("لم يتم تعيين TOKEN في متغيرات البيئة")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logging.info("✅ البوت بدأ العمل...")
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"خطأ عام: {e}")