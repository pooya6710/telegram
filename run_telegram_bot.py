import os
import sys
import logging

# تنظیم مسیر برای دسترسی به فایل‌های پروژه
current_dir = os.path.dirname(os.path.abspath(__file__))
telegram_main_dir = os.path.join(current_dir, "telegram-main")
sys.path.insert(0, telegram_main_dir)

# تنظیم لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تلاش برای وارد کردن ماژول‌های مورد نیاز
try:
    from bot_handlers import register_handlers, bot
    from youtube_downloader import validate_youtube_url, extract_video_info, clean_old_downloads
    from debug_logger import debug_log
except ImportError as e:
    logger.error(f"خطا در وارد کردن ماژول‌ها: {e}")
    sys.exit(1)

def is_instagram_url(url: str) -> bool:
    """بررسی اعتبار لینک اینستاگرام"""
    return 'instagram.com' in url

def process_instagram_url(message, url):
    """پردازش لینک اینستاگرام و دانلود آن"""
    debug_log(f"شروع پردازش لینک اینستاگرام: {url}", "INFO")
    # کدهای پردازش اینستاگرام در اینجا قرار می‌گیرد

def main():
    """راه‌اندازی ربات تلگرام"""
    try:
        # ثبت هندلرهای ربات
        register_handlers(bot)
        
        # اضافه کردن هندلر برای لینک‌های اینستاگرام
        @bot.message_handler(func=lambda message: is_instagram_url(message.text))
        def instagram_link_handler(message):
            try:
                # ثبت اطلاعات کاربر
                user_id = message.from_user.id
                url = message.text.strip()
                
                # بررسی اعتبار URL
                if not is_instagram_url(url):
                    bot.reply_to(message, "❌ لینک اینستاگرام نامعتبر است.")
                    return
                
                # ارسال پیام در حال پردازش
                processing_msg = bot.reply_to(message, "🔄 در حال پردازش لینک اینستاگرام...")
                
                # پردازش لینک
                debug_log(f"کاربر {user_id} لینک اینستاگرام ارسال کرده است: {url}", "INFO")
                
                # اینجا منطق پردازش اینستاگرام را اضافه می‌کنیم
                # در نسخه فعلی فقط پیام نمایش می‌دهیم
                bot.edit_message_text(
                    "✅ لینک اینستاگرام شناسایی شد. قابلیت دانلود اینستاگرام در حال پیاده‌سازی است.",
                    chat_id=message.chat.id,
                    message_id=processing_msg.message_id
                )
                
            except Exception as e:
                debug_log(f"خطا در پردازش لینک اینستاگرام: {str(e)}", "ERROR")
                bot.reply_to(message, f"❌ خطا در پردازش لینک اینستاگرام: {str(e)}")
        
        # پاکسازی فایل‌های قدیمی
        clean_old_downloads()
        
        # شروع دریافت پیام‌ها
        logger.info("ربات تلگرام با موفقیت راه‌اندازی شد")
        debug_log("ربات تلگرام راه‌اندازی شد", "INFO")
        bot.infinity_polling()
        
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}")
        debug_log(f"خطا در راه‌اندازی ربات: {str(e)}", "ERROR")

if __name__ == "__main__":
    main()