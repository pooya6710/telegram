
import os
import telebot
import logging
import psutil
import time
import signal
import sys

# تنظیم سیستم لاگینگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "7338644071:AAEex9j0nMualdoywHSGFiBoMAzRpkFypPk"
bot = telebot.TeleBot(TOKEN)

def kill_existing_bots():
    """Find and kill any existing bot processes"""
    try:
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check if it's a Python process running run_bot.py
                if proc.info['pid'] != current_pid and proc.info['name'] == 'python':
                    cmdline = proc.info['cmdline']
                    if cmdline and any('run_bot.py' in cmd for cmd in cmdline):
                        logger.info(f"Terminating existing bot process: {proc.info['pid']}")
                        proc.terminate()
                        proc.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue
    except Exception as e:
        logger.error(f"Error in kill_existing_bots: {e}")

def signal_handler(signum, frame):
    """Handle termination signals"""
    logger.info("Received termination signal. Cleaning up...")
    try:
        if os.path.exists("bot.lock"):
            os.remove("bot.lock")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")
        sys.exit(1)

def create_lock_file():
    """Create and manage lock file"""
    try:
        with open("bot.lock", "w") as f:
            f.write(str(os.getpid()))
        return True
    except Exception as e:
        logger.error(f"Error creating lock file: {e}")
        return False

@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    help_btn = telebot.types.InlineKeyboardButton("📚 راهنما", callback_data="help")
    quality_btn = telebot.types.InlineKeyboardButton("📊 کیفیت ویدیو", callback_data="quality")
    status_btn = telebot.types.InlineKeyboardButton("📈 وضعیت سرور", callback_data="status")
    markup.add(help_btn, quality_btn)
    markup.add(status_btn)
    
    bot.reply_to(message, 
        "👋 سلام!\n\n"
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
    # تنظیم signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🚀 ربات در حال راه‌اندازی...")
    try:
        # متوقف کردن نمونه‌های قبلی
        kill_existing_bots()
        time.sleep(1)  # صبر برای اطمینان از توقف کامل
        
        # ایجاد فایل قفل جدید
        if not create_lock_file():
            logger.error("خطا در ایجاد فایل قفل")
            sys.exit(1)
            
        # حذف وب‌هوک قبلی
        bot.remove_webhook()
        time.sleep(0.5)
        
        # شروع پولینگ
        logger.info("شروع پولینگ ربات...")
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
        
    except Exception as e:
        logger.error(f"❌ خطا در راه‌اندازی ربات: {e}")
    finally:
        # پاکسازی در هنگام خروج
        if os.path.exists("bot.lock"):
            os.remove("bot.lock")
