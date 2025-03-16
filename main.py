import os
import sys
import time
import threading
import logging
from flask import Flask, request, jsonify, render_template, redirect, url_for

# تنظیم لاگینگ اصلی
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# استفاده از try-except برای اطمینان از بارگذاری ماژول‌ها
try:
    import telebot
    from telebot import types
except ImportError:
    logger.error("⚠️ ماژول telebot نصب نشده است")
    sys.exit(1)

# واردکردن ماژول‌های داخلی
try:
    from debug_logger import debug_log, debug_decorator
    from config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_HOST, WEBHOOK_PORT, ADMIN_IDS
    from database import initialize_database
    from bot_handlers import register_handlers, webhook, bot
    from utils import setup_bot, check_dependencies, scheduled_tasks
except ImportError as e:
    logger.error(f"⚠️ خطا در بارگذاری ماژول‌های داخلی: {e}")
    sys.exit(1)

# ایجاد اپلیکیشن فلسک
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key_for_development_only")

# مسیرها و روت‌های فلسک
@app.route('/')
def index():
    """صفحه اصلی وب"""
    return render_template('index.html')

@app.route('/status')
def status():
    """صفحه وضعیت سیستم"""
    try:
        from system_info import get_system_info
        from youtube_downloader import get_all_active_downloads
        from database import get_all_users, get_all_downloads
        
        # دریافت اطلاعات سیستم
        sys_info = get_system_info()
        
        # دریافت اطلاعات دانلودهای فعال
        active_downloads = get_all_active_downloads()
        
        # دریافت آمار کاربران
        users = get_all_users(limit=10)
        user_count = len(get_all_users(limit=1000))
        
        # دریافت آمار دانلودها
        recent_downloads = get_all_downloads(limit=10)
        download_count = len(get_all_downloads(limit=1000))
        
        return render_template(
            'status.html',
            system=sys_info,
            active_downloads=active_downloads,
            users=users,
            user_count=user_count,
            downloads=recent_downloads,
            download_count=download_count
        )
    except Exception as e:
        logger.error(f"خطا در صفحه وضعیت: {str(e)}")
        return f"خطا در نمایش وضعیت: {str(e)}", 500

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """مسیر دریافت وب‌هوک تلگرام"""
    return webhook()

@app.route('/setup_webhook', methods=['GET'])
def setup_webhook_route():
    """تنظیم مجدد وب‌هوک"""
    try:
        result = setup_bot(bot, WEBHOOK_URL)
        return jsonify({'success': True, 'message': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/health')
def health_check():
    """بررسی سلامت سرویس"""
    return jsonify({'status': 'ok', 'timestamp': time.time()})

@debug_decorator
def main():
    """تابع اصلی برنامه"""
    # بررسی وابستگی‌ها
    check_dependencies()
    
    # راه‌اندازی پایگاه داده
    initialize_database()
    
    # اطلاع‌رسانی به ادمین
    admin_id = ADMIN_IDS[0] if ADMIN_IDS else None
    
    try:
        if admin_id:
            bot.send_message(admin_id, "🤖 ربات یوتیوب دانلودر با موفقیت راه‌اندازی شد!")
    except Exception as e:
        logger.error(f"خطا در ارسال پیام به ادمین: {e}")
    
    # ثبت هندلرهای ربات
    register_handlers(bot)
    
    # تنظیم وب‌هوک
    if WEBHOOK_URL:
        setup_bot(bot, WEBHOOK_URL)
        logger.info(f"🔄 وب‌هوک با آدرس {WEBHOOK_URL} تنظیم شد")
    else:
        logger.warning("⚠️ آدرس وب‌هوک تنظیم نشده است. استفاده از حالت پولینگ...")
    
    # راه‌اندازی ترد وظایف زمان‌بندی شده
    scheduler_thread = threading.Thread(target=scheduled_tasks, daemon=True)
    scheduler_thread.start()
    
    return app

if __name__ == "__main__":
    # راه‌اندازی برنامه اصلی
    app = main()
    
    # راه‌اندازی فلسک
    debug_log("در حال راه‌اندازی سرور وب...", "INFO")
    app.run(host=WEBHOOK_HOST, port=WEBHOOK_PORT, debug=True)
