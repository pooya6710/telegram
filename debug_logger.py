import os
import sys
<<<<<<< HEAD
import time
import json
import logging
import traceback
import inspect
from datetime import datetime
from functools import wraps

# تنظیم لاگر با فرمت کامل و سطح DEBUG
=======
import logging
import traceback
import datetime
import json
import inspect
import functools
from typing import Any, Dict, Optional, Union, Callable

# تنظیم سطح لاگینگ
>>>>>>> 89853c1 (Checkpoint before assistant change: Initial commit: Setup Python Telegram bot with database, logging, and environment configuration.  Includes dependencies and project structure.)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

<<<<<<< HEAD
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

    try:
        # اطلاعات فریم اجرایی فعلی - با مدیریت خطا
        frame = inspect.currentframe()
        if frame and frame.f_back:
            func_name = frame.f_back.f_code.co_name if hasattr(frame.f_back, 'f_code') else "unknown"
            file_name = frame.f_back.f_code.co_filename if hasattr(frame.f_back, 'f_code') else "unknown"
            line_num = frame.f_back.f_lineno if hasattr(frame.f_back, 'f_lineno') else 0
        else:
            func_name = "unknown"
            file_name = "unknown"
            line_num = 0
        
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
            
        # تبدیل به رشته JSON برای خوانایی بهتر با مدیریت خطا
        try:
            log_message = json.dumps(log_entry, ensure_ascii=False, indent=2)
        except Exception:
            # اگر JSON سازی خطا داشت، یک پیام ساده استفاده کن
            log_message = f"{level}: {message}"
        
        # لاگ با سطح مناسب
        if DEBUG_CONFIG["log_to_console"]:
            # اطمینان از اینکه سطح لاگ معتبر است
            log_level = level.lower() if level.lower() in ['debug', 'info', 'warning', 'error', 'critical'] else 'debug'
            log_func = getattr(logger, log_level)
            log_func(log_message)

        # نوشتن به فایل اگر فعال باشد - با مدیریت خطا
        if DEBUG_CONFIG["log_to_file"]:
            try:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{log_message}\n{'='*50}\n")
            except Exception:
                # در صورت خطا در نوشتن فایل، به سادگی آن را نادیده بگیر
                pass
    
    except Exception as e:
        # در صورت هر گونه خطا، به سادگی یک پیام ساده لاگ کن
        logger.error(f"Error in debug_log: {str(e)} - Original message: {message}")


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
    لاگ کردن آپدیت‌های تلگرام با جزئیات و مدیریت خطا
    
    Args:
        update: آبجکت Update تلگرام
    """
    if not DEBUG_CONFIG["enabled"] or not DEBUG_CONFIG["log_telegram_updates"]:
        return
        
    try:
        # بررسی آیا آپدیت شیء است یا دیکشنری
        if isinstance(update, dict):
            # اگر آپدیت یک دیکشنری است، آن را مستقیماً استفاده کن
            update_dict = {}
            
            # استخراج شناسه آپدیت
            update_dict["update_id"] = update.get("update_id", "unknown")
            
            # استخراج اطلاعات پیام
            if "message" in update:
                message = update["message"]
                message_info = {
                    "message_id": message.get("message_id", "unknown"),
                }
                
                # استخراج اطلاعات چت
                if "chat" in message:
                    message_info["chat_id"] = message["chat"].get("id", "unknown")
                
                # استخراج اطلاعات کاربر
                if "from" in message:
                    message_info["user_id"] = message["from"].get("id", "unknown")
                    message_info["username"] = message["from"].get("username", "unknown")
                
                # استخراج متن پیام
                message_info["text"] = message.get("text", "no_text")
                
                # استخراج تاریخ پیام
                if "date" in message:
                    try:
                        from datetime import datetime
                        date = datetime.fromtimestamp(message["date"])
                        message_info["date"] = date.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        message_info["date"] = "unknown"
                
                update_dict["message"] = message_info
                
            # استخراج اطلاعات کالبک کوئری
            elif "callback_query" in update:
                callback = update["callback_query"]
                callback_info = {
                    "id": callback.get("id", "unknown"),
                    "data": callback.get("data", "unknown"),
                }
                
                # استخراج اطلاعات کاربر
                if "from" in callback:
                    callback_info["user_id"] = callback["from"].get("id", "unknown")
                    callback_info["username"] = callback["from"].get("username", "unknown")
                
                # استخراج اطلاعات پیام مرتبط
                if "message" in callback and "chat" in callback["message"]:
                    callback_info["chat_id"] = callback["message"]["chat"].get("id", "unknown")
                
                update_dict["callback_query"] = callback_info
            
            debug_log("آپدیت تلگرام (JSON) دریافت شد", "INFO", {
                "update": update_dict
            })
            
        else:
            # اگر آپدیت یک شیء است، اطلاعات آن را به روش معمول استخراج کن
            update_dict = {}
            
            # استخراج شناسه آپدیت
            try:
                if hasattr(update, 'update_id'):
                    update_dict["update_id"] = update.update_id
            except Exception:
                update_dict["update_id"] = "error_extracting"
                
            # استخراج اطلاعات پیام
            try:
                if hasattr(update, 'message') and update.message:
                    message_info = {}
                    
                    if hasattr(update.message, 'message_id'):
                        message_info["message_id"] = update.message.message_id
                    
                    if hasattr(update.message, 'chat') and hasattr(update.message.chat, 'id'):
                        message_info["chat_id"] = update.message.chat.id
                    
                    if hasattr(update.message, 'from_user'):
                        if hasattr(update.message.from_user, 'id'):
                            message_info["user_id"] = update.message.from_user.id
                        if hasattr(update.message.from_user, 'username'):
                            message_info["username"] = update.message.from_user.username
                    
                    if hasattr(update.message, 'text'):
                        message_info["text"] = update.message.text
                    
                    if hasattr(update.message, 'date'):
                        try:
                            message_info["date"] = update.message.date.strftime("%Y-%m-%d %H:%M:%S") if update.message.date else None
                        except Exception:
                            message_info["date"] = "error_formatting_date"
                    
                    update_dict["message"] = message_info
            except Exception as msg_error:
                update_dict["message_extraction_error"] = str(msg_error)
                
            # استخراج اطلاعات کالبک کوئری
            try:
                if hasattr(update, 'callback_query') and update.callback_query:
                    callback_info = {}
                    
                    if hasattr(update.callback_query, 'id'):
                        callback_info["id"] = update.callback_query.id
                    
                    if hasattr(update.callback_query, 'data'):
                        callback_info["data"] = update.callback_query.data
                    
                    if hasattr(update.callback_query, 'from_user'):
                        if hasattr(update.callback_query.from_user, 'id'):
                            callback_info["user_id"] = update.callback_query.from_user.id
                        if hasattr(update.callback_query.from_user, 'username'):
                            callback_info["username"] = update.callback_query.from_user.username
                    
                    if hasattr(update.callback_query, 'message') and hasattr(update.callback_query.message, 'chat'):
                        if hasattr(update.callback_query.message.chat, 'id'):
                            callback_info["chat_id"] = update.callback_query.message.chat.id
                    
                    update_dict["callback_query"] = callback_info
            except Exception as cb_error:
                update_dict["callback_extraction_error"] = str(cb_error)
            
            debug_log("آپدیت تلگرام (شیء) دریافت شد", "INFO", {
                "update": update_dict
            })
            
    except Exception as e:
        # در صورت بروز هر خطایی، یک پیام خطای ساده ثبت کن
        try:
            debug_log(f"خطا در لاگ کردن آپدیت تلگرام: {e}", "ERROR", {
                "error_type": type(e).__name__,
                "update_type": type(update).__name__ if update else "None",
                "traceback": traceback.format_exc()
            })
        except Exception:
            # اگر حتی نمی‌توان خطا را لاگ کرد، از یک پیام ساده استفاده کن
            logger.error("خطای بحرانی در لاگ کردن آپدیت تلگرام")


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
=======
# ایجاد لاگر اصلی
logger = logging.getLogger(__name__)

# تنظیم فایل لاگ
file_handler = logging.FileHandler('bot_debug.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# تعیین حداکثر تعداد لاگ‌های ذخیره شده
MAX_LOGS_COUNT = 1000
logs_buffer = []

def debug_log(message: str, level: str = "DEBUG", context: Optional[Dict[str, Any]] = None) -> None:
    """
    ثبت لاگ با اطلاعات اضافی

    Args:
        message: پیام لاگ
        level: سطح لاگ (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        context: اطلاعات زمینه اضافی به صورت دیکشنری
    """
    # ایجاد کپی از context برای جلوگیری از تغییر دادن آن
    if context is None:
        context = {}
    else:
        context = context.copy()

    # اضافه کردن اطلاعات caller
    frame = inspect.currentframe().f_back
    context['caller'] = {
        'file': os.path.basename(frame.f_code.co_filename),
        'function': frame.f_code.co_name,
        'line': frame.f_lineno
    }

    # اضافه کردن timestamp
    context['timestamp'] = datetime.datetime.now().isoformat()

    # تعیین سطح لاگ
    log_level = getattr(logging, level.upper(), logging.DEBUG)
    
    # ساخت پیام نهایی با کانتکست
    full_message = f"{message}"
    if context:
        try:
            context_str = json.dumps(context, ensure_ascii=False, default=str)
            full_message = f"{message} - Context: {context_str}"
        except Exception as e:
            full_message = f"{message} - Context Error: {str(e)}"

    # افزودن به بافر و بررسی اندازه آن
    log_entry = {
        'message': message,
        'level': level,
        'context': context,
        'timestamp': context['timestamp']
    }
    logs_buffer.append(log_entry)
    
    if len(logs_buffer) > MAX_LOGS_COUNT:
        logs_buffer.pop(0)  # حذف قدیمی‌ترین لاگ
    
    # ارسال به لاگر
    logger.log(log_level, full_message)

def log_webhook_request(data: Union[str, bytes, Dict]) -> None:
    """
    ثبت لاگ درخواست وب‌هوک تلگرام

    Args:
        data: داده‌های درخواست (string، bytes یا dict)
    """
    try:
        # تبدیل داده‌ها به string با مدیریت انواع مختلف
        if isinstance(data, bytes):
            data_str = data.decode('utf-8', errors='replace')
        elif isinstance(data, dict):
            data_str = json.dumps(data, ensure_ascii=False)
        else:
            data_str = str(data)
        
        # کوتاه کردن داده‌ها اگر خیلی طولانی باشند
        if len(data_str) > 1000:
            data_preview = data_str[:1000] + '... [truncated]'
        else:
            data_preview = data_str
        
        debug_log("درخواست وب‌هوک دریافت شد", "INFO", {
            "data_length": len(data_str),
            "data_preview": data_preview
        })
    except Exception as e:
        debug_log(f"خطا در لاگ کردن درخواست وب‌هوک: {str(e)}", "ERROR")

def log_telegram_update(update) -> None:
    """
    ثبت لاگ آپدیت تلگرام

    Args:
        update: آبجکت Update تلگرام
    """
    try:
        update_dict = {}
        
        # استخراج نوع آپدیت
        if hasattr(update, 'message') and update.message:
            update_type = 'message'
            update_dict['chat_id'] = update.message.chat.id if hasattr(update.message, 'chat') else None
            update_dict['user_id'] = update.message.from_user.id if hasattr(update.message, 'from_user') else None
            update_dict['text'] = update.message.text if hasattr(update.message, 'text') else None
            update_dict['message_id'] = update.message.message_id if hasattr(update.message, 'message_id') else None
        elif hasattr(update, 'callback_query') and update.callback_query:
            update_type = 'callback_query'
            update_dict['query_id'] = update.callback_query.id if hasattr(update.callback_query, 'id') else None
            update_dict['user_id'] = update.callback_query.from_user.id if hasattr(update.callback_query, 'from_user') else None
            update_dict['data'] = update.callback_query.data if hasattr(update.callback_query, 'data') else None
        else:
            update_type = 'unknown'
        
        debug_log(f"آپدیت تلگرام از نوع {update_type} دریافت شد", "INFO", update_dict)
    except Exception as e:
        debug_log(f"خطا در لاگ کردن آپدیت تلگرام: {str(e)}", "ERROR")

def format_exception_with_context(e: Exception) -> str:
    """
    فرمت‌بندی خطا با اطلاعات اضافی

    Args:
        e: خطای رخ داده

    Returns:
        متن فرمت‌بندی شده خطا
    """
    # دریافت traceback
    tb = traceback.format_exc()
    
    # اطلاعات زمان و نوع خطا
    error_time = datetime.datetime.now().isoformat()
    error_type = type(e).__name__
    error_msg = str(e)
    
    # فرمت‌بندی نهایی
    result = f"[{error_time}] {error_type}: {error_msg}\n\nTraceback:\n{tb}"
    return result

def debug_decorator(func: Callable) -> Callable:
    """
    دکوراتور برای اضافه کردن لاگینگ به توابع

    Args:
        func: تابعی که باید لاگ شود

    Returns:
        تابع بسته‌بندی شده با قابلیت لاگینگ
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        module_name = func.__module__
        
        # لاگ ورود به تابع
        debug_log(f"شروع اجرای {func_name}", "DEBUG", {
            "module": module_name,
            "args_count": len(args),
            "kwargs_names": list(kwargs.keys())
        })
        
        start_time = datetime.datetime.now()
        
        try:
            # اجرای تابع اصلی
            result = func(*args, **kwargs)
            
            # محاسبه زمان اجرا
            execution_time = (datetime.datetime.now() - start_time).total_seconds()
            
            # لاگ پایان اجرای موفق
            debug_log(f"پایان موفق اجرای {func_name}", "DEBUG", {
                "execution_time_seconds": execution_time
>>>>>>> 89853c1 (Checkpoint before assistant change: Initial commit: Setup Python Telegram bot with database, logging, and environment configuration.  Includes dependencies and project structure.)
            })
            
            return result
        except Exception as e:
<<<<<<< HEAD
            execution_time = time.time() - start_time
            
            debug_log(f"خطا در اجرای {func.__name__}", "ERROR", {
                "execution_time": f"{execution_time:.4f} seconds",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            })
            
=======
            # محاسبه زمان اجرا
            execution_time = (datetime.datetime.now() - start_time).total_seconds()
            
            # لاگ خطای رخ داده
            error_details = format_exception_with_context(e)
            debug_log(f"خطا در اجرای {func_name}: {str(e)}", "ERROR", {
                "execution_time_seconds": execution_time,
                "error_type": type(e).__name__,
                "error_details": error_details
            })
            
            # انتشار مجدد خطا
>>>>>>> 89853c1 (Checkpoint before assistant change: Initial commit: Setup Python Telegram bot with database, logging, and environment configuration.  Includes dependencies and project structure.)
            raise
    
    return wrapper

<<<<<<< HEAD

def format_exception_with_context(e):
    """
    فرمت‌بندی استثناها با اطلاعات بافت کامل
    
    Args:
        e: استثنای ایجاد شده
    
    Returns:
        رشته فرمت‌بندی شده از استثنا با اطلاعات اضافی
    """
    try:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        
        # بررسی معتبر بودن اطلاعات خطا
        if not all([exc_type, exc_value, exc_traceback]):
            # اگر اطلاعات خطا کامل نیست، از خود استثنا استفاده کن
            return f"Error: {str(e)}\nType: {type(e).__name__}\nTraceback: {traceback.format_exc()}"
        
        # استخراج زنجیره کامل فراخوانی با مدیریت خطا
        try:
            stack_trace = traceback.extract_tb(exc_traceback)
            
            # ساخت پیام خطا با جزئیات کامل
            error_details = {
                "error_type": exc_type.__name__ if hasattr(exc_type, "__name__") else str(exc_type),
                "error_message": str(exc_value),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "stack_trace": []
            }
            
            # اضافه کردن اطلاعات فریم‌ها با مدیریت خطا
            for frame in stack_trace:
                try:
                    frame_info = {
                        "file": frame.filename if hasattr(frame, "filename") else "unknown",
                        "line": frame.lineno if hasattr(frame, "lineno") else 0,
                        "function": frame.name if hasattr(frame, "name") else "unknown",
                        "code": frame.line if hasattr(frame, "line") else "unknown"
                    }
                    error_details["stack_trace"].append(frame_info)
                except Exception:
                    # اگر دسترسی به اطلاعات فریم با خطا مواجه شد، یک مقدار پیش‌فرض قرار بده
                    error_details["stack_trace"].append({"info": "frame info extraction failed"})
            
            # تبدیل به JSON با مدیریت خطا
            try:
                return json.dumps(error_details, ensure_ascii=False, indent=2)
            except Exception:
                # اگر تبدیل به JSON با خطا مواجه شد، از فرمت متنی استفاده کن
                return f"Error: {str(exc_value)}\nType: {exc_type.__name__ if hasattr(exc_type, '__name__') else str(exc_type)}\nTraceback: {traceback.format_exc()}"
                
        except Exception:
            # اگر استخراج اطلاعات فریم با خطا مواجه شد، از traceback ساده استفاده کن
            return traceback.format_exc()
            
    except Exception:
        # در صورت هر گونه خطای غیرمنتظره، یک پیام ساده برگردان
        return f"Error occurred: {str(e)}"
=======
def get_recent_logs(count: int = 50, level: Optional[str] = None) -> list:
    """
    دریافت لاگ‌های اخیر

    Args:
        count: تعداد لاگ‌ها
        level: سطح لاگ (اختیاری)

    Returns:
        لیست لاگ‌های اخیر
    """
    if level:
        filtered_logs = [log for log in logs_buffer if log['level'].upper() == level.upper()]
    else:
        filtered_logs = logs_buffer.copy()
    
    # مرتب‌سازی بر اساس timestamp و محدود کردن تعداد
    sorted_logs = sorted(filtered_logs, key=lambda x: x['timestamp'], reverse=True)
    return sorted_logs[:count]

def clear_logs() -> None:
    """پاک کردن بافر لاگ‌ها"""
    logs_buffer.clear()
>>>>>>> 89853c1 (Checkpoint before assistant change: Initial commit: Setup Python Telegram bot with database, logging, and environment configuration.  Includes dependencies and project structure.)
