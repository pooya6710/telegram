import os
import time
import threading
from typing import Optional, Dict, Any, List
import logging
import json

# مدیریت وابستگی‌ها با مکانیزم fallback
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from debug_logger import debug_log, debug_decorator

@debug_decorator
def setup_bot(bot, webhook_url: Optional[str] = None):
    """
    تنظیم وب‌هوک برای ربات
    
    Args:
        bot: نمونه ربات تلگرام
        webhook_url: آدرس وب‌هوک (اختیاری)
        
    Returns:
        پیام وضعیت
    """
    try:
        if webhook_url:
            # حذف وب‌هوک قبلی
            bot.remove_webhook()
            
            # تنظیم وب‌هوک جدید
            bot.set_webhook(url=webhook_url)
            debug_log(f"وب‌هوک تنظیم شد: {webhook_url}", "INFO")
            return f"وب‌هوک با آدرس {webhook_url} تنظیم شد"
        else:
            # حذف وب‌هوک
            bot.remove_webhook()
            debug_log("وب‌هوک حذف شد", "INFO")
            return "وب‌هوک حذف شد"
    except Exception as e:
        debug_log(f"خطا در تنظیم وب‌هوک: {str(e)}", "ERROR")
        return f"خطا در تنظیم وب‌هوک: {str(e)}"

@debug_decorator
def check_dependencies():
    """
    بررسی وابستگی‌های برنامه
    """
    dependencies = [
        ('telebot', 'ماژول تلگرام'),
        ('flask', 'ماژول فلسک'),
        ('psutil', 'ماژول مانیتورینگ سیستم'),
        ('yt_dlp', 'ماژول دانلود یوتیوب'),
        ('sqlite3', 'ماژول دیتابیس')
    ]
    
    missing = []
    
    for module_name, description in dependencies:
        try:
            __import__(module_name)
            debug_log(f"✅ {description} ({module_name}) با موفقیت بارگذاری شد", "INFO")
        except ImportError:
            debug_log(f"❌ {description} ({module_name}) در دسترس نیست", "WARNING")
            missing.append(f"{description} ({module_name})")
    
    if missing:
        debug_log(f"⚠️ {len(missing)} ماژول مورد نیاز یافت نشد: {', '.join(missing)}", "WARNING")
    else:
        debug_log("✅ همه ماژول‌های مورد نیاز با موفقیت بارگذاری شدند", "INFO")

@debug_decorator
def scheduled_tasks():
    """
    اجرای وظایف زمان‌بندی شده
    """
    debug_log("ترد وظایف زمان‌بندی شده آغاز به کار کرد", "INFO")
    
    while True:
        try:
            # پاکسازی فایل‌های دانلود قدیمی (هر 24 ساعت)
            try:
                from youtube_downloader import clean_old_downloads
                
                count = clean_old_downloads(max_age_days=1)
                debug_log(f"پاکسازی فایل‌های قدیمی انجام شد: {count} فایل حذف شد", "INFO")
            except Exception as e:
                debug_log(f"خطا در پاکسازی فایل‌های قدیمی: {str(e)}", "ERROR")
            
            # بررسی وضعیت سیستم و هشدار در صورت نیاز
            try:
                if PSUTIL_AVAILABLE:
                    # بررسی CPU
                    cpu_percent = psutil.cpu_percent(interval=1)
                    if cpu_percent > 90:
                        debug_log(f"هشدار: مصرف CPU بالاست: {cpu_percent}%", "WARNING")
                    
                    # بررسی RAM
                    memory = psutil.virtual_memory()
                    if memory.percent > 90:
                        debug_log(f"هشدار: مصرف حافظه بالاست: {memory.percent}%", "WARNING")
                    
                    # بررسی دیسک
                    disk = psutil.disk_usage('/')
                    if disk.percent > 90:
                        debug_log(f"هشدار: فضای دیسک کم است: {disk.percent}% استفاده شده", "WARNING")
            except Exception as e:
                debug_log(f"خطا در بررسی وضعیت سیستم: {str(e)}", "ERROR")
            
            # بارگذاری کاربران مسدود شده
            try:
                from user_management import load_blocked_users_from_db
                
                load_blocked_users_from_db()
            except Exception as e:
                debug_log(f"خطا در بارگذاری کاربران مسدود: {str(e)}", "ERROR")
            
        except Exception as e:
            debug_log(f"خطا در اجرای وظایف زمان‌بندی شده: {str(e)}", "ERROR")
        
        # خواب برای 1 ساعت
        time.sleep(3600)

@debug_decorator
def format_size(size_bytes: int) -> str:
    """
    تبدیل حجم به فرمت قابل خواندن
    
    Args:
        size_bytes: حجم به بایت
        
    Returns:
        متن فرمت‌بندی شده
    """
    # حجم‌های مختلف
    kb = 1024
    mb = kb * 1024
    gb = mb * 1024
    tb = gb * 1024
    
    if size_bytes >= tb:
        return f"{size_bytes / tb:.2f} TB"
    elif size_bytes >= gb:
        return f"{size_bytes / gb:.2f} GB"
    elif size_bytes >= mb:
        return f"{size_bytes / mb:.2f} MB"
    elif size_bytes >= kb:
        return f"{size_bytes / kb:.2f} KB"
    else:
        return f"{size_bytes} bytes"

@debug_decorator
def get_bot_info() -> Dict[str, Any]:
    """
    دریافت اطلاعات ربات
    
    Returns:
        دیکشنری حاوی اطلاعات ربات
    """
    from database import get_all_users, get_all_downloads
    from youtube_downloader import get_all_active_downloads
    
    try:
        # دریافت آمار کاربران
        users = get_all_users(limit=1000)
        user_count = len(users)
        
        # دریافت آمار دانلودها
        all_downloads = get_all_downloads(limit=1000)
        download_count = len(all_downloads)
        
        # دانلودهای فعال
        active_downloads = get_all_active_downloads()
        active_count = len(active_downloads)
        
        # آمار وضعیت دانلودها
        status_counts = {
            "pending": len([d for d in all_downloads if d.get('status') == 0]),
            "processing": len([d for d in all_downloads if d.get('status') == 1]),
            "completed": len([d for d in all_downloads if d.get('status') == 2]),
            "failed": len([d for d in all_downloads if d.get('status') == 3]),
            "canceled": len([d for d in all_downloads if d.get('status') == 4])
        }
        
        # آمار نقش کاربران
        role_counts = {
            "blocked": len([u for u in users if u.get('role') == -1]),
            "normal": len([u for u in users if u.get('role') == 0]),
            "premium": len([u for u in users if u.get('role') == 1]),
            "admin": len([u for u in users if u.get('role') in [2, 3]])
        }
        
        return {
            "user_count": user_count,
            "download_count": download_count,
            "active_downloads": active_count,
            "status_counts": status_counts,
            "role_counts": role_counts
        }
    except Exception as e:
        debug_log(f"خطا در دریافت اطلاعات ربات: {str(e)}", "ERROR")
        return {
            "error": str(e)
        }

@debug_decorator
def generate_status_html() -> str:
    """
    تولید HTML وضعیت برای صفحه وب
    
    Returns:
        HTML وضعیت
    """
    from system_info import get_system_info
    
    try:
        # دریافت اطلاعات سیستم
        sys_info = get_system_info()
        
        # دریافت اطلاعات ربات
        bot_info = get_bot_info()
        
        # تولید HTML
        html = "<div class='status-container'>"
        
        # بخش سیستم
        html += "<div class='status-section'>"
        html += "<h3>وضعیت سیستم</h3>"
        
        # CPU
        cpu_percent = sys_info.get('cpu', {}).get('usage_percent', 0)
        html += f"<div class='status-item'><span>CPU:</span> {cpu_percent}%</div>"
        
        # RAM
        ram_percent = sys_info.get('memory', {}).get('percent_used', 0)
        ram_used = sys_info.get('memory', {}).get('used_human', 'نامشخص')
        ram_total = sys_info.get('memory', {}).get('total_human', 'نامشخص')
        html += f"<div class='status-item'><span>RAM:</span> {ram_percent}% ({ram_used} / {ram_total})</div>"
        
        # دیسک
        disk_percent = sys_info.get('disk', {}).get('percent_used', 0)
        disk_free = sys_info.get('disk', {}).get('free_human', 'نامشخص')
        html += f"<div class='status-item'><span>دیسک:</span> {disk_percent}% (آزاد: {disk_free})</div>"
        
        # زمان کارکرد
        uptime = sys_info.get('uptime', {}).get('uptime_human', 'نامشخص')
        html += f"<div class='status-item'><span>زمان کارکرد:</span> {uptime}</div>"
        
        html += "</div>"
        
        # بخش آمار ربات
        html += "<div class='status-section'>"
        html += "<h3>آمار ربات</h3>"
        
        # تعداد کاربران
        user_count = bot_info.get('user_count', 0)
        html += f"<div class='status-item'><span>کاربران:</span> {user_count}</div>"
        
        # تعداد دانلودها
        download_count = bot_info.get('download_count', 0)
        html += f"<div class='status-item'><span>دانلودها:</span> {download_count}</div>"
        
        # دانلودهای فعال
        active_downloads = bot_info.get('active_downloads', 0)
        html += f"<div class='status-item'><span>دانلودهای فعال:</span> {active_downloads}</div>"
        
        html += "</div>"
        
        html += "</div>"
        
        return html
    except Exception as e:
        debug_log(f"خطا در تولید HTML وضعیت: {str(e)}", "ERROR")
        return f"<div class='error'>خطا در دریافت وضعیت: {str(e)}</div>"
