import os
import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# استيراد المعالجات من الملفات المختلفة
from handlers import start_handler, media_handler, text_handler, quality_command_handler, callback_query_handler
from admin_panel import panel_handler, admin_callback_handler
from utils import auto_clear_cache

# إعدادات الـ Logging لمراقبة عمل البوت
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.environ.get("BOT_TOKEN")

def main():
    if not TOKEN:
        print("❌ خطأ: لم يتم العثور على BOT_TOKEN في متغيرات البيئة!")
        return

    # بناء تطبيق البوت
    app = Application.builder().token(TOKEN).build()

    # إعداد المهام الدورية (تنظيف الملفات المؤقتة كل 10 دقائق)
    if app.job_queue:
        app.job_queue.run_repeating(
            lambda _: asyncio.create_task(auto_clear_cache()), 
            interval=600, 
            first=10
        )

    # --- ترتيب المعالجات (Handlers) ---

    # 1. الأوامر الأساسية (Commands)
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("panel", panel_handler)) # لوحة التحكم للمالك فقط
    app.add_handler(CommandHandler("quality", quality_command_handler))

    # 2. معالجة الأزرار التفاعلية (Callback Queries)
    # معالجة أزرار لوحة تحكم الأدمن والصيانة
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^(admin_|toggle_|close_admin)"))
    
    # معالجة أزرار اختيار الجودة للمستخدمين (تعديل أو استخراج)
    app.add_handler(CallbackQueryHandler(callback_query_handler, pattern="^(q_|cancel_)"))

    # 3. معالجة الوسائط (Media)
    # التعامل مع ملفات الصوت والفيديو المرسلة
    app.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.Document.ALL, media_handler))

    # 4. معالجة النصوص العامة (Text)
    # تشمل الإذاعة، أزرار القائمة الرئيسية، وإدخال بيانات الأغاني
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # تشغيل البوت بنظام Polling
    print("🤖 البوت يعمل الآن بنجاح مع نظام القوائم ولوحة الإدارة...")
    app.run_polling()

if __name__ == "__main__":
    main()
