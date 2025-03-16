import os
import time
import json
import datetime
import platform
import psutil
import shutil
from debug_logger import debug_log

# متغیر برای کش کردن وضعیت سرور
SERVER_CACHE = {
    "timestamp": None,
    "status": None
}

def format_bytes(bytes_value):
    """تبدیل بایت به فرمت قابل خواندن برای انسان"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

def get_cached_server_status():
    """دریافت وضعیت سرور از کش با مدیریت خطای بهتر"""
    global SERVER_CACHE

    # اگر وضعیت در کش موجود باشد و کمتر از 10 دقیقه (600 ثانیه) از آخرین بروزرسانی گذشته باشد
    try:
        if SERVER_CACHE["status"] is not None and SERVER_CACHE["timestamp"] is not None:
            time_diff = (datetime.datetime.now() - SERVER_CACHE["timestamp"]).total_seconds()
            if time_diff < 600:
                return SERVER_CACHE["status"]
    except Exception as e:
        debug_log(f"خطا در بررسی کش وضعیت سرور: {e}", "ERROR")
    
    # بررسی فایل کش
    try:
        if os.path.exists("server_status.json"):
            file_time = os.path.getmtime("server_status.json")
            current_time = time.time()
            if current_time - file_time < 600:  # کمتر از 10 دقیقه
                with open("server_status.json", "r", encoding="utf-8") as file:
                    data = json.load(file)
                    SERVER_CACHE["status"] = data["status"]
                    SERVER_CACHE["timestamp"] = datetime.datetime.strptime(
                        data["timestamp"], "%Y-%m-%d %H:%M:%S"
                    )
                    return data["status"]
    except Exception as e:
        debug_log(f"خطا در خواندن فایل کش وضعیت سرور: {e}", "ERROR")
    
    return None

def generate_server_status():
    """تولید گزارش وضعیت سرور با مدیریت خطا برای هر بخش"""
    global SERVER_CACHE
    
    try:
        status_sections = ["📊 **وضعیت سرور:**\n"]

        # وضعیت ربات
        status_sections.append(f"🔹 **وضعیت ربات:** `فعال ✅`\n")
        
        # سیستم‌عامل و پایتون
        try:
            status_sections.append(f"🔹 **سیستم عامل:** `{platform.platform()}`\n")
            status_sections.append(f"🔹 **پایتون:** `{platform.python_version()}`\n")
        except Exception as e:
            status_sections.append("🔹 **سیستم عامل:** `اطلاعات در دسترس نیست`\n")
            debug_log(f"خطا در دریافت اطلاعات سیستم: {e}", "ERROR")

        # CPU
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            status_sections.append(f"🔹 **CPU:** `{cpu_usage}%`\n")
        except Exception as e:
            status_sections.append("🔹 **CPU:** `اطلاعات در دسترس نیست`\n")
            debug_log(f"خطا در دریافت اطلاعات CPU: {e}", "ERROR")

        # RAM
        try:
            ram = psutil.virtual_memory()
            status_sections.append(f"🔹 **RAM:** `{ram.used / (1024**3):.2f}GB / {ram.total / (1024**3):.2f}GB`\n")
        except Exception as e:
            status_sections.append("🔹 **RAM:** `اطلاعات در دسترس نیست`\n")
            debug_log(f"خطا در دریافت اطلاعات RAM: {e}", "ERROR")

        # فضای دیسک
        try:
            disk_usage = shutil.disk_usage("/")
            free_gb = disk_usage.free / (1024**3)
            total_gb = disk_usage.total / (1024**3)
            status_sections.append(f"🔹 **فضای دیسک:** `{free_gb:.2f}GB آزاد از {total_gb:.2f}GB`\n")
        except Exception as e:
            status_sections.append("🔹 **فضای دیسک:** `اطلاعات در دسترس نیست`\n")
            debug_log(f"خطا در دریافت اطلاعات دیسک: {e}", "ERROR")

        # زمان سرور
        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_sections.append(f"🔹 **زمان سرور:** `{current_time}`\n")
            
            # منطقه زمانی
            timezone = time.tzname
            status_sections.append(f"🔹 **منطقه زمانی:** `{timezone[0]}`\n")
        except Exception as e:
            status_sections.append("🔹 **زمان سرور:** `اطلاعات در دسترس نیست`\n")
            debug_log(f"خطا در دریافت اطلاعات زمان: {e}", "ERROR")

        # مدت زمان روشن بودن سرور
        try:
            uptime_seconds = time.time() - psutil.boot_time()
            uptime_hours = uptime_seconds // 3600
            uptime_days = uptime_hours // 24
            
            if uptime_days > 0:
                status_sections.append(f"🔹 **مدت روشن بودن:** `{int(uptime_days)} روز و {int(uptime_hours % 24)} ساعت`\n")
            else:
                status_sections.append(f"🔹 **مدت روشن بودن:** `{int(uptime_hours)} ساعت`\n")
        except Exception as e:
            status_sections.append("🔹 **مدت روشن بودن:** `اطلاعات در دسترس نیست`\n")
            debug_log(f"خطا در دریافت اطلاعات uptime: {e}", "ERROR")

        # اطلاعات شبکه
        try:
            net_io = psutil.net_io_counters()
            sent_gb = net_io.bytes_sent / (1024**3)
            recv_gb = net_io.bytes_recv / (1024**3)
            status_sections.append(f"🔹 **ترافیک شبکه:** `ارسال: {sent_gb:.2f}GB، دریافت: {recv_gb:.2f}GB`\n")
            
            # تعداد اتصالات
            connections = len(psutil.net_connections())
            status_sections.append(f"🔹 **تعداد اتصالات:** `{connections}`\n")
        except Exception as e:
            status_sections.append("🔹 **ترافیک شبکه:** `اطلاعات در دسترس نیست`\n")
            debug_log(f"خطا در دریافت اطلاعات شبکه: {e}", "ERROR")

        # ترکیب بخش‌های پیام
        status_msg = "".join(status_sections)
        
        # ذخیره در کش
        SERVER_CACHE["status"] = status_msg
        SERVER_CACHE["timestamp"] = datetime.datetime.now()
        
        # ذخیره وضعیت سرور در یک فایل JSON برای کش کردن
        try:
            with open("server_status.json", "w", encoding="utf-8") as file:
                json.dump(
                    {
                        "timestamp": SERVER_CACHE["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                        "status": status_msg
                    }, file)
        except Exception as cache_write_error:
            debug_log(f"خطا در ذخیره کش وضعیت سرور: {cache_write_error}", "ERROR")
        
        return status_msg
        
    except Exception as e:
        debug_log(f"خطای کلی در تولید وضعیت سرور: {e}", "ERROR")
        return "⚠ خطا در دریافت وضعیت سرور"