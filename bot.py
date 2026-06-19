import os
import logging
import json
import random
import string
import pyotp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes

TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = []

admin_id_str = os.environ.get('ADMIN_ID', '')
if admin_id_str:
    try:
        ADMIN_IDS = [int(x.strip()) for x in admin_id_str.split(',') if x.strip()]
    except:
        ADMIN_IDS = []

# ============= ডেটা ফাইল =============
DATA_FILE = "data.json"

def load_data():
    """JSON ফাইল থেকে ডেটা লোড করে"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"users": {}, "accounts": [], "next_id": 1}
    return {"users": {}, "accounts": [], "next_id": 1}

def save_data(data):
    """ডেটা JSON ফাইলে সেভ করে"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ============= কনভার্সেশন স্টেট =============
MAIN_MENU, WORK_MENU, WAITING_2FA_SECRET, WAITING_DONE, WAITING_WITHDRAW, WITHDRAW_MENU, REFER_MENU, HELP_MENU, ADMIN_MENU, ADMIN_ADD_BALANCE = range(10)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== ডেটাবেস ফাংশন =====================
def get_user_balance(user_id):
    data = load_data()
    user_data = data["users"].get(str(user_id), {})
    return user_data.get("balance", 0)

def update_user_balance(user_id, amount):
    data = load_data()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"balance": 0, "accounts": []}
    data["users"][uid]["balance"] = data["users"][uid].get("balance", 0) + amount
    save_data(data)
    return True

def get_user_accounts(user_id):
    data = load_data()
    uid = str(user_id)
    if uid in data["users"]:
        return data["users"][uid].get("accounts", [])
    return []

def add_account(user_id, username, password, secret="", code="", status="Pending"):
    data = load_data()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"balance": 0, "accounts": []}
    
    account = {
        "id": data["next_id"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": user_id,
        "username": username,
        "password": password,
        "secret": secret,
        "code": code,
        "status": status
    }
    data["users"][uid]["accounts"].append(account)
    data["next_id"] += 1
    save_data(data)
    return account

def update_account_status(user_id, account_id, new_status):
    data = load_data()
    uid = str(user_id)
    if uid in data["users"]:
        for acc in data["users"][uid]["accounts"]:
            if acc["id"] == account_id:
                acc["status"] = new_status
                save_data(data)
                return True
    return False

def get_pending_accounts():
    data = load_data()
    pending = []
    for uid, user_data in data["users"].items():
        for acc in user_data.get("accounts", []):
            if acc.get("status") == "Pending Approval":
                pending.append(acc)
    return pending

def get_all_users():
    data = load_data()
    users = {}
    for uid, user_data in data["users"].items():
        users[uid] = {
            "balance": user_data.get("balance", 0),
            "count": len(user_data.get("accounts", []))
        }
    return users

def get_all_accounts():
    data = load_data()
    accounts = []
    for uid, user_data in data["users"].items():
        for acc in user_data.get("accounts", []):
            accounts.append(acc)
    return accounts

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ===================== 2FA জেনারেটর =====================
def generate_2fa_code(secret):
    try:
        if not secret or len(secret) < 16:
            return None
        totp = pyotp.TOTP(secret)
        return totp.now()
    except Exception as e:
        logger.error(f"2FA generate error: {e}")
        return None

# ===================== র্যান্ডম জেনারেটর =====================
def generate_random_username():
    adjectives = ["cool", "happy", "super", "great", "mega", "ultra", "pro", "star", "king", "queen"]
    nouns = ["user", "insta", "gram", "snap", "chat", "wave", "pulse", "nova", "zen", "vibe"]
    number = ''.join(random.choices(string.digits, k=4))
    return f"{random.choice(adjectives)}_{random.choice(nouns)}_{number}"

def generate_random_password():
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choices(chars, k=12))

# ===================== মেনু =====================
def get_main_menu():
    keyboard = [
        [KeyboardButton("👤 ACCOUNT"), KeyboardButton("💰 BALANCE")],
        [KeyboardButton("📋 WORK"), KeyboardButton("🏧 WITHDRAW")],
        [KeyboardButton("👥 REFER"), KeyboardButton("❓ HELP")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_main_menu_admin():
    keyboard = [
        [KeyboardButton("👤 ACCOUNT"), KeyboardButton("💰 BALANCE")],
        [KeyboardButton("📋 WORK"), KeyboardButton("🏧 WITHDRAW")],
        [KeyboardButton("👥 REFER"), KeyboardButton("❓ HELP")],
        [KeyboardButton("👑 এডমিন প্যানেল")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_work_menu():
    keyboard = [
        [KeyboardButton("📱 INSTA 2FA")],
        [KeyboardButton("❌ CANCEL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_insta_2fa_menu():
    keyboard = [
        [KeyboardButton("🔑 সিক্রেট KEY দিন")],
        [KeyboardButton("❌ CANCEL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_done_menu():
    keyboard = [
        [KeyboardButton("✅ DONE")],
        [KeyboardButton("❌ CANCEL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_withdraw_menu():
    keyboard = [
        [KeyboardButton("💳 BKASH"), KeyboardButton("📱 NAGAD")],
        [KeyboardButton("💰 BINANCE")],
        [KeyboardButton("❌ CANCEL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_refer_menu():
    keyboard = [
        [KeyboardButton("❌ CANCEL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_help_menu():
    keyboard = [
        [KeyboardButton("❌ CANCEL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_menu():
    keyboard = [
        [KeyboardButton("📊 ডেটাবেস ভিউ"), KeyboardButton("📋 সব ডেটা কপি")],
        [KeyboardButton("📈 স্ট্যাটিস্টিক্স"), KeyboardButton("👥 ইউজার লিস্ট")],
        [KeyboardButton("💰 টাকা যোগ করুন"), KeyboardButton("⏳ পেন্ডিং")],
        [KeyboardButton("🗑️ ডেটা ডিলিট")],
        [KeyboardButton("❌ CANCEL")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===================== মেইন মেনুতে ফেরত =====================
async def go_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_admin(user_id):
        await update.message.reply_text(
            "🔙 **মেইন মেনুতে ফিরে এসেছেন!**",
            reply_markup=get_main_menu_admin()
        )
    else:
        await update.message.reply_text(
            "🔙 **মেইন মেনুতে ফিরে এসেছেন!**",
            reply_markup=get_main_menu()
        )
    return MAIN_MENU

# ===================== এডমিন নোটিফিকেশন =====================
async def notify_admin(context, user_id, username, email, password):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🆕 **নতুন অ্যাকাউন্ট জমা পড়েছে!**\n\n"
                f"👤 ইউজার আইডি: `{user_id}`\n"
                f"👤 ইউজারনেম: @{username or 'N/A'}\n"
                f"📧 ইমেইল: `{email}`\n"
                f"🔑 পাসওয়ার্ড: `{password}`\n\n"
                f"📌 এডমিন প্যানেলে গিয়ে APPROVE করুন।",
                parse_mode='Markdown'
            )
        except:
            pass

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
                    if update_user_balance(referrer_id, 10):
                        try:
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=f"🎉 **অভিনন্দন!**\n\nআপনার রেফার লিংক ব্যবহার করেছেন {user.first_name}!\n\n💰 আপনার ব্যালেন্সে **+১০ টাকা** যোগ করা হয়েছে!"
                            )
                        except:
                            pass
            except:
                pass
        
        if is_admin(user.id):
            await update.message.reply_text(
                f"👋 **স্বাগতম এডমিন {user.first_name}!**\n\n"
                f"📌 নিচের অপশন থেকে বেছে নিন:",
                parse_mode='Markdown',
                reply_markup=get_main_menu_admin()
            )
        else:
            await update.message.reply_text(
                f"👋 **স্বাগতম {user.first_name}!**\n\n"
                f"📌 নিচের ৬টি অপশন থেকে বেছে নিন:",
                parse_mode='Markdown',
                reply_markup=get_main_menu()
            )
        return MAIN_MENU
    except Exception as e:
        logger.error(f"Start error: {e}")
        return MAIN_MENU

# ===================== টেক্সট হ্যান্ডলার =====================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        user_id = update.effective_user.id
        user = update.effective_user
        
        # ===== CANCEL =====
        if text == "❌ CANCEL":
            return await go_to_main_menu(update, context)
        
        # ===== এডমিন প্যানেল =====
        if text == "👑 এডমিন প্যানেল":
            if is_admin(user_id):
                await update.message.reply_text(
                    "👑 **এডমিন প্যানেল**\n\nনিচের অপশন থেকে বেছে নিন:",
                    parse_mode='Markdown',
                    reply_markup=get_admin_menu()
                )
                return ADMIN_MENU
            else:
                await update.message.reply_text("⛔ আপনি এডমিন নন!")
                return MAIN_MENU
        
        # ===== এডমিন কমান্ড =====
        if is_admin(user_id):
            if text == "📊 ডেটাবেস ভিউ":
                return await admin_data_view(update, context)
            elif text == "📋 সব ডেটা কপি":
                return await admin_copy_data(update, context)
            elif text == "📈 স্ট্যাটিস্টিক্স":
                return await admin_stats(update, context)
            elif text == "👥 ইউজার লিস্ট":
                return await admin_user_list(update, context)
            elif text == "💰 টাকা যোগ করুন":
                await update.message.reply_text(
                    "💰 **টাকা যোগ করুন**\n\n"
                    "ফরম্যাট: `USER_ID AMOUNT`\n\n"
                    "উদাহরণ: `123456789 50`\n\n"
                    "❌ CANCEL - বাতিল করুন"
                )
                return ADMIN_ADD_BALANCE
            elif text == "⏳ পেন্ডিং":
                return await admin_pending(update, context)
            elif text == "🗑️ ডেটা ডিলিট":
                return await admin_delete_data(update, context)
        
        # ===== ACCOUNT =====
        if text == "👤 ACCOUNT":
            accounts = get_user_accounts(user_id)
            balance = get_user_balance(user_id)
            
            msg = f"👤 **আপনার প্রোফাইল**\n\n"
            msg += f"🆔 **ইউজার আইডি:** `{user_id}`\n"
            msg += f"👤 **ইউজারনেম:** @{user.username or 'N/A'}\n"
            msg += f"📛 **নাম:** {user.first_name}\n\n"
            msg += f"💰 **ব্যালেন্স:** {balance} টাকা\n"
            msg += f"📊 **মোট অ্যাকাউন্ট:** {len(accounts)}\n\n"
            
            if accounts:
                msg += "📋 **আপনার অ্যাকাউন্টসমূহ:**\n\n"
                for acc in accounts[-5:]:
                    msg += f"📧 {acc.get('username', 'N/A')}\n"
                    msg += f"🔑 {acc.get('password', 'N/A')}\n"
                    msg += f"📊 {acc.get('status', 'Pending')}\n━━━━━━━\n"
            else:
                msg += "❌ এখনো কোনো অ্যাকাউন্ট নেই।"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
            return MAIN_MENU
        
        # ===== WORK =====
        elif text == "📋 WORK":
            await update.message.reply_text(
                "📋 **WORK মেনু**\n\n"
                "🔹 ইনস্টাগ্রাম অ্যাকাউন্ট তৈরি করতে **INSTA 2FA** বাটনে ক্লিক করুন।",
                reply_markup=get_work_menu()
            )
            return WORK_MENU
        
        # ===== BALANCE =====
        elif text == "💰 BALANCE":
            balance = get_user_balance(user_id)
            accounts = get_user_accounts(user_id)
            
            msg = f"💰 **আপনার ব্যালেন্স**\n\n"
            msg += f"📊 মোট ব্যালেন্স: **{balance} টাকা**\n"
            msg += f"📋 মোট অ্যাকাউন্ট: {len(accounts)}\n\n"
            msg += f"📌 প্রতি অ্যাকাউন্টে **১০ টাকা** করে পাবেন!\n"
            msg += f"👥 প্রতি রেফারে **১০ টাকা** বোনাস!\n\n"
            msg += f"আরও কাজ করুন এবং ব্যালেন্স বাড়ান! 💪"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
            return MAIN_MENU
        
        # ===== WITHDRAW =====
        elif text == "🏧 WITHDRAW":
            balance = get_user_balance(user_id)
            
            if balance < 100:
                await update.message.reply_text(
                    f"❌ **ব্যালেন্স কম!**\n\n"
                    f"আপনার ব্যালেন্স: {balance} টাকা\n"
                    f"মিনিমাম উইথড্র: ১০০ টাকা"
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
        
        # ===== REFER =====
        elif text == "👥 REFER":
            refer_link = f"https://t.me/{context.bot.username}?start=ref_{user_id}"
            
            await update.message.reply_text(
                f"👥 **রেফার**\n\n"
                f"আপনার রেফার লিংক:\n`{refer_link}`\n\n"
                f"🎁 প্রতি রেফারে **১০ টাকা** বোনাস!",
                parse_mode='Markdown',
                reply_markup=get_refer_menu()
            )
            return REFER_MENU
        
        # ===== HELP =====
        elif text == "❓ HELP":
            admin_contact = os.environ.get('ADMIN_CONTACT', '@EarnerSupport')
            
            await update.message.reply_text(
                f"❓ **সাহায্য**\n\n"
                f"📌 **কীভাবে কাজ করবেন:**\n"
                f"1️⃣ WORK → INSTA 2FA\n"
                f"2️⃣ ইউজারনেম ও পাসওয়ার্ড পাবেন\n"
                f"3️⃣ সিক্রেট KEY দিন\n"
                f"4️⃣ সিক্রেট কী দিন → অটো 2FA কোড পাবেন\n"
                f"5️⃣ DONE ক্লিক করুন\n"
                f"6️⃣ এডমিন APPROVE করলে ব্যালেন্স পাবেন\n\n"
                f"💰 **আয়ের উপায়:**\n"
                f"• প্রতি অ্যাকাউন্টে **১০ টাকা**\n"
                f"• প্রতি রেফারে **১০ টাকা**\n\n"
                f"🏧 **উইথড্র:**\n"
                f"• মিনিমাম: ১০০ টাকা\n"
                f"• চার্জ: ৫ টাকা\n\n"
                f"📞 **এডমিন:** {admin_contact}",
                parse_mode='Markdown',
                reply_markup=get_help_menu()
            )
            return HELP_MENU
        
        # ===== INSTA 2FA =====
        elif text == "📱 INSTA 2FA":
            username = generate_random_username()
            password = generate_random_password()
            context.user_data['temp_username'] = username
            context.user_data['temp_password'] = password
            
            add_account(user_id, username, password, status="Waiting for Secret")
            
            await update.message.reply_text(
                f"🎯 **আপনার অ্যাকাউন্ট তৈরি হয়েছে!**\n\n"
                f"👤 ইউজারনেম: `{username}`\n"
                f"🔑 পাসওয়ার্ড: `{password}`\n\n"
                f"🔐 এখন **সিক্রেট KEY দিন** বাটনে ক্লিক করুন।",
                parse_mode='Markdown',
                reply_markup=get_insta_2fa_menu()
            )
            return WAITING_2FA_SECRET
        
        # ===== সিক্রেট KEY দিন =====
        elif text == "🔑 সিক্রেট KEY দিন":
            await update.message.reply_text(
                "🔐 **আপনার Google Authenticator সিক্রেট কী দিন:**\n\n"
                "উদাহরণ: `JBSWY3DPEHPK3PXP`\n\n"
                "❌ CANCEL - বাতিল করুন"
            )
            return WAITING_2FA_SECRET
        
        # ===== DONE =====
        elif text == "✅ DONE":
            accounts = get_user_accounts(user_id)
            for acc in accounts:
                if acc.get('status') == '2FA Generated':
                    acc['status'] = 'Pending Approval'
                    # এডমিনকে নোটিফিকেশন
                    await notify_admin(
                        context,
                        user_id,
                        user.username or "Unknown",
                        acc.get('username', 'N/A'),
                        acc.get('password', 'N/A')
                    )
                    break
            
            menu = get_main_menu_admin() if is_admin(user_id) else get_main_menu()
            await update.message.reply_text(
                f"✅ **অ্যাকাউন্ট জমা দেওয়া হয়েছে!**\n\n"
                f"⏳ **এডমিন APPROVE করলে ব্যালেন্স যুক্ত হবে।**\n\n"
                f"📌 এডমিনকে নোটিফিকেশন পাঠানো হয়েছে।",
                reply_markup=menu
            )
            return MAIN_MENU
        
        # ===== উইথড্র মেথড =====
        elif text in ["💳 BKASH", "📱 NAGAD", "💰 BINANCE"]:
            method = text.replace("💳 ", "").replace("📱 ", "").replace("💰 ", "")
            context.user_data['withdraw_method'] = method
            await update.message.reply_text(
                f"📤 **উইথড্র ({method})**\n\n"
                f"আপনার {method} অ্যাকাউন্ট আইডি লিখুন:\n\n"
                f"❌ CANCEL - বাতিল করুন"
            )
            return WAITING_WITHDRAW
        
        else:
            menu = get_main_menu_admin() if is_admin(user_id) else get_main_menu()
            await update.message.reply_text(
                "❓ **অজানা কমান্ড!**\n\nনিচের বাটনগুলো ব্যবহার করুন:",
                reply_markup=menu
            )
            return MAIN_MENU
            
    except Exception as e:
        logger.error(f"Text error: {e}")
        await update.message.reply_text("⚠️ কিছু সমস্যা হয়েছে।")
        return MAIN_MENU

# ===================== 2FA সিক্রেট হ্যান্ডলার =====================
async def twofa_secret_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        secret = update.message.text.strip().upper()
        user_id = update.effective_user.id
        
        if len(secret) < 16:
            await update.message.reply_text(
                "❌ **ভুল সিক্রেট কী!**\n\nসিক্রেট কী কমপক্ষে ১৬ অক্ষরের হতে হবে।"
            )
            return WAITING_2FA_SECRET
        
        otp_code = generate_2fa_code(secret)
        
        if otp_code:
            accounts = get_user_accounts(user_id)
            for acc in accounts:
                if acc.get('status') == 'Waiting for Secret':
                    acc['secret'] = secret
                    acc['code'] = otp_code
                    acc['status'] = '2FA Generated'
                    break
            
            await update.message.reply_text(
                f"✅ **2FA কোড জেনারেট করা হয়েছে!**\n\n"
                f"🔐 সিক্রেট কী: `{secret}`\n"
                f"🔑 **আপনার 2FA কোড: `{otp_code}`**\n\n"
                f"⏳ এই কোড ৩০ সেকেন্ডের জন্য বৈধ।\n\n"
                f"📌 অ্যাকাউন্ট খোলা শেষ হলে **DONE** ক্লিক করুন।",
                parse_mode='Markdown',
                reply_markup=get_done_menu()
            )
            return WAITING_DONE
        else:
            await update.message.reply_text(
                "❌ **সিক্রেট কী থেকে কোড জেনারেট করা যায়নি!**"
            )
            return WAITING_2FA_SECRET
    except Exception as e:
        logger.error(f"Secret handler error: {e}")
        await update.message.reply_text("⚠️ কিছু সমস্যা হয়েছে।")
        return WAITING_2FA_SECRET

# ===================== উইথড্র হ্যান্ডলার =====================
async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        account_id = update.message.text.strip()
        method = context.user_data.get('withdraw_method', 'Unknown')
        user_id = update.effective_user.id
        
        balance = get_user_balance(user_id)
        if balance < 100:
            await update.message.reply_text("❌ ব্যালেন্স কম!")
            return MAIN_MENU
        
        update_user_balance(user_id, -100)
        
        menu = get_main_menu_admin() if is_admin(user_id) else get_main_menu()
        await update.message.reply_text(
            f"✅ **উইথড্র রিকোয়েস্ট পাঠানো হয়েছে!**\n\n"
            f"📤 মেথড: {method}\n"
            f"🆔 অ্যাকাউন্ট: `{account_id}`\n"
            f"💰 উইথড্র: ১০০ টাকা\n"
            f"💸 চার্জ: ৫ টাকা\n"
            f"📊 পাবেন: ৯৫ টাকা",
            parse_mode='Markdown',
            reply_markup=menu
        )
        return MAIN_MENU
    except Exception as e:
        logger.error(f"Withdraw error: {e}")
        return WITHDRAW_MENU

# ===================== এডমিন পেন্ডিং =====================
async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = get_pending_accounts()
    
    if not pending:
        await update.message.reply_text("✅ কোনো পেন্ডিং অ্যাকাউন্ট নেই!")
        return ADMIN_MENU
    
    msg = "⏳ **পেন্ডিং অ্যাকাউন্টসমূহ:**\n\n"
    for i, acc in enumerate(pending, 1):
        msg += f"{i}. 👤 ইউজার আইডি: `{acc.get('user_id')}`\n"
        msg += f"   📧 ইমেইল: {acc.get('username')}\n"
        msg += f"   🔑 পাসওয়ার্ড: {acc.get('password')}\n"
        msg += f"   🔐 2FA কোড: {acc.get('code')}\n"
        msg += f"   📅 {acc.get('timestamp')}\n━━━━━━━━━\n"
    
    await update.message.reply_text(msg[:4000], parse_mode='Markdown')
    return ADMIN_MENU

# ===================== এডমিন ফাংশন =====================
async def admin_data_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = get_all_accounts()
    if accounts:
        msg = "📊 **ডেটাবেস ভিউ (শেষ ২০টি)**\n\n"
        for i, acc in enumerate(accounts[-20:], 1):
            msg += f"{i}. 👤 ইউজার: `{acc.get('user_id')}`\n"
            msg += f"   📧 {acc.get('username')}\n"
            msg += f"   🔑 {acc.get('password')}\n"
            msg += f"   📊 {acc.get('status')}\n━━━━━━━\n"
        await update.message.reply_text(msg[:4000], parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ ডেটাবেস খালি!")
    return ADMIN_MENU

async def admin_copy_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = get_all_accounts()
    if accounts:
        csv_text = "ID,User ID,Username,Password,Secret,2FA Code,Status,Timestamp\n"
        for acc in accounts[:100]:
            csv_text += f"{acc.get('id')},{acc.get('user_id')},{acc.get('username')},{acc.get('password')},{acc.get('secret')},{acc.get('code')},{acc.get('status')},{acc.get('timestamp')}\n"
        await update.message.reply_text(f"📄 **CSV ডেটা:**\n\n```\n{csv_text[:3900]}\n```", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ ডেটাবেস খালি!")
    return ADMIN_MENU

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = get_all_accounts()
    users = get_all_users()
    total = len(accounts)
    completed = len([a for a in accounts if a.get('status') == 'Completed'])
    pending = len([a for a in accounts if a.get('status') == 'Pending Approval'])
    waiting = len([a for a in accounts if a.get('status') == 'Waiting for Secret'])
    generated = len([a for a in accounts if a.get('status') == '2FA Generated'])
    
    msg = f"📈 **স্ট্যাটিস্টিক্স**\n\n"
    msg += f"📊 মোট অ্যাকাউন্ট: {total}\n"
    msg += f"✅ কমপ্লিট: {completed}\n"
    msg += f"⏳ পেন্ডিং এপ্রুভাল: {pending}\n"
    msg += f"🔐 ওয়েটিং ফর সিক্রেট: {waiting}\n"
    msg += f"🔑 2FA জেনারেটেড: {generated}\n"
    msg += f"👥 মোট ইউজার: {len(users)}"
    
    await update.message.reply_text(msg, parse_mode='Markdown')
    return ADMIN_MENU

async def admin_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    if users:
        msg = "👥 **ইউজার লিস্ট**\n\n"
        for uid, data in list(users.items())[:20]:
            msg += f"🆔 {uid}\n"
            msg += f"📊 অ্যাকাউন্ট: {data['count']}\n"
            msg += f"💰 ব্যালেন্স: {data['balance']}\n━━━━━━━\n"
        await update.message.reply_text(msg[:4000], parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ কোনো ইউজার নেই!")
    return ADMIN_MENU

async def admin_delete_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ হ্যাঁ", callback_data="confirm_delete")],
        [InlineKeyboardButton("❌ না", callback_data="cancel_delete")]
    ]
    await update.message.reply_text("⚠️ **পুরো ডেটাবেস ডিলিট করবেন?**\n\nএই কাজ অপরিবর্তনীয়!", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_MENU

# ===================== এডমিন টাকা যোগ করুন =====================
async def admin_add_balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        parts = text.split()
        
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ **ভুল ফরম্যাট!**\n\n"
                "ফরম্যাট: `USER_ID AMOUNT`\n"
                "উদাহরণ: `123456789 50`\n\n"
                "❌ CANCEL - বাতিল করুন"
            )
            return ADMIN_ADD_BALANCE
        
        target_user_id = int(parts[0])
        amount = int(parts[1])
        
        if update_user_balance(target_user_id, amount):
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"💰 **ব্যালেন্স আপডেট!**\n\n"
                    f"আপনার অ্যাকাউন্টে **+{amount} টাকা** যোগ করা হয়েছে!\n"
                    f"📊 নতুন ব্যালেন্স: {get_user_balance(target_user_id)} টাকা"
                )
            except:
                pass
            
            await update.message.reply_text(
                f"✅ **টাকা যোগ করা হয়েছে!**\n\n"
                f"🆔 ইউজার আইডি: `{target_user_id}`\n"
                f"💰 পরিমাণ: {amount} টাকা\n"
                f"📊 নতুন ব্যালেন্স: {get_user_balance(target_user_id)} টাকা"
            )
        else:
            await update.message.reply_text(
                f"❌ **ইউজার পাওয়া যায়নি!**"
            )
        
        return ADMIN_MENU
    except ValueError:
        await update.message.reply_text(
            "❌ **ভুল ইনপুট!**\n\n"
            "ইউজার আইডি এবং টাকা সংখ্যা হতে হবে।\n"
            "উদাহরণ: `123456789 50`"
        )
        return ADMIN_ADD_BALANCE
    except Exception as e:
        logger.error(f"Admin add balance error: {e}")
        await update.message.reply_text(f"⚠️ এরর: {str(e)[:200]}")
        return ADMIN_MENU

# ===================== ইনলাইন বাটন =====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "confirm_delete":
            # ডেটা রিসেট
            save_data({"users": {}, "accounts": [], "next_id": 1})
            await query.edit_message_text("🗑️ **ডেটাবেস ডিলিট করা হয়েছে!**")
            return ADMIN_MENU
        
        elif query.data == "cancel_delete":
            await query.edit_message_text("✅ ডিলিট বাতিল!")
            return ADMIN_MENU
        
        return MAIN_MENU
    except Exception as e:
        logger.error(f"Button error: {e}")
        return MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await go_to_main_menu(update, context)

# ===================== মেইন =====================
def main():
    try:
        app = Application.builder().token(TOKEN).build()
        
        conv = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                MAIN_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
                ],
                WORK_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
                ],
                WAITING_2FA_SECRET: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, twofa_secret_handler)
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
                ADMIN_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
                ],
                ADMIN_ADD_BALANCE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_balance_handler)
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
