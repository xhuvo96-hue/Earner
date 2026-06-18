import os
import logging
import json
import random
import string
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials

TOKEN = os.environ.get('BOT_TOKEN')
SHEET_NAME = os.environ.get('SHEET_NAME', 'Instagram Accounts')

MAIN_MENU, WAITING_2FA, WAITING_DONE, WAITING_WITHDRAW = range(4)

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

def generate_random_username():
    adjectives = ["cool", "happy", "super", "great", "mega", "ultra", "pro", "star", "king", "queen"]
    nouns = ["user", "insta", "gram", "snap", "chat", "wave", "pulse", "nova", "zen", "vibe"]
    number = ''.join(random.choices(string.digits, k=4))
    return f"{random.choice(adjectives)}_{random.choice(nouns)}_{number}"

def generate_random_password():
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choices(chars, k=12))

# ============= নিচের নেভিগেশন বার (৪টি বাটন) =============
def get_bottom_menu():
    keyboard = [
        [
            KeyboardButton("👤 অ্যাকাউন্ট"),
            KeyboardButton("📋 কাজ (INSTA 2FA)")
        ],
        [
            KeyboardButton("🏧 উইথড্র ব্যালেন্স"),
            KeyboardButton("👥 রেফার")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ============= স্টার্ট =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = f"""
👋 **স্বাগতম {user.first_name}!**

📌 **ইনস্টাগ্রাম অ্যাকাউন্ট তৈরি করুন**
🔹 নিচের অপশন থেকে বেছে নিন:

━━━━━━━━━━━━━━━━━━━━━
📱 **নতুন অ্যাকাউন্ট তৈরি**
🔐 **2FA সহ অ্যাকাউন্ট**
━━━━━━━━━━━━━━━━━━━━━

⚠️ শর্তাবলী:
• ন্যূনতম বয়স: 14+
• একাধিক অ্যাকাউন্ট নিষিদ্ধ
• দায়িত্ব ব্যবহারকারীর

© Earner Bot
    """
    
    inline_keyboard = [
        [InlineKeyboardButton("📱 নতুন অ্যাকাউন্ট তৈরি", callback_data="new_account")],
        [InlineKeyboardButton("🔐 2FA সহ অ্যাকাউন্ট", callback_data="new_account_2fa")],
        [InlineKeyboardButton("ℹ️ হেল্প", callback_data="help")]
    ]
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )
    
    await update.message.reply_text(
        "📌 **নিচের বাটনগুলো ব্যবহার করুন:**",
        parse_mode='Markdown',
        reply_markup=get_bottom_menu()
    )
    return MAIN_MENU

# ============= ইনলাইন বাটন হ্যান্ডলার =============
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    sheet = context.bot_data.get('sheet')

    if query.data == "new_account" or query.data == "new_account_2fa":
        username = generate_random_username()
        password = generate_random_password()
        context.user_data['temp_username'] = username
        context.user_data['temp_password'] = password
        context.user_data['account_type'] = query.data
        
        if sheet:
            save_to_sheet(sheet, user_id, query.from_user.username or "Unknown", username, password, status="2FA Pending")
        
        keyboard = [[InlineKeyboardButton("✅ 2FA কোড দিন", callback_data="give_2fa")]]
        await query.edit_message_text(
            f"🎯 **আপনার অ্যাকাউন্ট তৈরি হয়েছে!**\n\n"
            f"👤 ইউজারনেম: `{username}`\n"
            f"🔑 পাসওয়ার্ড: `{password}`\n\n"
            f"📌 **প্লিজ আপনার 2FA কোড দিন।**",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAITING_2FA

    elif query.data == "give_2fa":
        await query.edit_message_text(
            "🔐 **আপনার 2FA কোড লিখুন:**\n\n"
            "উদাহরণ: `123456`"
        )
        return WAITING_2FA

    elif query.data == "help":
        await query.edit_message_text(
            "ℹ️ **সাহায্য:**\n\n"
            "1. নতুন অ্যাকাউন্ট তৈরি করতে বাটনে ক্লিক করুন\n"
            "2. ইউজারনেম ও পাসওয়ার্ড অটো জেনারেট হবে\n"
            "3. 2FA কোড দিন\n"
            "4. DONE বাটনে ক্লিক করুন\n\n"
            "📞 সাপোর্ট: @EarnerSupport"
        )
        return MAIN_MENU

    elif query.data == "done_account":
        if sheet:
            try:
                records = sheet.get_all_records()
                for i, row in enumerate(records, start=2):
                    if str(row.get('User ID')) == str(user_id) and row.get('Status') == '2FA Provided':
                        sheet.update_cell(i, 7, 'Completed')
                        break
            except:
                pass
        await query.edit_message_text(
            "🎉 **অভিনন্দন!**\n\n"
            "আপনার অ্যাকাউন্ট সম্পূর্ণ হয়েছে!\n\n"
            "আরও অ্যাকাউন্ট তৈরি করতে /start দিন।"
        )
        return MAIN_MENU

    elif query.data in ["withdraw_binance", "withdraw_bkash", "withdraw_nagad"]:
        method = query.data.replace("withdraw_", "").capitalize()
        context.user_data['withdraw_method'] = method
        await query.edit_message_text(
            f"📤 **উইথড্র ({method})**\n\n"
            f"আপনার {method} অ্যাকাউন্ট আইডি লিখুন:"
        )
        return WAITING_WITHDRAW

    return MAIN_MENU

# ============= 2FA হ্যান্ডলার =============
async def twofa_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    twofa_code = update.message.text.strip()
    user_id = update.effective_user.id
    sheet = context.bot_data.get('sheet')
    
    if sheet:
        try:
            records = sheet.get_all_records()
            for i, row in enumerate(records, start=2):
                if str(row.get('User ID')) == str(user_id) and row.get('Status') == '2FA Pending':
                    sheet.update_cell(i, 6, twofa_code)
                    sheet.update_cell(i, 7, '2FA Provided')
                    break
        except:
            pass
    
    keyboard = [[InlineKeyboardButton("✅ অ্যাকাউন্ট সম্পূর্ণ (DONE)", callback_data="done_account")]]
    await update.message.reply_text(
        f"✅ **2FA কোড সংরক্ষিত!**\n\n"
        f"🔑 আপনার কোড: `{twofa_code}`\n\n"
        f"অ্যাকাউন্ট সম্পূর্ণ করতে **DONE** বাটনে ক্লিক করুন।",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return WAITING_DONE

# ============= উইথড্র হ্যান্ডলার =============
async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_id = update.message.text.strip()
    method = context.user_data.get('withdraw_method', 'Unknown')
    sheet = context.bot_data.get('sheet')
    
    if sheet:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, str(update.effective_user.id), update.effective_user.username or "Unknown", f"Withdraw: {method}", account_id, "95 Taka", "Pending"])
    
    await update.message.reply_text(
        f"✅ **উইথড্র রিকোয়েস্ট পাঠানো হয়েছে!**\n\n"
        f"📤 মেথড: {method}\n"
        f"🆔 অ্যাকাউন্ট: `{account_id}`\n"
        f"💰 পরিমাণ: ১০০ টাকা\n"
        f"💸 চার্জ: ৫ টাকা\n"
        f"📊 পাবেন: ৯৫ টাকা\n\n"
        f"আমাদের টিম প্রসেস করবে।"
    )
    return MAIN_MENU

# ============= টেক্সট মেসেজ হ্যান্ডলার (নিচের ৪টি বাটন) =============
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    sheet = context.bot_data.get('sheet')
    
    # ========== ১. অ্যাকাউন্ট (ব্যালেন্স সহ) ==========
    if text == "👤 অ্যাকাউন্ট":
        balance = 0
        account_count = 0
        
        if sheet:
            try:
                records = sheet.get_all_records()
                user_accounts = [r for r in records if str(r.get('User ID')) == str(user_id)]
                account_count = len(user_accounts)
                # প্রতি অ্যাকাউন্টের জন্য ১০ টাকা করে ব্যালেন্স
                balance = account_count * 10
            except:
                pass
        
        msg = f"""
👤 **আপনার অ্যাকাউন্ট**

📊 **মোট অ্যাকাউন্ট:** {account_count}
💰 **ব্যালেন্স:** {balance} টাকা

━━━━━━━━━━━━━━━━━━━━━
📋 **আপনার অ্যাকাউন্টসমূহ:**
"""
        if sheet and account_count > 0:
            try:
                records = sheet.get_all_records()
                user_accounts = [r for r in records if str(r.get('User ID')) == str(user_id)]
                for acc in user_accounts[-5:]:  # শেষ ৫টি দেখাবে
                    msg += f"\n📧 {acc.get('Instagram Email')}\n🔑 {acc.get('Instagram Password')}\n📊 {acc.get('Status', 'Pending')}\n━━━━━━━━━"
            except:
                pass
        else:
            msg += "\n❌ এখনো কোনো অ্যাকাউন্ট নেই।"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    # ========== ২. কাজ (INSTA 2FA) ==========
    elif text == "📋 কাজ (INSTA 2FA)":
        keyboard = [
            [InlineKeyboardButton("📱 INSTA 2FA (নতুন)", callback_data="new_account")],
            [InlineKeyboardButton("🔐 INSTA 2FA (2FA সহ)", callback_data="new_account_2fa")]
        ]
        await update.message.reply_text(
            "📋 **কাজ (INSTA 2FA)**\n\n"
            "🔹 ইনস্টাগ্রাম অ্যাকাউন্ট তৈরি করুন\n"
            "🔹 2FA কোড দিন\n"
            "🔹 অ্যাকাউন্ট সম্পূর্ণ করুন\n\n"
            "নিচের অপশন থেকে বেছে নিন:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # ========== ৩. উইথড্র ব্যালেন্স ==========
    elif text == "🏧 উইথড্র ব্যালেন্স":
        keyboard = [
            [InlineKeyboardButton("💰 Binance", callback_data="withdraw_binance")],
            [InlineKeyboardButton("💳 Bkash", callback_data="withdraw_bkash")],
            [InlineKeyboardButton("📱 Nagad", callback_data="withdraw_nagad")]
        ]
        await update.message.reply_text(
            "🏧 **উইথড্র ব্যালেন্স**\n\n"
            "⚠️ মিনিমাম: ১০০ টাকা\n"
            "💸 চার্জ: ৫ টাকা\n"
            "📊 পাবেন: ৯৫ টাকা\n\n"
            "পছন্দের মেথড বেছে নিন:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # ========== ৪. রেফার ==========
    elif text == "👥 রেফার":
        user = update.effective_user
        refer_link = f"https://t.me/{context.bot.username}?start=ref_{user.id}"
        keyboard = [
            [InlineKeyboardButton("📤 শেয়ার করুন", url=f"https://t.me/share/url?url={refer_link}&text=আমার রেফার লিংক ব্যবহার করুন! 🎉")]
        ]
        await update.message.reply_text(
            f"👥 **রেফার প্রোগ্রাম**\n\n"
            f"আপনার রেফার লিংক:\n`{refer_link}`\n\n"
            f"🎁 প্রতি রেফারের জন্য **১০ টাকা** বোনাস!\n\n"
            f"লিংক শেয়ার করুন এবং বোনাস পান! 🚀",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    else:
        await update.message.reply_text(
            "❓ **অজানা কমান্ড!**\n\n"
            "নিচের বাটনগুলো ব্যবহার করুন অথবা /start দিন।"
        )

# ============= ক্যান্সেল =============
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ বাতিল। /start দিয়ে শুরু করুন।")
    return MAIN_MENU

# ============= মেইন =============
def main():
    sheet = setup_google_sheets()
    app = Application.builder().token(TOKEN).build()
    app.bot_data['sheet'] = sheet
    
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(button_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
            ],
            WAITING_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, twofa_handler)],
            WAITING_DONE: [CallbackQueryHandler(button_handler, pattern="^done_account$")],
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
