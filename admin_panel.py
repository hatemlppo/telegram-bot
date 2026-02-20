import sqlite3
from telegram import Update
from telegram.ext import ContextTypes
from utils import DB_FILE, OWNER_ID
import utils

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        await query.answer("🚫 هذا القسم خاص بالمطور فقط!", show_alert=True)
        return

    from keyboards import admin_panel_keyboard

    if query.data == "admin_stats":
        conn = sqlite3.connect(DB_FILE)
        users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        files_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        conn.close()
        await query.edit_message_text(
            f"📊 **إحصائيات الإدارة:**\n\n👥 عدد المشتركين: {users_count}\n📁 الملفات المعالجة: {files_count}",
            reply_markup=admin_panel_keyboard(utils.MAINTENANCE_MODE)
        )

    elif query.data == "toggle_maintenance":
        utils.MAINTENANCE_MODE = not utils.MAINTENANCE_MODE
        status = "شغال" if not utils.MAINTENANCE_MODE else "في وضع الصيانة"
        await query.answer(f"⚙️ تم تغيير حالة البوت إلى: {status}", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=admin_panel_keyboard(utils.MAINTENANCE_MODE))

    elif query.data == "admin_broadcast":
        context.user_data['admin_step'] = 'broadcasting'
        await query.edit_message_text("📢 أرسل الآن الرسالة (نص فقط) ليتم إرسالها للجميع:")

    elif query.data == "close_admin":
        await query.message.delete()
