import os
import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

from handlers import start_handler, media_handler, text_handler, panel_handler
from keyboards import button_handler
from utils import auto_clear_cache

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")

def main():
    app = Application.builder().token(TOKEN).build()

    # تنظيف الكاش كل 10 دقائق
    app.job_queue.run_repeating(lambda _: asyncio.create_task(auto_clear_cache()), interval=600, first=10)

    # Handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("panel", panel_handler))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.Document.ALL, media_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(button_handler))  # لأزرار Inline

    print("🤖 Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()