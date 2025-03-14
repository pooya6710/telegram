import os
import logging
import time
import threading
import json
import traceback
import platform
from datetime import datetime
from flask import Flask, jsonify, render_template, redirect, url_for

# تنظیم لاگر اصلی
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# واردکردن ماژول‌های داخلی
try:
    # سیستم لاگینگ پیشرفته
    from debug_logger import debug_log, log_webhook_request, log_telegram_update, debug_decorator, format_exception_with_context
    logger.info("✅ سیستم دیباگینگ پیشرفته در main.py با موفقیت بارگذاری شد")
except ImportError as e:
    logger.error(f"⚠️ خطا در بارگذاری ماژول debug_logger: {e}")
    # تعریف توابع جایگزین در صورت عدم دسترسی به ماژول دیباگینگ
    def debug_log(message, level="DEBUG", context=None):
        logger.debug(f"{message} - Context: {context}")
    
    def log_webhook_request(data):
        logger.debug(f"Webhook data: {data[:200] if isinstance(data, str) else str(data)[:200]}...")
    
    def log_telegram_update(update):
        logger.debug(f"Telegram update: {update}")
    
    def debug_decorator(func):
        return func
    
    def format_exception_with_context(e):
        return traceback.format_exc()

# وارد کردن ماژول‌های بات 
from bot import start_bot, get_cached_server_status

# وارد کردن ماژول‌ها با مدیریت خطا
try:
    import psutil
    logger.info("✅ ماژول psutil با موفقیت بارگذاری شد")
except ImportError:
    logger.warning("⚠️ ماژول psutil در دسترس نیست. برخی از قابلیت‌های نمایش وضعیت سیستم غیرفعال خواهند بود.")

# ایجاد اپلیکیشن Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-development')

# وضعیت ربات
bot_status = {
    "running": False,
    "start_time": time.time(),
    "uptime": "0 ساعت و 0 دقیقه",
    "users_count": 0,
    "downloads_count": 0,
    "last_activity": "هنوز فعالیتی ثبت نشده"
}

# مسیر ذخیره‌سازی وضعیت سرور
SERVER_STATUS_FILE = "server_status.json"

# بروزرسانی آمار ربات
def update_bot_status():
    # محاسبه زمان آپتایم
    uptime_seconds = int(time.time() - bot_status["start_time"])
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    bot_status["uptime"] = f"{hours} ساعت و {minutes} دقیقه"
    
    # خواندن اطلاعات ذخیره شده از فایل، اگر وجود داشته باشد
    if os.path.exists(SERVER_STATUS_FILE):
        try:
            with open(SERVER_STATUS_FILE, 'r', encoding='utf-8') as f:
                saved_status = json.load(f)
                # آپدیت آمار از فایل ذخیره شده
                if "users_count" in saved_status:
                    bot_status["users_count"] = saved_status["users_count"]
                if "downloads_count" in saved_status:
                    bot_status["downloads_count"] = saved_status["downloads_count"]
                if "last_activity" in saved_status:
                    bot_status["last_activity"] = saved_status["last_activity"]
                # وضعیت فعال بودن ربات را از سرور بگیر
                server_status = get_cached_server_status()
                if server_status and "is_bot_running" in server_status:
                    bot_status["running"] = server_status["is_bot_running"]
        except Exception as e:
            logger.error(f"خطا در خواندن فایل وضعیت سرور: {e}")

# صفحه اصلی داشبورد
@app.route('/')
def home():
    update_bot_status()
    
    # اطلاعات سیستم
    system_info = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # اضافه کردن اطلاعات با مدیریت خطا
    try:
        system_info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات CPU: {e}")
        system_info["cpu_percent"] = 0
        
    try:
        memory = psutil.virtual_memory()
        system_info["memory"] = {
            "total": round(memory.total / (1024**3), 2),  # به گیگابایت
            "used_percent": memory.percent
        }
    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات حافظه: {e}")
        system_info["memory"] = {
            "total": 0,
            "used_percent": 0
        }
        
    try:
        disk = psutil.disk_usage('/')
        system_info["disk"] = {
            "total": round(disk.total / (1024**3), 2),  # به گیگابایت
            "used_percent": disk.percent
        }
    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات دیسک: {e}")
        system_info["disk"] = {
            "total": 0,
            "used_percent": 0
        }
    
    return render_template('index.html', 
                           bot_status=bot_status, 
                           system_info=system_info)

# صفحه آمار ربات به فرمت JSON
@app.route('/api/status')
def api_status():
    update_bot_status()
    return jsonify(bot_status)

# بررسی سلامت سرور
@app.route('/ping')
def ping():
    return "سرور فعال است!", 200

# اجرای ربات در یک ترد جداگانه
def run_bot():
    try:
        bot_status["running"] = True
        # ذخیره وضعیت در فایل
        with open(SERVER_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"is_bot_running": True}, f)
            
        # اجرای ربات در یک ترد جداگانه
        def bot_runner():
            # تلاش برای اجرا با وب‌هوک
            webhook_success = start_bot()
            if not webhook_success:
                # اگر وب‌هوک موفق نبود، به حالت polling تغییر وضعیت می‌دهیم
                logger.info("⚠️ وب‌هوک با خطا مواجه شد. تغییر به حالت polling...")
                os.environ['WEBHOOK_MODE'] = 'false'
                start_bot()  # اجرای مجدد در حالت polling
        
        bot_thread = threading.Thread(target=bot_runner)
        bot_thread.daemon = True
        bot_thread.start()
        logger.info("🚀 ربات تلگرام با موفقیت راه‌اندازی شد!")
    except Exception as e:
        logger.error(f"⚠️ خطا در راه‌اندازی ربات: {e}")
        bot_status["running"] = False

# راه‌اندازی ربات با استفاده از with app.app_context()
# توجه: در نسخه‌های جدید Flask، before_first_request حذف شده است
# بنابراین از روش دیگری استفاده می‌کنیم
# راه‌اندازی ربات با مدیریت خطا
try:
    with app.app_context():
        try:
            run_bot()
            logger.info("🔄 ربات تلگرام در پس‌زمینه اجرا می‌شود...")
        except Exception as e:
            logger.error(f"⚠️ خطای غیرمنتظره در راه‌اندازی ربات: {e}")
            traceback.print_exc()  # چاپ جزئیات خطا برای دیباگ
except Exception as context_error:
    logger.error(f"⚠️ خطا در کانتکست اپلیکیشن: {context_error}")
    traceback.print_exc()

# مسیر برای دریافت وب‌هوک تلگرام
@app.route('/<path:token>/', methods=['POST'])
@debug_decorator
def webhook_handler(token):
    from bot import webhook
    # مقایسه با توکن واقعی
    real_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if token == real_token:
        debug_log("درخواست وب‌هوک معتبر دریافت شد", "INFO")
        
        # ثبت درخواست وب‌هوک برای تحلیل و دیباگ
        try:
            req_data = request.get_data()
            log_webhook_request(req_data)
        except Exception as req_error:
            debug_log("خطا در ثبت داده‌های وب‌هوک", "ERROR", {
                "error": str(req_error)
            })
            
        # پردازش وب‌هوک
        try:
            result = webhook()
            debug_log("وب‌هوک با موفقیت پردازش شد", "INFO", {
                "result": str(result)
            })
            return result
        except Exception as e:
            error_details = format_exception_with_context(e)
            debug_log("خطا در پردازش وب‌هوک", "ERROR", {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": error_details
            })
            
            # ارسال پیام خطا به ادمین برای بررسی
            from bot import notify_admin
            notify_admin(f"⚠️ خطا در پردازش وب‌هوک:\n{error_details[:3000]}") # محدود کردن طول پیام
            
            return f"خطای سرور: {str(e)}", 500
    else:
        # برای امنیت بیشتر، تمام توکن را نمایش نمی‌دهیم
        masked_token = token[:5] + "..." if len(token) > 5 else token
        debug_log("درخواست وب‌هوک با توکن نامعتبر", "WARNING", {
            "masked_token": masked_token
        })
        return '', 403

# مسیر ساده برای تست وب‌هوک
@app.route('/webhook-test', methods=['GET'])
def webhook_test():
    return jsonify({
        "status": "ok",
        "message": "سرور وب‌هوک فعال است",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

# مسیر برای تست وب‌هوک با شبیه‌سازی پیام تلگرام
@app.route('/simulate-webhook', methods=['GET'])
def simulate_webhook():
    from bot import webhook, bot, ADMIN_CHAT_ID
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    
    if not token:
        return jsonify({"error": "توکن ربات یافت نشد"}), 500
        
    try:
        # یک پیام تست ساده بسازیم که شبیه به فرمت پیام‌های تلگرام باشد
        test_message = {
            "update_id": 123456789,
            "message": {
                "message_id": 123,
                "from": {
                    "id": ADMIN_CHAT_ID,  # آیدی ادمین
                    "first_name": "ادمین",
                    "is_bot": False
                },
                "chat": {
                    "id": ADMIN_CHAT_ID,
                    "first_name": "ادمین",
                    "type": "private"
                },
                "date": int(datetime.now().timestamp()),
                "text": "/start"
            }
        }
        
        # تبدیل به JSON
        json_str = json.dumps(test_message)
        
        # ارسال پیام درست به ادمین
        try:
            bot.send_message(ADMIN_CHAT_ID, "🔄 در حال اجرای وب‌هوک شبیه‌سازی شده...")
        except Exception as e:
            print(f"خطا در ارسال پیام به ادمین: {e}")
            
        # شبیه‌سازی درخواست POST به وب‌هوک
        import requests
        
        # آدرس وب‌هوک
        webhook_url = f"https://telegram-production-cc29.up.railway.app/{token}/"
        
        # ارسال درخواست
        response = requests.post(webhook_url, json=test_message)
        
        # نتیجه
        result = {
            "status": "ok" if response.status_code == 200 else "error",
            "url": webhook_url.replace(token, "***TOKEN***"),
            "response_code": response.status_code,
            "response_text": response.text,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return jsonify(result)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"خطا در شبیه‌سازی وب‌هوک: {error_details}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "details": error_details,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }), 500

# مسیر برای بررسی وضعیت ربات و اطلاعات آن
@app.route('/bot-check', methods=['GET'])
def bot_check():
    from bot import bot  # واردکردن ربات
    bot_info = None
    try:
        # تلاش برای دریافت اطلاعات از تلگرام
        bot_info = bot.get_me()
        bot_status = {
            "id": bot_info.id,
            "username": bot_info.username,
            "first_name": bot_info.first_name,
            "is_bot": bot_info.is_bot,
            "can_receive_messages": True
        }
        status_code = 200
    except Exception as e:
        # در صورت خطا
        bot_status = {
            "error": str(e),
            "is_connected": False,
            "traceback": traceback.format_exc()
        }
        status_code = 500
    
    # برگرداندن اطلاعات
    return jsonify({
        "status": "ok" if bot_info else "error",
        "bot": bot_status,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "environment": {
            "webhook_mode": os.environ.get('WEBHOOK_MODE', 'true'),
            "port": os.environ.get('PORT', '5000'),
            "has_token": bool(os.environ.get('TELEGRAM_BOT_TOKEN', ''))
        }
    }), status_code

# مسیر برای ارسال پیام آزمایشی به ادمین
@app.route('/send-test-message', methods=['GET'])
def send_test_message():
    from bot import bot, ADMIN_CHAT_ID, notify_admin  # واردکردن ربات و آیدی ادمین
    
    try:
        # تلاش برای ارسال پیام آزمایشی به ادمین
        message = f"🔄 پیام آزمایشی: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # روش اول: مستقیم با تابع ربات
        result = bot.send_message(ADMIN_CHAT_ID, message)
        message_id = result.message_id
        
        # روش دوم: استفاده از تابع notify_admin
        notify_admin("📢 یک پیام آزمایشی با تابع notify_admin")
        
        return jsonify({
            "status": "ok",
            "message": "پیام آزمایشی با موفقیت ارسال شد",
            "message_id": message_id,
            "admin_chat_id": ADMIN_CHAT_ID,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        # در صورت خطا
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }), 500

# اجرای سرور Flask
if __name__ == "__main__":
    logger.info("🚀 راه‌اندازی سرور وب داشبورد...")
    port = int(os.environ.get("PORT", 5000))  # استفاده از پورت متغیر محیطی
    app.run(host="0.0.0.0", port=port)
