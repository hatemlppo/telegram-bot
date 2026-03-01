from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

# القائمة الرئيسية
def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("🎵 تعديل الأغاني"), KeyboardButton("🎬 استخراج من الفيديو")],
        [KeyboardButton("🖼️ أغنيتي")],
        [KeyboardButton("🔙 الرجوع إلى البداية")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# قائمة أغنيتي الداخلية
def my_song_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎵 تعديل أغنية (اسم + صورة)", callback_data="mysong_edit")],
        [InlineKeyboardButton("🎬 استخراج من فيديو + صورة", callback_data="mysong_extract")],
        [InlineKeyboardButton("🆕 رفع ملف صوتي + صورة جديدة", callback_data="mysong_new")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_action")]
    ]
    return InlineKeyboardMarkup(keyboard)

# قائمة اختيار الجودة
def quality_keyboard(action_type):
    keyboard = [
        [
            InlineKeyboardButton("128k", callback_data=f"q_128_{action_type}"),
            InlineKeyboardButton("192k", callback_data=f"q_192_{action_type}"),
            InlineKeyboardButton("256k", callback_data=f"q_256_{action_type}")
        ],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_action")]
    ]
    return InlineKeyboardMarkup(keyboard)

# لوحة تحكم الإدارة
def admin_panel_keyboard(maintenance_status):
    m_text = "🔴 إيقاف الصيانة" if maintenance_status else "🟢 تفعيل الصيانة"
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات البوت الشاملة", callback_data="admin_stats")],
        [InlineKeyboardButton(m_text, callback_data="toggle_maintenance")],
        [InlineKeyboardButton("📢 إذاعة (Broadcast)", callback_data="admin_broadcast")],
        [InlineKeyboardButton("❌ إغلاق اللوحة", callback_data="close_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)