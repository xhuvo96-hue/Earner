import os
import logging
import json
import random
import string
import pyotp
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials

TOKEN = os.environ.get('BOT_TOKEN')
SHEET_NAME = os.environ.get('SHEET_NAME', 'Instagram Accounts')
ADMIN_IDS = []

# ADMIN_ID পার্স করুন
admin_id_str = os.environ.get('ADMIN_ID', '')
if admin_id_str:
    try:
        ADMIN_IDS = [int(x.strip()) for x in admin_id_str.split(',') if x.strip()]
    except:
        ADMIN_IDS = []

# কনভার্সেশন স্টেট
MAIN_MENU, WAITING_2FA_SECRET, WAITING_DONE, WAITING_WITHDRAW_ACCOUNT, ADMIN_MENU = range(5)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== Google Sheets (এরর হ্যান্ডলিং সহ) =====================
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
        
        # শীট খোঁজা বা তৈরি করা
        try:
            sheet = client.open(SHEET_NAME).sheet1
        except:
            sheet = client.create(SHEET_NAME).sheet1
            # হেডার তৈরি
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

def get_sheet_data(sheet, limit=50):
    """সীমিত ডেটা রিটার্ন করে (ক্র্যাশ প্রুফ)"""
    if not sheet:
        return []
    try:
        records = sheet.get_all_records()
        # শুধু শেষ limit টা ডেটা নিবো
        if len(records) > limit:
            return records[-limit:]
        return records
    except Exception as e:
        logger.error(f"Get data error: {e}")
        return []

def get_all_sheet_data(sheet):
    """সব ডেটা রিটার্ন করে (ছোট ডেটার জন্য)"""
    if not sheet:
        return []
    try:
        return sheet.get_all_records()
    except Exception as e:
        logger.error(f"Get all data error: {e}")
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

def generate_2fa_code(secret):
    try:
        if not secret or len(secret) < 16:
            return None
        totp = pyotp.TOTP(secret)
        return totp.now()
    except Exception as e:
        logger.error(f"2FA generate error: {e}")
        return None

# ===================== এডমিন চেক =====================
def is_admin(user_id):
    return user_id in ADMIN_IDS

# ===================== মেনু =====================
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
    try:
        user = update.effective_user
        
        inline_keyboard = [
            [InlineKeyboardButton("📱 নতুন অ্যাকাউন্ট তৈরি", callback_data="new_account")],
            [InlineKeyboardButton("🔐 2FA সহ অ্যাকাউন্ট", callback_data="new_account_2fa")],
            [InlineKeyboardButton("ℹ️ হেল্প", callback_data="help")]
        ]
        
        if is_admin(user.id):
            await update.message.reply_text(
                f"👑 **এডমিন প্যানেল**\n\nস্বাগতম {user.first_name}!",
                parse_mode='Markdown',
                reply_markup=get_admin_menu()
            )
            return ADMIN_MENU
        
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
        await update.message.reply_text("⚠️ কিছু সমস্যা হয়েছে। আবার চেষ্টা করুন।")
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
        
        if text == "📊 ডেটাবেস ভিউ":
            if sheet:
                try:
                    records = get_sheet_data(sheet, 20)  # শুধু ২০টা ডেটা
                    if records:
                        msg = "📊 **ডেটাবেস ভিউ (শেষ ২০টি)**\n\n"
                        for i, row in enumerate(records, 1):
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
        
        elif text == "📋 সব ডেটা কপি":
            if sheet:
                try:
                    records = get_all_sheet_data(sheet)
                    if records:
                        # CSV ফরম্যাটে (ছোট করে)
                        csv_text = "Timestamp,User ID,Username,Email,Password,2FA,Status\n"
                        for row in records[:50]:  # শুধু ৫০টা
                            csv_text += f"{row.get('Timestamp', 'N/A')},{row.get('User ID', 'N/A')},{row.get('Username', 'N/A')},{row.get('Instagram Email', 'N/A')},{row.get('Instagram Password', 'N/A')},{row.get('2FA Code', 'N/A')},{row.get('Status', 'N/A')}\n"
                        
                        if len(csv_text) > 4000:
                            csv_text = csv_text[:3900] + "\n... (ট্রাঙ্কেটেড)"
                        
                        await update.message.reply_text(
                            f"📄 **CSV ডেটা (শেষ ৫০টি):**\n\n```\n{csv_text}\n```",
                            parse_mode='Markdown'
                        )
                    else:
                        await update.message.reply_text("❌ ডেটাবেস খালি!")
                except Exception as e:
                    await update.message.reply_text(f"⚠️ এরর: {str(e)[:200]}")
            else:
                await update.message.reply_text("⚠️ ডেটাবেস সংযোগ নেই!")
            return ADMIN_MENU
        
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
                    msg += f"📊 মোট: {total}\n✅ কমপ্লিট: {completed}\n⏳ পেন্ডিং: {pending}\n🔐 2FA: {twofa_pending}\n👥 ইউজার: {unique_users}"
                    
                    await update.message.reply_text(msg, parse_mode='Markdown')
                except Exception as e:
                    await update.message.reply_text(f"⚠️ এরর: {str(e)[:200]}")
            else:
                await update.message.reply_text("⚠️ ডেটাবেস সংযোগ নেই!")
            return ADMIN_MENU
        
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
                        for uid, data in list(users.items())[:20]:  # শুধু ২০টা
                            msg += f"🆔 {uid}\n👤 @{data['username']}\n📊 {data['count']}\n━━━━━━━\n"
                        await update.message.reply_text(msg[:4000], parse_mode='Markdown')
                    else:
                        await update.message.reply_text("❌ কোনো ইউজার নেই!")
                except Exception as e:
                    await update.message.reply_text(f"⚠️ এরর: {str(e)[:200]}")
            else:
                await update.message.reply_text("⚠️ ডেটাবেস সংযোগ নেই!")
            return ADMIN_MENU
        
        elif text == "🔙 ইউজার মেনু":
            return await start(update, context)
        
        else:
            await update.message.reply_text("❓ অজানা কমান্ড!")
            return ADMIN_MENU
    except Exception as e:
        logger.error(f"Admin handler error: {e}")
        await update.message.reply_text("⚠️ কিছু সমস্যা হয়েছে।")
        return ADMIN_MENU

# ===================== বাকি হ্যান্ডলারগুলো (এরর হ্যান্ডলিং সহ) =====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        sheet = context.bot_data.get('sheet')

        if query.data == "new_account":
            username = generate_random_username()
            password = generate_random_password()
            
            if sheet:
                save_to_sheet(sheet, user_id, query.from_user.username or "Unknown", username, password, status="Pending")
            
            await query.edit_message_text(
                f"🎯 **অ্যাকাউন্ট তৈরি!**\n\n👤 `{username}`\n🔑 `{password}`\n\n✅ সেভ করা হয়েছে!",
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
                f"🎯 **অ্যাকাউন্ট তৈরি!**\n\n👤 `{username}`\n🔑 `{password}`\n\n🔐 **সিক্রেট কী দিন:**",
                parse_mode='Markdown'
            )
            return WAITING_2FA_SECRET

        elif query.data == "help":
            await query.edit_message_text(
                "ℹ️ **সাহায্য:**\n\n1. নতুন অ্যাকাউন্ট তৈরি করুন\n2. 2FA সিক্রেট কী দিন\n3. বট অটো কোড দিবে\n4. DONE ক্লিক করুন"
            )
            return MAIN_MENU

        elif query.data == "done_account":
            if sheet:
                try:
                    records = get_all_sheet_data(sheet)
                    for i, row in enumerate(records, start=2):
                        if str(row.get('User ID')) == str(user_id) and row.get('Status') == '2FA Generated':
                            sheet.update_cell(i, 7, 'Completed')
                            break
                except:
                    pass
            await query.edit_message_text("🎉 **অভিনন্দন!** অ্যাকাউন্ট সম্পূর্ণ হয়েছে!")
            return MAIN_MENU

        elif query.data in ["withdraw_binance", "withdraw_bkash", "withdraw_nagad"]:
            method = query.data.replace("withdraw_", "").capitalize()
            context.user_data['withdraw_method'] = method
            await query.edit_message_text(f"📤 **উইথড্র ({method})**\n\nআপনার {method} অ্যাকাউন্ট আইডি দিন:")
            return WAITING_WITHDRAW_ACCOUNT

        return MAIN_MENU
    except Exception as e:
        logger.error(f"Button handler error: {e}")
        await update.callback_query.edit_message_text("⚠️ কিছু সমস্যা হয়েছে।")
        return MAIN_MENU

async def twofa_secret_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        secret = update.message.text.strip().upper()
        user_id = update.effective_user.id
        sheet = context.bot_data.get('sheet')
        
        if len(secret) < 16:
            await update.message.reply_text("❌ সিক্রেট কী কমপক্ষে ১৬ অক্ষরের হতে হবে!")
            return WAITING_2FA_SECRET
        
        otp_code = generate_2fa_code(secret)
        
        if otp_code:
            if sheet:
                try:
                    records = get_all_sheet_data(sheet)
                    for i, row in enumerate(records, start=2):
                        if str(row.get('User ID')) == str(user_id) and row.get('Status') == 'Waiting for 2FA Secret':
                            sheet.update_cell(i, 6, f"Secret: {secret}")
                            sheet.update_cell(i, 7, '2FA Generated')
                            break
                except:
                    pass
            
            keyboard = [[InlineKeyboardButton("✅ DONE", callback_data="done_account")]]
            await update.message.reply_text(
                f"✅ **2FA কোড:** `{otp_code}`\n\n⏳ ৩০ সেকেন্ড বৈধ\n\nDONE ক্লিক করুন।",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return WAITING_DONE
        else:
            await update.message.reply_text("❌ সিক্রেট কী থেকে কোড তৈরি করা যায়নি!")
            return WAITING_2FA_SECRET
    except Exception as e:
        logger.error(f"2FA secret handler error: {e}")
        await update.message.reply_text("⚠️ কিছু সমস্যা হয়েছে।")
        return WAITING_2FA_SECRET

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
            f"✅ **উইথড্র রিকোয়েস্ট!**\n\n📤 {method}\n🆔 `{account_id}`\n💰 পাবেন: ৯৫ টাকা"
        )
        return MAIN_MENU
    except Exception as e:
        logger.error(f"Withdraw handler error: {e}")
        await update.message.reply_text("⚠️ কিছু সমস্যা হয়েছে।")
        return MAIN_MENU

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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
                    records = get_all_sheet_data(sheet)
                    user_accounts = [r for r in records if str(r.get('User ID')) == str(user_id)]
                    account_count = len(user_accounts)
                    balance = account_count * 10
                    
                    msg += f"💰 **ব্যালেন্স:** {balance} টাকা\n"
                    msg += f"📊 **মোট:** {account_count}\n\n"
                    
                    if account_count > 0:
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
        
        elif text == "📋 কাজ (INSTA 2FA)":
            inline_keyboard = [
                [InlineKeyboardButton("📱 নতুন", callback_data="new_account")],
                [InlineKeyboardButton("🔐 2FA সহ", callback_data="new_account_2fa")]
            ]
            await update.message.reply_text(
                "📋 **কাজ**\n\nনিচের অপশন বেছে নিন:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard)
            )
        
        elif text == "🏧 উইথড্র ব্যালেন্স":
            keyboard = [
                [InlineKeyboardButton("💰 Binance", callback_data="withdraw_binance")],
                [InlineKeyboardButton("💳 Bkash", callback_data="withdraw_bkash")],
                [InlineKeyboardButton("📱 Nagad", callback_data="withdraw_nagad")]
            ]
            await update.message.reply_text(
                "🏧 **উইথড্র**\n\n⚠️ মিনিমাম ১০০ টাকা\n💸 চার্জ ৫ টাকা\n📊 পাবেন ৯৫ টাকা",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif text == "👥 রেফার":
            user = update.effective_user
            refer_link = f"https://t.me/{context.bot.username}?start=ref_{user.id}"
            keyboard = [[InlineKeyboardButton("📤 শেয়ার করুন", url=f"https://t.me/share/url?url={refer_link}&text=আমার রেফার লিংক!")]]
            await update.message.reply_text(
                f"👥 **রেফার**\n\n`{refer_link}`\n\n🎁 প্রতি রেফারে ১০ টাকা!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        else:
            await update.message.reply_text("❓ নিচের বাটন ব্যবহার করুন।")
    except Exception as e:
        logger.error(f"Text handler error: {e}")
        await update.message.reply_text("⚠️ কিছু সমস্যা হয়েছে।")

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
                WAITING_2FA_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, twofa_secret_handler)],
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
        logger.error(f"Main error: {e}")
        print(f"❌ বট চালু করতে পারেনি: {e}")

if __name__ == '__main__':
    main()
