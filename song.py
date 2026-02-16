import os
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

TOKEN = "8229000508:AAHW4D6HDgj8z3beN0IjSjFK0844TvYZapo"  # حط توكن البوت هنا
ARTIST_NAME = "HATEM_F2"  # اسم المغني الثابت


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ارسل ملف MP3 او فيديو 🎵📹\n"
        "وبعدها راح اكلك اكتب اسم الاغنية."
    )


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.audio.get_file()
    file_path = "input.mp3"
    await file.download_to_drive(file_path)

    context.user_data["file_path"] = file_path
    await update.message.reply_text("ادخل اسم الاغنية:")


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.video.get_file()
    video_path = "input_video.mp4"
    audio_path = "extracted.mp3"

    await file.download_to_drive(video_path)

    # استخراج الصوت من الفيديو
    subprocess.run([
        "ffmpeg", "-i", video_path,
        "-q:a", "0", "-map", "a",
        audio_path
    ])

    os.remove(video_path)

    context.user_data["file_path"] = audio_path
    await update.message.reply_text("ادخل اسم الاغنية:")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "file_path" not in context.user_data:
        return

    file_path = context.user_data["file_path"]
    new_title = update.message.text

    try:
        audio = MP3(file_path, ID3=EasyID3)
    except:
        audio = MP3(file_path)
        audio.add_tags()

    audio["title"] = new_title
    audio["artist"] = ARTIST_NAME
    audio.save()

    await update.message.reply_audio(
        audio=open(file_path, "rb"),
        title=new_title,
        performer=ARTIST_NAME
    )

    os.remove(file_path)
    context.user_data.clear()


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
app.add_handler(MessageHandler(filters.VIDEO, handle_video))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
