import logging
import datetime
import traceback
from typing import Any, Dict, Optional

# تنظیم لاگر
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debug_logs.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def debug_log(message: str, level: str = "INFO", context: Optional[Dict[str, Any]] = None) -> None:
    """ثبت پیام‌های دیباگ"""
    if context is None:
        context = {}

    log_func = getattr(logger, level.lower(), logger.info)
    log_func(f"{message} | Context: {context}")

def debug_decorator(func):
    """دکوراتور برای ثبت ورود و خروج توابع"""
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        debug_log(f"شروع اجرای تابع {func_name}", "INFO")
        try:
            result = func(*args, **kwargs)
            debug_log(f"پایان موفق تابع {func_name}", "INFO")
            return result
        except Exception as e:
            debug_log(f"خطا در تابع {func_name}: {str(e)}", "ERROR", {
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise
    return wrapper

def debug_download(func):
    """دکوراتور مخصوص دیباگ دانلودها"""
    def wrapper(*args, **kwargs):
        download_id = args[1] if len(args) > 1 else "unknown"
        debug_log(f"شروع دانلود {download_id}", "INFO")
        try:
            result = func(*args, **kwargs)
            debug_log(f"پایان دانلود {download_id}", "INFO")
            return result
        except Exception as e:
            debug_log(f"خطا در دانلود {download_id}: {str(e)}", "ERROR")
            raise
    return wrapper

class AdvancedDebugger:
    """کلاس پیشرفته برای دیباگ"""
    def __init__(self):
        self.start_time = datetime.datetime.now()

    def log_step(self, step_id: int, step_name: str, context: Dict[str, Any]) -> None:
        debug_log(f"گام {step_id}: {step_name}", "INFO", context)
        
    def log_download_start(self, download_id: int, url: str, user_id: int) -> None:
        """ثبت شروع دانلود"""
        context = {
            "download_id": download_id,
            "url": url,
            "user_id": user_id,
            "start_time": datetime.datetime.now().isoformat()
        }
        debug_log(f"شروع دانلود {download_id}", "INFO", context)

debugger = AdvancedDebugger()

def log_youtube_process(url, user_id, status):
    debugger.log_step(-1, "youtube_process", {
        "url": url,
        "user_id": user_id,
        "status": status,
        "timestamp": datetime.datetime.now().isoformat()
    })

#The original AdvancedDebugger class and its associated functions are removed because they are replaced by the new ones in the edited code.  The function calls are adapted to use the new functions.