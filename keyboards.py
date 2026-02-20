from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def quality_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("128k", callback_data="quality_128k"),
            InlineKeyboardButton("192k", callback_data="quality_192k"),
            InlineKeyboardButton("256k", callback_data="quality_256k"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("quality_"):
        quality = data.split("_")[1]
        context.user_data["audio_quality"] = quality
        await query.edit_message_text(f"✅ تم تعيين جودة الصوت: {quality}")