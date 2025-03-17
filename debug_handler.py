
import logging
import json
import os
import time
from datetime import datetime
from functools import wraps
import traceback
import inspect
import threading
from typing import Dict, Any, Optional

# تنظیمات لاگر
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("detailed_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AdvancedDebugger:
    def __init__(self):
        self.download_states: Dict[int, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        
    def log_download_start(self, download_id: int, url: str, user_id: int) -> None:
        with self.lock:
            self.download_states[download_id] = {
                'start_time': datetime.now().isoformat(),
                'url': url,
                'user_id': user_id,
                'steps': [],
                'errors': [],
                'status': 'starting'
            }
            self._save_state()
    
    def log_step(self, download_id: int, step_name: str, details: dict) -> None:
        with self.lock:
            if download_id in self.download_states:
                self.download_states[download_id]['steps'].append({
                    'time': datetime.now().isoformat(),
                    'name': step_name,
                    'details': details
                })
                self._save_state()
    
    def log_error(self, download_id: int, error: Exception, context: dict = None) -> None:
        with self.lock:
            if download_id in self.download_states:
                error_info = {
                    'time': datetime.now().isoformat(),
                    'type': type(error).__name__,
                    'message': str(error),
                    'traceback': traceback.format_exc(),
                    'context': context or {}
                }
                self.download_states[download_id]['errors'].append(error_info)
                self.download_states[download_id]['status'] = 'error'
                self._save_state()
                
                # لاگ کردن با جزئیات بیشتر
                logger.error(f"Error in download {download_id}:", exc_info=True, extra={
                    'download_id': download_id,
                    'error_info': error_info,
                    'download_state': self.download_states[download_id]
                })
    
    def log_completion(self, download_id: int, success: bool, details: dict = None) -> None:
        with self.lock:
            if download_id in self.download_states:
                self.download_states[download_id].update({
                    'end_time': datetime.now().isoformat(),
                    'success': success,
                    'completion_details': details or {},
                    'status': 'completed' if success else 'failed'
                })
                self._save_state()
    
    def get_download_state(self, download_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self.download_states.get(download_id)
    
    def _save_state(self) -> None:
        try:
            with open('debug_states.json', 'w', encoding='utf-8') as f:
                json.dump(self.download_states, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving debug state: {e}")

# ایجاد نمونه سینگلتون
debugger = AdvancedDebugger()

def debug_download(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # استخراج اطلاعات تابع
        frame = inspect.currentframe()
        arg_info = inspect.getargvalues(frame)
        call_info = {
            'args': arg_info.args,
            'locals': {key: arg_info.locals[key] for key in arg_info.args}
        }
        
        # استخراج download_id از آرگومان‌ها
        download_id = None
        for key, value in kwargs.items():
            if 'download_id' in key:
                download_id = value
                break
        if download_id is None and len(args) > 1:
            download_id = args[1]  # فرض می‌کنیم دومین آرگومان download_id است
            
        if download_id:
            debugger.log_step(download_id, func.__name__, {
                'call_info': call_info,
                'thread_id': threading.get_ident()
            })
            
        try:
            result = func(*args, **kwargs)
            if download_id:
                debugger.log_step(download_id, f"{func.__name__}_completed", {
                    'result': str(result)
                })
            return result
        except Exception as e:
            if download_id:
                debugger.log_error(download_id, e, {
                    'function': func.__name__,
                    'call_info': call_info
                })
            raise
    return wrapper
