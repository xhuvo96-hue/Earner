import os
import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials

TOKEN = os.environ.get('BOT_TOKEN')
SHEET_NAME = os.environ.get('SHEET_NAME', 'Instagram Accounts')

SELECTING_OPTION, WAITING_FOR_INSTAGRAM_INFO, WAITING_FOR_2FA = range(3)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_google_sheets():
    try:
        if 'GOOGLE_CREDENTIALS_JSON' in os.environ:
            creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except Exception as e:
        logger.error(f"Google Sheets error: {e}")
        return None

def save_to_sheet(sheet, user_id, username, email, password, twofa="", status="Pending"):
    if sheet:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, str(user_id), username, email, password, twofa, status])
        return True
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📱 নতুন অ্যাকাউন্ট তৈরি", callback_data="new_account")],
        [InlineKeyboardButton("🔐 2FA সহ অ্যাকাউন্ট", callback_data="new_account_2fa")],
        [InlineKeyboardButton("ℹ️ হেল্প", callback_data="help")]
    ]
    await update.message.reply_text(
        f"👋 স্বাগতম!\n\nইনস্টাগ্রাম অ্যাকাউন্ট তৈরি করতে নিচের অপশন বেছে নিন:\n\n© {user.first_name}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data in ["new_account", "new_account_2fa"]:
        context.user_data['account_type'] = query.data
        await query.edit_message_text(
            "📝 ইমেইল এবং পাসওয়ার্ড দিন:\n\nফরম্যাট: ইমেইল, পাসওয়ার্ড\nউদাহরণ: example@gmail.com, pass123"
        )
        return WAITING_FOR_INSTAGRAM_INFO
    else:
        await query.edit_message_text("সাহায্য: ইমেইল, পাসওয়ার্ড ফরম্যাটে দিন।")

async def instagram_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if ',' in text:
        email, password = [x.strip() for x in text.split(',')]
        sheet = context.bot_data.get('sheet')
        user = update.effective_user
        
        if context.user_data.get('account_type') == "new_account_2fa":
            context.user_data['temp_email'] = email
            context.user_data['temp_password'] = password
            await update.message.reply_text("🔐 2FA কোড দিন:")
            return WAITING_FOR_2FA
        else:
            save_to_sheet(sheet, user.id, user.username or "Unknown", email, password)
            await update.message.reply_text(f"✅ অ্যাকাউন্ট সংরক্ষিত!\n📧 {email}")
            return ConversationHandler.END
    else:
        await update.message.reply_text("❌ ভুল ফরম্যাট! আবার চেষ্টা করুন।")
        return WAITING_FOR_INSTAGRAM_INFO

async def twofa_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    twofa = update.message.text.strip()
    email = context.user_data.get('temp_email')
    password = context.user_data.get('temp_password')
    sheet = context.bot_data.get('sheet')
    user = update.effective_user
    
    save_to_sheet(sheet, user.id, user.username or "Unknown", email, password, twofa, "2FA Pending")
    await update.message.reply_text(f"✅ 2FA অ্যাকাউন্ট সংরক্ষিত!\n📧 {email}\n🔑 {twofa}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ বাতিল। /start দিয়ে শুরু করুন।")
    return ConversationHandler.END

def main():
    sheet = setup_google_sheets()
    app = Application.builder().token(TOKEN).build()
    app.bot_data['sheet'] = sheet
    
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            WAITING_FOR_INSTAGRAM_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, instagram_info_handler)],
            WAITING_FOR_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, twofa_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 বট চালু!")
    app.run_polling()

if __name__ == '__main__':
    main()
