import sqlite3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils import DB_FILE, MAINTENANCE_MODE

OWNER_ID = 8460454874 

# لوحة المفاتيح الخاصة بالآدمن
def admin_keyboard():
    # جلب حالة الصيانة الحالية (نصياً)
    import utils
    m_text = "🔴 إيقاف الصيانة" if utils.MAINTENANCE_MODE else "🟢 تفعيل الصيانة"
    
    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton(m_text, callback_data="toggle_maintenance")],
        [InlineKeyboardButton("📢 إذاعة للمستخدمين", callback_data="admin_broadcast")],
        [InlineKeyboardButton("❌ إغلاق القائمة", callback_data="admin_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    await update.message.reply_text(
        "🛠 **لوحة تحكم المالك**\nإختر من القائمة أدناه الإجراء المطلوب:",
        reply_markup=admin_keyboard()
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        await query.answer("غير مصرح لك!", show_alert=True)
        return

    import utils # لاستيراد وتعديل حالة الصيانة

    if query.data == "admin_stats":
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        u_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM files")
        f_count = c.fetchone()[0]
        conn.close()
        
        await query.edit_message_text(
            f"📊 **إحصائيات البوت:**\n\n👥 عدد المستخدمين: {u_count}\n📁 الملفات المعدلة: {f_count}",
            reply_markup=admin_keyboard()
        )

    elif query.data == "toggle_maintenance":
        utils.MAINTENANCE_MODE = not utils.MAINTENANCE_MODE
        status = "تفعيل" if utils.MAINTENANCE_MODE else "إيقاف"
        await query.answer(f"تم {status} وضع الصيانة بنجاح", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=admin_keyboard())

    elif query.data == "admin_broadcast":
        await query.edit_message_text("📝 أرسل الرسالة التي تريد إذاعتها الآن (نص فقط):")
        context.user_data['admin_step'] = 'broadcasting'

    elif query.data == "admin_close":
        await query.message.delete()
