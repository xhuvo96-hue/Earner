import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get('BOT_TOKEN')
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ বট কাজ করছে! 🎉\n\nটেস্ট সফল! এখন পুরো কোড আপলোড করুন।")

def main():
    print("🤖 বট চালু হচ্ছে...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    print("✅ বট চালু!")
    app.run_polling()

if __name__ == '__main__':
    main()
