
import os
import telebot
import logging

# تنظیم سیستم لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# تنظیم توکن ربات
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7338644071:AAEex9j0nMualdoywHSGFiBoMAzRpkFypPk")

if not TOKEN:
    logger.error("❌ هیچ توکنی تنظیم نشده است! لطفا توکن را در متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم کنید.")
    exit(1)

# ایجاد نمونه ربات
bot = telebot.TeleBot(TOKEN)

# تعریف دستور /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "سلام! ربات راه‌اندازی شد و آماده استفاده است. 🤖")

# تعریف دستور /help
@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = """
🤖 راهنمای استفاده از ربات:
/start - شروع کار با ربات
/help - نمایش این راهنما
    """
    bot.reply_to(message, help_text)

# پاسخ به پیام های متنی
@bot.message_handler(func=lambda message: True)
def echo_message(message):
    bot.reply_to(message, f"پیام شما دریافت شد: {message.text}")

if __name__ == "__main__":
    logger.info("🚀 ربات در حال راه‌اندازی...")
    try:
        logger.info("🤖 ربات با موفقیت راه‌اندازی شد!")
        # ایجاد پوشه‌های مورد نیاز
        os.makedirs("videos", exist_ok=True)
        os.makedirs("instagram_videos", exist_ok=True)
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"❌ خطا در راه‌اندازی ربات: {e}")
