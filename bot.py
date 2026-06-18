import os
import logging
import json
import random
import string
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ================== কনফিগারেশন ==================
TOKEN = os.environ.get('BOT_TOKEN')
SHEET_NAME = os.environ.get('SHEET_NAME', 'Instagram Accounts')

# কনভার্সেশন স্টেট
MAIN_MENU, WAITING_INSTAGRAM_INFO, WAITING_2FA, WAITING_DONE, WAITING_WITHDRAW, WAITING_REFER = range(6)

# লগিং
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ইউজার ডেটা স্টোর (টেম্পোরারি)
user_data_store = {}

# ================== Google Sheets ==================
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

# ================== র্যান্ডম ইউজারনেম ও পাসওয়ার্ড জেনারেটর ==================
def generate_random_username():
    adjectives = ["cool", "happy", "super", "great", "mega", "ultra", "pro", "star", "king", "queen"]
    nouns = ["user", "insta", "gram", "snap", "chat", "wave", "pulse", "nova", "zen", "vibe"]
    number = ''.join(random.choices(string.digits, k=4))
    return f"{random.choice(adjectives)}_{random.choice(nouns)}_{number}"

def generate_random_password():
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choices(chars, k=12))

# ================== মেইন মেনু ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data_store[user.id] = {}
    keyboard = [
        [InlineKeyboardButton("👤 আমার অ্যাকাউন্ট", callback_data="my_account")],
        [InlineKeyboardButton("📋 কাজ (INSTA 2FA)", callback_data="work_insta_2fa")],
        [InlineKeyboardButton("🏧 উইথড্র ব্যালেন্স", callback_data="withdraw")],
        [InlineKeyboardButton("👥 রেফার", callback_data="refer")]
    ]
    await update.message.reply_text(
        f"👋 স্বাগতম {user.first_name}!\n\n"
        f"নিচের অপশন থেকে বেছে নিন:\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MAIN_MENU

# ================== বাটন হ্যান্ডলার ==================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    # ========== ১. আমার অ্যাকাউন্ট ==========
    if query.data == "my_account":
        sheet = context.bot_data.get('sheet')
        if sheet:
            try:
                records = sheet.get_all_records()
                user_accounts = [r for r in records if str(r.get('User ID')) == str(user_id)]
                if user_accounts:
                    msg = "👤 **আপনার অ্যাকাউন্টসমূহ:**\n\n"
                    for acc in user_accounts:
                        msg += f"📧 {acc.get('Instagram Email')}\n"
                        msg += f"🔑 {acc.get('Instagram Password')}\n"
                        msg += f"📊 স্ট্যাটাস: {acc.get('Status', 'Pending')}\n"
                        msg += f"📅 {acc.get('Timestamp')}\n━━━━━━━━━━━\n"
                    await query.edit_message_text(msg, parse_mode='Markdown')
                else:
                    await query.edit_message_text("❌ আপনার কোনো অ্যাকাউন্ট নেই।")
            except Exception as e:
                await query.edit_message_text(f"⚠️ এরর: {str(e)}")
        else:
            await query.edit_message_text("⚠️ ডেটাবেস সংযোগ নেই।")
        return MAIN_MENU
    
    # ========== ২. কাজ (INSTA 2FA) ==========
    elif query.data == "work_insta_2fa":
        # র্যান্ডম ইউজারনেম ও পাসওয়ার্ড জেনারেট
        username = generate_random_username()
        password = generate_random_password()
        
        # ডেটা সেভ
        context.user_data['temp_username'] = username
        context.user_data['temp_password'] = password
        
        # শীটে সেভ
        sheet = context.bot_data.get('sheet')
        if sheet:
            save_to_sheet(sheet, user_id, query.from_user.username or "Unknown", username, password, status="2FA Pending")
        
        keyboard = [
            [InlineKeyboardButton("✅ 2FA কোড দিন", callback_data="give_2fa")]
        ]
        await query.edit_message_text(
            f"🎯 **আপনার অ্যাকাউন্ট তৈরি হয়েছে!**\n\n"
            f"👤 ইউজারনেম: `{username}`\n"
            f"🔑 পাসওয়ার্ড: `{password}`\n\n"
            f"📌 **প্লিজ আপনার 2FA কোড দিন।**",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAITING_2FA
    
    # ========== ২FA কোড দিন বাটন ==========
    elif query.data == "give_2fa":
        await query.edit_message_text(
            "🔐 **আপনার 2FA কোড লিখুন:**\n\n"
            "উদাহরণ: `123456`"
        )
        return WAITING_2FA
    
    # ========== ৩. উইথড্র ==========
    elif query.data == "withdraw":
        keyboard = [
            [InlineKeyboardButton("💰 Binance", callback_data="withdraw_binance")],
            [InlineKeyboardButton("💳 Bkash", callback_data="withdraw_bkash")],
            [InlineKeyboardButton("📱 Nagad", callback_data="withdraw_nagad")],
            [InlineKeyboardButton("🔙 ব্যাক", callback_data="back_main")]
        ]
        await query.edit_message_text(
            "🏧 **উইথড্র ব্যালেন্স**\n\n"
            "⚠️ মিনিমাম উইথড্র: **১০০ টাকা**\n"
            "💸 চার্জ: **৫ টাকা** কাটা হবে\n\n"
            "আপনার পছন্দের অপশন বেছে নিন:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAITING_WITHDRAW
    
    # ========== উইথড্র অপশনসমূহ ==========
    elif query.data in ["withdraw_binance", "withdraw_bkash", "withdraw_nagad"]:
        method = query.data.replace("withdraw_", "").capitalize()
        context.user_data['withdraw_method'] = method
        await query.edit_message_text(
            f"📤 **উইথড্র ({method})**\n\n"
            f"আপনার {method} অ্যাকাউন্ট আইডি দিন:\n\n"
            f"উদাহরণ: `example@binance.com` বা `017XXXXXXXX`"
        )
        return WAITING_WITHDRAW
    
    # ========== ৪. রেফার ==========
    elif query.data == "refer":
        user = query.from_user
        refer_link = f"https://t.me/{context.bot.username}?start=ref_{user.id}"
        keyboard = [
            [InlineKeyboardButton("📤 শেয়ার করুন", url=f"https://t.me/share/url?url={refer_link}&text=আমার রেফার লিংক ব্যবহার করুন!")],
            [InlineKeyboardButton("🔙 ব্যাক", callback_data="back_main")]
        ]
        await query.edit_message_text(
            f"👥 **রেফার প্রোগ্রাম**\n\n"
            f"আপনার রেফার লিংক:\n`{refer_link}`\n\n"
            f"প্রতি রেফারের জন্য **১০ টাকা** বোনাস!\n\n"
            f"লিংক শেয়ার করুন এবং বোনাস পান! 🎉",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return MAIN_MENU
    
    # ========== ব্যাক ==========
    elif query.data == "back_main":
        return await show_main_menu(update, context)

# ================== 2FA হ্যান্ডলার ==================
async def twofa_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    twofa_code = update.message.text.strip()
    user_id = update.effective_user.id
    
    # 2FA কোড সেভ
    sheet = context.bot_data.get('sheet')
    if sheet:
        try:
            records = sheet.get_all_records()
            for i, row in enumerate(records, start=2):
                if str(row.get('User ID')) == str(user_id) and row.get('Status') == '2FA Pending':
                    sheet.update_cell(i, 6, twofa_code)  # 2FA Code কলাম
                    sheet.update_cell(i, 7, '2FA Provided')
                    break
        except Exception as e:
            logger.error(f"2FA update error: {e}")
    
    keyboard = [
        [InlineKeyboardButton("✅ অ্যাকাউন্ট সম্পূর্ণ (DONE)", callback_data="done_account")],
        [InlineKeyboardButton("🔙 ব্যাক", callback_data="back_main")]
    ]
    await update.message.reply_text(
        f"✅ **2FA কোড সংরক্ষিত!**\n\n"
        f"🔑 আপনার 2FA কোড: `{twofa_code}`\n\n"
        f"আপনার অ্যাকাউন্ট সম্পূর্ণ হলে **DONE** বাটনে ক্লিক করুন।",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return WAITING_DONE

# ================== DONE বাটন ==================
async def done_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    sheet = context.bot_data.get('sheet')
    if sheet:
        try:
            records = sheet.get_all_records()
            for i, row in enumerate(records, start=2):
                if str(row.get('User ID')) == str(user_id) and row.get('Status') == '2FA Provided':
                    sheet.update_cell(i, 7, 'Completed')
                    break
        except Exception as e:
            logger.error(f"Done update error: {e}")
    
    await query.edit_message_text(
        "🎉 **অভিনন্দন!**\n\n"
        "আপনার অ্যাকাউন্ট সম্পূর্ণ হয়েছে!\n\n"
        "আরও কাজ করতে /start দিন।"
    )
    return MAIN_MENU

# ================== উইথড্র হ্যান্ডলার ==================
async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_id = update.message.text.strip()
    method = context.user_data.get('withdraw_method', 'Unknown')
    
    # উইথড্র তথ্য শীটে সেভ
    sheet = context.bot_data.get('sheet')
    if sheet:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([
            timestamp,
            str(update.effective_user.id),
            update.effective_user.username or "Unknown",
            f"Withdraw: {method}",
            account_id,
            "Amount: 100 - 5 = 95",
            "Pending"
        ])
    
    await update.message.reply_text(
        f"✅ **উইথড্র রিকোয়েস্ট পাঠানো হয়েছে!**\n\n"
        f"📤 মেথড: {method}\n"
        f"🆔 অ্যাকাউন্ট: `{account_id}`\n"
        f"💰 পরিমাণ: ১০০ টাকা\n"
        f"💸 চার্জ: ৫ টাকা\n"
        f"📊 পাবেন: ৯৫ টাকা\n\n"
        f"আমাদের টিম আপনার রিকোয়েস্ট প্রসেস করবে।"
    )
    return MAIN_MENU

# ================== শো মেইন মেনু ==================
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("👤 আমার অ্যাকাউন্ট", callback_data="my_account")],
        [InlineKeyboardButton("📋 কাজ (INSTA 2FA)", callback_data="work_insta_2fa")],
        [InlineKeyboardButton("🏧 উইথড্র ব্যালেন্স", callback_data="withdraw")],
        [InlineKeyboardButton("👥 রেফার", callback_data="refer")]
    ]
    await query.edit_message_text(
        "🏠 **মেইন মেনু**\n\n"
        "নিচের অপশন থেকে বেছে নিন:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MAIN_MENU

# ================== ক্যান্সেল ==================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ বাতিল করা হয়েছে। /start দিয়ে আবার শুরু করুন।")
    return MAIN_MENU

# ================== মেইন ফাংশন ==================
def main():
    sheet = setup_google_sheets()
    app = Application.builder().token(TOKEN).build()
    app.bot_data['sheet'] = sheet
    
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(button_handler, pattern="^(my_account|work_insta_2fa|withdraw|refer|back_main|give_2fa|done_account|withdraw_binance|withdraw_bkash|withdraw_nagad)$")
            ],
            WAITING_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, twofa_handler)],
            WAITING_DONE: [CallbackQueryHandler(done_account, pattern="^done_account$")],
            WAITING_WITHDRAW: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 বট চালু!")
    app.run_polling()

if __name__ == '__main__':
    main()
