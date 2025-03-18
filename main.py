import os
import sys
import logging
import time
import threading
import json
import traceback
import platform
import psutil
from datetime import datetime
from flask import Flask, jsonify, render_template, redirect, url_for, request

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

# بررسی توکن تلگرام قبل از وارد کردن ماژول بات
def check_telegram_token():
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("⚠️ متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم نشده است!")
        return False, "توکن تلگرام تنظیم نشده است"

    # بررسی فرمت توکن (باید شامل کولون باشد و بخش اول آن عدد باشد)
    if ":" not in token:
        logger.error("⚠️ فرمت توکن معتبر نیست (باید شامل کولون (:) باشد)")
        return False, "فرمت توکن تلگرام نامعتبر است - کولون یافت نشد"

    # تلاش برای تبدیل بخش اول توکن به عدد صحیح (برای اطمینان از صحت فرمت)
    try:
        int(token.split(':')[0])
        return True, None
    except ValueError:
        logger.error("⚠️ بخش اول توکن باید یک عدد صحیح باشد")
        return False, "فرمت توکن تلگرام نامعتبر است - بخش اول باید عدد باشد"

# بررسی توکن
token_valid, token_error = check_telegram_token()
if not token_valid:
    logger.error(f"⚠️ خطا در توکن تلگرام: {token_error}")
    print(f"⚠️ برنامه به دلیل خطا در توکن تلگرام متوقف می‌شود: {token_error}")
    sys.exit(1)

# وارد کردن ماژول‌های بات 
from bot import start_bot, TOKEN
from server_status import get_cached_server_status, generate_server_status

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
def index():
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

# صفحه وضعیت سیستم
@app.route('/status')
def status():
    update_bot_status()

    # اطلاعات سیستم
    try:
        # تبدیل بایت به فرمت قابل خواندن
        def format_bytes(bytes_value):
            """تبدیل بایت به فرمت قابل خواندن برای انسان"""
            suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
            index = 0
            while bytes_value >= 1024 and index < len(suffixes) - 1:
                bytes_value /= 1024
                index += 1
            return f"{bytes_value:.2f} {suffixes[index]}"

        # ساختار اطلاعات سیستم
        system = {
            "os": {
                "system": platform.system(),
                "release": platform.release(),
                "architecture": platform.machine(),
                "python_version": platform.python_version()
            },
            "cpu": {
                "usage_percent": psutil.cpu_percent(interval=0.1),
                "cores": psutil.cpu_count(logical=True)
            },
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "used": psutil.virtual_memory().used,
                "percent_used": psutil.virtual_memory().percent,
                "total_human": format_bytes(psutil.virtual_memory().total),
                "used_human": format_bytes(psutil.virtual_memory().used)
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "used": psutil.disk_usage('/').used,
                "free": psutil.disk_usage('/').free,
                "percent_used": psutil.disk_usage('/').percent,
                "total_human": format_bytes(psutil.disk_usage('/').total),
                "free_human": format_bytes(psutil.disk_usage('/').free)
            },
            "uptime": {
                "seconds": int(time.time() - psutil.boot_time()),
                "uptime_human": "",
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
            },
            "process": {
                "this_process": {
                    "pid": os.getpid(),
                    "memory_usage": format_bytes(psutil.Process(os.getpid()).memory_info().rss),
                    "threads_count": len(psutil.Process(os.getpid()).threads())
                }
            },
            "network": {
                "connections": len(psutil.net_connections()),
                "bytes_sent": format_bytes(psutil.net_io_counters().bytes_sent),
                "bytes_recv": format_bytes(psutil.net_io_counters().bytes_recv)
            },
            "server": {
                "hostname": platform.node(),
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": time.tzname[0],
                "active_threads": threading.active_count()
            }
        }

        # فرمت زمان کارکرد
        uptime_seconds = system["uptime"]["seconds"]
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60

        if days > 0:
            system["uptime"]["uptime_human"] = f"{days} روز و {hours} ساعت"
        elif hours > 0:
            system["uptime"]["uptime_human"] = f"{hours} ساعت و {minutes} دقیقه"
        else:
            system["uptime"]["uptime_human"] = f"{minutes} دقیقه و {seconds} ثانیه"

    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات سیستم: {e}")
        system = {}

    # دانلودهای فعال - در اینجا یک دیکشنری خالی برمی‌گردانیم چون هنوز API دانلودها پیاده‌سازی نشده
    active_downloads = {}

    # کاربران - فعلاً لیست خالی
    users = []
    user_count = 0

    # دانلودها - فعلاً لیست خالی
    downloads = []

    return render_template('status.html', 
                          bot_status=bot_status, 
                          system=system,
                          active_downloads=active_downloads,
                          users=users,
                          user_count=user_count,
                          downloads=downloads)

# بررسی سلامت سرور
@app.route('/ping')
def ping():
    return "سرور فعال است!", 200

# اجرای ربات در یک ترد جداگانه
def run_bot():
    max_retries = 5
    retry_delay = 10  # seconds
    retry_count = 0

    while retry_count < max_retries:
        try:
            bot_status["running"] = True
            with open(SERVER_STATUS_FILE, 'w', encoding='utf-8') as f:
                json.dump({"is_bot_running": True}, f)
            
            if start_bot():
                logger.info("🚀 ربات تلگرام با موفقیت راه‌اندازی شد!")
                return True
            else:
                raise Exception("خطا در راه‌اندازی اولیه ربات")

        except Exception as e:
            retry_count += 1
            logger.error(f"⚠️ خطا در راه‌اندازی ربات (تلاش {retry_count}/{max_retries}): {e}")
            bot_status["running"] = False
            
            if retry_count < max_retries:
                logger.info(f"🔄 تلاش مجدد در {retry_delay} ثانیه...")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # Increase delay for next retry
            else:
                logger.error("❌ تمام تلاش‌ها برای راه‌اندازی ربات ناموفق بود")
                return False

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
    debug_log(f"درخواست وب‌هوک دریافت شد با توکن مخفی {token[:3]}...", "INFO")

    # مقایسه با توکن واقعی با مدیریت خطای پیشرفته
    try:
        real_token = os.environ.get('TELEGRAM_BOT_TOKEN')

        # بررسی وجود توکن
        if not real_token:
            debug_log("⚠️ متغیر محیطی TELEGRAM_BOT_TOKEN در دسترس نیست", "ERROR")
            return "خطای پیکربندی سرور (توکن یافت نشد)", 500

        # توکن معتبر است
        if token == real_token:
            debug_log("درخواست وب‌هوک معتبر تأیید شد", "INFO")

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
        # توکن نامعتبر است
        else:
            # برای امنیت بیشتر، تمام توکن را نمایش نمی‌دهیم
            masked_token = token[:5] + "..." if len(token) > 5 else token
            debug_log("درخواست وب‌هوک با توکن نامعتبر رد شد", "WARNING", {
                "masked_token": masked_token
            })
            return 'Forbidden', 403

    except Exception as outer_error:
        # خطای کلی در پردازش درخواست
        error_details = format_exception_with_context(outer_error)
        debug_log("خطای کلی در پردازش درخواست وب‌هوک", "ERROR", {
            "error_type": type(outer_error).__name__,
            "error_message": str(outer_error),
            "traceback": error_details
        })

        # در صورت خطای کلی، کد 500 برمی‌گردانیم
        return f"Internal Server Error: {str(outer_error)}", 500

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
@debug_decorator
def simulate_webhook():
    from bot import webhook, bot, ADMIN_CHAT_ID
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')

    if not token:
        debug_log("خطا در شبیه‌سازی وب‌هوک: توکن ربات یافت نشد", "ERROR")
        return jsonify({"error": "توکن ربات یافت نشد"}), 500

    try:
        debug_log("شروع شبیه‌سازی وب‌هوک", "INFO")

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
        debug_log("پیام تست آماده شد", "DEBUG", {
            "message": test_message
        })

        # ارسال پیام درست به ادمین
        try:
            bot.send_message(ADMIN_CHAT_ID, "🔄 در حال اجرای وب‌هوک شبیه‌سازی شده...")
            debug_log("پیام اطلاع‌رسانی به ادمین ارسال شد", "INFO")
        except Exception as notify_error:
            debug_log("خطا در ارسال پیام به ادمین", "ERROR", {
                "error": str(notify_error)
            })

        # شبیه‌سازی درخواست POST به وب‌هوک
        import requests

        # آدرس وب‌هوک
        webhook_url = f"https://telegram-production-cc29.up.railway.app/{token}/"
        debug_log("آدرس وب‌هوک", "DEBUG", {
            "url": webhook_url.replace(token, "***TOKEN***"),
        })

        # ارسال درخواست
        debug_log("ارسال درخواست POST به وب‌هوک", "INFO")
        response = requests.post(webhook_url, json=test_message)

        # نتیجه
        result = {
            "status": "ok" if response.status_code == 200 else "error",
            "url": webhook_url.replace(token, "***TOKEN***"),
            "response_code": response.status_code,
            "response_text": response.text,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        debug_log("شبیه‌سازی وب‌هوک انجام شد", "INFO", {
            "status": result["status"],
            "response_code": result["response_code"]
        })

        return jsonify(result)
    except Exception as e:
        error_details = format_exception_with_context(e)
        debug_log("خطا در شبیه‌سازی وب‌هوک", "ERROR", {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": error_details
        })

        return jsonify({
            "status": "error",
            "error": str(e),
            "details": error_details,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }), 500

# مسیر برای بررسی وضعیت ربات و اطلاعات آن
@app.route('/bot-check', methods=['GET'])
@debug_decorator
def bot_check():
    from bot import bot  # واردکردن ربات
    bot_info = None

    debug_log("درخواست بررسی وضعیت ربات دریافت شد", "INFO")

    try:
        # تلاش برای دریافت اطلاعات از تلگرام
        debug_log("در حال دریافت اطلاعات ربات از API تلگرام", "DEBUG")
        bot_info = bot.get_me()

        bot_status = {
            "id": bot_info.id,
            "username": bot_info.username,
            "first_name": bot_info.first_name,
            "is_bot": bot_info.is_bot,
            "can_receive_messages": True
        }
        status_code = 200

        debug_log("اطلاعات ربات با موفقیت دریافت شد", "INFO", {
            "bot_username": bot_info.username,
            "bot_id": bot_info.id
        })
    except Exception as e:
        # در صورت خطا
        error_details = format_exception_with_context(e)
        debug_log("خطا در دریافت اطلاعات ربات", "ERROR", {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": error_details
        })

        bot_status = {
            "error": str(e),
            "is_connected": False,
            "traceback": error_details
        }
        status_code = 500

    # اطلاعات محیط اجرا
    environment = {
        "webhook_mode": os.environ.get('WEBHOOK_MODE', 'true'),
        "port": os.environ.get('PORT', '5000'),
        "has_token": bool(os.environ.get('TELEGRAM_BOT_TOKEN', ''))
    }

    debug_log("اطلاعات محیط اجرا", "DEBUG", {
        "environment": environment
    })

    # برگرداندن اطلاعات
    result = {
        "status": "ok" if bot_info else "error",
        "bot": bot_status,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "environment": environment
    }

    debug_log("پاسخ بررسی وضعیت ربات ارسال شد", "INFO", {
        "status": result["status"],
        "timestamp": result["timestamp"]
    })

    return jsonify(result), status_code

# مسیر برای ارسال پیام آزمایشی به ادمین
@app.route('/send-test-message', methods=['GET'])
@debug_decorator
def send_test_message():
    from bot import bot, ADMIN_CHAT_ID, notify_admin  # واردکردن ربات و آیدی ادمین

    debug_log("درخواست ارسال پیام آزمایشی به ادمین دریافت شد", "INFO")

    try:
        # تلاش برای ارسال پیام آزمایشی به ادمین
        message = f"🔄 پیام آزمایشی: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        debug_log("در حال ارسال پیام آزمایشی", "DEBUG", {
            "message": message,
            "admin_chat_id": ADMIN_CHAT_ID
        })

        # روش اول: مستقیم با تابع ربات
        result = bot.send_message(ADMIN_CHAT_ID, message)
        message_id = result.message_id
        debug_log("پیام با موفقیت ارسال شد", "INFO", {
            "message_id": message_id
        })

        # روش دوم: استفاده از تابع notify_admin
        notify_admin("📢 یک پیام آزمایشی با تابع notify_admin")
        debug_log("پیام اطلاع‌رسانی با موفقیت ارسال شد", "INFO")

        response = {
            "status": "ok",
            "message": "پیام آزمایشی با موفقیت ارسال شد",
            "message_id": message_id,
            "admin_chat_id": ADMIN_CHAT_ID,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        debug_log("پاسخ ارسال پیام آزمایشی آماده شد", "INFO", {
            "status": "ok",
            "timestamp": response["timestamp"]
        })

        return jsonify(response)
    except Exception as e:
        # در صورت خطا
        error_details = format_exception_with_context(e)
        debug_log("خطا در ارسال پیام آزمایشی", "ERROR", {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": error_details
        })

        response = {
            "status": "error",
            "error": str(e),
            "details": error_details,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        return jsonify(response), 500

# اجرای سرور Flask
if __name__ == "__main__":
    logger.info("🚀 راه‌اندازی سرور وب داشبورد...")
    port = int(os.environ.get("PORT", 5000))  # استفاده از پورت متغیر محیطی
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)