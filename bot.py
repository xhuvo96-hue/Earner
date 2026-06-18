import os
import logging
import json
import random
import string
import pyotp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials

TOKEN = os.environ.get('BOT_TOKEN')
SHEET_NAME = os.environ.get('SHEET_NAME', 'Instagram Accounts')
ADMIN_IDS = [int(os.environ.get('ADMIN_ID', '0'))]  # Railway তে ADMIN_ID যোগ করুন

# কনভার্সেশন স্টেট
MAIN_MENU, WAITING_2FA_SECRET, WAITING_DONE, WAITING_WITHDRAW_ACCOUNT, ADMIN_MENU = range(5)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================== Google Sheets =====================
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

# ===================== র্যান্ডম জেনারেটর =====================
def generate_random_username():
    adjectives = ["cool", "happy", "super", "great", "mega", "ultra", "pro", "star", "king", "queen"]
    nouns = ["user", "insta", "gram", "snap", "chat", "wave", "pulse", "nova", "zen", "vibe"]
    number = ''.join(random.choices(string.digits, k=4))
    return f"{random.choice(adjectives)}_{random.choice(nouns)}_{number}"

def generate_random_password():
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choices(chars, k=12))

def generate_2fa_code(secret):
    try:
        totp = pyotp.TOTP(secret)
        return totp.now()
    except:
        return None

# ===================== এডমিন চেক =====================
def is_admin(user_id):
    return user_id in ADMIN_IDS

# ===================== নিচের বাটন =====================
def get_bottom_menu():
    keyboard = [
        [
            KeyboardButton("👤 আমার অ্যাকাউন্ট"),
            KeyboardButton("📋 কাজ (INSTA 2FA)")
        ],
        [
            KeyboardButton("🏧 উইথড্র ব্যালেন্স"),
            KeyboardButton("👥 রেফার")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_menu():
    keyboard = [
        [KeyboardButton("📊 ডেটাবেস ভিউ")],
        [KeyboardButton("📋 সব ডেটা কপি")],
        [KeyboardButton("📈 স্ট্যাটিস্টিক্স")],
        [KeyboardButton("👥 ইউজার লিস্ট")],
        [KeyboardButton("🔙 ইউজার মেনু")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===================== স্টার্ট =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    inline_keyboard = [
        [InlineKeyboardButton("📱 নতুন অ্যাকাউন্ট তৈরি", callback_data="new_account")],
        [InlineKeyboardButton("🔐 2FA সহ অ্যাকাউন্ট", callback_data="new_account_2fa")],
        [InlineKeyboardButton("ℹ️ হেল্প", callback_data="help")]
    ]
    
    # এডমিন হলে আলাদা মেনু
    if is_admin(user.id):
        await update.message.reply_text(
            f"👑 **এডমিন প্যানেল**\n\n"
            f"স্বাগতম {user.first_name}!\n"
            f"নিচের অপশন থেকে বেছে নিন:",
            parse_mode='Markdown',
            reply_markup=get_admin_menu()
        )
        return ADMIN_MENU
    
    await update.message.reply_text(
        f"👋 **স্বাগতম {user.first_name}!**\n\n"
        f"📌 নিচের বাটনগুলো ব্যবহার করুন:\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 **নতুন অ্যাকাউন্ট তৈরি**\n"
        f"🔐 **2FA সহ অ্যাকাউন্ট**\n"
        f"━━━━━━━━━━━━━━━━━━━━━",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )
    
    await update.message.reply_text(
        "📌 **নিচের মেনু থেকে বেছে নিন:**",
        reply_markup=get_bottom_menu()
    )
    return MAIN_MENU

# ===================== এডমিন টেক্সট হ্যান্ডলার =====================
async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    sheet = context.bot_data.get('sheet')
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ আপনি এডমিন নন!")
        return MAIN_MENU
    
    if text == "📊 ডেটাবেস ভিউ":
        if sheet:
            try:
                records = sheet.get_all_records()
                if records:
                    msg = "📊 **ডেটাবেস ভিউ**\n\n"
                    for i, row in enumerate(records[-10:], 1):  # শেষ ১০টি দেখাবে
                        msg += f"{i}. 📧 {row.get('Instagram Email')}\n"
                        msg += f"   🔑 {row.get('Instagram Password')}\n"
                        msg += f"   📊 {row.get('Status', 'Pending')}\n"
                        msg += f"   📅 {row.get('Timestamp')}\n━━━━━━━\n"
                    msg += f"\n📌 মোট রেকর্ড: {len(records)}"
                    await update.message.reply_text(msg, parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ ডেটাবেস খালি!")
            except Exception as e:
                await update.message.reply_text(f"⚠️ এরর: {e}")
        else:
            await update.message.reply_text("⚠️ ডেটাবেস সংযোগ নেই!")
        return ADMIN_MENU
    
    elif text == "📋 সব ডেটা কপি":
        if sheet:
            try:
                records = sheet.get_all_records()
                if records:
                    # টেক্সট ফরম্যাটে ডেটা তৈরি
                    data_text = "📋 **সমস্ত ডেটা**\n\n"
                    data_text += "Timestamp | User ID | Username | Email | Password | 2FA | Status\n"
                    data_text += "━" * 60 + "\n"
                    
                    for row in records:
                        data_text += f"{row.get('Timestamp', 'N/A')} | "
                        data_text += f"{row.get('User ID', 'N/A')} | "
                        data_text += f"{row.get('Username', 'N/A')} | "
                        data_text += f"{row.get('Instagram Email', 'N/A')} | "
                        data_text += f"{row.get('Instagram Password', 'N/A')} | "
                        data_text += f"{row.get('2FA Code', 'N/A')} | "
                        data_text += f"{row.get('Status', 'N/A')}\n"
                    
                    # কপি করার জন্য কোড ব্লকে পাঠান
                    await update.message.reply_text(
                        f"```\n{data_text}\n```",
                        parse_mode='Markdown'
                    )
                    
                    # CSV ফরম্যাটেও পাঠান
                    csv_text = "Timestamp,User ID,Username,Email,Password,2FA,Status\n"
                    for row in records:
                        csv_text += f"{row.get('Timestamp', 'N/A')},{row.get('User ID', 'N/A')},{row.get('Username', 'N/A')},{row.get('Instagram Email', 'N/A')},{row.get('Instagram Password', 'N/A')},{row.get('2FA Code', 'N/A')},{row.get('Status', 'N/A')}\n"
                    
                    await update.message.reply_text(
                        f"📄 **CSV ফরম্যাট (কপি করুন):**\n\n```\n{csv_text}\n```",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text("❌ ডেটাবেস খালি!")
            except Exception as e:
                await update.message.reply_text(f"⚠️ এরর: {e}")
        else:
            await update.message.reply_text("⚠️ ডেটাবেস সংযোগ নেই!")
        return ADMIN_MENU
    
    elif text == "📈 স্ট্যাটিস্টিক্স":
        if sheet:
            try:
                records = sheet.get_all_records()
                total = len(records)
                completed = len([r for r in records if r.get('Status') == 'Completed'])
                pending = len([r for r in records if r.get('Status') == 'Pending'])
                twofa_pending = len([r for r in records if '2FA' in str(r.get('Status', ''))])
                
                # ইউনিক ইউজার
                unique_users = len(set([r.get('User ID') for r in records]))
                
                msg = f"📈 **স্ট্যাটিস্টিক্স**\n\n"
                msg += f"📊 মোট অ্যাকাউন্ট: {total}\n"
                msg += f"✅ কমপ্লিট: {completed}\n"
                msg += f"⏳ পেন্ডিং: {pending}\n"
                msg += f"🔐 2FA পেন্ডিং: {twofa_pending}\n"
                msg += f"👥 ইউনিক ইউজার: {unique_users}\n"
                
                await update.message.reply_text(msg, parse_mode='Markdown')
            except Exception as e:
                await update.message.reply_text(f"⚠️ এরর: {e}")
        else:
            await update.message.reply_text("⚠️ ডেটাবেস সংযোগ নেই!")
        return ADMIN_MENU
    
    elif text == "👥 ইউজার লিস্ট":
        if sheet:
            try:
                records = sheet.get_all_records()
                users = {}
                for row in records:
                    uid = row.get('User ID')
                    if uid and uid not in users:
                        users[uid] = {
                            'username': row.get('Username', 'Unknown'),
                            'count': 1
                        }
                    elif uid in users:
                        users[uid]['count'] += 1
                
                if users:
                    msg = "👥 **ইউজার লিস্ট**\n\n"
                    for uid, data in users.items():
                        msg += f"🆔 {uid}\n"
                        msg += f"👤 @{data['username']}\n"
                        msg += f"📊 অ্যাকাউন্ট: {data['count']}\n━━━━━━━\n"
                    await update.message.reply_text(msg, parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ কোনো ইউজার নেই!")
            except Exception as e:
                await update.message.reply_text(f"⚠️ এরর: {e}")
        else:
            await update.message.reply_text("⚠️ ডেটাবেস সংযোগ নেই!")
        return ADMIN_MENU
    
    elif text == "🔙 ইউজার মেনু":
        # ইউজার মেনুতে ফেরত যান
        return await start(update, context)
    
    else:
        await update.message.reply_text("❓ অজানা কমান্ড!")
        return ADMIN_MENU

# ===================== ইনলাইন বাটন হ্যান্ডলার =====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    sheet = context.bot_data.get('sheet')

    if query.data == "new_account":
        username = generate_random_username()
        password = generate_random_password()
        context.user_data['temp_username'] = username
        context.user_data['temp_password'] = password
        
        if sheet:
            save_to_sheet(sheet, user_id, query.from_user.username or "Unknown", username, password, status="Pending")
        
        await query.edit_message_text(
            f"🎯 **আপনার অ্যাকাউন্ট তৈরি হয়েছে!**\n\n"
            f"👤 ইউজারনেম: `{username}`\n"
            f"🔑 পাসওয়ার্ড: `{password}`\n\n"
            f"✅ অ্যাকাউন্ট সেভ করা হয়েছে!",
            parse_mode='Markdown'
        )
        return MAIN_MENU

    elif query.data == "new_account_2fa":
        username = generate_random_username()
        password = generate_random_password()
        context.user_data['temp_username'] = username
        context.user_data['temp_password'] = password
        
        if sheet:
            save_to_sheet(sheet, user_id, query.from_user.username or "Unknown", username, password, status="Waiting for 2FA Secret")
        
        await query.edit_message_text(
            f"🎯 **আপনার অ্যাকাউন্ট তৈরি হয়েছে!**\n\n"
            f"👤 ইউজারনেম: `{username}`\n"
            f"🔑 পাসওয়ার্ড: `{password}`\n\n"
            f"🔐 **প্লিজ আপনার Google Authenticator সিক্রেট কী দিন:**\n\n"
            f"উদাহরণ: `JBSWY3DPEHPK3PXP`",
            parse_mode='Markdown'
        )
        return WAITING_2FA_SECRET

    elif query.data == "help":
        await query.edit_message_text(
            "ℹ️ **সাহায্য:**\n\n"
            "1. নতুন অ্যাকাউন্ট তৈরি করতে বাটনে ক্লিক করুন\n"
            "2. 2FA অ্যাকাউন্টের জন্য সিক্রেট কী দিন\n"
            "3. বট অটো 2FA কোড জেনারেট করে দিবে\n"
            "4. DONE বাটনে ক্লিক করুন\n\n"
            "📞 সাপোর্ট: @EarnerSupport"
        )
        return MAIN_MENU

    elif query.data == "done_account":
        if sheet:
            try:
                records = sheet.get_all_records()
                for i, row in enumerate(records, start=2):
                    if str(row.get('User ID')) == str(user_id) and row.get('Status') == '2FA Generated':
                        sheet.update_cell(i, 7, 'Completed')
                        break
            except:
                pass
        await query.edit_message_text(
            "🎉 **অভিনন্দন!**\n\n"
            "আপনার 2FA অ্যাকাউন্ট সম্পূর্ণ হয়েছে!"
        )
        return MAIN_MENU

    elif query.data in ["withdraw_binance", "withdraw_bkash", "withdraw_nagad"]:
        method = query.data.replace("withdraw_", "").capitalize()
        context.user_data['withdraw_method'] = method
        await query.edit_message_text(
            f"📤 **উইথড্র ({method})**\n\n"
            f"আপনার {method} অ্যাকাউন্ট আইডি লিখুন:"
        )
        return WAITING_WITHDRAW_ACCOUNT

    return MAIN_MENU

# ===================== 2FA সিক্রেট হ্যান্ডলার =====================
async def twofa_secret_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    secret = update.message.text.strip().upper()
    user_id = update.effective_user.id
    sheet = context.bot_data.get('sheet')
    
    if len(secret) < 16:
        await update.message.reply_text(
            "❌ **ভুল সিক্রেট কী!**\n\n"
            "সিক্রেট কী কমপক্ষে ১৬ অক্ষরের হতে হবে।\n"
            "আবার চেষ্টা করুন অথবা /cancel দিন।"
        )
        return WAITING_2FA_SECRET
    
    otp_code = generate_2fa_code(secret)
    
    if otp_code:
        if sheet:
            try:
                records = sheet.get_all_records()
                for i, row in enumerate(records, start=2):
                    if str(row.get('User ID')) == str(user_id) and row.get('Status') == 'Waiting for 2FA Secret':
                        sheet.update_cell(i, 6, f"Secret: {secret}, OTP: {otp_code}")
                        sheet.update_cell(i, 7, '2FA Generated')
                        break
            except Exception as e:
                logger.error(f"2FA secret save error: {e}")
        
        keyboard = [[InlineKeyboardButton("✅ অ্যাকাউন্ট সম্পূর্ণ (DONE)", callback_data="done_account")]]
        await update.message.reply_text(
            f"✅ **2FA কোড জেনারেট করা হয়েছে!**\n\n"
            f"🔑 **আপনার 2FA কোড: `{otp_code}`**\n\n"
            f"⏳ এই কোড ৩০ সেকেন্ডের জন্য বৈধ।\n\n"
            f"অ্যাকাউন্ট সম্পূর্ণ করতে **DONE** বাটনে ক্লিক করুন।",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAITING_DONE
    else:
        await update.message.reply_text(
            "❌ **সিক্রেট কী থেকে কোড জেনারেট করা যায়নি!**"
        )
        return WAITING_2FA_SECRET

# ===================== উইথড্র হ্যান্ডলার =====================
async def withdraw_account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_id = update.message.text.strip()
    method = context.user_data.get('withdraw_method', 'Unknown')
    sheet = context.bot_data.get('sheet')
    user_id = update.effective_user.id
    
    if sheet:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([
            timestamp,
            str(user_id),
            update.effective_user.username or "Unknown",
            f"Withdraw: {method}",
            account_id,
            "Amount: 100 - 5 = 95 Taka",
            "Pending"
        ])
    
    await update.message.reply_text(
        f"✅ **উইথড্র রিকোয়েস্ট পাঠানো হয়েছে!**\n\n"
        f"📤 মেথড: {method}\n"
        f"🆔 অ্যাকাউন্ট: `{account_id}`\n"
        f"💰 পাবেন: ৯৫ টাকা\n\n"
        f"আমাদের টিম প্রসেস করবে।"
    )
    return MAIN_MENU

# ===================== টেক্সট হ্যান্ডলার (ইউজার) =====================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    # এডমিন চেক
    if is_admin(user_id) and text in ["📊 ডেটাবেস ভিউ", "📋 সব ডেটা কপি", "📈 স্ট্যাটিস্টিক্স", "👥 ইউজার লিস্ট", "🔙 ইউজার মেনু"]:
        await admin_text_handler(update, context)
        return
    
    sheet = context.bot_data.get('sheet')
    
    if text == "👤 আমার অ্যাকাউন্ট":
        balance = 0
        account_count = 0
        msg = "👤 **আপনার অ্যাকাউন্ট**\n\n"
        
        if sheet:
            try:
                records = sheet.get_all_records()
                user_accounts = [r for r in records if str(r.get('User ID')) == str(user_id)]
                account_count = len(user_accounts)
                balance = account_count * 10
                
                msg += f"💰 **ব্যালেন্স:** {balance} টাকা\n"
                msg += f"📊 **মোট অ্যাকাউন্ট:** {account_count}\n\n"
                
                if account_count > 0:
                    msg += "📋 **আপনার অ্যাকাউন্টসমূহ:**\n\n"
                    for acc in user_accounts[-5:]:
                        msg += f"📧 {acc.get('Instagram Email')}\n"
                        msg += f"🔑 {acc.get('Instagram Password')}\n"
                        msg += f"📊 স্ট্যাটাস: {acc.get('Status', 'Pending')}\n━━━━━━━\n"
                else:
                    msg += "❌ এখনো কোনো অ্যাকাউন্ট নেই।"
            except:
                msg += "⚠️ ডেটাবেস এরর।"
        else:
            msg += "⚠️ ডেটাবেস সংযোগ নেই।"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    elif text == "📋 কাজ (INSTA 2FA)":
        inline_keyboard = [
            [InlineKeyboardButton("📱 নতুন অ্যাকাউন্ট তৈরি", callback_data="new_account")],
            [InlineKeyboardButton("🔐 2FA সহ অ্যাকাউন্ট", callback_data="new_account_2fa")]
        ]
        await update.message.reply_text(
            "📋 **কাজ (INSTA 2FA)**\n\n"
            "🔹 ইনস্টাগ্রাম অ্যাকাউন্ট তৈরি করুন\n"
            "🔹 2FA সিক্রেট কী দিন\n"
            "🔹 বট অটো কোড জেনারেট করবে\n\n"
            "নিচের অপশন থেকে বেছে নিন:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
    
    elif text == "🏧 উইথড্র ব্যালেন্স":
        keyboard = [
            [InlineKeyboardButton("💰 Binance", callback_data="withdraw_binance")],
            [InlineKeyboardButton("💳 Bkash", callback_data="withdraw_bkash")],
            [InlineKeyboardButton("📱 Nagad", callback_data="withdraw_nagad")]
        ]
        await update.message.reply_text(
            "🏧 **উইথড্র**\n\n"
            "⚠️ মিনিমাম: ১০০ টাকা\n"
            "💸 চার্জ: ৫ টাকা\n"
            "📊 পাবেন: ৯৫ টাকা\n\n"
            "পছন্দের মেথড বেছে নিন:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif text == "👥 রেফার":
        user = update.effective_user
        refer_link = f"https://t.me/{context.bot.username}?start=ref_{user.id}"
        keyboard = [
            [InlineKeyboardButton("📤 শেয়ার করুন", url=f"https://t.me/share/url?url={refer_link}&text=আমার রেফার লিংক! 🎉")]
        ]
        await update.message.reply_text(
            f"👥 **রেফার**\n\n"
            f"আপনার লিংক:\n`{refer_link}`\n\n"
            f"🎁 প্রতি রেফারে ১০ টাকা বোনাস!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    else:
        await update.message.reply_text("❓ নিচের বাটন ব্যবহার করুন।")

# ===================== ক্যান্সেল =====================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ বাতিল। /start দিন।")
    return MAIN_MENU

# ===================== মেইন =====================
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
            ADMIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler)
            ],
            WAITING_2FA_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, twofa_secret_handler)],
            WAITING_DONE: [CallbackQueryHandler(button_handler, pattern="^done_account$")],
            WAITING_WITHDRAW_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_account_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 বট চালু!")
    app.run_polling()

if __name__ == '__main__':
    main()
