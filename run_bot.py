import os
import sys
import telebot
import logging
import time
import signal
import json
from datetime import datetime
import psutil
import traceback

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

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("توکن ربات تنظیم نشده است")
    sys.exit(1)
bot = telebot.TeleBot(TOKEN)

def kill_other_bot_instances():
    """حذف سایر نمونه‌های در حال اجرای ربات"""
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] != current_pid:
                cmdline = proc.info['cmdline']
                if cmdline and 'python' in cmdline[0] and 'run_bot.py' in ' '.join(cmdline):
                    proc.terminate()
                    logger.info(f"نمونه قبلی ربات با PID {proc.info['pid']} متوقف شد")
                    time.sleep(1)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def initialize_bot():
    """راه‌اندازی نمونه ربات با مدیریت خطا"""
    global bot
    try:
        # حذف سایر نمونه‌های ربات
        kill_other_bot_instances()

        # حذف وب‌هوک‌های قبلی
        temp_bot = telebot.TeleBot(TOKEN)
        temp_bot.remove_webhook()
        time.sleep(0.5)

        # ایجاد نمونه جدید ربات
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
    @bot.message_handler(func=lambda message: 'youtube.com' in message.text or 'youtu.be' in message.text)
    def youtube_link_handler(message):
        try:
            from youtube_downloader import download_video, validate_youtube_url, extract_video_info
            debug_msg = bot.reply_to(message, "🔄 در حال پردازش لینک...")

            url = message.text.strip()
            if not validate_youtube_url(url):
                bot.edit_message_text("❌ لینک نامعتبر است", message.chat.id, debug_msg.message_id)
                return

            video_info = extract_video_info(url)
            if not video_info:
                bot.edit_message_text("❌ خطا در دریافت اطلاعات ویدیو", message.chat.id, debug_msg.message_id)
                return

            bot.edit_message_text("⏳ در حال دانلود ویدیو...", message.chat.id, debug_msg.message_id)
            success, file_path, error = download_video(url, int(time.time()), message.from_user.id)

            if success and file_path:
                with open(file_path, 'rb') as video_file:
                    bot.send_video(message.chat.id, video_file, caption=f"✅ دانلود شد\n🎥 {video_info.get('title', '')}")
                os.remove(file_path)  # پاک کردن فایل پس از ارسال
            else:
                error_msg = error.get('error', 'خطای نامشخص') if error else 'خطای نامشخص'
                bot.edit_message_text(f"❌ {error_msg}", message.chat.id, debug_msg.message_id)

        except Exception as e:
            error_msg = str(e)
            detailed_error = traceback.format_exc()
            logger.error(f"Error processing YouTube link: {detailed_error}")

            if "Invalid URL" in error_msg:
                error_response = "❌ لینک نامعتبر است. لطفاً یک لینک معتبر یوتیوب ارسال کنید."
            elif "Video unavailable" in error_msg:
                error_response = "❌ این ویدیو در دسترس نیست یا خصوصی است."
            elif "Sign in" in error_msg:
                error_response = "❌ این ویدیو نیاز به ورود به حساب کاربری دارد."
            else:
                error_response = f"⚠️ خطا در پردازش لینک:\n{error_msg}"

            bot.edit_message_text(
                error_response,
                message.chat.id,
                debug_msg.message_id
            )

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
                from server_status import generate_server_status
                try:
                    bot.answer_callback_query(call.id)
                    status_text = generate_server_status()
                    bot.edit_message_text(
                        status_text,
                        call.message.chat.id,
                        call.message.message_id,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"خطا در نمایش وضعیت سرور: {e}")
                    bot.answer_callback_query(call.id, "⚠️ خطا در دریافت وضعیت سرور")
        except Exception as e:
            logger.error(f"خطا در پردازش callback: {e}")
            try:
                bot.answer_callback_query(call.id, "⚠️ خطایی رخ داد")
            except:
                pass

def generate_server_status():
    #  This function needs to be implemented to get the actual server status.
    #  Replace this with your logic to check server resources, etc.
    return "📈 سرور در حال اجرا است.  CPU: 50%, Memory: 75%"


from debug_handler import debugger

def main():
    """تابع اصلی اجرای ربات"""
    global bot
    try:
        logger.info("شروع راه‌اندازی ربات...")

        # تنظیم مدیریت خطای سراسری
        def handle_exception(exc_type, exc_value, exc_traceback):
            logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

        sys.excepthook = handle_exception

        # ایجاد نمونه جدید ربات
        bot = telebot.TeleBot(TOKEN)

        # تنظیم هندلرهای ربات
        setup_bot_handlers()

        # تست اتصال
        bot.get_me()
        logger.info("ربات با موفقیت به سرور تلگرام متصل شد")

        # راه‌اندازی ربات با تنظیمات بهینه
        bot.infinity_polling(timeout=60, long_polling_timeout=60)

    except Exception as e:
        logger.error(f"خطا در اجرای ربات: {str(e)}")
        logger.info("تلاش مجدد برای اتصال در 10 ثانیه...")
        time.sleep(10)
        main()  # تلاش مجدد

if __name__ == "__main__":
    main()