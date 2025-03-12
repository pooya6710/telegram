
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
TOKEN = "7338644071:AAEex9j0nMualdoywHSGFiBoMAzRpkFypPk"
bot = telebot.TeleBot(TOKEN)

# تعریف دستور /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "سلام! به ربات چندکاره خوش آمدید. 🤖\nبرای دیدن راهنما دستور /help را بفرستید.")

# تعریف دستور /help
@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = """
🤖 راهنمای استفاده از ربات:
/start - شروع کار با ربات
/help - نمایش این راهنما
/info - دریافت اطلاعات

همچنین می‌توانید لینک ویدیوی یوتیوب یا اینستاگرام را ارسال کنید تا دانلود شود.
    """
    bot.reply_to(message, help_text)

# تعریف دستور /info
@bot.message_handler(commands=['info'])
def handle_info(message):
    info_text = "🤖 این ربات چندکاره است و قابلیت‌های متنوعی دارد."
    bot.reply_to(message, info_text)

# پاسخ به پیام های معمولی
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text
    
    # بررسی لینک یوتیوب یا اینستاگرام
    if "youtube.com" in text or "youtu.be" in text:
        bot.reply_to(message, "لینک یوتیوب شناسایی شد. در حال پردازش...")
    elif "instagram.com" in text:
        bot.reply_to(message, "لینک اینستاگرام شناسایی شد. در حال پردازش...")
    else:
        bot.reply_to(message, f"پیام دریافت شد: {text}")

if __name__ == "__main__":
    logger.info("🚀 در حال راه‌اندازی ربات...")
    try:
        logger.info("🤖 ربات با موفقیت راه‌اندازی شد!")
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"❌ خطا در راه‌اندازی ربات: {e}")
