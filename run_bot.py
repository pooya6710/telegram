import os
import sys
import json
import logging
import psutil
import time
import signal
from datetime import datetime
import telebot
from threading import Lock, Thread
from queue import Queue

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

# متغیرهای گلوبال
TOKEN = "7338644071:AAEex9j0nMualdoywHSGFiBoMAzRpkFypPk"
bot = None
download_queue = Queue()
active_downloads = {}
lock = Lock()

def initialize_bot():
    """Initialize bot with proper error handling"""
    global bot
    try:
        bot = telebot.TeleBot(TOKEN)
        logger.info("Bot initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing bot: {str(e)}")
        return False

def clean_up():
    """Clean up resources before exit"""
    try:
        if os.path.exists("bot.lock"):
            os.remove("bot.lock")
        logger.info("Cleanup completed")
    except Exception as e:
        logger.error(f"Error in cleanup: {str(e)}")

def kill_existing_bots():
    """Kill any existing bot processes"""
    current_pid = os.getpid()
    killed = []

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if (proc.info['pid'] != current_pid and 
                    'python' in proc.info['name'].lower() and 
                    any('run_bot.py' in cmd for cmd in proc.info.get('cmdline', []))):
                    proc.terminate()
                    proc.wait(timeout=3)
                    killed.append(proc.info['pid'])
                    logger.info(f"Terminated bot process: {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue
    except Exception as e:
        logger.error(f"Error killing existing bots: {str(e)}")

    return killed

def create_lock_file():
    """Create and manage lock file"""
    try:
        lock_data = {
            "pid": os.getpid(),
            "start_time": datetime.now().isoformat(),
            "token_hash": hash(TOKEN)
        }

        with open("bot.lock", "w") as f:
            json.dump(lock_data, f)

        logger.info(f"Lock file created with PID {os.getpid()}")
        return True
    except Exception as e:
        logger.error(f"Error creating lock file: {str(e)}")
        return False

def setup_handlers(bot_instance):
    """Set up bot message handlers"""

    @bot_instance.message_handler(commands=['start'])
    def start(message):
        try:
            markup = telebot.types.InlineKeyboardMarkup(row_width=2)
            help_btn = telebot.types.InlineKeyboardButton("📚 راهنما", callback_data="help")
            status_btn = telebot.types.InlineKeyboardButton("📈 وضعیت", callback_data="status")

            markup.add(help_btn, status_btn)

            bot_instance.reply_to(message, 
                "👋 سلام!\n\n"
                "🎬 به ربات دانلود ویدیو خوش آمدید.\n\n"
                "🔸 قابلیت‌های ربات:\n"
                "• دانلود ویدیو از یوتیوب و اینستاگرام\n"
                "• امکان انتخاب کیفیت ویدیو\n"
                "• نمایش وضعیت سرور",
                reply_markup=markup
            )
        except Exception as e:
            logger.error(f"Error in start command: {str(e)}")
            bot_instance.reply_to(message, "متأسفانه خطایی رخ داد. لطفا دوباره تلاش کنید.")

    @bot_instance.callback_query_handler(func=lambda call: True)
    def handle_query(call):
        try:
            if call.data == "help":
                bot_instance.answer_callback_query(call.id)
                bot_instance.reply_to(call.message, "🔹 راهنمای استفاده از ربات:\n• برای دانلود ویدیو، لینک را ارسال کنید")
            elif call.data == "status":
                bot_instance.answer_callback_query(call.id)
                bot_instance.reply_to(call.message, "📈 سرور در حال اجرا است")
        except Exception as e:
            logger.error(f"Error in callback handler: {str(e)}")

def signal_handler(signum, frame):
    """Handle termination signals"""
    logger.info(f"Received signal {signum}")
    clean_up()
    sys.exit(0)

def main():
    """Main function with improved error handling"""
    try:
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("Starting bot initialization...")

        # Kill existing bot instances
        killed = kill_existing_bots()
        if killed:
            logger.info(f"Killed {len(killed)} existing bot processes")
            time.sleep(1)

        # Create lock file
        if not create_lock_file():
            logger.error("Failed to create lock file")
            sys.exit(1)

        # Initialize bot
        if not initialize_bot():
            logger.error("Failed to initialize bot")
            clean_up()
            sys.exit(1)

        # Set up handlers
        setup_handlers(bot)

        # Remove webhook and start polling
        try:
            bot.remove_webhook()
            time.sleep(0.5)
            logger.info("Starting bot polling...")
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"Error in bot polling: {str(e)}")
            clean_up()
            sys.exit(1)

    except Exception as e:
        logger.error(f"Critical error in main function: {str(e)}")
        clean_up()
        sys.exit(1)
    finally:
        clean_up()

if __name__ == "__main__":
    main()