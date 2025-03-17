
import os
import telebot
import logging
import psutil
import time

# تنظیم سیستم لاگینگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "7338644071:AAEex9j0nMualdoywHSGFiBoMAzRpkFypPk"
bot = telebot.TeleBot(TOKEN)

def check_existing_bot():
    """Check and terminate any existing bot processes"""
    try:
        if os.path.exists("bot.lock"):
            with open("bot.lock", "r") as f:
                old_pid = int(f.read().strip())
                if psutil.pid_exists(old_pid):
                    try:
                        process = psutil.Process(old_pid)
                        process.terminate()
                        time.sleep(1)
                    except:
                        pass
            os.remove("bot.lock")
        
        with open("bot.lock", "w") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.error(f"Error handling bot lock: {e}")

@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    help_btn = telebot.types.InlineKeyboardButton("📚 راهنما", callback_data="help")
    quality_btn = telebot.types.InlineKeyboardButton("📊 کیفیت ویدیو", callback_data="quality")
    status_btn = telebot.types.InlineKeyboardButton("📈 وضعیت سرور", callback_data="status")
    markup.add(help_btn, quality_btn)
    markup.add(status_btn)
    
    bot.reply_to(message, 
        "👋 سلام پویا!\n\n"
        "🎬 به ربات دانلود ویدیو خوش آمدید.\n\n"
        "🔸 قابلیت‌های ربات:\n"
        "• دانلود ویدیو از یوتیوب و اینستاگرام\n"
        "• امکان انتخاب کیفیت ویدیو\n" 
        "• جستجوی هشتگ در کانال‌های تلگرام\n"
        "• نمایش وضعیت سرور\n\n"
        "🔹 روش استفاده:\n"
        "• برای دانلود ویدیو، لینک ویدیوی مورد نظر را ارسال کنید\n"
        "• برای جستجوی هشتگ، از دستور /search_hashtag استفاده کنید\n"
        "• برای نمایش وضعیت سرور، از دستور /status استفاده کنید",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "help":
        bot.answer_callback_query(call.id)
        bot.reply_to(call.message, "🔹 راهنمای استفاده از ربات:\n• برای دانلود ویدیو، لینک را ارسال کنید\n• برای جستجوی هشتگ، از /search_hashtag استفاده کنید")
    elif call.data == "quality":
        bot.answer_callback_query(call.id)
        bot.reply_to(call.message, "📊 کیفیت‌های موجود: 144p, 240p, 360p, 480p, 720p, 1080p")
    elif call.data == "status":
        bot.answer_callback_query(call.id)
        bot.reply_to(call.message, "📈 سرور در حال اجرا است")

if __name__ == "__main__":
    logger.info("🚀 ربات در حال راه‌اندازی...")
    try:
        check_existing_bot()
        bot.remove_webhook()
        time.sleep(0.5)
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"❌ خطا در راه‌اندازی ربات: {e}")
        if os.path.exists("bot.lock"):
            os.remove("bot.lock")
