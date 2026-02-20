import os
import subprocess
import sqlite3
from telegram import Update
from telegram.ext import ContextTypes
from utils import check_subscription, is_maintenance, DB_FILE, OWNER_ID
from keyboards import main_menu_keyboard, quality_keyboard

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_maintenance(update, context): return
    
    user = update.effective_user
    if not await check_subscription(user.id, context):
        await update.message.reply_text("⚠️ اشترك بالقناة أولاً: @THTOMI")
        return

    # تسجيل المستخدم
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO users(user_id, first_name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🚀 أهلاً بك {user.first_name} في بوت الخدمات الصوتية.\nإختر ماذا تريد أن تفعل الآن:",
        reply_markup=main_menu_keyboard()
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id

    # 1. أوامر الأدمن (إذاعة)
    if context.user_data.get('admin_step') == 'broadcasting' and user_id == OWNER_ID:
        # كود الإذاعة (كما في الردود السابقة)
        context.user_data['admin_step'] = None
        await update.message.reply_text("✅ تمت الإذاعة.")
        return

    # 2. معالجة الأزرار الجديدة
    if user_text == "🎵 تعديل الأغاني":
        await update.message.reply_text("اختر الجودة المطلوبة لتعديل الملف الصوتي:", 
                                       reply_markup=quality_keyboard("edit"))
    
    elif user_text == "🎬 استخراج من الفيديو":
        await update.message.reply_text("اختر الجودة المطلوبة لاستخراج الصوت من الفيديو:", 
                                       reply_markup=quality_keyboard("extract"))
    
    elif user_text == "🔙 الرجوع إلى البداية":
        await start_handler(update, context)

    # 3. معالجة النصوص (العنوان والفنان) بعد اختيار الملف
    elif "file_path" in context.user_data:
        # (كود الميتادات الخاص بك هنا...)
        pass

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data.startswith("q_"):
        parts = data.split("_")
        quality = parts[1] + "k"
        action = parts[2]
        context.user_data['selected_quality'] = quality
        context.user_data['action_type'] = action
        
        text = "أرسل الآن الملف الصوتي (MP3) لتعديله:" if action == "edit" else "أرسل الآن ملف الفيديو لاستخراج الصوت منه:"
        await query.edit_message_text(f"✅ تم اختيار جودة {quality}.\n\n{text}")
