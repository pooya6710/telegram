
import os
import sys
import telebot
import logging
import psutil
import time
import signal
import json
from datetime import datetime

# تنظیم سیستم لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TOKEN = "7338644071:AAEex9j0nMualdoywHSGFiBoMAzRpkFypPk"
bot = None
current_process = None

def initialize_bot():
    """Initialize bot instance with error handling"""
    global bot
    try:
        bot = telebot.TeleBot(TOKEN)
        logger.info("Bot initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
        return False

def kill_existing_bots():
    """Find and kill any existing bot processes"""
    try:
        current_pid = os.getpid()
        killed_count = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] != current_pid:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any('run_bot.py' in cmd for cmd in cmdline):
                        logger.info(f"Terminating bot process: {proc.info['pid']}")
                        proc.terminate()
                        proc.wait(timeout=3)
                        killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
                logger.warning(f"Error while terminating process: {e}")
                continue
            
        return killed_count
    except Exception as e:
        logger.error(f"Error in kill_existing_bots: {e}")
        return 0

def cleanup():
    """Cleanup resources before exit"""
    try:
        if os.path.exists("bot.lock"):
            os.remove("bot.lock")
            logger.info("Removed lock file")
            
        if current_process:
            current_process.terminate()
            logger.info("Terminated bot process")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def signal_handler(signum, frame):
    """Handle termination signals"""
    logger.info(f"Received signal {signum}")
    cleanup()
    sys.exit(0)

def create_lock_file():
    """Create and manage lock file with error handling"""
    try:
        pid = os.getpid()
        lock_data = {
            "pid": pid,
            "start_time": datetime.now().isoformat(),
            "token": TOKEN[:8] + "..."  # Partially mask token for security
        }
        
        with open("bot.lock", "w") as f:
            json.dump(lock_data, f)
        
        logger.info(f"Created lock file with PID {pid}")
        return True
    except Exception as e:
        logger.error(f"Failed to create lock file: {e}")
        return False

def setup_bot_handlers():
    """Setup bot command handlers"""
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        try:
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
        except Exception as e:
            logger.error(f"Error in start handler: {e}")
            bot.reply_to(message, "⚠️ خطایی رخ داد. لطفا دوباره تلاش کنید.")

    @bot.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        try:
            if call.data == "help":
                bot.answer_callback_query(call.id)
                bot.reply_to(call.message, "🔹 راهنمای استفاده از ربات:\n• برای دانلود ویدیو، لینک را ارسال کنید\n• برای جستجوی هشتگ، از /search_hashtag استفاده کنید")
            elif call.data == "quality":
                bot.answer_callback_query(call.id)
                bot.reply_to(call.message, "📊 کیفیت‌های موجود: 144p, 240p, 360p, 480p, 720p, 1080p")
            elif call.data == "status":
                bot.answer_callback_query(call.id)
                bot.reply_to(call.message, "📈 سرور در حال اجرا است")
        except Exception as e:
            logger.error(f"Error in callback handler: {e}")
            try:
                bot.answer_callback_query(call.id, "⚠️ خطایی رخ داد")
            except:
                pass

def main():
    """Main function with improved error handling"""
    try:
        # تنظیم signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Starting bot initialization...")
        
        # متوقف کردن نمونه‌های قبلی
        killed_count = kill_existing_bots()
        if killed_count > 0:
            logger.info(f"Terminated {killed_count} existing bot processes")
            time.sleep(2)  # انتظار برای اطمینان از توقف کامل
        
        # ایجاد فایل قفل
        if not create_lock_file():
            logger.error("Failed to create lock file")
            sys.exit(1)
        
        # راه‌اندازی ربات
        if not initialize_bot():
            logger.error("Failed to initialize bot")
            cleanup()
            sys.exit(1)
        
        # تنظیم هندلرهای ربات
        setup_bot_handlers()
        
        # حذف وب‌هوک قبلی
        try:
            bot.remove_webhook()
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Error removing webhook: {e}")
        
        # شروع پولینگ
        logger.info("Starting bot polling...")
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
        
    except Exception as e:
        logger.error(f"Critical error in main: {e}")
        cleanup()
        sys.exit(1)
    finally:
        cleanup()

if __name__ == "__main__":
    main()
