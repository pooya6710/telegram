import os
import sys
import time
import json
import logging
import traceback
import inspect
from datetime import datetime
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
LOG_FILE = "debug_logs.txt"

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


def setup_file_handler():
    """تنظیم هندلر فایل برای ذخیره لاگ‌ها"""
    if DEBUG_CONFIG["log_to_file"]:
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(getattr(logging, DEBUG_CONFIG["log_level"]))
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)


setup_file_handler()


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

    # اطلاعات فریم اجرایی فعلی
    frame = inspect.currentframe().f_back
    func_name = frame.f_code.co_name
    file_name = frame.f_code.co_filename
    line_num = frame.f_lineno
    
    # ساخت پیام لاگ با جزئیات
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "level": level,
        "message": message,
        "location": {
            "file": os.path.basename(file_name),
            "function": func_name,
            "line": line_num
        }
    }
    
    # افزودن اطلاعات زمینه اگر ارائه شده باشد
    if context:
        log_entry["context"] = context
        
    # تبدیل به رشته JSON برای خوانایی بهتر
    log_message = json.dumps(log_entry, ensure_ascii=False, indent=2)
    
    # لاگ با سطح مناسب
    if DEBUG_CONFIG["log_to_console"]:
        log_func = getattr(logger, level.lower())
        log_func(log_message)

    # نوشتن به فایل اگر فعال باشد
    if DEBUG_CONFIG["log_to_file"]:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{log_message}\n{'='*50}\n")


def log_webhook_request(data):
    """
    لاگ کردن درخواست‌های وب‌هوک با جزئیات کامل
    
    Args:
        data: داده‌های درخواست وب‌هوک
    """
    if not DEBUG_CONFIG["enabled"] or not DEBUG_CONFIG["log_webhooks"]:
        return
        
    try:
        # تلاش برای تبدیل به دیکشنری JSON
        if isinstance(data, bytes):
            data_str = data.decode('utf-8')
        else:
            data_str = str(data)
            
        try:
            # تلاش برای تجزیه JSON
            json_data = json.loads(data_str)
            debug_log("درخواست وب‌هوک دریافت شد", "INFO", {
                "webhook_data": json_data,
                "data_type": "JSON",
                "data_size": len(data_str)
            })
        except json.JSONDecodeError:
            # اگر JSON نباشد، رشته را لاگ کن
            debug_log("درخواست وب‌هوک دریافت شد (غیر JSON)", "INFO", {
                "webhook_data": data_str[:500] + ("..." if len(data_str) > 500 else ""),
                "data_type": "String",
                "data_size": len(data_str)
            })
    except Exception as e:
        debug_log(f"خطا در لاگ کردن درخواست وب‌هوک: {e}", "ERROR", {
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        })


def log_telegram_update(update):
    """
    لاگ کردن آپدیت‌های تلگرام با جزئیات
    
    Args:
        update: آبجکت Update تلگرام
    """
    if not DEBUG_CONFIG["enabled"] or not DEBUG_CONFIG["log_telegram_updates"]:
        return
        
    try:
        update_dict = {}
        # استخراج اطلاعات مهم از آپدیت
        if hasattr(update, 'update_id'):
            update_dict["update_id"] = update.update_id
            
        if hasattr(update, 'message') and update.message:
            update_dict["message"] = {
                "message_id": update.message.message_id,
                "chat_id": update.message.chat.id,
                "user_id": update.message.from_user.id if update.message.from_user else None,
                "username": update.message.from_user.username if update.message.from_user else None,
                "text": update.message.text if hasattr(update.message, 'text') else None,
                "date": update.message.date.strftime("%Y-%m-%d %H:%M:%S") if update.message.date else None,
            }
            
        elif hasattr(update, 'callback_query') and update.callback_query:
            update_dict["callback_query"] = {
                "id": update.callback_query.id,
                "chat_id": update.callback_query.message.chat.id if update.callback_query.message else None,
                "user_id": update.callback_query.from_user.id,
                "username": update.callback_query.from_user.username,
                "data": update.callback_query.data,
            }
            
        debug_log("آپدیت تلگرام دریافت شد", "INFO", {
            "update": update_dict
        })
    except Exception as e:
        debug_log(f"خطا در لاگ کردن آپدیت تلگرام: {e}", "ERROR", {
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        })


def log_api_call(func_name, args, kwargs, result=None, error=None):
    """
    لاگ کردن فراخوانی‌های API با جزئیات
    
    Args:
        func_name: نام تابع API
        args: آرگومان‌های موقعیتی
        kwargs: آرگومان‌های کلید-مقدار
        result: نتیجه فراخوانی (اختیاری)
        error: خطا در صورت وجود (اختیاری)
    """
    if not DEBUG_CONFIG["enabled"] or not DEBUG_CONFIG["log_api_calls"]:
        return
        
    # حذف اطلاعات حساس مانند توکن
    safe_args = []
    for arg in args:
        if isinstance(arg, str) and len(arg) > 30:
            safe_args.append(arg[:5] + "..." + arg[-5:])
        else:
            safe_args.append(arg)
            
    safe_kwargs = {}
    for key, value in kwargs.items():
        if key.lower() in ["token", "api_key", "secret"] or "token" in key.lower():
            safe_kwargs[key] = "***REDACTED***"
        elif isinstance(value, str) and len(value) > 30:
            safe_kwargs[key] = value[:5] + "..." + value[-5:]
        else:
            safe_kwargs[key] = value
    
    log_data = {
        "function": func_name,
        "args": safe_args,
        "kwargs": safe_kwargs
    }
    
    if result is not None:
        # فقط بخشی از نتیجه را لاگ می‌کنیم تا لاگ خیلی بزرگ نشود
        if hasattr(result, '__dict__'):
            log_data["result"] = str(result)[:100] + ("..." if len(str(result)) > 100 else "")
        else:
            log_data["result"] = str(result)[:100] + ("..." if len(str(result)) > 100 else "")
    
    if error is not None:
        log_data["error"] = {
            "type": type(error).__name__, 
            "message": str(error),
            "traceback": traceback.format_exc()
        }
        debug_log(f"خطا در فراخوانی API: {func_name}", "ERROR", log_data)
    else:
        debug_log(f"فراخوانی API: {func_name}", "DEBUG", log_data)


def debug_decorator(func):
    """
    دکوراتور برای لاگ کردن ورودی‌ها و خروجی‌های توابع
    
    Args:
        func: تابعی که باید لاگ شود
    
    Returns:
        تابع بسته‌بندی شده با قابلیت لاگینگ
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not DEBUG_CONFIG["enabled"]:
            return func(*args, **kwargs)
            
        debug_log(f"شروع اجرای {func.__name__}", "DEBUG", {
            "args": str(args),
            "kwargs": str(kwargs)
        })
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            debug_log(f"پایان اجرای {func.__name__}", "DEBUG", {
                "execution_time": f"{execution_time:.4f} seconds",
                "result": str(result)[:100] + ("..." if str(result) and len(str(result)) > 100 else "")
            })
            
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            
            debug_log(f"خطا در اجرای {func.__name__}", "ERROR", {
                "execution_time": f"{execution_time:.4f} seconds",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            })
            
            raise
    
    return wrapper


def format_exception_with_context(e):
    """
    فرمت‌بندی استثناها با اطلاعات بافت کامل
    
    Args:
        e: استثنای ایجاد شده
    
    Returns:
        رشته فرمت‌بندی شده از استثنا با اطلاعات اضافی
    """
    exc_type, exc_value, exc_traceback = sys.exc_info()
    
    # استخراج زنجیره کامل فراخوانی
    stack_trace = traceback.extract_tb(exc_traceback)
    
    # ساخت پیام خطا با جزئیات کامل
    error_details = {
        "error_type": exc_type.__name__,
        "error_message": str(exc_value),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stack_trace": []
    }
    
    for frame in stack_trace:
        error_details["stack_trace"].append({
            "file": frame.filename,
            "line": frame.lineno,
            "function": frame.name,
            "code": frame.line
        })
    
    return json.dumps(error_details, ensure_ascii=False, indent=2)