import os
import sys
import logging
import time
import importlib.util

# تنظیم لاگر
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('telegram_bot.log')
    ]
)
logger = logging.getLogger(__name__)

def is_instagram_url(url: str) -> bool:
    """بررسی اعتبار لینک اینستاگرام"""
    return 'instagram.com' in url and ('/p/' in url or '/reel/' in url or '/tv/' in url)

def process_instagram_url(message, url):
    """پردازش لینک اینستاگرام و دانلود آن"""
    try:
        # وارد کردن telegram-main/run_bot.py
        spec = importlib.util.spec_from_file_location("run_bot", "telegram-main/run_bot.py")
        run_bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run_bot)
        
        # فراخوانی تابع process_instagram_url از ماژول وارد شده
        run_bot.process_instagram_url(message, url)
        
    except Exception as e:
        logger.error(f"خطا در پردازش لینک اینستاگرام: {str(e)}")
        # بررسی وجود نشانی debug_msg
        if hasattr(message, 'reply_to') and callable(message.reply_to):
            message.reply_to(f"⚠️ خطا در پردازش لینک اینستاگرام: {str(e)}")

def main():
    """راه‌اندازی ربات تلگرام"""
    try:
        # وارد کردن telegram-main/run_bot.py به صورت مستقیم
        sys.path.append("telegram-main")
        # از importlib استفاده می‌کنیم چون نام دایرکتوری حاوی کاراکتر منهای میانی (-) است
        spec = importlib.util.spec_from_file_location("run_bot", "telegram-main/run_bot.py")
        run_bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run_bot)
        
        # اجرای تابع اصلی
        main_bot = run_bot.main
        
        # اجرای تابع اصلی
        main_bot()
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {str(e)}")
        logger.info("تلاش مجدد در 10 ثانیه...")
        time.sleep(10)
        main()

if __name__ == "__main__":
    main()