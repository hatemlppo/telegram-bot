import os
import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# استيراد المعالجات من ملفاتها الخاصة
from handlers import start_handler, media_handler, text_handler, quality_command_handler
from keyboards import button_handler
from admin_panel import panel_handler, admin_callback_handler  # استيراد لوحة التحكم
from utils import auto_clear_cache

# إعداد نظام التسجيل (Logging) لمراقبة الأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# جلب التوكن من متغيرات البيئة
TOKEN = os.environ.get("BOT_TOKEN")

def main():
    if not TOKEN:
        print("❌ خطأ: لم يتم العثور على BOT_TOKEN في متغيرات البيئة!")
        return

    # بناء التطبيق
    app = Application.builder().token(TOKEN).build()

    # إعداد المهام الدورية: تنظيف الكاش كل 10 دقائق
    if app.job_queue:
        app.job_queue.run_repeating(
            lambda _: asyncio.create_task(auto_clear_cache()), 
            interval=600, 
            first=10
        )

    # --- ترتيب المعالجات (Handlers) ---

    # 1. أوامر المستخدمين والآدمن الأساسية
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("panel", panel_handler))     # أمر لوحة التحكم للمالك
    app.add_handler(CommandHandler("quality", quality_command_handler))
    
    # 2. معالجة الأزرار التفاعلية (Inline Buttons)
    # معالج خاص بأزرار لوحة التحكم (التي تبدأ بـ admin_ أو toggle_)
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^(admin_|toggle_)"))
    # معالج الأزرار العامة (مثل جودة الصوت)
    app.add_handler(CallbackQueryHandler(button_handler))

    # 3. معالجة الوسائط (صوت، فيديو، مستندات)
    app.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.Document.ALL, media_handler))

    # 4. معالجة النصوص العامة والإذاعة
    # (يجب أن يكون الأخير لكي لا يحجب الأوامر الأخرى)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # تشغيل البوت
    print("🤖 Bot is running with Admin Panel support...")
    app.run_polling()

if __name__ == "__main__":
    main()
