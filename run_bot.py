
import os
import sys
import telebot
import logging
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

def initialize_bot():
    """راه‌اندازی نمونه ربات با مدیریت خطا"""
    global bot
    try:
        bot = telebot.TeleBot(TOKEN)
        logger.info("ربات با موفقیت راه‌اندازی شد")
        return True
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}")
        return False

def cleanup_resources():
    """پاکسازی منابع قبل از خروج"""
    try:
        # حذف فایل قفل
        if os.path.exists("bot.lock"):
            try:
                with open("bot.lock", "r") as f:
                    lock_data = json.load(f)
                    if lock_data.get("pid") == os.getpid():
                        os.remove("bot.lock")
                        logger.info("فایل قفل حذف شد")
            except:
                os.remove("bot.lock")
                logger.info("فایل قفل با خطا حذف شد")
                
    except Exception as e:
        logger.error(f"خطا در پاکسازی منابع: {e}")

def handle_termination(signum, frame):
    """مدیریت سیگنال‌های خاتمه"""
    logger.info(f"سیگنال {signum} دریافت شد")
    cleanup_resources()
    sys.exit(0)

def create_process_lock():
    """ایجاد و مدیریت فایل قفل با مدیریت خطا"""
    try:
        pid = os.getpid()
        lock_data = {
            "pid": pid,
            "start_time": datetime.now().isoformat(),
            "token_hash": hash(TOKEN)
        }
        
        with open("bot.lock", "w") as f:
            json.dump(lock_data, f)
        
        logger.info(f"فایل قفل با PID {pid} ایجاد شد")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد فایل قفل: {e}")
        return False

def setup_bot_handlers():
    """تنظیم هندلرهای ربات"""
    
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
                "• نمایش وضعیت سرور\n\n"
                "🔹 روش استفاده:\n"
                "• برای دانلود ویدیو، لینک را ارسال کنید\n"
                "• برای تنظیم کیفیت، از دکمه کیفیت ویدیو استفاده کنید\n"
                "• برای مشاهده وضعیت، دکمه وضعیت سرور را بزنید",
                reply_markup=markup
            )
            logger.info(f"دستور start برای کاربر {message.from_user.id} اجرا شد")
        except Exception as e:
            logger.error(f"خطا در اجرای دستور start: {e}")
            bot.reply_to(message, "⚠️ خطایی رخ داد. لطفا دوباره تلاش کنید.")

    @bot.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        try:
            if call.data == "help":
                bot.answer_callback_query(call.id)
                bot.reply_to(call.message, "🔹 راهنمای استفاده از ربات:\n• برای دانلود ویدیو، لینک را ارسال کنید\n• برای تنظیم کیفیت، از منوی کیفیت ویدیو استفاده کنید")
            elif call.data == "quality":
                bot.answer_callback_query(call.id)
                bot.reply_to(call.message, "📊 کیفیت‌های موجود: 144p, 240p, 360p, 480p, 720p, 1080p")
            elif call.data == "status":
                bot.answer_callback_query(call.id)
                bot.reply_to(call.message, "📈 سرور در حال اجرا است")
        except Exception as e:
            logger.error(f"خطا در پردازش callback: {e}")
            try:
                bot.answer_callback_query(call.id, "⚠️ خطایی رخ داد")
            except:
                pass

def main():
    """تابع اصلی با مدیریت خطای بهتر"""
    try:
        # تنظیم مدیریت سیگنال‌ها
        signal.signal(signal.SIGINT, handle_termination)
        signal.signal(signal.SIGTERM, handle_termination)
        
        logger.info("شروع راه‌اندازی ربات...")
        
        # ایجاد فایل قفل
        if not create_process_lock():
            logger.error("خطا در ایجاد فایل قفل")
            sys.exit(1)
        
        # راه‌اندازی ربات
        if not initialize_bot():
            logger.error("خطا در راه‌اندازی ربات")
            cleanup_resources()
            sys.exit(1)
        
        # تنظیم هندلرهای ربات
        setup_bot_handlers()
        
        # حذف وب‌هوک قبلی
        try:
            bot.remove_webhook()
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"خطا در حذف وب‌هوک: {e}")
        
        # شروع پولینگ
        logger.info("شروع پولینگ ربات...")
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
        
    except Exception as e:
        logger.error(f"خطای بحرانی در تابع اصلی: {e}")
        cleanup_resources()
        sys.exit(1)
    finally:
        cleanup_resources()

if __name__ == "__main__":
    main()
