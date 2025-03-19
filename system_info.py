import os
import platform
import datetime
import json
from typing import Dict, Any, Optional
import threading
import time

# مدیریت وابستگی‌ها با مکانیزم fallback
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import shutil
    SHUTIL_AVAILABLE = True
except ImportError:
    SHUTIL_AVAILABLE = False

from debug_logger import debug_log, debug_decorator

# کش اطلاعات سیستم برای بهبود کارایی
system_info_cache = {}
system_info_cache_time = 0
CACHE_TIMEOUT = 60  # مدت زمان اعتبار کش به ثانیه

# قفل برای همزمانی
cache_lock = threading.Lock()

@debug_decorator
def _bytes_to_human_readable(size_bytes: int) -> str:
    """
    تبدیل بایت به فرمت قابل خواندن برای انسان
    
    Args:
        size_bytes: اندازه به بایت
        
    Returns:
        متن فرمت‌بندی شده (مثلا "2.5 GB")
    """
    if size_bytes == 0:
        return "0 B"
    
    # تعریف پیشوندها
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    base = 1024
    exponent = int(min(len(units) - 1, (len(str(size_bytes)) - 1) // 3))
    
    # محاسبه اندازه با واحد مناسب
    size = size_bytes / (base ** exponent)
    unit = units[exponent]
    
    # فرمت‌بندی با دو رقم اعشار
    return f"{size:.2f} {unit}"

@debug_decorator
def get_cpu_info() -> Dict[str, Any]:
    """
    دریافت اطلاعات CPU
    
    Returns:
        دیکشنری حاوی اطلاعات CPU
    """
    cpu_info = {
        "cores": 0,
        "usage_percent": 0,
        "architecture": platform.machine(),
        "processor": platform.processor() or "نامشخص"
    }
    
    if PSUTIL_AVAILABLE:
        try:
            cpu_info["cores"] = psutil.cpu_count(logical=True)
            cpu_info["physical_cores"] = psutil.cpu_count(logical=False)
            cpu_info["usage_percent"] = psutil.cpu_percent(interval=0.5)
            
            # اطلاعات بیشتر در صورت امکان
            freq = psutil.cpu_freq()
            if freq:
                cpu_info["frequency_mhz"] = freq.current
                
            # دمای CPU در صورت پشتیبانی
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    cpu_temps = []
                    for name, entries in temps.items():
                        if any("cpu" in name.lower() for name in [name] + [e.label for e in entries if e.label]):
                            for entry in entries:
                                cpu_temps.append({
                                    "label": entry.label or name,
                                    "temperature": entry.current
                                })
                    if cpu_temps:
                        cpu_info["temperatures"] = cpu_temps
        
        except Exception as e:
            debug_log(f"خطا در دریافت اطلاعات CPU: {str(e)}", "WARNING")
    
    return cpu_info

@debug_decorator
def get_memory_info() -> Dict[str, Any]:
    """
    دریافت اطلاعات حافظه
    
    Returns:
        دیکشنری حاوی اطلاعات حافظه
    """
    memory_info = {
        "total": 0,
        "available": 0,
        "used": 0,
        "percent_used": 0,
        "total_human": "نامشخص",
        "available_human": "نامشخص",
        "used_human": "نامشخص"
    }
    
    if PSUTIL_AVAILABLE:
        try:
            mem = psutil.virtual_memory()
            memory_info["total"] = mem.total
            memory_info["available"] = mem.available
            memory_info["used"] = mem.used
            memory_info["percent_used"] = mem.percent
            
            # تبدیل به فرمت قابل خواندن
            memory_info["total_human"] = _bytes_to_human_readable(mem.total)
            memory_info["available_human"] = _bytes_to_human_readable(mem.available)
            memory_info["used_human"] = _bytes_to_human_readable(mem.used)
            
            # اطلاعات swap
            swap = psutil.swap_memory()
            memory_info["swap"] = {
                "total": swap.total,
                "used": swap.used,
                "free": swap.free,
                "percent_used": swap.percent,
                "total_human": _bytes_to_human_readable(swap.total),
                "used_human": _bytes_to_human_readable(swap.used),
                "free_human": _bytes_to_human_readable(swap.free)
            }
            
        except Exception as e:
            debug_log(f"خطا در دریافت اطلاعات حافظه: {str(e)}", "WARNING")
    
    return memory_info

@debug_decorator
def get_disk_info() -> Dict[str, Any]:
    """
    دریافت اطلاعات دیسک
    
    Returns:
        دیکشنری حاوی اطلاعات دیسک
    """
    disk_info = {
        "total": 0,
        "free": 0,
        "used": 0,
        "percent_used": 0,
        "total_human": "نامشخص",
        "free_human": "نامشخص",
        "used_human": "نامشخص"
    }
    
    # تلاش با psutil
    if PSUTIL_AVAILABLE:
        try:
            current_dir = os.path.abspath(os.getcwd())
            disk_usage = psutil.disk_usage(current_dir)
            
            disk_info["total"] = disk_usage.total
            disk_info["free"] = disk_usage.free
            disk_info["used"] = disk_usage.used
            disk_info["percent_used"] = disk_usage.percent
            
            # تبدیل به فرمت قابل خواندن
            disk_info["total_human"] = _bytes_to_human_readable(disk_usage.total)
            disk_info["free_human"] = _bytes_to_human_readable(disk_usage.free)
            disk_info["used_human"] = _bytes_to_human_readable(disk_usage.used)
            
            # اطلاعات اضافی
            disk_info["partitions"] = []
            
            # اطلاعات پارتیشن‌ها
            for part in psutil.disk_partitions(all=False):
                if os.path.exists(part.mountpoint):
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        disk_info["partitions"].append({
                            "device": part.device,
                            "mountpoint": part.mountpoint,
                            "fstype": part.fstype,
                            "total": usage.total,
                            "used": usage.used,
                            "free": usage.free,
                            "percent_used": usage.percent,
                            "total_human": _bytes_to_human_readable(usage.total),
                            "used_human": _bytes_to_human_readable(usage.used),
                            "free_human": _bytes_to_human_readable(usage.free)
                        })
                    except Exception:
                        # برخی پارتیشن‌ها ممکن است قابل دسترسی نباشند
                        pass
            
        except Exception as e:
            debug_log(f"خطا در دریافت اطلاعات دیسک با psutil: {str(e)}", "WARNING")
    
    # اگر psutil در دسترس نبود یا خطا داد، از shutil استفاده کنیم
    if disk_info["total"] == 0 and SHUTIL_AVAILABLE:
        try:
            current_dir = os.path.abspath(os.getcwd())
            total, used, free = shutil.disk_usage(current_dir)
            
            disk_info["total"] = total
            disk_info["free"] = free
            disk_info["used"] = used
            disk_info["percent_used"] = (used / total) * 100 if total > 0 else 0
            
            # تبدیل به فرمت قابل خواندن
            disk_info["total_human"] = _bytes_to_human_readable(total)
            disk_info["free_human"] = _bytes_to_human_readable(free)
            disk_info["used_human"] = _bytes_to_human_readable(used)
            
        except Exception as e:
            debug_log(f"خطا در دریافت اطلاعات دیسک با shutil: {str(e)}", "WARNING")
    
    return disk_info

@debug_decorator
def get_system_uptime() -> Dict[str, Any]:
    """
    دریافت زمان کارکرد سیستم
    
    Returns:
        دیکشنری حاوی اطلاعات زمان کارکرد
    """
    uptime_info = {
        "uptime_seconds": 0,
        "uptime_human": "نامشخص",
        "boot_time": "نامشخص"
    }
    
    if PSUTIL_AVAILABLE:
        try:
            # زمان راه‌اندازی
            boot_time = psutil.boot_time()
            boot_datetime = datetime.datetime.fromtimestamp(boot_time)
            
            # زمان کارکرد
            uptime_seconds = time.time() - boot_time
            
            # تبدیل به فرمت قابل خواندن
            days, remainder = divmod(uptime_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            uptime_human = f"{int(days)} روز, {int(hours)} ساعت, {int(minutes)} دقیقه"
            
            uptime_info["uptime_seconds"] = uptime_seconds
            uptime_info["uptime_human"] = uptime_human
            uptime_info["boot_time"] = boot_datetime.strftime("%Y-%m-%d %H:%M:%S")
            
        except Exception as e:
            debug_log(f"خطا در دریافت زمان کارکرد سیستم: {str(e)}", "WARNING")
    
    return uptime_info

@debug_decorator
def get_network_info() -> Dict[str, Any]:
    """
    دریافت اطلاعات شبکه
    
    Returns:
        دیکشنری حاوی اطلاعات شبکه
    """
    network_info = {
        "interfaces": [],
        "connections_count": 0
    }
    
    if PSUTIL_AVAILABLE:
        try:
            # آمار اینترفیس‌های شبکه
            net_io = psutil.net_io_counters(pernic=True)
            net_addr = psutil.net_if_addrs()
            
            for interface_name, stats in net_io.items():
                interface_info = {
                    "name": interface_name,
                    "bytes_sent": stats.bytes_sent,
                    "bytes_recv": stats.bytes_recv,
                    "bytes_sent_human": _bytes_to_human_readable(stats.bytes_sent),
                    "bytes_recv_human": _bytes_to_human_readable(stats.bytes_recv),
                    "addresses": []
                }
                
                # افزودن آدرس‌های IP
                if interface_name in net_addr:
                    for addr in net_addr[interface_name]:
                        if addr.family.name == 'AF_INET':  # IPv4
                            interface_info["addresses"].append({
                                "type": "IPv4",
                                "address": addr.address,
                                "netmask": addr.netmask
                            })
                        elif addr.family.name == 'AF_INET6':  # IPv6
                            interface_info["addresses"].append({
                                "type": "IPv6",
                                "address": addr.address
                            })
                
                network_info["interfaces"].append(interface_info)
            
            # تعداد کانکشن‌های فعال
            connections = psutil.net_connections()
            network_info["connections_count"] = len(connections)
            
            # تعداد کانکشن‌ها بر اساس وضعیت
            status_count = {}
            for conn in connections:
                status = conn.status
                status_count[status] = status_count.get(status, 0) + 1
            
            network_info["connections_by_status"] = status_count
            
        except Exception as e:
            debug_log(f"خطا در دریافت اطلاعات شبکه: {str(e)}", "WARNING")
    
    return network_info

@debug_decorator
def get_process_info() -> Dict[str, Any]:
    """
    دریافت اطلاعات فرایندها
    
    Returns:
        دیکشنری حاوی اطلاعات فرایندها
    """
    process_info = {
        "total_count": 0,
        "running_count": 0,
        "this_process": {
            "pid": os.getpid(),
            "cpu_percent": 0,
            "memory_percent": 0,
            "memory_usage": "نامشخص",
            "threads_count": 0
        }
    }
    
    if PSUTIL_AVAILABLE:
        try:
            # اطلاعات همه فرایندها
            all_processes = list(psutil.process_iter(['pid', 'name', 'status']))
            process_info["total_count"] = len(all_processes)
            process_info["running_count"] = sum(1 for p in all_processes if p.info['status'] == 'running')
            
            # اطلاعات وضعیت‌ها
            status_count = {}
            for p in all_processes:
                status = p.info['status']
                status_count[status] = status_count.get(status, 0) + 1
            
            process_info["status_count"] = status_count
            
            # اطلاعات این فرایند
            current_process = psutil.Process(os.getpid())
            
            with current_process.oneshot():  # بهینه‌سازی با استفاده از oneshot
                cpu_percent = current_process.cpu_percent(interval=0.1)
                memory_percent = current_process.memory_percent()
                memory_info = current_process.memory_info()
                threads_count = current_process.num_threads()
                
                process_info["this_process"]["cpu_percent"] = cpu_percent
                process_info["this_process"]["memory_percent"] = memory_percent
                process_info["this_process"]["memory_usage"] = _bytes_to_human_readable(memory_info.rss)
                process_info["this_process"]["threads_count"] = threads_count
                process_info["this_process"]["create_time"] = datetime.datetime.fromtimestamp(
                    current_process.create_time()
                ).strftime("%Y-%m-%d %H:%M:%S")
                
        except Exception as e:
            debug_log(f"خطا در دریافت اطلاعات فرایندها: {str(e)}", "WARNING")
    
    return process_info

@debug_decorator
def get_os_info() -> Dict[str, Any]:
    """
    دریافت اطلاعات سیستم‌عامل
    
    Returns:
        دیکشنری حاوی اطلاعات سیستم‌عامل
    """
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "node": platform.node()
    }

@debug_decorator
def get_system_info(cache: bool = True) -> Dict[str, Any]:
    """
    دریافت اطلاعات کامل سیستم
    
    Args:
        cache: استفاده از کش (True در صورت استفاده)
        
    Returns:
        دیکشنری حاوی همه اطلاعات سیستم
    """
    global system_info_cache, system_info_cache_time
    
    current_time = time.time()
    
    # استفاده از کش در صورت معتبر بودن
    with cache_lock:
        if cache and system_info_cache and (current_time - system_info_cache_time) < CACHE_TIMEOUT:
            return system_info_cache.copy()
    
    debug_log("در حال جمع‌آوری اطلاعات سیستم...", "INFO")
    
    # جمع‌آوری اطلاعات
    system_info = {
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "disk": get_disk_info(),
        "os": get_os_info(),
        "uptime": get_system_uptime(),
        "network": get_network_info(),
        "process": get_process_info(),
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # به‌روزرسانی کش
    with cache_lock:
        system_info_cache = system_info.copy()
        system_info_cache_time = current_time
    
    return system_info

@debug_decorator
def get_system_status_text() -> str:
    """
    دریافت متن وضعیت سیستم برای نمایش به کاربر
    
    Returns:
        متن فرمت‌بندی شده برای نمایش
    """
    system_info = get_system_info()
    
    # فرمت‌بندی اطلاعات
    status_lines = [
        "🖥 *وضعیت سیستم*",
        "",
        "*سیستم‌عامل:* " + system_info["os"]["system"] + " " + system_info["os"]["release"],
        f"*زمان کارکرد:* {system_info['uptime']['uptime_human']}",
        "",
        "💻 *CPU:*",
        f"🔄 استفاده: {system_info['cpu']['usage_percent']}%",
        f"📊 هسته‌ها: {system_info['cpu']['cores']}",
        "",
        "🧠 *حافظه:*",
        f"📊 استفاده: {system_info['memory']['percent_used']}%",
        f"💾 کل: {system_info['memory']['total_human']}",
        f"🔄 استفاده شده: {system_info['memory']['used_human']}",
        f"✅ آزاد: {system_info['memory']['available_human']}",
        "",
        "💿 *دیسک:*",
        f"📊 استفاده: {system_info['disk']['percent_used']}%",
        f"💾 کل: {system_info['disk']['total_human']}",
        f"🔄 استفاده شده: {system_info['disk']['used_human']}",
        f"✅ آزاد: {system_info['disk']['free_human']}",
        "",
        "🤖 *فرایند فعلی:*",
        f"🆔 PID: {system_info['process']['this_process']['pid']}",
        f"🔄 CPU: {system_info['process']['this_process']['cpu_percent']}%",
        f"🧠 حافظه: {system_info['process']['this_process']['memory_usage']}",
        f"🧵 تعداد ترد‌ها: {system_info['process']['this_process']['threads_count']}",
        "",
        "⏱ *زمان:* " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ]
    
    return "\n".join(status_lines)

@debug_decorator
def get_system_status_short() -> str:
    """
    دریافت خلاصه وضعیت سیستم
    
    Returns:
        متن خلاصه وضعیت
    """
    system_info = get_system_info()
    
    status = (
        f"CPU: {system_info['cpu']['usage_percent']}% | "
        f"RAM: {system_info['memory']['percent_used']}% | "
        f"Disk: {system_info['disk']['percent_used']}%"
    )
    
    return status
