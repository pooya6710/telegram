
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

def predict_resource_usage(current_usage, history_length=5):
    """پیش‌بینی مصرف منابع"""
    try:
        # شبیه‌سازی تاریخچه برای پیش‌بینی ساده
        if current_usage > 80:
            trend = "🔴 افزایشی (هشدار)"
            prediction = "احتمال پر شدن منابع در ساعات آینده"
        elif current_usage > 60:
            trend = "🟡 ثابت (نیاز به توجه)"
            prediction = "احتمال افزایش مصرف در روزهای آینده"
        else:
            trend = "🟢 پایدار"
            prediction = "وضعیت پایدار برای هفته آینده"
        
        return trend, prediction
    except:
        return "نامشخص", "پیش‌بینی امکان‌پذیر نیست"

def generate_server_status():
    """تولید وضعیت سرور با جزئیات"""
    try:
        status_sections = [
            "📊 **وضعیت تفصیلی سرور:**\n",
            "➖➖➖➖➖➖➖➖➖➖➖➖\n"
        ]

        # وضعیت ربات
        status_sections.append("🤖 **وضعیت ربات:**\n")
        status_sections.append("▫️ وضعیت: `فعال ✅`\n")
        if os.path.exists("bot.lock"):
            with open("bot.lock", "r") as f:
                bot_data = f.read().strip()
                status_sections.append(f"▫️ PID ربات: `{bot_data}`\n")

        # سیستم‌عامل و پایتون
        status_sections.append("\n💻 **اطلاعات سیستم:**\n")
        status_sections.append(f"▫️ سیستم عامل: `{platform.platform()}`\n")
        status_sections.append(f"▫️ معماری: `{platform.machine()}`\n")
        status_sections.append(f"▫️ پایتون: `{platform.python_version()}`\n")
        status_sections.append(f"▫️ پردازنده: `{platform.processor() or 'نامشخص'}`\n")

        # CPU
        cpu_usage = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq()
        cpu_count = psutil.cpu_count()
        cpu_trend, cpu_prediction = predict_resource_usage(cpu_usage)
        
        status_sections.append("\n🔄 **وضعیت CPU:**\n")
        status_sections.append(f"▫️ استفاده: `{cpu_usage}%`\n")
        status_sections.append(f"▫️ تعداد هسته: `{cpu_count}`\n")
        if cpu_freq:
            status_sections.append(f"▫️ فرکانس: `{cpu_freq.current:.1f} MHz`\n")
        status_sections.append(f"▫️ روند: `{cpu_trend}`\n")
        status_sections.append(f"▫️ پیش‌بینی: `{cpu_prediction}`\n")

        # RAM
        ram = psutil.virtual_memory()
        ram_trend, ram_prediction = predict_resource_usage(ram.percent)
        
        status_sections.append("\n💾 **وضعیت RAM:**\n")
        status_sections.append(f"▫️ کل: `{format_bytes(ram.total)}`\n")
        status_sections.append(f"▫️ استفاده شده: `{format_bytes(ram.used)} ({ram.percent}%)`\n")
        status_sections.append(f"▫️ آزاد: `{format_bytes(ram.available)}`\n")
        status_sections.append(f"▫️ روند: `{ram_trend}`\n")
        status_sections.append(f"▫️ پیش‌بینی: `{ram_prediction}`\n")

        # SWAP
        swap = psutil.swap_memory()
        status_sections.append("\n💿 **وضعیت SWAP:**\n")
        status_sections.append(f"▫️ کل: `{format_bytes(swap.total)}`\n")
        status_sections.append(f"▫️ استفاده شده: `{format_bytes(swap.used)} ({swap.percent}%)`\n")
        status_sections.append(f"▫️ آزاد: `{format_bytes(swap.free)}`\n")

        # دیسک
        disk = psutil.disk_usage('/')
        disk_trend, disk_prediction = predict_resource_usage(disk.percent)
        
        status_sections.append("\n💽 **وضعیت دیسک:**\n")
        status_sections.append(f"▫️ کل: `{format_bytes(disk.total)}`\n")
        status_sections.append(f"▫️ استفاده شده: `{format_bytes(disk.used)} ({disk.percent}%)`\n")
        status_sections.append(f"▫️ آزاد: `{format_bytes(disk.free)}`\n")
        status_sections.append(f"▫️ روند: `{disk_trend}`\n")
        status_sections.append(f"▫️ پیش‌بینی: `{disk_prediction}`\n")

        # شبکه
        net_io = psutil.net_io_counters()
        status_sections.append("\n🌐 **وضعیت شبکه:**\n")
        status_sections.append(f"▫️ دریافت شده: `{format_bytes(net_io.bytes_recv)}`\n")
        status_sections.append(f"▫️ ارسال شده: `{format_bytes(net_io.bytes_sent)}`\n")
        status_sections.append(f"▫️ خطاهای دریافت: `{net_io.errin}`\n")
        status_sections.append(f"▫️ خطاهای ارسال: `{net_io.errout}`\n")

        # زمان سرور
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time
        
        status_sections.append("\n⏰ **اطلاعات زمانی:**\n")
        status_sections.append(f"▫️ زمان سرور: `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n")
        status_sections.append(f"▫️ زمان راه‌اندازی: `{boot_time.strftime('%Y-%m-%d %H:%M:%S')}`\n")
        status_sections.append(f"▫️ مدت کارکرد: `{str(uptime).split('.')[0]}`\n")

        # فرایندها
        processes = len(list(psutil.process_iter()))
        status_sections.append("\n📝 **وضعیت فرایندها:**\n")
        status_sections.append(f"▫️ تعداد کل: `{processes}`\n")

        status_text = "".join(status_sections)

        # ذخیره در فایل
        try:
            with open("server_status.json", "w", encoding="utf-8") as f:
                json.dump({
                    "status": status_text,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "details": {
                        "cpu_usage": cpu_usage,
                        "ram_usage": ram.percent,
                        "disk_usage": disk.percent,
                        "predictions": {
                            "cpu": cpu_prediction,
                            "ram": ram_prediction,
                            "disk": disk_prediction
                        }
                    }
                }, f, ensure_ascii=False)
        except Exception as e:
            debug_log(f"خطا در ذخیره وضعیت سرور: {e}", "ERROR")

        return status_text

    except Exception as e:
        debug_log(f"خطا در تولید وضعیت سرور: {e}", "ERROR")
        return "⚠️ خطا در دریافت وضعیت سرور"
