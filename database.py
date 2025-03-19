import os
import sqlite3
import json
import datetime
import threading
from typing import Any, Dict, List, Optional, Tuple, Union
from config import DATABASE_PATH, UserRole, DownloadStatus
from debug_logger import debug_log, debug_decorator

# لاک برای جلوگیری از مشکلات همزمانی در دسترسی به دیتابیس
db_lock = threading.RLock()

@debug_decorator
def dict_factory(cursor, row):
    """تبدیل نتیجه کوئری به دیکشنری"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

@debug_decorator
def get_db_connection():
    """ایجاد اتصال به دیتابیس"""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = dict_factory
    return conn

@debug_decorator
def initialize_database():
    """ایجاد جداول پایگاه داده در صورت عدم وجود"""
    debug_log("شروع ایجاد پایگاه داده...", "INFO")
    
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # جدول کاربران
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,  -- شناسه تلگرام کاربر
                username TEXT,  -- نام کاربری تلگرام
                first_name TEXT,  -- نام کاربر
                last_name TEXT,  -- نام خانوادگی کاربر
                role INTEGER DEFAULT 0,  -- نقش کاربر (0: معمولی، 1: ویژه، 2: ادمین، 3: سوپر ادمین، -1: مسدود شده)
                join_date TEXT,  -- تاریخ عضویت
                last_activity TEXT,  -- آخرین فعالیت
                download_count INTEGER DEFAULT 0,  -- تعداد دانلودها
                notes TEXT  -- یادداشت‌های اضافی
            )
            ''')
            
            # جدول دانلودها
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,  -- شناسه کاربر
                url TEXT,  -- آدرس ویدیو
                status INTEGER,  -- وضعیت دانلود (0: در انتظار، 1: در حال پردازش، 2: کامل شده، 3: شکست خورده، 4: لغو شده)
                start_time TEXT,  -- زمان شروع دانلود
                end_time TEXT,  -- زمان پایان دانلود
                file_path TEXT,  -- مسیر فایل دانلود شده
                file_size INTEGER,  -- حجم فایل
                quality TEXT,  -- کیفیت دانلود
                metadata TEXT,  -- متادیتای ویدیو
                error_message TEXT,  -- پیام خطا در صورت وجود
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')
            
            # جدول لاگ‌ها
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,  -- زمان لاگ
                level TEXT,  -- سطح لاگ
                message TEXT,  -- پیام لاگ
                user_id INTEGER,  -- شناسه کاربر مرتبط
                context TEXT  -- اطلاعات اضافی
            )
            ''')
            
            # جدول تنظیمات
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT
            )
            ''')
            
            # ایجاد شاخص‌ها
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON downloads(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_download_status ON downloads(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_level ON logs(level)')
            
            # ذخیره تغییرات
            conn.commit()
            debug_log("پایگاه داده با موفقیت ایجاد شد", "INFO")
            
        except Exception as e:
            debug_log(f"خطا در ایجاد پایگاه داده: {str(e)}", "ERROR")
            raise
        finally:
            if 'conn' in locals():
                conn.close()

# --- مدیریت کاربران ---

@debug_decorator
def add_or_update_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None, role: int = UserRole.NORMAL) -> bool:
    """
    افزودن یا به‌روزرسانی کاربر در دیتابیس
    
    Args:
        user_id: شناسه کاربر
        username: نام کاربری (اختیاری)
        first_name: نام (اختیاری)
        last_name: نام خانوادگی (اختیاری)
        role: نقش کاربر (اختیاری)
        
    Returns:
        True در صورت موفقیت
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # بررسی وجود کاربر
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            user = cursor.fetchone()
            
            current_time = datetime.datetime.now().isoformat()
            
            if user:
                # به‌روزرسانی کاربر موجود
                cursor.execute('''
                UPDATE users SET 
                    username = COALESCE(?, username),
                    first_name = COALESCE(?, first_name),
                    last_name = COALESCE(?, last_name),
                    last_activity = ?
                WHERE id = ?
                ''', (username, first_name, last_name, current_time, user_id))
            else:
                # افزودن کاربر جدید
                cursor.execute('''
                INSERT INTO users (id, username, first_name, last_name, role, join_date, last_activity, download_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                ''', (user_id, username, first_name, last_name, role, current_time, current_time))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            debug_log(f"خطا در افزودن/به‌روزرسانی کاربر: {str(e)}", "ERROR")
            return False

@debug_decorator
def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """
    دریافت اطلاعات کاربر
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        دیکشنری حاوی اطلاعات کاربر یا None
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            user = cursor.fetchone()
            
            conn.close()
            return user
            
        except Exception as e:
            debug_log(f"خطا در دریافت اطلاعات کاربر: {str(e)}", "ERROR")
            return None

@debug_decorator
def update_user_role(user_id: int, role: int) -> bool:
    """
    به‌روزرسانی نقش کاربر
    
    Args:
        user_id: شناسه کاربر
        role: نقش جدید
        
    Returns:
        True در صورت موفقیت
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('UPDATE users SET role = ? WHERE id = ?', (role, user_id))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            debug_log(f"خطا در به‌روزرسانی نقش کاربر: {str(e)}", "ERROR")
            return False

@debug_decorator
def increment_download_count(user_id: int) -> bool:
    """
    افزایش تعداد دانلودهای کاربر
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        True در صورت موفقیت
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('UPDATE users SET download_count = download_count + 1 WHERE id = ?', (user_id,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            debug_log(f"خطا در افزایش تعداد دانلودها: {str(e)}", "ERROR")
            return False

@debug_decorator
def get_all_users(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    دریافت لیست کاربران
    
    Args:
        limit: محدودیت تعداد
        offset: آفست (برای صفحه‌بندی)
        
    Returns:
        لیست کاربران
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users ORDER BY last_activity DESC LIMIT ? OFFSET ?', (limit, offset))
            users = cursor.fetchall()
            
            conn.close()
            return users
            
        except Exception as e:
            debug_log(f"خطا در دریافت لیست کاربران: {str(e)}", "ERROR")
            return []

# --- مدیریت دانلودها ---

@debug_decorator
def add_download(user_id: int, url: str, quality: str = "best") -> int:
    """
    افزودن دانلود جدید
    
    Args:
        user_id: شناسه کاربر
        url: آدرس ویدیو
        quality: کیفیت دانلود
        
    Returns:
        شناسه دانلود یا -1 در صورت خطا
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            current_time = datetime.datetime.now().isoformat()
            
            cursor.execute('''
            INSERT INTO downloads (user_id, url, status, start_time, quality)
            VALUES (?, ?, ?, ?, ?)
            ''', (user_id, url, DownloadStatus.PENDING, current_time, quality))
            
            # دریافت ID آخرین رکورد اضافه شده
            download_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            # افزایش تعداد دانلودهای کاربر
            increment_download_count(user_id)
            
            return download_id
            
        except Exception as e:
            debug_log(f"خطا در افزودن دانلود جدید: {str(e)}", "ERROR")
            return -1

@debug_decorator
def update_download_status(download_id: int, status: int, file_path: str = None, 
                          file_size: int = None, metadata: Dict = None, error_message: str = None) -> bool:
    """
    به‌روزرسانی وضعیت دانلود
    
    Args:
        download_id: شناسه دانلود
        status: وضعیت جدید
        file_path: مسیر فایل (اختیاری)
        file_size: حجم فایل (اختیاری)
        metadata: متادیتا (اختیاری)
        error_message: پیام خطا (اختیاری)
        
    Returns:
        True در صورت موفقیت
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            current_time = datetime.datetime.now().isoformat()
            metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
            
            # به‌روزرسانی رکورد
            update_fields = ["status = ?", "end_time = ?"]
            params = [status, current_time]
            
            if file_path:
                update_fields.append("file_path = ?")
                params.append(file_path)
                
            if file_size is not None:
                update_fields.append("file_size = ?")
                params.append(file_size)
                
            if metadata_json:
                update_fields.append("metadata = ?")
                params.append(metadata_json)
                
            if error_message:
                update_fields.append("error_message = ?")
                params.append(error_message)
                
            # افزودن شناسه دانلود به پارامترها
            params.append(download_id)
            
            query = f"UPDATE downloads SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, params)
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            debug_log(f"خطا در به‌روزرسانی وضعیت دانلود: {str(e)}", "ERROR")
            return False

@debug_decorator
def get_download(download_id: int) -> Optional[Dict[str, Any]]:
    """
    دریافت اطلاعات دانلود
    
    Args:
        download_id: شناسه دانلود
        
    Returns:
        دیکشنری حاوی اطلاعات دانلود یا None
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM downloads WHERE id = ?', (download_id,))
            download = cursor.fetchone()
            
            # تبدیل متادیتا از JSON به دیکشنری
            if download and download.get('metadata'):
                try:
                    download['metadata'] = json.loads(download['metadata'])
                except:
                    download['metadata'] = {}
            
            conn.close()
            return download
            
        except Exception as e:
            debug_log(f"خطا در دریافت اطلاعات دانلود: {str(e)}", "ERROR")
            return None

@debug_decorator
def get_user_downloads(user_id: int, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    """
    دریافت دانلودهای کاربر
    
    Args:
        user_id: شناسه کاربر
        limit: محدودیت تعداد
        offset: آفست (برای صفحه‌بندی)
        
    Returns:
        لیست دانلودها
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM downloads 
            WHERE user_id = ? 
            ORDER BY start_time DESC 
            LIMIT ? OFFSET ?
            ''', (user_id, limit, offset))
            
            downloads = cursor.fetchall()
            
            # تبدیل متادیتا از JSON به دیکشنری
            for download in downloads:
                if download.get('metadata'):
                    try:
                        download['metadata'] = json.loads(download['metadata'])
                    except:
                        download['metadata'] = {}
            
            conn.close()
            return downloads
            
        except Exception as e:
            debug_log(f"خطا در دریافت دانلودهای کاربر: {str(e)}", "ERROR")
            return []

@debug_decorator
def get_all_downloads(status: Optional[int] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    دریافت همه دانلودها
    
    Args:
        status: وضعیت دانلود (اختیاری)
        limit: محدودیت تعداد
        offset: آفست (برای صفحه‌بندی)
        
    Returns:
        لیست دانلودها
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if status is not None:
                cursor.execute('''
                SELECT * FROM downloads 
                WHERE status = ? 
                ORDER BY start_time DESC 
                LIMIT ? OFFSET ?
                ''', (status, limit, offset))
            else:
                cursor.execute('''
                SELECT * FROM downloads 
                ORDER BY start_time DESC 
                LIMIT ? OFFSET ?
                ''', (limit, offset))
            
            downloads = cursor.fetchall()
            
            # تبدیل متادیتا از JSON به دیکشنری
            for download in downloads:
                if download.get('metadata'):
                    try:
                        download['metadata'] = json.loads(download['metadata'])
                    except:
                        download['metadata'] = {}
            
            conn.close()
            return downloads
            
        except Exception as e:
            debug_log(f"خطا در دریافت همه دانلودها: {str(e)}", "ERROR")
            return []

@debug_decorator
def get_active_downloads_count(user_id: int) -> int:
    """
    دریافت تعداد دانلودهای فعال کاربر
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        تعداد دانلودهای فعال
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT COUNT(*) as count FROM downloads 
            WHERE user_id = ? AND status IN (?, ?)
            ''', (user_id, DownloadStatus.PENDING, DownloadStatus.PROCESSING))
            
            result = cursor.fetchone()
            count = result['count'] if result else 0
            
            conn.close()
            return count
            
        except Exception as e:
            debug_log(f"خطا در دریافت تعداد دانلودهای فعال: {str(e)}", "ERROR")
            return 0

# --- مدیریت لاگ‌ها ---

@debug_decorator
def add_log(level: str, message: str, user_id: Optional[int] = None, context: Optional[Dict] = None) -> int:
    """
    افزودن لاگ جدید
    
    Args:
        level: سطح لاگ
        message: پیام لاگ
        user_id: شناسه کاربر (اختیاری)
        context: اطلاعات اضافی (اختیاری)
        
    Returns:
        شناسه لاگ یا -1 در صورت خطا
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            current_time = datetime.datetime.now().isoformat()
            context_json = json.dumps(context, ensure_ascii=False) if context else None
            
            cursor.execute('''
            INSERT INTO logs (timestamp, level, message, user_id, context)
            VALUES (?, ?, ?, ?, ?)
            ''', (current_time, level, message, user_id, context_json))
            
            log_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            return log_id
            
        except Exception as e:
            debug_log(f"خطا در افزودن لاگ جدید: {str(e)}", "ERROR")
            return -1

@debug_decorator
def get_logs(level: Optional[str] = None, user_id: Optional[int] = None, 
            limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    دریافت لاگ‌ها
    
    Args:
        level: سطح لاگ (اختیاری)
        user_id: شناسه کاربر (اختیاری)
        limit: محدودیت تعداد
        offset: آفست (برای صفحه‌بندی)
        
    Returns:
        لیست لاگ‌ها
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM logs"
            params = []
            conditions = []
            
            if level:
                conditions.append("level = ?")
                params.append(level)
                
            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)
                
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            logs = cursor.fetchall()
            
            # تبدیل context از JSON به دیکشنری
            for log in logs:
                if log.get('context'):
                    try:
                        log['context'] = json.loads(log['context'])
                    except:
                        log['context'] = {}
            
            conn.close()
            return logs
            
        except Exception as e:
            debug_log(f"خطا در دریافت لاگ‌ها: {str(e)}", "ERROR")
            return []

# --- مدیریت تنظیمات ---

@debug_decorator
def set_setting(key: str, value: str, description: str = None) -> bool:
    """
    تنظیم یک مقدار در جدول تنظیمات
    
    Args:
        key: کلید تنظیم
        value: مقدار
        description: توضیحات (اختیاری)
        
    Returns:
        True در صورت موفقیت
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, description)
            VALUES (?, ?, ?)
            ''', (key, value, description))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            debug_log(f"خطا در تنظیم مقدار {key}: {str(e)}", "ERROR")
            return False

@debug_decorator
def get_setting(key: str, default: str = None) -> str:
    """
    دریافت یک تنظیم
    
    Args:
        key: کلید تنظیم
        default: مقدار پیش‌فرض در صورت عدم وجود
        
    Returns:
        مقدار تنظیم یا مقدار پیش‌فرض
    """
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                return result['value']
            else:
                return default
                
        except Exception as e:
            debug_log(f"خطا در دریافت تنظیم {key}: {str(e)}", "ERROR")
            return default
