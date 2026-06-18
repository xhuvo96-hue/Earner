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
ADMIN_IDS = []

admin_id_str = os.environ.get('ADMIN_ID', '')
if admin_id_str:
    try:
        ADMIN_IDS = [int(x.strip()) for x in admin_id_str.split(',') if x.strip()]
    except:
        ADMIN_IDS = []

MAIN_MENU, WORK_MENU, WAITING_2FA, WAITING_DONE, WAITING_WITHDRAW, WITHDRAW_MENU, REFER_MENU, HELP_MENU = range(8)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
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
        try:
            sheet = client.open(SHEET_NAME).sheet1
        except:
            sheet = client.create(SHEET_NAME).sheet1
            headers = ["Timestamp", "User ID", "Username", "Instagram Email", "Instagram Password", "2FA Code", "Status", "Balance"]
            sheet.append_row(headers)
        return sheet
    except Exception as e:
        logger.error(f"Google Sheets setup error: {e}")
        return None

def get_all_sheet_data(sheet):
    if not sheet:
        return []
    try:
        return sheet.get_all_records()
    except Exception as e:
        logger.error(f"Get data error: {e}")
        return []

def save_to_sheet(sheet, user_id, username, email, password, twofa="", status="Pending"):
    if not sheet:
        return False
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, str(user_id), username, email, password, twofa, status, "0"])
        return True
    except Exception as e:
        logger.error(f"Save error: {e}")
        return False

def update_balance(sheet, user_id, amount):
    try:
        if not sheet:
            return False
        records = get_all_sheet_data(sheet)
        for i, row in enumerate(records, start=2):
            if str(row.get('User ID')) == str(user_id):
                current_balance = int(row.get('Balance', 0))
                new_balance = current_balance + amount
                sheet.update_cell(i, 8, str(new_balance))
                return True
        return False
    except Exception as e:
        logger.error(f"Update balance error: {e}")
        return False

def get_user_balance(sheet, user_id):
    if not sheet:
        return 0
    try:
        records = get_all_sheet_data(sheet)
        for row in records:
            if str(row.get('User ID')) == str(user_id):
                return int(row.get('Balance', 0))
        return 0
    except Exception as e:
        logger.error(f"Get balance error: {e}")
        return 0

def get_user_accounts(sheet, user_id):
    if not sheet:
        return []
    try:
        records = get_all_sheet_data(sheet)
        return [r for r in records if str(r.get('User ID')) == str(user_id)]
    except Exception as e:
        logger.error(f"Get user accounts error: {e}")
        return []

# ===================== র্যান্ডম জেনারেটর =====================
def generate_random_username():
    adjectives = ["cool", "happy", "super", "great", "mega", "ultra", "pro", "star", "king", "queen"]
    nouns = ["user", "insta", "gram", "snap", "chat", "wave", "pulse", "nova", "zen", "vibe"]
    number = ''.join(random.choices(string.digits, k=4))
    return f"{random.choice(adjectives)}_{random.choice(nouns)}_{number}"

def generate_random_password():
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choices(chars, k=12))

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ===================== মেনু =====================
def get_main_menu():
    """মেইন মেনু - ৬টি বাটন"""
    keyboard = [
        [KeyboardButton("👤 ACCOUNT")],
        [KeyboardButton("📋 WORK")],
        [KeyboardButton("💰 BALANCE")],
        [KeyboardButton("🏧 WITHDRAW")],
        [KeyboardButton("👥 REFER")],
        [KeyboardButton("❓ HELP")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_work_menu():
    """WORK সাব-মেনু"""
    keyboard = [
        [KeyboardButton("📱 INSTA 2FA")],
        [KeyboardButton("🔙 MAIN MENU")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_insta_2fa_menu():
    """INSTA 2FA এর ভিতরের মেনু"""
    keyboard = [
        [KeyboardButton("🔑 2FA KEY দিন")],
        [KeyboardButton("❌ CANCEL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_withdraw_menu():
    """WITHDRAW সাব-মেনু"""
    keyboard = [
        [KeyboardButton("💳 BKASH")],
        [KeyboardButton("📱 NAGAD")],
        [KeyboardButton("💰 BINANCE")],
        [KeyboardButton("❌ CANCEL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_refer_menu():
    """REFER মেনু"""
    keyboard = [
        [KeyboardButton("❌ CANCEL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_help_menu():
    """HELP মেনু"""
    keyboard = [
        [KeyboardButton("❌ CANCEL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===================== স্টার্ট =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        
        # রেফার চেক
        if context.args and context.args[0].startswith('ref_'):
            referrer_id = context.args[0].replace('ref_', '')
            try:
                referrer_id = int(referrer_id)
                if referrer_id != user.id:
                    sheet = context.bot_data.get('sheet')
                    if sheet:
                        if update_balance(sheet, referrer_id, 10):
                            try:
                                await context.bot.send_message(
                                    chat_id=referrer_id,
                                    text=f"🎉 **অভিনন্দন!**\n\nআপনার রেফার লিংক ব্যবহার করেছেন {user.first_name}!\n\n💰 আপনার ব্যালেন্সে **+১০ টাকা** যোগ করা হয়েছে!"
                                )
                            except:
                                pass
            except:
                pass
        
        sheet = context.bot_data.get('sheet')
        if not sheet:
            sheet = setup_google_sheets()
            context.bot_data['sheet'] = sheet
        
        await update.message.reply_text(
            f"👋 **স্বাগতম {user.first_name}!**\n\n"
            f"📌 নিচের ৬টি অপশন থেকে বেছে নিন:\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 ACCOUNT - আপনার প্রোফাইল\n"
            f"📋 WORK - অ্যাকাউন্ট তৈরি করুন\n"
            f"💰 BALANCE - ব্যালেন্স দেখুন\n"
            f"🏧 WITHDRAW - টাকা তুলুন\n"
            f"👥 REFER - বন্ধুদের ডাকুন\n"
            f"❓ HELP - সাহায্য নিন\n"
            f"━━━━━━━━━━━━━━━━━━━━━",
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
        return MAIN_MENU
    except Exception as e:
        logger.error(f"Start error: {e}")
        return MAIN_MENU

# ===================== টেক্সট হ্যান্ডলার (মেইন) =====================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        user_id = update.effective_user.id
        sheet = context.bot_data.get('sheet')
        user = update.effective_user
        
        # ========== 1. ACCOUNT ==========
        if text == "👤 ACCOUNT":
            accounts = get_user_accounts(sheet, user_id)
            balance = get_user_balance(sheet, user_id)
            
            msg = f"👤 **আপনার প্রোফাইল**\n\n"
            msg += f"🆔 **ইউজার আইডি:** `{user_id}`\n"
            msg += f"👤 **ইউজারনেম:** @{user.username or 'N/A'}\n"
            msg += f"📛 **নাম:** {user.first_name}\n\n"
            msg += f"💰 **ব্যালেন্স:** {balance} টাকা\n"
            msg += f"📊 **মোট অ্যাকাউন্ট:** {len(accounts)}\n\n"
            
            if accounts:
                msg += "📋 **আপনার অ্যাকাউন্টসমূহ:**\n\n"
                for acc in accounts[-5:]:
                    msg += f"📧 {acc.get('Instagram Email', 'N/A')}\n"
                    msg += f"🔑 {acc.get('Instagram Password', 'N/A')}\n"
                    msg += f"📊 {acc.get('Status', 'Pending')}\n━━━━━━━\n"
            else:
                msg += "❌ এখনো কোনো অ্যাকাউন্ট নেই।"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
            return MAIN_MENU
        
        # ========== 2. WORK ==========
        elif text == "📋 WORK":
            await update.message.reply_text(
                "📋 **WORK মেনু**\n\n"
                "🔹 ইনস্টাগ্রাম অ্যাকাউন্ট তৈরি করতে **INSTA 2FA** বাটনে ক্লিক করুন।\n\n"
                "📌 প্রতিটি অ্যাকাউন্ট তৈরিতে **১০ টাকা** পাবেন!",
                reply_markup=get_work_menu()
            )
            return WORK_MENU
        
        # ========== 3. BALANCE ==========
        elif text == "💰 BALANCE":
            balance = get_user_balance(sheet, user_id)
            accounts = get_user_accounts(sheet, user_id)
            
            msg = f"💰 **আপনার ব্যালেন্স**\n\n"
            msg += f"📊 মোট ব্যালেন্স: **{balance} টাকা**\n"
            msg += f"📋 মোট অ্যাকাউন্ট: {len(accounts)}\n\n"
            msg += f"📌 প্রতি অ্যাকাউন্টে **১০ টাকা** করে পাবেন!\n"
            msg += f"👥 প্রতি রেফারে **১০ টাকা** বোনাস!\n\n"
            msg += f"আরও কাজ করুন এবং ব্যালেন্স বাড়ান! 💪"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
            return MAIN_MENU
        
        # ========== 4. WITHDRAW ==========
        elif text == "🏧 WITHDRAW":
            balance = get_user_balance(sheet, user_id)
            
            if balance < 100:
                await update.message.reply_text(
                    f"❌ **ব্যালেন্স কম!**\n\n"
                    f"আপনার ব্যালেন্স: {balance} টাকা\n"
                    f"মিনিমাম উইথড্র: ১০০ টাকা\n\n"
                    f"আরও কাজ করুন এবং ব্যালেন্স বাড়ান! 💪"
                )
                return MAIN_MENU
            
            await update.message.reply_text(
                f"🏧 **উইথড্র**\n\n"
                f"💰 আপনার ব্যালেন্স: {balance} টাকা\n"
                f"⚠️ মিনিমাম: ১০০ টাকা\n"
                f"💸 চার্জ: ৫ টাকা\n"
                f"📊 পাবেন: ৯৫ টাকা\n\n"
                f"পছন্দের মেথড বেছে নিন:",
                reply_markup=get_withdraw_menu()
            )
            return WITHDRAW_MENU
        
        # ========== 5. REFER ==========
        elif text == "👥 REFER":
            refer_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
            
            await update.message.reply_text(
                f"👥 **রেফার**\n\n"
                f"আপনার রেফার লিংক:\n`{refer_link}`\n\n"
                f"🎁 প্রতি রেফারে **১০ টাকা** বোনাস!\n\n"
                f"লিংক শেয়ার করুন এবং বোনাস পান! 🚀\n\n"
                f"📤 লিংক কপি করে বন্ধুদের পাঠান।",
                parse_mode='Markdown',
                reply_markup=get_refer_menu()
            )
            return REFER_MENU
        
        # ========== 6. HELP ==========
        elif text == "❓ HELP":
            admin_contact = os.environ.get('ADMIN_CONTACT', '@EarnerSupport')
            
            await update.message.reply_text(
                f"❓ **সাহায্য**\n\n"
                f"📌 **কীভাবে কাজ করবেন:**\n"
                f"1️⃣ WORK → INSTA 2FA ক্লিক করুন\n"
                f"2️⃣ ইউজারনেম ও পাসওয়ার্ড পাবেন\n"
                f"3️⃣ 2FA KEY দিন বাটনে ক্লিক করুন\n"
                f"4️⃣ 2FA কোড দিন\n"
                f"5️⃣ অ্যাকাউন্ট কমপ্লিট!\n\n"
                f"💰 **আয়ের উপায়:**\n"
                f"• প্রতি অ্যাকাউন্টে **১০ টাকা**\n"
                f"• প্রতি রেফারে **১০ টাকা** বোনাস\n\n"
                f"🏧 **উইথড্র:**\n"
                f"• মিনিমাম: ১০০ টাকা\n"
                f"• চার্জ: ৫ টাকা\n\n"
                f"📞 **এডমিন কন্টাক্ট:**\n{admin_contact}",
                parse_mode='Markdown',
                reply_markup=get_help_menu()
            )
            return HELP_MENU
        
        # ========== CANCEL ==========
        elif text == "❌ CANCEL":
            await update.message.reply_text(
                "🔙 **মেইন মেনুতে ফিরে আসা হয়েছে!**",
                reply_markup=get_main_menu()
            )
            return MAIN_MENU
        
        # ========== MAIN MENU ==========
        elif text == "🔙 MAIN MENU":
            await update.message.reply_text(
                "🔙 **মেইন মেনুতে ফিরে এসেছেন!**",
                reply_markup=get_main_menu()
            )
            return MAIN_MENU
        
        # ========== INSTA 2FA ==========
        elif text == "📱 INSTA 2FA":
            username = generate_random_username()
            password = generate_random_password()
            context.user_data['temp_username'] = username
            context.user_data['temp_password'] = password
            
            if sheet:
                save_to_sheet(sheet, user_id, user.username or "Unknown", username, password, status="2FA Pending")
            
            await update.message.reply_text(
                f"🎯 **আপনার অ্যাকাউন্ট তৈরি হয়েছে!**\n\n"
                f"👤 ইউজারনেম: `{username}`\n"
                f"🔑 পাসওয়ার্ড: `{password}`\n\n"
                f"🔐 এখন **2FA KEY দিন** বাটনে ক্লিক করে আপনার 2FA কোড দিন।\n\n"
                f"অথবা **CANCEL** বাটনে ক্লিক করে বাতিল করুন।",
                parse_mode='Markdown',
                reply_markup=get_insta_2fa_menu()
            )
            return WAITING_2FA
        
        # ========== 2FA KEY দিন ==========
        elif text == "🔑 2FA KEY দিন":
            await update.message.reply_text(
                "🔐 **আপনার 2FA কোড লিখুন:**\n\n"
                "উদাহরণ: `123456`\n\n"
                "📌 2FA কোডটি আপনার Google Authenticator অ্যাপ থেকে নিন।"
            )
            return WAITING_2FA
        
        # ========== উইথড্র মেথড ==========
        elif text in ["💳 BKASH", "📱 NAGAD", "💰 BINANCE"]:
            method = text.replace("💳 ", "").replace("📱 ", "").replace("💰 ", "")
            context.user_data['withdraw_method'] = method
            await update.message.reply_text(
                f"📤 **উইথড্র ({method})**\n\n"
                f"আপনার {method} অ্যাকাউন্ট আইডি লিখুন:\n\n"
                f"📌 উদাহরণ: `017XXXXXXXX` বা `example@binance.com`"
            )
            return WAITING_WITHDRAW
        
        else:
            await update.message.reply_text(
                "❓ **অজানা কমান্ড!**\n\n"
                "নিচের বাটনগুলো ব্যবহার করুন:",
                reply_markup=get_main_menu()
            )
            return MAIN_MENU
            
    except Exception as e:
        logger.error(f"Text error: {e}")
        await update.message.reply_text("⚠️ কিছু সমস্যা হয়েছে।")
        return MAIN_MENU

# ===================== 2FA হ্যান্ডলার =====================
async def twofa_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        twofa_code = update.message.text.strip()
        user_id = update.effective_user.id
        sheet = context.bot_data.get('sheet')
        
        if sheet:
            try:
                records = get_all_sheet_data(sheet)
                for i, row in enumerate(records, start=2):
                    if str(row.get('User ID')) == str(user_id) and row.get('Status') == '2FA Pending':
                        sheet.update_cell(i, 6, twofa_code)
                        sheet.update_cell(i, 7, 'Completed')
                        # ব্যালেন্স আপডেট
                        update_balance(sheet, user_id, 10)
                        break
            except:
                pass
        
        await update.message.reply_text(
            f"🎉 **অভিনন্দন!**\n\n"
            f"✅ আপনার অ্যাকাউন্ট সম্পূর্ণ হয়েছে!\n"
            f"💰 আপনার ব্যালেন্সে **+১০ টাকা** যোগ করা হয়েছে!\n\n"
            f"আরও অ্যাকাউন্ট তৈরি করতে **WORK** বাটনে ক্লিক করুন।",
            reply_markup=get_main_menu()
        )
        return MAIN_MENU
    except Exception as e:
        logger.error(f"2FA error: {e}")
        return WAITING_2FA

# ===================== উইথড্র হ্যান্ডলার =====================
async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
                "95 Taka",
                "Pending",
                str(get_user_balance(sheet, user_id) - 100)
            ])
            update_balance(sheet, user_id, -100)
        
        await update.message.reply_text(
            f"✅ **উইথড্র রিকোয়েস্ট পাঠানো হয়েছে!**\n\n"
            f"📤 মেথড: {method}\n"
            f"🆔 অ্যাকাউন্ট: `{account_id}`\n"
            f"💰 উইথড্র: ১০০ টাকা\n"
            f"💸 চার্জ: ৫ টাকা\n"
            f"📊 পাবেন: ৯৫ টাকা\n\n"
            f"আমাদের টিম আপনার রিকোয়েস্ট প্রসেস করবে।",
            parse_mode='Markdown',
            reply_markup=get_main_menu()
        )
        return MAIN_MENU
    except Exception as e:
        logger.error(f"Withdraw error: {e}")
        return WITHDRAW_MENU

# ===================== এডমিন হ্যান্ডলার =====================
async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        user_id = update.effective_user.id
        sheet = context.bot_data.get('sheet')
        
        if not is_admin(user_id):
            await update.message.reply_text("⛔ আপনি এডমিন নন!")
            return MAIN_MENU
        
        if text == "📊 ডেটাবেস ভিউ":
            try:
                records = get_all_sheet_data(sheet)
                if records:
                    msg = "📊 **ডেটাবেস ভিউ (শেষ ২০টি)**\n\n"
                    for i, row in enumerate(records[-20:], 1):
                        msg += f"{i}. 📧 {row.get('Instagram Email', 'N/A')}\n"
                        msg += f"   🔑 {row.get('Instagram Password', 'N/A')}\n"
                        msg += f"   📊 {row.get('Status', 'Pending')}\n"
                        msg += f"   💰 {row.get('Balance', 0)}\n━━━━━━━\n"
                    await update.message.reply_text(msg[:4000], parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ ডেটাবেস খালি!")
            except Exception as e:
                await update.message.reply_text(f"⚠️ এরর: {str(e)[:200]}")
        
        elif text == "📋 সব ডেটা কপি":
            try:
                records = get_all_sheet_data(sheet)
                if records:
                    csv_text = "Timestamp,User ID,Username,Email,Password,2FA,Status,Balance\n"
                    for row in records[:100]:
                        csv_text += f"{row.get('Timestamp', 'N/A')},{row.get('User ID', 'N/A')},{row.get('Username', 'N/A')},{row.get('Instagram Email', 'N/A')},{row.get('Instagram Password', 'N/A')},{row.get('2FA Code', 'N/A')},{row.get('Status', 'N/A')},{row.get('Balance', 0)}\n"
                    await update.message.reply_text(f"📄 **CSV ডেটা:**\n\n```\n{csv_text[:3900]}\n```", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ ডেটাবেস খালি!")
            except Exception as e:
                await update.message.reply_text(f"⚠️ এরর: {str(e)[:200]}")
        
        elif text == "📈 স্ট্যাটিস্টিক্স":
            try:
                records = get_all_sheet_data(sheet)
                total = len(records)
                completed = len([r for r in records if r.get('Status') == 'Completed'])
                pending = len([r for r in records if r.get('Status') == 'Pending'])
                twofa = len([r for r in records if '2FA' in str(r.get('Status', ''))])
                unique_users = len(set([r.get('User ID') for r in records if r.get('User ID')]))
                msg = f"📈 **স্ট্যাটিস্টিক্স**\n\n📊 মোট: {total}\n✅ কমপ্লিট: {completed}\n⏳ পেন্ডিং: {pending}\n🔐 2FA: {twofa}\n👥 ইউজার: {unique_users}"
                await update.message.reply_text(msg, parse_mode='Markdown')
            except Exception as e:
                await update.message.reply_text(f"⚠️ এরর: {str(e)[:200]}")
        
        elif text == "👥 ইউজার লিস্ট":
            try:
                records = get_all_sheet_data(sheet)
                users = {}
                for row in records:
                    uid = row.get('User ID')
                    if uid:
                        if uid not in users:
                            users[uid] = {'count': 1, 'balance': int(row.get('Balance', 0))}
                        else:
                            users[uid]['count'] += 1
                if users:
                    msg = "👥 **ইউজার লিস্ট**\n\n"
                    for uid, data in list(users.items())[:20]:
                        msg += f"🆔 {uid}\n📊 অ্যাকাউন্ট: {data['count']}\n💰 ব্যালেন্স: {data['balance']}\n━━━━━━━\n"
                    await update.message.reply_text(msg[:4000], parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ কোনো ইউজার নেই!")
            except Exception as e:
                await update.message.reply_text(f"⚠️ এরর: {str(e)[:200]}")
        
        elif text == "🗑️ ডেটা ডিলিট":
            keyboard = [
                [InlineKeyboardButton("✅ হ্যাঁ", callback_data="confirm_delete")],
                [InlineKeyboardButton("❌ না", callback_data="cancel_delete")]
            ]
            await update.message.reply_text("⚠️ **পুরো ডেটাবেস ডিলিট করবেন?**\n\nএই কাজ অপরিবর্তনীয়!", reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif text == "🔙 ইউজার মেনু":
            await update.message.reply_text(
                "🔙 **ইউজার মেনুতে ফিরে এসেছেন!**",
                reply_markup=get_main_menu()
            )
            return MAIN_MENU
        
        return WORK_MENU
    except Exception as e:
        logger.error(f"Admin error: {e}")
        return WORK_MENU

# ===================== ইনলাইন বাটন =====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "confirm_delete":
            sheet = context.bot_data.get('sheet')
            if sheet:
                try:
                    sheet.clear()
                    headers = ["Timestamp", "User ID", "Username", "Instagram Email", "Instagram Password", "2FA Code", "Status", "Balance"]
                    sheet.append_row(headers)
                    await query.edit_message_text("🗑️ **ডেটাবেস ডিলিট করা হয়েছে!**")
                except:
                    await query.edit_message_text("⚠️ ডিলিট করতে পারেনি!")
            return WORK_MENU
        
        elif query.data == "cancel_delete":
            await query.edit_message_text("✅ ডিলিট বাতিল!")
            return WORK_MENU
        
        return MAIN_MENU
    except Exception as e:
        logger.error(f"Button error: {e}")
        return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ বাতিল করা হয়েছে।\n\n"
        "🔙 **মেইন মেনুতে ফিরে আসুন:** /start",
        reply_markup=get_main_menu()
    )
    return MAIN_MENU

# ===================== মেইন =====================
def main():
    try:
        sheet = setup_google_sheets()
        app = Application.builder().token(TOKEN).build()
        app.bot_data['sheet'] = sheet
        
        conv = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                MAIN_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
                ],
                WORK_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
                ],
                WAITING_2FA: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, twofa_handler)
                ],
                WAITING_DONE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
                ],
                WITHDRAW_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
                ],
                WAITING_WITHDRAW: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_handler)
                ],
                REFER_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
                ],
                HELP_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
                ],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )
        
        app.add_handler(conv)
        app.add_handler(CallbackQueryHandler(button_handler))
        
        print("🤖 বট চালু!")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"❌ বট চালু করতে পারেনি: {e}")

if __name__ == '__main__':
    main()
