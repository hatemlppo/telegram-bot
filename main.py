import os
import subprocess
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from mutagen.id3 import ID3, TIT2, TPE1, APIC

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_USERNAME = "THTOMI"
MAX_FILE_SIZE = 70 * 1024 * 1024  # 70MB

COVER_CACHE = "channel_cover_cached.jpg"


async def check_subscription(user_id, context):
    try:
        member = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status not in ["left", "kicked"]
    except:
        return False


async def get_channel_cover(context):
    # إذا موجود بالكاش لا تحمله مرة ثانية
    if os.path.exists(COVER_CACHE):
        return COVER_CACHE

    try:
        chat = await context.bot.get_chat(f"@{CHANNEL_USERNAME}")
        if chat.photo:
            photo = await context.bot.get_file(chat.photo.big_file_id)
            await photo.download_to_drive(COVER_CACHE)
            return COVER_CACHE
    except Exception as e:
        logging.error(f"خطأ جلب صورة القناة: {e}")

    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_subscription(update.message.from_user.id, context):
        await update.message.reply_text("⚠️ يجب الاشتراك في القناة أولاً")
        return

    await update.message.reply_text("🎵 ارسل ملف صوت او فيديو (حد اقصى 70MB)")


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_subscription(update.message.from_user.id, context):
        await update.message.reply_text("⚠️ اشترك بالقناة أولاً")
        return

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
        return

    if size > MAX_FILE_SIZE:
        await update.message.reply_text("❌ الحد الأقصى 70MB")
        return

    input_path = f"input_{update.message.from_user.id}"
    output_path = f"output_{update.message.from_user.id}.mp3"

    await file.download_to_drive(input_path)

    await update.message.reply_text("⏳ جاري التحويل...")

    result = subprocess.run([
        "ffmpeg", "-i", input_path,
        "-vn",
        "-ar", "44100",
        "-ac", "2",
        "-b:a", "192k",
        output_path,
        "-y"
    ], capture_output=True)

    os.remove(input_path)

    if result.returncode != 0:
        await update.message.reply_text("❌ فشل التحويل")
        return

    context.user_data["file_path"] = output_path
    context.user_data["step"] = "title"

    await update.message.reply_text("📝 ارسل اسم الاغنية:")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "file_path" not in context.user_data:
        return

    file_path = context.user_data["file_path"]
    step = context.user_data.get("step")

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

            # جلب صورة القناة من الكاش أو تحميلها
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

            os.remove(file_path)
            context.user_data.clear()

        except Exception as e:
            logging.error(e)
            await update.message.reply_text("❌ حدث خطأ أثناء التعديل")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.AUDIO | filters.VIDEO | filters.Document.ALL,
        handle_media
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot Running...")
    app.run_polling()


if __name__ == "__main__":
    main()