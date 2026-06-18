import os
import logging
import json
import random
import string
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials

TOKEN = os.environ.get('BOT_TOKEN')
SHEET_NAME = os.environ.get('SHEET_NAME', 'Instagram Accounts')
ADMIN_IDS = []

# এডমিন আইডি পার্স করুন
admin_id_str = os.environ.get('ADMIN_ID', '')
if admin_id_str:
    try:
        ADMIN_IDS = [int(x.strip()) for x in admin_id_str.split(',') if x.strip()]
    except:
        ADMIN_IDS = []

# কনভার্সেশন স্টেট
MAIN_MENU, WAITING_2FA, WAITING_DONE, WAITING_WITHDRAW_ACCOUNT, ADMIN_MENU = range(5)

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
            headers = ["Timestamp", "User ID", "Username", "Instagram Email", "Instagram Password", "2FA Code", "Status"]
            sheet.append_row(headers)
        return sheet
    except Exception as e:
        logger.error(f"Google Sheets setup error: {e}")
        return None

def save_to_sheet(sheet, user_id, username, email, password, twofa="", status="Pending"):
    if not sheet:
        return False
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, str(user_id), username, email, password, twofa, status])
        return True
    except Exception as e:
        logger.error(f"Save error: {e}")
        return False

def get_all_sheet_data(sheet):
    if not sheet:
        return []
    try:
        return sheet.get_all_records()
    except Exception as e:
        logger.error(f"Get data error: {e}")
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

# ===================== এডমিন চেক =====================
def is_admin(user_id):
    return user_id in ADMIN_IDS

# ===================== মেনু =====================
def get_bottom_menu():
    keyboard = [
        [KeyboardButton("👤 আমার অ্যাকাউন্ট"), KeyboardButton("📋 কাজ (INSTA 2FA)")],
        [KeyboardButton("🏧 উইথড্র ব্যালেন্স"), KeyboardButton("👥 রেফার")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_menu():
    keyboard = [
        [KeyboardButton("📊 ডেটাবেস ভিউ")],
        [KeyboardButton("📋 সব ডেটা কপি")],
        [KeyboardButton("📈 স্ট্যাটিস্টিক্স")],
        [KeyboardButton("👥 ইউজার লিস্ট")],
        [KeyboardButton("🗑️ ডেটা ডিলিট")],
        [KeyboardButton("🔙 ইউজার মেনু")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===================== স্টার্ট =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        
        inline_keyboard = [
            [InlineKeyboardButton("📱 নতুন অ্যাকাউন্ট তৈরি", callback_data="new_account")],
            [InlineKeyboardButton("🔐 2FA সহ অ্যাকাউন্ট", callback_data="new_account_2fa")],
            [InlineKeyboardButton("ℹ️ হেল্প", callback_data="help")]
        ]
        
        # এডমিন কিনা চেক
        if is_admin(user.id):
            await update.message.reply_text(
                f"👑 **এডমিন প্যানেল**\n\n"
                f"স্বাগতম {user.first_name}!\n"
                f"নিচের অপশন থেকে বেছে নিন:",
                parse_mode='Markdown',
                reply_markup=get_admin_menu()
            )
            return ADMIN_MENU
        
        # ইউজার মেনু
        await update.message.reply_text(
            f"👋 **স্বাগতম {user.first_name}!**\n\n"
            f"📌 নিচের বাটনগুলো ব্যবহার করুন:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
        
        await update.message.reply_text(
            "📌 **নিচের মেনু থেকে বেছে নিন:**",
            reply_markup=get_bottom_menu()
        )
        return MAIN_MENU
    except Exception as e:
        logger.error(f"Start error: {e}")
        return MAIN_MENU

# ===================== এডমিন হ্যান্ডলার =====================
async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        user_id = update.effective_user.id
        sheet = context.bot_data.get('sheet')
        
        if not is_admin(user_id):
            await update.message.reply_text("⛔ আপনি এডমিন নন!")
            return MAIN_MENU
        
        # ===== ডেটাবেস ভিউ =====
        if text == "📊 ডেটাবেস ভিউ":
            if sheet:
                try:
                    records = get_all_sheet_data(sheet)
                    if records:
                        msg = "📊 **ডেটাবেস ভিউ (শেষ ২০টি)**\n\n"
                        for i, row in enumerate(records[-20:], 1):
                            msg += f"{i}. 📧 {row.get('Instagram Email', 'N/A')}\n"
                            msg += f"   🔑 {row.get('Instagram Password', 'N/A')}\n"
                            msg += f"   📊 {row.get('Status', 'Pending')}\n"
                            msg += f"   📅 {row.get('Timestamp', 'N/A')}\n━━━━━━━\n"
                        await update.message.reply_text(msg[:4000], parse_mode='Markdown')
                    else:
                        await update.message.reply_text("❌ ডেটাবেস খালি!")
                except Exception as e:
                    await update.message.reply_text(f"⚠️ এরর: {str(e)[:200]}")
            else:
                await update.message.reply_text("⚠️ ডেটাবেস সংযোগ নেই!")
            return ADMIN_MENU
        
        # ===== সব ডেটা কপি =====
        elif text == "📋 সব ডেটা কপি":
            if sheet:
                try:
                    records = get_all_sheet_data(sheet)
                    if records:
                        csv_text = "Timestamp,User ID,Username,Email,Password,2FA,Status\n"
                        for row in records[:100]:
                            csv_text += f"{row.get('Timestamp', 'N/A')},{row.get('User ID', 'N/A')},{row.get('Username', 'N/A')},{row.get('Instagram Email', 'N/A')},{row.get('Instagram Password', 'N/A')},{row.get('2FA Code', 'N/A')},{row.get('Status', 'N/A')}\n"
                        await update.message.reply_text(
                            f"📄 **CSV ডেটা (শেষ ১০০টি):**\n\n```\n{csv_text[:3900]}\n```",
                            parse_mode='Markdown'
                        )
                    else:
                        await update.message.reply_text("❌ ডেটাবেস খালি!")
                except Exception as e:
                    await update.message.reply_text(f"⚠️ এরর: {str(e)[:200]}")
            else:
                await update.message.reply_text("⚠️ ডেটাবেস সংযোগ নেই!")
            return ADMIN_MENU
        
        # ===== স্ট্যাটিস্টিক্স =====
        elif text == "📈 স্ট্যাটিস্টিক্স":
            if sheet:
                try:
                    records = get_all_sheet_data(sheet)
                    total = len(records)
                    completed = len([r for r in records if r.get('Status') == 'Completed'])
                    pending = len([r for r in records if r.get('Status') == 'Pending'])
                    twofa_pending = len([r for r in records if '2FA' in str(r.get('Status', ''))])
                    unique_users = len(set([r.get('User ID') for r in records if r.get('User ID')]))
                    
                    msg = f"📈 **স্ট্যাটিস্টিক্স**\n\n"
                    msg += f"📊 মোট অ্যাকাউন্ট: {total}\n"
                    msg += f"✅ কমপ্লিট: {completed}\n"
                    msg += f"⏳ পেন্ডিং: {pending}\n"
                    msg += f"🔐 2FA পেন্ডিং: {twofa_pending}\n"
                    msg += f"👥 ইউনিক ইউজার: {unique_users}"
                    
                    await update.message.reply_text(msg, parse_mode='Markdown')
                except Exception as e:
                    await update.message.reply_text(f"⚠️ এরর: {str(e)[:200]}")
            else:
                await update.message.reply_text("⚠️ ডেটাবেস সংযোগ নেই!")
            return ADMIN_MENU
        
        # ===== ইউজার লিস্ট =====
        elif text == "👥 ইউজার লিস্ট":
            if sheet:
                try:
                    records = get_all_sheet_data(sheet)
                    users = {}
                    for row in records:
                        uid = row.get('User ID')
                        if uid:
                            if uid not in users:
                                users[uid] = {'username': row.get('Username', 'Unknown'), 'count': 1}
                            else:
                                users[uid]['count'] += 1
                    
                    if users:
                        msg = "👥 **ইউজার লিস্ট**\n\n"
                        for uid, data in list(users.items())[:30]:
                            msg += f"🆔 {uid}\n"
                            msg += f"👤 @{data['username']}\n"
                            msg += f"📊 অ্যাকাউন্ট: {data['count']}\n━━━━━━━\n"
                        await update.message.reply_text(msg[:4000], parse_mode='Markdown')
                    else:
                        await update.message.reply_text("❌ কোনো ইউজার নেই!")
                except Exception as e:
                    await update.message.reply_text(f"⚠️ এরর: {str(e)[:200]}")
            else:
                await update.message.reply_text("⚠️ ডেটাবেস সংযোগ নেই!")
            return ADMIN_MENU
        
        # ===== ডেটা ডিলিট =====
        elif text == "🗑️ ডেটা ডিলিট":
            keyboard = [
                [InlineKeyboardButton("✅ হ্যাঁ, ডিলিট করুন", callback_data="confirm_delete")],
                [InlineKeyboardButton("❌ না, বাতিল", callback_data="cancel_delete")]
            ]
            await update.message.reply_text(
                "⚠️ **সতর্কতা!**\n\n"
                "আপনি কি পুরো ডেটাবেস ডিলিট করতে চান?\n\n"
                "এই কাজটি **অপরিবর্তনীয়**!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return ADMIN_MENU
        
        # ===== ইউজার মেনু =====
        elif text == "🔙 ইউজার মেনু":
            return await start(update, context)
        
        else:
            await update.message.reply_text("❓ অজানা কমান্ড!")
            return ADMIN_MENU
    except Exception as e:
        logger.error(f"Admin error: {e}")
        await update.message.reply_text("⚠️ কিছু সমস্যা হয়েছে।")
        return ADMIN_MENU

# ===================== ইনলাইন বাটন হ্যান্ডলার =====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        sheet = context.bot_data.get('sheet')

        # ===== নতুন অ্যাকাউন্ট =====
        if query.data == "new_account":
            username = generate_random_username()
            password = generate_random_password()
            if sheet:
                save_to_sheet(sheet, user_id, query.from_user.username or "Unknown", username, password, status="Pending")
            await query.edit_message_text(
                f"🎯 **অ্যাকাউন্ট তৈরি!**\n\n"
                f"👤 ইউজারনেম: `{username}`\n"
                f"🔑 পাসওয়ার্ড: `{password}`\n\n"
                f"✅ সেভ করা হয়েছে!",
                parse_mode='Markdown'
            )
            return MAIN_MENU

        # ===== 2FA সহ অ্যাকাউন্ট =====
        elif query.data == "new_account_2fa":
            username = generate_random_username()
            password = generate_random_password()
            context.user_data['temp_username'] = username
            if sheet:
                save_to_sheet(sheet, user_id, query.from_user.username or "Unknown", username, password, status="2FA Pending")
            await query.edit_message_text(
                f"🎯 **অ্যাকাউন্ট তৈরি!**\n\n"
                f"👤 ইউজারনেম: `{username}`\n"
                f"🔑 পাসওয়ার্ড: `{password}`\n\n"
                f"🔐 **আপনার 2FA কোড লিখুন:**",
                parse_mode='Markdown'
            )
            return WAITING_2FA

        # ===== হেল্প =====
        elif query.data == "help":
            await query.edit_message_text(
                "ℹ️ **সাহায্য:**\n\n"
                "1. নতুন অ্যাকাউন্ট তৈরি করুন\n"
                "2. 2FA কোড দিন\n"
                "3. DONE ক্লিক করুন\n\n"
                "📞 সাপোর্ট: @EarnerSupport"
            )
            return MAIN_MENU

        # ===== DONE =====
        elif query.data == "done_account":
            if sheet:
                try:
                    records = get_all_sheet_data(sheet)
                    for i, row in enumerate(records, start=2):
                        if str(row.get('User ID')) == str(user_id) and row.get('Status') == '2FA Provided':
                            sheet.update_cell(i, 7, 'Completed')
                            break
                except:
                    pass
            await query.edit_message_text("🎉 **অভিনন্দন!** অ্যাকাউন্ট সম্পূর্ণ হয়েছে!")
            return MAIN_MENU

        # ===== উইথড্র মেথড =====
        elif query.data in ["withdraw_binance", "withdraw_bkash", "withdraw_nagad"]:
            method = query.data.replace("withdraw_", "").capitalize()
            context.user_data['withdraw_method'] = method
            await query.edit_message_text(
                f"📤 **উইথড্র ({method})**\n\n"
                f"আপনার {method} অ্যাকাউন্ট আইডি লিখুন:"
            )
            return WAITING_WITHDRAW_ACCOUNT

        # ===== ডিলিট কনফর্ম =====
        elif query.data == "confirm_delete":
            if sheet:
                try:
                    # সব ডেটা ডিলিট
                    sheet.clear()
                    # হেডার আবার যোগ
                    headers = ["Timestamp", "User ID", "Username", "Instagram Email", "Instagram Password", "2FA Code", "Status"]
                    sheet.append_row(headers)
                    await query.edit_message_text("🗑️ **ডেটাবেস সফলভাবে ডিলিট করা হয়েছে!**")
                except Exception as e:
                    await query.edit_message_text(f"⚠️ ডিলিট করতে পারেনি: {e}")
            else:
                await query.edit_message_text("⚠️ ডেটাবেস সংযোগ নেই!")
            return ADMIN_MENU

        # ===== ডিলিট বাতিল =====
        elif query.data == "cancel_delete":
            await query.edit_message_text("✅ ডিলিট বাতিল করা হয়েছে!")
            return ADMIN_MENU

        return MAIN_MENU
    except Exception as e:
        logger.error(f"Button error: {e}")
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
                        sheet.update_cell(i, 7, '2FA Provided')
                        break
            except:
                pass
        
        keyboard = [[InlineKeyboardButton("✅ DONE", callback_data="done_account")]]
        await update.message.reply_text(
            f"✅ **2FA কোড সংরক্ষিত!**\n\n"
            f"🔑 কোড: `{twofa_code}`\n\n"
            f"অ্যাকাউন্ট সম্পূর্ণ করতে **DONE** ক্লিক করুন।",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAITING_DONE
    except Exception as e:
        logger.error(f"2FA error: {e}")
        return WAITING_2FA

# ===================== উইথড্র হ্যান্ডলার =====================
async def withdraw_account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                "Pending"
            ])
        
        await update.message.reply_text(
            f"✅ **উইথড্র রিকোয়েস্ট!**\n\n"
            f"📤 মেথড: {method}\n"
            f"🆔 অ্যাকাউন্ট: `{account_id}`\n"
            f"💰 পাবেন: ৯৫ টাকা\n\n"
            f"আমাদের টিম প্রসেস করবে।"
        )
        return MAIN_MENU
    except Exception as e:
        logger.error(f"Withdraw error: {e}")
        return MAIN_MENU

# ===================== টেক্সট হ্যান্ডলার =====================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        user_id = update.effective_user.id
        
        # এডমিন চেক
        if is_admin(user_id) and text in ["📊 ডেটাবেস ভিউ", "📋 সব ডেটা কপি", "📈 স্ট্যাটিস্টিক্স", "👥 ইউজার লিস্ট", "🗑️ ডেটা ডিলিট", "🔙 ইউজার মেনู"]:
            await admin_text_handler(update, context)
            return
        
        sheet = context.bot_data.get('sheet')
        
        # ===== আমার অ্যাকাউন্ট =====
        if text == "👤 আমার অ্যাকাউন্ট":
            msg = "👤 **আপনার অ্যাকাউন্ট**\n\n"
            if sheet:
                try:
                    records = get_all_sheet_data(sheet)
                    user_accounts = [r for r in records if str(r.get('User ID')) == str(user_id)]
                    balance = len(user_accounts) * 10
                    msg += f"💰 ব্যালেন্স: {balance} টাকা\n"
                    msg += f"📊 মোট অ্যাকাউন্ট: {len(user_accounts)}\n\n"
                    if user_accounts:
                        msg += "📋 **আপনার অ্যাকাউন্টসমূহ:**\n\n"
                        for acc in user_accounts[-5:]:
                            msg += f"📧 {acc.get('Instagram Email', 'N/A')}\n"
                            msg += f"🔑 {acc.get('Instagram Password', 'N/A')}\n"
                            msg += f"📊 {acc.get('Status', 'Pending')}\n━━━━━━━\n"
                    else:
                        msg += "❌ কোনো অ্যাকাউন্ট নেই।"
                except:
                    msg += "⚠️ ডেটাবেস এরর।"
            else:
                msg += "⚠️ ডেটাবেস সংযোগ নেই।"
            await update.message.reply_text(msg[:4000], parse_mode='Markdown')
        
        # ===== কাজ (INSTA 2FA) =====
        elif text == "📋 কাজ (INSTA 2FA)":
            inline_keyboard = [
                [InlineKeyboardButton("📱 নতুন অ্যাকাউন্ট", callback_data="new_account")],
                [InlineKeyboardButton("🔐 2FA সহ অ্যাকাউন্ট", callback_data="new_account_2fa")]
            ]
            await update.message.reply_text(
                "📋 **কাজ (INSTA 2FA)**\n\n"
                "নিচের অপশন থেকে বেছে নিন:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard)
            )
        
        # ===== উইথড্র =====
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
        
        # ===== রেফার =====
        elif text == "👥 রেফার":
            user = update.effective_user
            refer_link = f"https://t.me/{context.bot.username}?start=ref_{user.id}"
            keyboard = [
                [InlineKeyboardButton("📤 শেয়ার করুন", url=f"https://t.me/share/url?url={refer_link}&text=আমার রেফার লিংক ব্যবহার করুন! 🎉")]
            ]
            await update.message.reply_text(
                f"👥 **রেফার**\n\n"
                f"আপনার লিংক:\n`{refer_link}`\n\n"
                f"🎁 প্রতি রেফারে **১০ টাকা** বোনাস!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        else:
            await update.message.reply_text("❓ নিচের বাটন ব্যবহার করুন।")
    except Exception as e:
        logger.error(f"Text error: {e}")
        await update.message.reply_text("⚠️ কিছু সমস্যা হয়েছে।")

# ===================== ক্যান্সেল =====================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ বাতিল। /start দিন।")
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
                    CallbackQueryHandler(button_handler),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
                ],
                ADMIN_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler)
                ],
                WAITING_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, twofa_handler)],
                WAITING_DONE: [CallbackQueryHandler(button_handler, pattern="^done_account$")],
                WAITING_WITHDRAW_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_account_handler)],
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
