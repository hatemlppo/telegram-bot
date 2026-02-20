import os
import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from handlers import start_handler, media_handler, text_handler, panel_handler, quality_command_handler
from keyboards import button_handler
from utils import auto_clear_cache

# إعداد التسجيل لرؤية الأخطاء في التيرمينال
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.environ.get("BOT_TOKEN")

def main():
    if not TOKEN:
        print("❌ خطأ: لم يتم العثور على BOT_TOKEN في متغيرات البيئة!")
        return

    app = Application.builder().token(TOKEN).build()

    # تنظيف الكاش كل 10 دقائق
    if app.job_queue:
        app.job_queue.run_repeating(lambda _: asyncio.create_task(auto_clear_cache()), interval=600, first=10)

    # الترتيب مهم جداً هنا:
    # 1. الأوامر أولاً
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("panel", panel_handler))
    app.add_handler(CommandHandler("quality", quality_command_handler))
    
    # 2. الأزرار التفاعلية
    app.add_handler(CallbackQueryHandler(button_handler))

    # 3. الملفات (صوت، فيديو، مستندات)
    app.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.Document.ALL, media_handler))

    # 4. النصوص العامة (يجب أن تكون بعد الأوامر لكي لا تخطف الـ /start)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 Bot is running perfectly...")
    app.run_polling()

if __name__ == "__main__":
    main()
