import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# টোকেন সেটআপ
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    print("❌ ERROR: BOT_TOKEN পাওয়া যায়নি!")
    exit(1)

# লগিং সেটআপ
logging.basicConfig(level=logging.INFO)

# ===================== স্টার্ট =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("👤 আমার অ্যাকাউন্ট", callback_data="my_account")],
        [InlineKeyboardButton("📋 কাজ (INSTA 2FA)", callback_data="work")],
        [InlineKeyboardButton("🏧 উইথড্র ব্যালেন্স", callback_data="withdraw")],
        [InlineKeyboardButton("👥 রেফার", callback_data="refer")]
    ]
    await update.message.reply_text(
        f"👋 হ্যালো {user.first_name}!\n\n"
        f"নিচের অপশন থেকে বেছে নিন:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===================== বাটন =====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == "my_account":
        msg = "👤 আপনার অ্যাকাউন্টসমূহ:\n\n(এখনো কোনো অ্যাকাউন্ট নেই)"
    elif data == "work":
        msg = "📋 কাজ শুরু করুন:\n\nশীঘ্রই আসছে..."
    elif data == "withdraw":
        msg = "🏧 উইথড্র:\n\nমিনিমাম ১০০ টাকা\nচার্জ ৫ টাকা"
    elif data == "refer":
        msg = "👥 রেফার লিংক:\n\nশীঘ্রই আসছে..."
    else:
        msg = f"✅ আপনি ক্লিক করেছেন: {data}"
    
    await query.edit_message_text(msg)

# ===================== মেইন =====================
def main():
    print("🤖 বট চালু হচ্ছে...")
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ বট চালু! (/start দিন)")
    app.run_polling()

if __name__ == '__main__':
    main()
