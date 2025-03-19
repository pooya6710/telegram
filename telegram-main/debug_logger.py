import os
import sys
import logging
import time
import json
import traceback
import inspect
import datetime
from functools import wraps

# تنظیم لاگر با فرمت کامل و سطح DEBUG
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

# لاگر اصلی برنامه
logger = logging.getLogger("telegram_bot_debug")
logger.setLevel(logging.DEBUG)

# مسیر فایل لاگ
LOG_FILE = os.path.join(os.path.dirname(__file__), "debug_logs.txt")

# تنظیمات دیباگینگ
DEBUG_CONFIG = {
    "enabled": True,               # فعال‌سازی دیباگر
    "log_to_file": True,           # ذخیره لاگ‌ها در فایل
    "log_to_console": True,        # نمایش لاگ‌ها در کنسول
    "log_level": "DEBUG",          # سطح لاگینگ (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    "log_webhooks": True,          # لاگ کردن جزئیات وب‌هوک‌ها
    "log_telegram_updates": True,  # لاگ کردن آپدیت‌های تلگرام
    "log_api_calls": True,         # لاگ کردن فراخوانی‌های API
    "log_request_data": True,      # لاگ کردن داده‌های درخواست‌ها
}

def debug_log(message, level="DEBUG", context=None):
    """
    ثبت پیام لاگ با جزئیات بیشتر

    Args:
        message: پیام لاگ
        level: سطح لاگ (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        context: اطلاعات اضافی برای لاگ
    """
    if not DEBUG_CONFIG["enabled"]:
        return

    try:
        # اطلاعات فریم اجرایی فعلی
        frame = inspect.currentframe()
        func_name = frame.f_back.f_code.co_name if frame and frame.f_back else "unknown"
        file_name = frame.f_back.f_code.co_filename if frame and frame.f_back else "unknown"
        line_num = frame.f_back.f_lineno if frame and frame.f_back else 0

        # ساخت پیام لاگ با جزئیات
        log_entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": message,
            "location": {
                "file": os.path.basename(file_name),
                "function": func_name,
                "line": line_num
            }
        }

        if context:
            log_entry["context"] = context

        # تبدیل به JSON
        log_message = json.dumps(log_entry, ensure_ascii=False, indent=2)

        # لاگ با سطح مناسب
        if DEBUG_CONFIG["log_to_console"]:
            log_level = getattr(logging, level.upper(), logging.DEBUG)
            logger.log(log_level, log_message)

        # نوشتن به فایل
        if DEBUG_CONFIG["log_to_file"]:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{log_message}\n{'='*50}\n")

    except Exception as e:
        logger.error(f"Error in debug_log: {str(e)} - Original message: {message}")

def log_webhook_request(data):
    """لاگ کردن درخواست‌های وب‌هوک"""
    if not DEBUG_CONFIG["enabled"] or not DEBUG_CONFIG["log_webhooks"]:
        return

    try:
        if isinstance(data, bytes):
            data_str = data.decode('utf-8')
        else:
            data_str = str(data)

        try:
            json_data = json.loads(data_str)
            debug_log("درخواست وب‌هوک دریافت شد", "INFO", {
                "webhook_data": json_data
            })
        except json.JSONDecodeError:
            debug_log("درخواست وب‌هوک دریافت شد (غیر JSON)", "INFO", {
                "webhook_data": data_str[:500]
            })
    except Exception as e:
        debug_log(f"خطا در لاگ کردن درخواست وب‌هوک: {e}", "ERROR")

def log_telegram_update(update):
    """لاگ کردن آپدیت‌های تلگرام"""
    if not DEBUG_CONFIG["enabled"] or not DEBUG_CONFIG["log_telegram_updates"]:
        return

    try:
        update_dict = {}
        if hasattr(update, 'message'):
            update_dict["message_id"] = update.message.message_id
            update_dict["chat_id"] = update.message.chat.id
            update_dict["text"] = update.message.text
        elif hasattr(update, 'callback_query'):
            update_dict["callback_id"] = update.callback_query.id
            update_dict["data"] = update.callback_query.data

        debug_log("آپدیت تلگرام دریافت شد", "INFO", update_dict)
    except Exception as e:
        debug_log(f"خطا در لاگ کردن آپدیت تلگرام: {e}", "ERROR")

def debug_decorator(func):
    """دکوراتور برای لاگ کردن اجرای توابع"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            debug_log(f"اجرای {func.__name__}", "DEBUG", {
                "execution_time": f"{execution_time:.4f}s",
                "result": str(result)[:100]
            })
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            debug_log(f"خطا در {func.__name__}", "ERROR", {
                "execution_time": f"{execution_time:.4f}s",
                "error": str(e)
            })
            raise
    return wrapper

def format_exception_with_context(e):
    """فرمت‌بندی خطا با اطلاعات کامل"""
    error_details = {
        "error_type": type(e).__name__,
        "error_message": str(e),
        "traceback": traceback.format_exc(),
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return json.dumps(error_details, ensure_ascii=False, indent=2)