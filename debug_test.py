
import os
import telebot
import logging
from datetime import datetime

# تنظیم لاگینگ
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_imports():
    """تست وارد کردن کتابخانه‌های اصلی"""
    try:
        import telebot
        import yt_dlp
        import psutil
        import flask
        import requests
        logger.info("✅ تمام کتابخانه‌ها با موفقیت بارگذاری شدند")
        return True
    except ImportError as e:
        logger.error(f"❌ خطا در بارگذاری کتابخانه: {str(e)}")
        return False

def test_bot_token():
    """تست توکن ربات"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        try:
            bot = telebot.TeleBot(token)
            bot_info = bot.get_me()
            logger.info(f"✅ اتصال به ربات موفق: {bot_info.username}")
            return True
        except Exception as e:
            logger.error(f"❌ خطا در اتصال به ربات: {str(e)}")
            return False
    else:
        logger.error("❌ توکن ربات تنظیم نشده است")
        return False

if __name__ == "__main__":
    print("🔍 شروع تست دیباگ...")
    
    if test_imports():
        print("✅ تست کتابخانه‌ها: موفق")
    else:
        print("❌ تست کتابخانه‌ها: ناموفق")
        
    if test_bot_token():
        print("✅ تست توکن ربات: موفق")
    else:
        print("❌ تست توکن ربات: ناموفق")
