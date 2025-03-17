import os
import time
import json
import datetime
import platform
import psutil
import shutil
from debug_logger import debug_log

def format_bytes(bytes_value):
    """تبدیل بایت به فرمت قابل خواندن"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

def generate_server_status():
    """تولید وضعیت سرور"""
    try:
        status_sections = ["📊 **وضعیت سرور:**\n"]

        # وضعیت ربات
        status_sections.append("🤖 **وضعیت ربات:** `فعال ✅`\n")

        # سیستم‌عامل و پایتون
        status_sections.append(f"💻 **سیستم عامل:** `{platform.platform()}`\n")
        status_sections.append(f"🐍 **پایتون:** `{platform.python_version()}`\n")

        # CPU
        cpu_usage = psutil.cpu_percent(interval=1)
        status_sections.append(f"🔄 **CPU:** `{cpu_usage}%`\n")

        # RAM
        ram = psutil.virtual_memory()
        status_sections.append(f"💾 **RAM:** `{format_bytes(ram.used)} / {format_bytes(ram.total)} ({ram.percent}%)`\n")

        # دیسک
        disk = psutil.disk_usage('/')
        status_sections.append(f"💿 **دیسک:** `{format_bytes(disk.used)} / {format_bytes(disk.total)} ({disk.percent}%)`\n")

        # زمان سرور
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_sections.append(f"⏰ **زمان سرور:** `{current_time}`\n")

        # آپتایم
        uptime = time.time() - psutil.boot_time()
        uptime_str = str(datetime.timedelta(seconds=int(uptime)))
        status_sections.append(f"⌛ **آپتایم:** `{uptime_str}`\n")

        status_text = "".join(status_sections)

        # ذخیره در فایل
        try:
            with open("server_status.json", "w", encoding="utf-8") as f:
                json.dump({
                    "status": status_text,
                    "timestamp": datetime.datetime.now().isoformat()
                }, f, ensure_ascii=False)
        except Exception as e:
            debug_log(f"خطا در ذخیره وضعیت سرور: {e}", "ERROR")

        return status_text

    except Exception as e:
        debug_log(f"خطا در تولید وضعیت سرور: {e}", "ERROR")
        return "⚠️ خطا در دریافت وضعیت سرور"