import os
import sys
import json
import datetime
import threading
import concurrent.futures
import time
import traceback
import logging
import types
from requests.exceptions import ReadTimeout, ProxyError, ConnectionError

# تنظیم لاگر اصلی
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# واردکردن ماژول‌های داخلی
try:
    # سیستم لاگینگ پیشرفته
    from debug_logger import debug_log, log_webhook_request, log_telegram_update, debug_decorator, format_exception_with_context
    logger.info("✅ سیستم دیباگینگ پیشرفته با موفقیت بارگذاری شد")
except ImportError as e:
    logger.error(f"⚠️ خطا در بارگذاری ماژول debug_logger: {e}")
    # تعریف توابع جایگزین در صورت عدم دسترسی به ماژول دیباگینگ
    def debug_log(message, level="DEBUG", context=None):
        logger.debug(f"{message} - Context: {context}")
    
    def log_webhook_request(data):
        if isinstance(data, bytes):
            data_str = data.decode('utf-8')
        else:
            data_str = str(data)
        logger.debug(f"Webhook data: {data_str[:200]}...")
    
    def log_telegram_update(update):
        logger.debug(f"Telegram update: {update}")
    
    def debug_decorator(func):
        return func
    
    def format_exception_with_context(e):
        return traceback.format_exc()

# واردکردن ماژول‌های خارجی با مدیریت خطا
try:
    import telebot
    logger.info("✅ ماژول telebot با موفقیت بارگذاری شد")
except ImportError:
    logger.error("⚠️ ماژول telebot نصب نشده است")
    exit(1)

try:
    from flask import Flask, request
    logger.info("✅ ماژول flask با موفقیت بارگذاری شد")
except ImportError:
    logger.error("⚠️ ماژول flask نصب نشده است")

try:
    import shutil  # برای دریافت وضعیت دیسک
    logger.info("✅ ماژول shutil با موفقیت بارگذاری شد")
except ImportError:
    logger.error("⚠️ ماژول shutil در دسترس نیست")
    
try:
    import psutil  # برای دریافت اطلاعات CPU و RAM
    logger.info("✅ ماژول psutil با موفقیت بارگذاری شد")
except ImportError:
    logger.error("⚠️ ماژول psutil نصب نشده است")
    
try:
    import platform  # برای دریافت اطلاعات سیستم‌عامل
    logger.info("✅ ماژول platform با موفقیت بارگذاری شد")
except ImportError:
    logger.error("⚠️ ماژول platform در دسترس نیست")
    
try:
    import sqlite3
    logger.info("✅ ماژول sqlite3 با موفقیت بارگذاری شد")
except ImportError:
    logger.error("⚠️ ماژول sqlite3 در دسترس نیست")
    
try:
    from yt_dlp import YoutubeDL
    logger.info("✅ ماژول yt_dlp با موفقیت بارگذاری شد")
except ImportError:
    logger.error("⚠️ ماژول yt_dlp نصب نشده است")

app = Flask(__name__)

# ایجاد استخر ترد برای اجرای همزمان فرایندها با تعداد بهینه
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)  # کاهش تعداد ترد‌ها برای کاهش مصرف منابع


# برای دریافت وب‌هوک از فلسک استفاده می‌کنیم
@debug_decorator
def webhook():
    json_str = None
    debug_log("شروع دریافت وب‌هوک جدید", "INFO")
    
    try:
        # دریافت داده‌های از درخواست با مدیریت خطا
        try:
            json_raw = request.get_data()
            debug_log(f"داده خام وب‌هوک دریافت شد: {len(json_raw)} بایت", "DEBUG")
            
            # تلاش برای رمزگشایی داده‌ها
            try:
                json_str = json_raw.decode("UTF-8")
            except UnicodeDecodeError:
                # اگر UTF-8 کار نکرد، روش‌های دیگر را امتحان کن
                try:
                    json_str = json_raw.decode("latin-1")
                    debug_log("داده وب‌هوک با latin-1 رمزگشایی شد", "WARNING")
                except Exception:
                    # اگر همه روش‌ها شکست خورد، فقط داده باینری را لاگ کن
                    debug_log("عدم توانایی در رمزگشایی داده وب‌هوک", "ERROR")
                    log_webhook_request(json_raw)
                    return "خطای رمزگشایی داده", 400
            
            # لاگ کردن بخشی از داده دریافتی
            if json_str:
                preview = json_str[:100] + ("..." if len(json_str) > 100 else "")
                debug_log(f"داده دریافتی وب‌هوک: {preview}", "INFO")
                log_webhook_request(json_str)
                
        except Exception as req_error:
            debug_log(f"خطا در دریافت داده از درخواست وب‌هوک", "ERROR", {
                "error_type": type(req_error).__name__,
                "error_message": str(req_error)
            })
            return "خطا در دریافت داده درخواست", 400
            
        # تبدیل JSON به آبجکت Update تلگرام با مدیریت خطا
        try:
            # اطمینان از وجود داده
            if not json_str:
                debug_log("JSON خالی یا نامعتبر", "ERROR")
                return "داده JSON نامعتبر است", 400
                
            # تبدیل به آبجکت Update
            try:
                update = telebot.types.Update.de_json(json_str)
                if not update:
                    debug_log("تبدیل JSON به آبجکت Update با مشکل مواجه شد", "ERROR")
                    return "تبدیل JSON ناموفق بود", 400
            except Exception as json_error:
                debug_log(f"خطا در تبدیل JSON به آبجکت Update", "ERROR", {
                    "error_type": type(json_error).__name__,
                    "error_message": str(json_error),
                    "json_sample": json_str[:200] if json_str else "None"
                })
                return "خطا در تبدیل JSON", 400
                
            # ثبت آپدیت تلگرام در لاگ با مدیریت خطا
            try:
                log_telegram_update(update)
            except Exception as log_error:
                debug_log(f"خطا در لاگ کردن آپدیت تلگرام", "ERROR", {
                    "error_type": type(log_error).__name__,
                    "error_message": str(log_error)
                })
                # ادامه می‌دهیم حتی اگر لاگینگ خطا داشته باشد
                
            # بررسی نوع پیام برای لاگ با مدیریت خطا
            try:
                if hasattr(update, 'message') and update.message is not None:
                    user_id = None
                    msg_text = None
                    
                    # استخراج اطلاعات کاربر با مدیریت خطا
                    try:
                        if hasattr(update.message, 'from_user') and update.message.from_user is not None:
                            user_id = update.message.from_user.id
                            username = update.message.from_user.username if hasattr(update.message.from_user, 'username') else None
                    except Exception:
                        debug_log("خطا در استخراج اطلاعات کاربر", "WARNING")
                    
                    # استخراج متن پیام با مدیریت خطا
                    try:
                        msg_text = update.message.text if hasattr(update.message, 'text') else "[NO_TEXT]"
                    except Exception:
                        debug_log("خطا در استخراج متن پیام", "WARNING")
                        msg_text = "[ERROR_EXTRACTING_TEXT]"
                        
                    # لاگ کردن پیام
                    log_data = {
                        "user_id": user_id,
                        "chat_id": update.message.chat.id if hasattr(update.message, 'chat') and hasattr(update.message.chat, 'id') else None,
                        "message_id": update.message.message_id if hasattr(update.message, 'message_id') else None
                    }
                    
                    # اضافه کردن یوزرنیم اگر موجود باشد
                    if hasattr(update.message, 'from_user') and update.message.from_user and hasattr(update.message.from_user, 'username'):
                        log_data["username"] = update.message.from_user.username
                        
                    debug_log(f"پیام جدید از کاربر {user_id}: {msg_text}", "INFO", log_data)
                
                elif hasattr(update, 'callback_query') and update.callback_query is not None:
                    # استخراج اطلاعات کالبک کوئری با مدیریت خطا
                    callback_info = {}
                    
                    try:
                        if hasattr(update.callback_query, 'from_user') and update.callback_query.from_user:
                            callback_info["user_id"] = update.callback_query.from_user.id
                    except Exception:
                        debug_log("خطا در استخراج شناسه کاربر از کالبک کوئری", "WARNING")
                        callback_info["user_id"] = None
                        
                    try:
                        callback_info["query_id"] = update.callback_query.id if hasattr(update.callback_query, 'id') else None
                    except Exception:
                        debug_log("خطا در استخراج شناسه کالبک کوئری", "WARNING")
                        
                    try:
                        callback_info["data"] = update.callback_query.data if hasattr(update.callback_query, 'data') else None
                    except Exception:
                        debug_log("خطا در استخراج داده کالبک کوئری", "WARNING")
                        
                    # لاگ کردن کالبک کوئری
                    user_id_str = str(callback_info.get("user_id", "نامشخص"))
                    debug_log(f"کالبک کوئری جدید از کاربر {user_id_str}", "INFO", callback_info)
            except Exception as msg_log_error:
                debug_log(f"خطا در لاگ کردن جزئیات پیام", "ERROR", {
                    "error_type": type(msg_log_error).__name__,
                    "error_message": str(msg_log_error)
                })
                # ادامه می‌دهیم حتی اگر لاگینگ خطا داشته باشد
                
            # پردازش پیام با مدیریت خطا
            try:
                bot.process_new_updates([update])
                debug_log("پیام با موفقیت پردازش شد", "INFO")
                return "✅ Webhook دریافت شد!", 200
            except Exception as process_error:
                error_details = format_exception_with_context(process_error)
                debug_log(f"خطا در پردازش پیام توسط ربات", "ERROR", {
                    "error_type": type(process_error).__name__,
                    "error_message": str(process_error),
                    "traceback": error_details
                })
                
                # اطلاع‌رسانی به ادمین با محدود کردن طول پیام
                try:
                    notify_admin(f"⚠️ خطا در پردازش پیام:\n{str(process_error)}\n\n{error_details[:2000]}...")
                except Exception:
                    debug_log("خطا در اطلاع‌رسانی به ادمین", "ERROR")
                    
                return f"خطا در پردازش پیام", 500
                
        except Exception as update_error:
            error_details = format_exception_with_context(update_error)
            debug_log(f"خطا در پردازش آپدیت تلگرام", "ERROR", {
                "error_type": type(update_error).__name__,
                "error_message": str(update_error),
                "traceback": error_details
            })
            
            # اطلاع‌رسانی به ادمین
            try:
                notify_admin(f"⚠️ خطا در پردازش آپدیت:\n{str(update_error)}\n\n{error_details[:2000]}...")
            except Exception:
                debug_log("خطا در اطلاع‌رسانی به ادمین", "ERROR")
                
            return f"خطا در پردازش آپدیت", 500
            
    except Exception as e:
        # مدیریت هر گونه خطای غیرمنتظره
        try:
            error_details = format_exception_with_context(e)
            debug_log(f"خطای غیرمنتظره در پردازش وب‌هوک", "ERROR", {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": error_details
            })
            
            # اطلاع‌رسانی به ادمین
            try:
                notify_admin(f"⚠️ خطای غیرمنتظره در وب‌هوک:\n{str(e)}\n\n{error_details[:2000]}...")
            except Exception:
                debug_log("خطا در اطلاع‌رسانی به ادمین", "ERROR")
                
        except Exception as logging_error:
            # اگر حتی لاگینگ هم خطا داشت، یک پیام ساده ثبت کن
            print(f"Critical error in webhook handler: {str(e)} - Logging error: {str(logging_error)}")
            
        return f"خطای سرور", 500


SERVER_CACHE = {"status": None, "timestamp": None}


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
        print(f"⚠️ خطا در بررسی کش: {e}")

    # اگر وضعیت در کش نباشد یا منقضی شده باشد، از فایل بخوان
    if os.path.exists("server_status.json"):
        try:
            with open("server_status.json", "r", encoding="utf-8") as file:
                data = json.load(file)
                
                if "status" in data and "timestamp" in data:
                    try:
                        timestamp = datetime.datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S")
                        SERVER_CACHE["status"] = data["status"]
                        SERVER_CACHE["timestamp"] = timestamp
                        return data["status"]
                    except ValueError as e:
                        print(f"⚠️ خطا در تبدیل تاریخ: {e}")
                        return None
                else:
                    return None
        except Exception as e:
            print(f"⚠️ خطا در خواندن فایل کش: {e}")
            return None
    return None


MESSAGES_DB_TEXT = "channel_messages.json"
MESSAGES_DB_LINKS = "channel_links.json"
MAX_MESSAGES = 100000  # حداکثر تعداد لینک‌های ذخیره‌شده

# 📂 اگر فایل ذخیره‌ی پیام‌ها وجود نداشت، ایجادش کن
if not os.path.exists(MESSAGES_DB_LINKS):
    with open(MESSAGES_DB_LINKS, "w", encoding="utf-8") as file:
        json.dump({}, file, ensure_ascii=False, indent=4)

# 🔑 توکن ربات تلگرام از متغیرهای محیطی با مدیریت خطای پیشرفته
try:
    # دریافت توکن از متغیرهای محیطی
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    # بررسی اعتبار و فرمت توکن
    if not TOKEN:
        debug_log("⚠️ متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم نشده است!", "ERROR")
        # به جای ساخت توکن ساختگی، یک خطا را بالا می‌آوریم تا کد به صورت کامل متوقف شود
        raise ValueError("توکن تلگرام تنظیم نشده است")
        
    # بررسی فرمت توکن (باید شامل کولون باشد و بخش اول آن عدد باشد)
    if ":" not in TOKEN:
        debug_log(f"⚠️ فرمت توکن معتبر نیست (باید شامل کولون (:) باشد)", "ERROR")
        raise ValueError("فرمت توکن تلگرام نامعتبر است - کولون یافت نشد")
    
    # تلاش برای تبدیل بخش اول توکن به عدد صحیح (برای اطمینان از صحت فرمت)
    try:
        int(TOKEN.split(':')[0])
    except ValueError:
        debug_log(f"⚠️ بخش اول توکن باید یک عدد صحیح باشد", "ERROR")
        raise ValueError("فرمت توکن تلگرام نامعتبر است - بخش اول باید عدد باشد")
    
    debug_log(f"توکن تلگرام با موفقیت خوانده شد (طول: {len(TOKEN)})", "INFO")
    
    # ایجاد آبجکت ربات با توکن
    bot = telebot.TeleBot(TOKEN)
    
except Exception as e:
    debug_log(f"⚠️ خطا در تنظیم توکن ربات: {e}", "ERROR", {
        "error_type": type(e).__name__,
        "traceback": format_exception_with_context(e)
    })
    # به جای ادامه با توکن ناقص، برنامه را متوقف می‌کنیم تا مشکل حل شود
    print(f"⚠️ خطا در راه‌اندازی ربات. لطفاً توکن معتبر را تنظیم کنید: {e}")
    # ایجاد متغیر BOT_INIT_ERROR برای استفاده در بخش‌های دیگر
    BOT_INIT_ERROR = str(e)
    
    # استفاده از sys.exit() برای خروج از برنامه در محیط تولید
    if os.environ.get('FLASK_ENV') == 'production':
        sys.exit(1)
    else:
        # در محیط توسعه، اجازه می‌دهیم ادامه یابد اما بدون ایجاد آبجکت ربات
        print("⚠️ محیط توسعه شناسایی شد. ادامه بدون ربات فعال.")
        bot = None

# 📢 آیدی عددی ادمین
ADMIN_CHAT_ID = 286420965

# 📊 تنظیمات بهینه‌سازی فضا
MAX_VIDEOS_TO_KEEP = 0  # حداکثر تعداد ویدئو‌های ذخیره‌شده (صفر = حذف تمام فایل‌ها پس از ارسال)
VIDEO_CACHE_TIMEOUT = 60 * 10  # مدت زمان نگهداری کش ویدیو (10 دقیقه)

# 📂 مسیر ذخیره ویدیوها
VIDEO_FOLDER = "videos"
INSTAGRAM_FOLDER = "instagram_videos"
os.makedirs(VIDEO_FOLDER, exist_ok=True)
os.makedirs(INSTAGRAM_FOLDER, exist_ok=True)

# 🎬 تنظیمات کیفیت ویدیو
VIDEO_QUALITIES = {
    "144p": {"format": "160/17/18/597", "description": "کیفیت پایین (144p) - سریع‌ترین"},
    "240p": {"format": "133+140/242+140/243+140/134+140/18", "description": "کیفیت معمولی (240p)"},
    "360p": {"format": "134+140/243+140/18/597/22", "description": "کیفیت متوسط (360p)"},
    "480p": {"format": "135+140/244+140/247+140/22", "description": "کیفیت خوب (480p)"},
    "720p": {"format": "136+140/247+140/22", "description": "کیفیت عالی (720p) - حجم بالا"},
    "1080p": {"format": "137+140/248+140/22", "description": "کیفیت فول HD (1080p) - حجم بسیار بالا"}
}

DEFAULT_VIDEO_QUALITY = "240p"  # کیفیت پیش‌فرض برای صرفه‌جویی در فضا

# 🔖 فایل ذخیره اطلاعات هشتگ‌ها
HASHTAGS_FILE = "hashtags.json"

# پیام‌های بازیابی شده برای هر هشتگ 
hashtag_cache = {}

# زمان آخرین پاکسازی فایل‌ها
last_cleanup_time = 0

# تعداد حداکثر پیام برای جستجو در هر کانال
MAX_SEARCH_MESSAGES = 100000

# تعداد حداکثر پیام برای ارسال در هر هشتگ
MAX_SEND_MESSAGES = 100

# تابع بارگیری هشتگ‌ها و کانال‌ها از فایل
def load_hashtags():
    """بارگیری اطلاعات هشتگ‌ها و کانال‌ها از فایل"""
    try:
        if os.path.exists(HASHTAGS_FILE):
            with open(HASHTAGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                debug_log("اطلاعات هشتگ‌ها با موفقیت بارگیری شد", "INFO")
                return data
        else:
            data = {"hashtags": {}, "channels": []}
            with open(HASHTAGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            debug_log("فایل هشتگ‌ها ایجاد شد", "INFO")
            return data
    except Exception as e:
        debug_log(f"خطا در بارگیری اطلاعات هشتگ‌ها: {e}", "ERROR")
        return {"hashtags": {}, "channels": []}

# تابع ذخیره هشتگ‌ها و کانال‌ها در فایل
def save_hashtags(data):
    """ذخیره اطلاعات هشتگ‌ها و کانال‌ها در فایل"""
    try:
        with open(HASHTAGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        debug_log("اطلاعات هشتگ‌ها با موفقیت ذخیره شد", "INFO")
        return True
    except Exception as e:
        debug_log(f"خطا در ذخیره اطلاعات هشتگ‌ها: {e}", "ERROR")
        return False

# 🧹 پاکسازی فایل‌های قدیمی و حذف تمام فایل‌ها
def clear_folder(folder_path, max_files=MAX_VIDEOS_TO_KEEP):
    """حذف فایل‌های قدیمی و نگهداری حداکثر تعداد مشخصی فایل"""
    try:
        # اطمینان از وجود پوشه
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            debug_log(f"پوشه {folder_path} ایجاد شد", "INFO")
            return
            
        # بررسی آیا فولدر است یا خیر
        if not os.path.isdir(folder_path):
            debug_log(f"مسیر {folder_path} یک پوشه نیست", "ERROR")
            return
        
        try:
            # لیست فایل‌ها را دریافت می‌کنیم
            files = []
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                # فقط فایل‌ها را پردازش می‌کنیم (نه پوشه‌ها)
                if os.path.isfile(item_path):
                    files.append(item)
            
            # اگر max_files صفر باشد، همه فایل‌ها را حذف می‌کنیم
            if max_files == 0:
                files_to_delete = files
            # در غیر این صورت، فقط فایل‌های قدیمی را حذف می‌کنیم
            elif len(files) > max_files:
                # مرتب‌سازی فایل‌ها بر اساس زمان تغییر (قدیمی‌ترین اول)
                try:
                    files = sorted(files, key=lambda x: os.path.getmtime(os.path.join(folder_path, x)))
                except Exception as sort_error:
                    debug_log("خطا در مرتب‌سازی فایل‌ها بر اساس زمان", "WARNING", {"error": str(sort_error)})
                    # اگر مرتب‌سازی با خطا مواجه شد، به صورت معمولی مرتب می‌کنیم
                    files = sorted(files)
                
                # تعداد فایل‌هایی که باید حذف شوند
                files_to_delete = files[:-max_files] if max_files > 0 else files
            else:
                # اگر تعداد فایل‌ها کمتر از حد مجاز است و max_files غیرصفر است، نیازی به حذف نیست
                return
                
            debug_log(f"پاکسازی پوشه {folder_path}", "INFO", {
                "total_files": len(files),
                "files_to_delete": len(files_to_delete),
                "max_files": max_files
            })
            
            # حذف فایل‌های قدیمی
            deleted_count = 0
            for old_file in files_to_delete:
                try:
                    file_path = os.path.join(folder_path, old_file)
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as delete_error:
                    debug_log(f"خطا در حذف فایل {old_file}", "WARNING", {"error": str(delete_error)})
            
            debug_log(f"پاکسازی پوشه {folder_path} انجام شد", "INFO", {"deleted_files": deleted_count})
        except Exception as list_error:
            debug_log(f"خطا در خواندن لیست فایل‌های پوشه", "ERROR", {"error": str(list_error)})
            
    except Exception as e:
        debug_log(f"خطا در پاکسازی پوشه", "ERROR", {
            "folder": folder_path,
            "error": str(e),
            "traceback": traceback.format_exc()
        })


# 📌 دستور شروع - Start command
@bot.message_handler(commands=["start"])
def start_command(message):
    try:
        # ایجاد کیبورد اینلاین با دکمه‌های مختلف
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        help_btn = telebot.types.InlineKeyboardButton("📚 راهنما", callback_data="download_help")
        quality_btn = telebot.types.InlineKeyboardButton("📊 کیفیت ویدیو", callback_data="select_quality")
        status_btn = telebot.types.InlineKeyboardButton("📈 وضعیت سرور", callback_data="server_status")
        
        markup.add(help_btn, quality_btn)
        markup.add(status_btn)
        
        # ارسال پیام خوشامدگویی
        bot.send_message(
            message.chat.id,
            f"👋 سلام {message.from_user.first_name}!\n\n"
            "🎬 به ربات دانلود ویدیو خوش آمدید.\n\n"
            "🔸 <b>قابلیت‌های ربات:</b>\n"
            "• دانلود ویدیو از یوتیوب و اینستاگرام\n"
            "• امکان انتخاب کیفیت ویدیو\n"
            "• پاسخ‌گویی به سوالات متداول\n\n"
            "🔹 <b>روش استفاده:</b>\n"
            "کافیست لینک ویدیوی مورد نظر خود را از یوتیوب یا اینستاگرام ارسال کنید.",
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception as e:
        notify_admin(f"⚠️ خطا در دستور start:\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "⚠ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

# 📚 دستور راهنما - Help command
@bot.message_handler(commands=["help"])
def help_command(message):
    try:
        # ایجاد کیبورد اینلاین با دکمه‌های مختلف
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        quality_btn = telebot.types.InlineKeyboardButton("📊 انتخاب کیفیت ویدیو", callback_data="select_quality")
        hashtag_btn = telebot.types.InlineKeyboardButton("🔖 راهنمای هشتگ", callback_data="hashtag_help")
        
        markup.add(quality_btn, hashtag_btn)
        
        # ارسال پیام راهنما
        bot.send_message(
            message.chat.id,
            "🔰 <b>راهنمای استفاده از ربات</b>\n\n"
            "📌 <b>دستورات اصلی:</b>\n"
            "/start - شروع کار با ربات\n"
            "/help - نمایش این راهنما\n"
            "/server_status - مشاهده وضعیت سرور\n\n"
            "📥 <b>دانلود ویدیو:</b>\n"
            "• کافیست لینک ویدیوی مورد نظر را از یوتیوب یا اینستاگرام ارسال کنید\n"
            "• می‌توانید کیفیت مورد نظر را از منوی زیر انتخاب کنید\n\n"
            "🔖 <b>جستجوی هشتگ:</b>\n"
            "• برای مدیریت هشتگ‌ها از دستورات /add_hashtag، /remove_hashtag و /hashtags استفاده کنید\n"
            "• برای مدیریت کانال‌ها از دستورات /add_channel، /remove_channel و /channels استفاده کنید\n"
            "• برای جستجوی هشتگ در کانال‌ها از دستور /search استفاده کنید\n\n"
            "⚠️ <b>نکات مهم:</b>\n"
            "• برای صرفه‌جویی در حجم اینترنت و سرعت بالاتر، از کیفیت‌های پایین‌تر استفاده کنید\n"
            "• کیفیت پیش‌فرض 240p است\n"
            "• ویدیوهای بالای 50MB قابل ارسال نیستند و باید با کیفیت پایین‌تر دانلود شوند",
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception as e:
        notify_admin(f"⚠️ خطا در دستور help:\n{traceback.format_exc()}")
        bot.send_message(message.chat.id, "⚠ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

# 📌 مدیریت هشتگ‌ها - اضافه کردن هشتگ جدید
@bot.message_handler(commands=["add_hashtag"])
def add_hashtag_command(message):
    try:
        # جداسازی آرگومان‌ها
        args = message.text.split(maxsplit=2)
        
        # بررسی آرگومان‌های لازم
        if len(args) < 3:
            bot.reply_to(message, "⚠️ فرمت دستور نادرست است.\n"
                        "📝 نحوه استفاده: `/add_hashtag نام_هشتگ توضیحات`\n"
                        "مثال: `/add_hashtag آموزش این هشتگ برای ویدیوهای آموزشی است`", parse_mode="Markdown")
            return
        
        # دریافت نام هشتگ و توضیحات
        hashtag = args[1]
        description = args[2]
        
        # اضافه کردن # به ابتدای هشتگ اگر وجود نداشته باشد
        if not hashtag.startswith("#"):
            hashtag = "#" + hashtag
        
        # بارگیری اطلاعات هشتگ‌ها
        data = load_hashtags()
        
        # اضافه کردن هشتگ جدید
        data["hashtags"][hashtag] = {
            "description": description,
            "created_by": message.from_user.id,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "messages": []
        }
        
        # ذخیره اطلاعات هشتگ‌ها
        if save_hashtags(data):
            bot.reply_to(message, f"✅ هشتگ {hashtag} با موفقیت اضافه شد.")
        else:
            bot.reply_to(message, "⚠️ خطا در ذخیره اطلاعات هشتگ‌ها.")
    
    except Exception as e:
        debug_log(f"خطا در اضافه کردن هشتگ", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

# 📌 مدیریت هشتگ‌ها - حذف هشتگ
@bot.message_handler(commands=["remove_hashtag"])
def remove_hashtag_command(message):
    try:
        # جداسازی آرگومان‌ها
        args = message.text.split(maxsplit=1)
        
        # بررسی آرگومان‌های لازم
        if len(args) < 2:
            bot.reply_to(message, "⚠️ فرمت دستور نادرست است.\n"
                        "📝 نحوه استفاده: `/remove_hashtag نام_هشتگ`\n"
                        "مثال: `/remove_hashtag آموزش`", parse_mode="Markdown")
            return
        
        # دریافت نام هشتگ
        hashtag = args[1]
        
        # اضافه کردن # به ابتدای هشتگ اگر وجود نداشته باشد
        if not hashtag.startswith("#"):
            hashtag = "#" + hashtag
        
        # بارگیری اطلاعات هشتگ‌ها
        data = load_hashtags()
        
        # بررسی وجود هشتگ
        if hashtag not in data["hashtags"]:
            bot.reply_to(message, f"⚠️ هشتگ {hashtag} یافت نشد.")
            return
        
        # حذف هشتگ
        del data["hashtags"][hashtag]
        
        # ذخیره اطلاعات هشتگ‌ها
        if save_hashtags(data):
            bot.reply_to(message, f"✅ هشتگ {hashtag} با موفقیت حذف شد.")
        else:
            bot.reply_to(message, "⚠️ خطا در ذخیره اطلاعات هشتگ‌ها.")
    
    except Exception as e:
        debug_log(f"خطا در حذف هشتگ", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

# 📌 مدیریت هشتگ‌ها - لیست هشتگ‌ها
@bot.message_handler(commands=["hashtags"])
def list_hashtags_command(message):
    try:
        # بارگیری اطلاعات هشتگ‌ها
        data = load_hashtags()
        
        # بررسی وجود هشتگ
        if not data["hashtags"]:
            bot.reply_to(message, "⚠️ هنوز هیچ هشتگی تعریف نشده است.")
            return
        
        # ساخت پیام لیست هشتگ‌ها
        hashtags_list = ["🔖 <b>لیست هشتگ‌های تعریف شده:</b>\n"]
        
        for idx, (hashtag, info) in enumerate(data["hashtags"].items(), 1):
            hashtags_list.append(f"{idx}. <code>{hashtag}</code> - {info['description']}")
        
        # ارسال لیست هشتگ‌ها
        bot.reply_to(message, "\n".join(hashtags_list), parse_mode="HTML")
    
    except Exception as e:
        debug_log(f"خطا در نمایش لیست هشتگ‌ها", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

# 📌 مدیریت کانال‌ها - اضافه کردن کانال
@bot.message_handler(commands=["add_channel"])
def add_channel_command(message):
    try:
        # جداسازی آرگومان‌ها
        args = message.text.split(maxsplit=1)
        
        # بررسی آرگومان‌های لازم
        if len(args) < 2:
            bot.reply_to(message, "⚠️ فرمت دستور نادرست است.\n"
                        "📝 نحوه استفاده: `/add_channel آیدی_کانال`\n"
                        "مثال: `/add_channel @mychannel` یا `/add_channel -1001234567890`", parse_mode="Markdown")
            return
        
        # دریافت آیدی کانال
        channel_id = args[1]
        
        # بارگیری اطلاعات هشتگ‌ها
        data = load_hashtags()
        
        # بررسی تکراری نبودن کانال
        if channel_id in data["channels"]:
            bot.reply_to(message, f"⚠️ کانال {channel_id} قبلاً اضافه شده است.")
            return
        
        # اضافه کردن کانال جدید
        data["channels"].append(channel_id)
        
        # ذخیره اطلاعات هشتگ‌ها
        if save_hashtags(data):
            bot.reply_to(message, f"✅ کانال {channel_id} با موفقیت اضافه شد.")
        else:
            bot.reply_to(message, "⚠️ خطا در ذخیره اطلاعات کانال‌ها.")
    
    except Exception as e:
        debug_log(f"خطا در اضافه کردن کانال", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

# 📌 مدیریت کانال‌ها - حذف کانال
@bot.message_handler(commands=["remove_channel"])
def remove_channel_command(message):
    try:
        # جداسازی آرگومان‌ها
        args = message.text.split(maxsplit=1)
        
        # بررسی آرگومان‌های لازم
        if len(args) < 2:
            bot.reply_to(message, "⚠️ فرمت دستور نادرست است.\n"
                        "📝 نحوه استفاده: `/remove_channel آیدی_کانال`\n"
                        "مثال: `/remove_channel @mychannel` یا `/remove_channel -1001234567890`", parse_mode="Markdown")
            return
        
        # دریافت آیدی کانال
        channel_id = args[1]
        
        # بارگیری اطلاعات هشتگ‌ها
        data = load_hashtags()
        
        # بررسی وجود کانال
        if channel_id not in data["channels"]:
            bot.reply_to(message, f"⚠️ کانال {channel_id} یافت نشد.")
            return
        
        # حذف کانال
        data["channels"].remove(channel_id)
        
        # ذخیره اطلاعات هشتگ‌ها
        if save_hashtags(data):
            bot.reply_to(message, f"✅ کانال {channel_id} با موفقیت حذف شد.")
        else:
            bot.reply_to(message, "⚠️ خطا در ذخیره اطلاعات کانال‌ها.")
    
    except Exception as e:
        debug_log(f"خطا در حذف کانال", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

# 📌 مدیریت کانال‌ها - لیست کانال‌ها
@bot.message_handler(commands=["channels"])
def list_channels_command(message):
    try:
        # بارگیری اطلاعات هشتگ‌ها
        data = load_hashtags()
        
        # بررسی وجود کانال
        if not data["channels"]:
            bot.reply_to(message, "⚠️ هنوز هیچ کانالی تعریف نشده است.")
            return
        
        # ساخت پیام لیست کانال‌ها
        channels_list = ["📢 <b>لیست کانال‌های تعریف شده:</b>\n"]
        
        for idx, channel_id in enumerate(data["channels"], 1):
            channels_list.append(f"{idx}. <code>{channel_id}</code>")
        
        # ارسال لیست کانال‌ها
        bot.reply_to(message, "\n".join(channels_list), parse_mode="HTML")
    
    except Exception as e:
        debug_log(f"خطا در نمایش لیست کانال‌ها", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

# 📌 جستجوی هشتگ - دستور جستجوی هشتگ
@bot.message_handler(commands=["search"])
def search_hashtag_command(message):
    try:
        # جداسازی آرگومان‌ها
        args = message.text.split(maxsplit=1)
        
        # بررسی آرگومان‌های لازم
        if len(args) < 2:
            bot.reply_to(message, "⚠️ فرمت دستور نادرست است.\n"
                        "📝 نحوه استفاده: `/search نام_هشتگ`\n"
                        "مثال: `/search آموزش`", parse_mode="Markdown")
            return
        
        # دریافت نام هشتگ
        hashtag = args[1]
        
        # اضافه کردن # به ابتدای هشتگ اگر وجود نداشته باشد
        if not hashtag.startswith("#"):
            hashtag = "#" + hashtag
        
        # بارگیری اطلاعات هشتگ‌ها
        data = load_hashtags()
        
        # بررسی وجود هشتگ
        if hashtag not in data["hashtags"]:
            bot.reply_to(message, f"⚠️ هشتگ {hashtag} یافت نشد.")
            return
        
        # بررسی وجود پیام‌های ذخیره شده برای هشتگ
        hashtag_data = data["hashtags"][hashtag]
        if not hashtag_data["messages"]:
            processing_msg = bot.reply_to(message, f"🔍 در حال جستجوی کانال‌ها برای هشتگ {hashtag}...")
            
            # ایجاد ترد برای جستجوی هشتگ در کانال‌ها
            search_thread = threading.Thread(
                target=search_hashtag_in_channels,
                args=(message, hashtag, processing_msg.message_id)
            )
            search_thread.daemon = True
            search_thread.start()
        else:
            # نمایش پیام‌های ذخیره شده برای هشتگ
            show_hashtag_messages(message, hashtag, data["hashtags"][hashtag]["messages"])
    
    except Exception as e:
        debug_log(f"خطا در جستجوی هشتگ", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

# 📌 جستجوی هشتگ در کانال‌ها
def search_hashtag_in_channels(message, hashtag, processing_msg_id):
    try:
        # بارگیری اطلاعات هشتگ‌ها
        data = load_hashtags()
        
        # بررسی وجود کانال
        if not data["channels"]:
            bot.edit_message_text(
                "⚠️ هنوز هیچ کانالی تعریف نشده است.",
                chat_id=message.chat.id,
                message_id=processing_msg_id
            )
            return
        
        found_messages = []
        total_channels = len(data["channels"])
        processed_channels = 0
        
        # به‌روزرسانی پیام پردازش
        bot.edit_message_text(
            f"🔍 در حال جستجوی {total_channels} کانال برای هشتگ {hashtag}...\n"
            f"پیشرفت: 0/{total_channels} کانال",
            chat_id=message.chat.id,
            message_id=processing_msg_id
        )
        
        # جستجو در هر کانال
        for channel_id in data["channels"]:
            try:
                # به‌روزرسانی پیام پردازش
                processed_channels += 1
                bot.edit_message_text(
                    f"🔍 در حال جستجوی {total_channels} کانال برای هشتگ {hashtag}...\n"
                    f"پیشرفت: {processed_channels}/{total_channels} کانال",
                    chat_id=message.chat.id,
                    message_id=processing_msg_id
                )
                
                # دریافت پیام‌های کانال
                messages = []
                
                try:
                    # تبدیل channel_id به عدد اگر ممکن باشد (برای کانال‌های با آیدی عددی)
                    numeric_channel_id = None
                    if isinstance(channel_id, str):
                        if channel_id.startswith('-100') and channel_id[4:].isdigit():
                            numeric_channel_id = int(channel_id)
                        elif channel_id.lstrip('-').isdigit():
                            numeric_channel_id = int(channel_id)
                
                    # استفاده از channel_links.json برای بازیابی پیام‌ها
                    channel_data = {}
                    if os.path.exists('channel_links.json'):
                        with open('channel_links.json', 'r', encoding='utf-8') as f:
                            channel_data = json.load(f)
                    
                    # بررسی وجود پیام‌های کانال در فایل
                    channel_key = str(numeric_channel_id) if numeric_channel_id else channel_id
                    if channel_key in channel_data:
                        debug_log(f"پیام‌های کانال {channel_id} از فایل بازیابی شد", "INFO")
                        
                        # تبدیل داده‌های کانال به فرمت مناسب
                        for msg_data in channel_data[channel_key]:
                            # اطمینان از وجود فیلد text
                            if 'text' not in msg_data:
                                continue
                                
                            messages.append(types.SimpleNamespace(
                                chat_id=msg_data.get('chat_id'),
                                message_id=msg_data.get('message_id'),
                                text=msg_data.get('text', ''),
                                date=datetime.datetime.strptime(
                                    msg_data.get('date', '2025-01-01 00:00:00'), 
                                    '%Y-%m-%d %H:%M:%S'
                                )
                            ))
                    else:
                        debug_log(f"پیام‌های کانال {channel_id} در فایل یافت نشد", "INFO")
                        
                except Exception as get_history_error:
                    debug_log(f"خطا در دریافت تاریخچه کانال: {str(get_history_error)}", "WARNING")
                
                # بررسی هشتگ در پیام‌ها
                for msg in messages:
                    if hashtag.lower() in msg.text.lower():
                        found_messages.append({
                            "chat_id": channel_id,
                            "message_id": msg.message_id,
                            "text": msg.text[:100] + "..." if len(msg.text) > 100 else msg.text,
                            "date": msg.date.strftime("%Y-%m-%d %H:%M:%S") if hasattr(msg, "date") else "نامشخص"
                        })
                
                # محدود کردن تعداد پیام‌های یافت شده
                if len(found_messages) >= MAX_SEND_MESSAGES:
                    break
                    
            except Exception as channel_error:
                debug_log(f"خطا در جستجوی کانال {channel_id}", "WARNING", {"error": str(channel_error)})
                continue
        
        # ذخیره پیام‌های یافت شده در هشتگ
        data["hashtags"][hashtag]["messages"] = found_messages
        save_hashtags(data)
        
        # نمایش پیام‌های یافت شده
        if found_messages:
            bot.edit_message_text(
                f"✅ جستجو تکمیل شد. {len(found_messages)} پیام یافت شد.",
                chat_id=message.chat.id,
                message_id=processing_msg_id
            )
            time.sleep(1)  # تأخیر کوتاه
            show_hashtag_messages(message, hashtag, found_messages)
        else:
            bot.edit_message_text(
                f"⚠️ هیچ پیامی با هشتگ {hashtag} یافت نشد.",
                chat_id=message.chat.id,
                message_id=processing_msg_id
            )
    
    except Exception as e:
        debug_log(f"خطا در جستجوی هشتگ در کانال‌ها", "ERROR", {"error": str(e)})
        try:
            bot.edit_message_text(
                "⚠️ خطایی در جستجو رخ داد. لطفاً بعداً دوباره تلاش کنید.",
                chat_id=message.chat.id,
                message_id=processing_msg_id
            )
        except:
            pass

# 📌 نمایش پیام‌های هشتگ
def show_hashtag_messages(message, hashtag, messages):
    try:
        if not messages:
            bot.reply_to(message, f"⚠️ هیچ پیامی برای هشتگ {hashtag} یافت نشد.")
            return
        
        # محدود کردن تعداد پیام‌ها
        if len(messages) > MAX_SEND_MESSAGES:
            messages = messages[:MAX_SEND_MESSAGES]
        
        # ساخت پیام نتایج
        results = [f"🔖 <b>نتایج جستجو برای هشتگ {hashtag}:</b>\n"]
        
        for idx, msg in enumerate(messages, 1):
            chat_id = msg.get("chat_id", "نامشخص")
            message_id = msg.get("message_id", "نامشخص")
            text = msg.get("text", "")
            date = msg.get("date", "نامشخص")
            
            results.append(f"{idx}. <b>{date}</b>\n{text}\n")
        
        # ارسال نتایج
        bot.reply_to(message, "\n".join(results), parse_mode="HTML")
    
    except Exception as e:
        debug_log(f"خطا در نمایش پیام‌های هشتگ", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی در نمایش نتایج رخ داد. لطفاً بعداً دوباره تلاش کنید.")

# 📌 بررسی وضعیت سرور
@bot.message_handler(commands=["server_status"])
def server_status(message):
    try:
        # ابتدا بررسی شود که آیا وضعیت در کش موجود است
        cached_status = get_cached_server_status()
        if cached_status:
            bot.send_message(message.chat.id,
                             cached_status,
                             parse_mode="Markdown")
            return

        # ساخت پیام وضعیت سیستم با مدیریت خطا برای هر بخش
        status_sections = []
        status_sections.append("📊 **وضعیت سرور:**\n")
        
        # سیستم عامل و پایتون
        try:
            status_sections.append(f"🔹 **سیستم عامل:** `{platform.platform()}`\n")
            status_sections.append(f"🔹 **پایتون:** `{platform.python_version()}`\n")
        except Exception as sys_error:
            status_sections.append("🔹 **سیستم عامل:** `اطلاعات در دسترس نیست`\n")
            print(f"خطا در دریافت اطلاعات سیستم: {sys_error}")
            
        # وضعیت ربات
        status_sections.append(f"🔹 **وضعیت ربات:** `فعال ✅`\n")
        
        # اگر psutil موجود باشد، از آن استفاده کن
        if 'psutil' in globals():
            # اطلاعات CPU
            try:
                cpu_usage = psutil.cpu_percent(interval=0.5)
                status_sections.append(f"🔹 **CPU:** `{cpu_usage}%`\n")
            except Exception as cpu_error:
                status_sections.append("🔹 **CPU:** `اطلاعات در دسترس نیست`\n")
                print(f"خطا در دریافت اطلاعات CPU: {cpu_error}")
            
            # اطلاعات حافظه
            try:
                ram = psutil.virtual_memory()
                ram_used = ram.used / (1024**3)
                ram_total = ram.total / (1024**3)
                status_sections.append(f"🔹 **RAM:** `{ram_used:.2f}GB / {ram_total:.2f}GB`\n")
            except Exception as ram_error:
                status_sections.append("🔹 **RAM:** `اطلاعات در دسترس نیست`\n")
                print(f"خطا در دریافت اطلاعات RAM: {ram_error}")
        else:
            status_sections.append("🔹 **CPU/RAM:** `اطلاعات در دسترس نیست`\n")
        
        # اطلاعات دیسک با shutil
        if 'shutil' in globals():
            try:
                total, used, free = shutil.disk_usage("/")
                free_gb = free / (1024**3)
                status_sections.append(f"🔹 **فضای باقی‌مانده:** `{free_gb:.2f}GB`\n")
            except Exception as disk_error:
                status_sections.append("🔹 **فضای باقی‌مانده:** `اطلاعات در دسترس نیست`\n")
                print(f"خطا در دریافت اطلاعات دیسک: {disk_error}")
        else:
            status_sections.append("🔹 **فضای دیسک:** `اطلاعات در دسترس نیست`\n")
        
        # اطلاعات زمان
        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_sections.append(f"🔹 **زمان سرور:** `{current_time}`\n")
        except Exception as time_error:
            status_sections.append("🔹 **زمان سرور:** `اطلاعات در دسترس نیست`\n")
            print(f"خطا در دریافت اطلاعات زمان: {time_error}")
        
        # ترکیب بخش‌های پیام
        status_msg = "".join(status_sections)
        
        # ذخیره وضعیت سرور در یک فایل JSON برای کش کردن
        try:
            with open("server_status.json", "w", encoding="utf-8") as file:
                json.dump(
                    {
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": status_msg
                    }, file)
        except Exception as cache_write_error:
            print(f"خطا در ذخیره کش وضعیت سرور: {cache_write_error}")

        # ارسال پیام نهایی به کاربر
        bot.send_message(message.chat.id, status_msg, parse_mode="Markdown")

    except Exception as e:
        error_message = f"⚠ خطا در دریافت وضعیت سرور: {str(e)}"
        bot.send_message(message.chat.id, error_message)
        notify_admin(f"خطا در اجرای دستور server_status: {str(e)}\n{traceback.format_exc()}")


# 📂 مدیریت پاسخ‌های متنی
def load_responses():
    try:
        with open("responses.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_responses():
    with open("responses.json", "w", encoding="utf-8") as file:
        json.dump(responses, file, ensure_ascii=False, indent=4)


responses = load_responses()


# 📌 استخراج لینک مستقیم ویدیو بدون دانلود
# کش لینک‌های ویدیو برای جلوگیری از استخراج مجدد
video_url_cache = {}

def get_direct_video_url(link):
    try:
        # بررسی معتبر بودن لینک
        if not link or not isinstance(link, str):
            debug_log("لینک نامعتبر در get_direct_video_url", "WARNING", {"link": str(link)})
            return None
        
        # بررسی وجود لینک در کش
        current_time = time.time()
        if link in video_url_cache:
            cache_data = video_url_cache[link]
            # بررسی اعتبار کش (6 ساعت)
            if current_time - cache_data['timestamp'] < VIDEO_CACHE_TIMEOUT:
                debug_log(f"لینک مستقیم از کش بازیابی شد: {link}", "INFO")
                return cache_data['direct_url']
            else:
                # حذف کش منقضی شده
                del video_url_cache[link]
            
        # بررسی YoutubeDL
        if 'YoutubeDL' not in globals():
            debug_log("YoutubeDL در دسترس نیست", "ERROR")
            return None
            
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'noplaylist': True,
            'force_generic_extractor': False,
            'format': 'best[ext=mp4]/best',
            'socket_timeout': 10,  # کاهش زمان انتظار برای اتصال
            'retries': 2,         # کاهش تعداد تلاش‌های مجدد
        }
        
        debug_log(f"تلاش برای استخراج لینک مستقیم از {link}", "INFO")
        
        with YoutubeDL(ydl_opts) as ydl:
            try:
                # تنظیم محدودیت زمانی برای استخراج اطلاعات
                info = ydl.extract_info(link, download=False)
                
                if not info:
                    debug_log("اطلاعات استخراج شده خالی است", "WARNING")
                    return None
                    
                direct_url = info.get('url', None)
                
                # ذخیره لینک در کش
                if direct_url:
                    video_url_cache[link] = {
                        'direct_url': direct_url,
                        'timestamp': current_time
                    }
                    # محدود کردن اندازه کش به حداکثر 50 مورد
                    if len(video_url_cache) > 50:
                        # حذف قدیمی‌ترین مورد کش
                        oldest_link = min(video_url_cache.items(), key=lambda x: x[1]['timestamp'])[0]
                        del video_url_cache[oldest_link]
                
                if direct_url:
                    debug_log("لینک مستقیم با موفقیت استخراج شد", "INFO")
                    return direct_url
                else:
                    debug_log("لینک مستقیم در اطلاعات استخراج شده یافت نشد", "WARNING")
                    return None
                    
            except Exception as extract_error:
                debug_log(f"خطا در استخراج اطلاعات از لینک", "ERROR", {
                    "error": str(extract_error),
                    "traceback": traceback.format_exc()
                })
                return None
                
    except Exception as e:
        debug_log(f"خطا در دریافت لینک مستقیم ویدیو", "ERROR", {
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        
        try:
            # تلاش برای اطلاع به ادمین
            notify_admin(f"⚠️ خطا در دریافت لینک مستقیم ویدیو:\n{traceback.format_exc()}")
        except Exception as notify_error:
            debug_log(f"خطا در اطلاع به ادمین", "ERROR", {"error": str(notify_error)})
            
        return None


# 📌 دانلود ویدیو از اینستاگرام
def download_instagram(link):
    try:
        # بررسی معتبر بودن لینک
        if not link or not isinstance(link, str):
            debug_log("لینک نامعتبر در download_instagram", "WARNING", {"link": str(link)})
            return None
            
        # بررسی اینستاگرام در لینک
        if "instagram.com" not in link:
            debug_log("لینک اینستاگرام نیست", "WARNING", {"link": link})
            return None
            
        # بررسی YoutubeDL
        if 'YoutubeDL' not in globals():
            debug_log("YoutubeDL در دسترس نیست", "ERROR")
            return None

        # بررسی امکان استفاده از لینک مستقیم (سریع‌تر)
        direct_url = get_direct_video_url(link)
        if direct_url:
            debug_log(f"از لینک مستقیم برای ویدیوی اینستاگرام استفاده می‌شود", "INFO")
            return direct_url

        # پاکسازی فایل‌های قدیمی
        try:
            clear_folder(INSTAGRAM_FOLDER)
        except Exception as clear_error:
            debug_log("خطا در پاکسازی پوشه اینستاگرام", "WARNING", {"error": str(clear_error)})
            # ادامه می‌دهیم حتی اگر پاکسازی با خطا مواجه شود
            
        debug_log(f"شروع دانلود از اینستاگرام: {link}", "INFO")

        ydl_opts = {
            'outtmpl': f'{INSTAGRAM_FOLDER}/%(id)s.%(ext)s',
            'format': 'mp4/best',
            'quiet': True,  # ساکت‌تر برای سرعت بیشتر
            'noplaylist': True,
            'socket_timeout': 10,  # کاهش زمان انتظار برای اتصال
            'retries': 2,         # کاهش تعداد تلاش‌های مجدد
        }

        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(link, download=True)
                
                if not info:
                    debug_log("اطلاعات دانلود خالی است", "WARNING")
                    return None
                    
                if not info.get('id'):
                    debug_log("شناسه ویدیو در اطلاعات دانلود یافت نشد", "WARNING", {"info": str(info)[:500]})
                    return None
                    
                # چک کردن چندین فرمت فایل
                possible_extensions = ['mp4', 'webm', 'mkv', 'mov', 'avi']
                for ext in possible_extensions:
                    video_path = f"{INSTAGRAM_FOLDER}/{info['id']}.{ext}"
                    if os.path.exists(video_path):
                        debug_log(f"ویدیو با موفقیت دانلود شد: {video_path}", "INFO", {
                            "file_size": os.path.getsize(video_path) / (1024 * 1024),
                            "format": ext
                        })
                        return video_path
                
                # اگر هیچ فایلی یافت نشد
                debug_log("فایل ویدیو پس از دانلود یافت نشد", "WARNING", {"id": info['id']})
                return None
                
            except Exception as extract_error:
                debug_log("خطا در استخراج اطلاعات ویدیو", "ERROR", {
                    "error": str(extract_error),
                    "traceback": traceback.format_exc()
                })
                return None

    except Exception as e:
        debug_log(f"خطا در دانلود ویدیو از اینستاگرام", "ERROR", {
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        
        try:
            # اطلاع به ادمین
            notify_admin(f"⚠️ خطا در دانلود ویدیو از اینستاگرام:\n{traceback.format_exc()}")
        except Exception as notify_error:
            debug_log("خطا در اطلاع به ادمین", "ERROR", {"error": str(notify_error)})
            
        return None


# 📌 دانلود ویدیو از یوتیوب
def download_youtube(link):
    try:
        # بررسی معتبر بودن لینک
        if not link or not isinstance(link, str):
            debug_log("لینک نامعتبر در download_youtube", "WARNING", {"link": str(link)})
            return None
            
        # بررسی YoutubeDL
        if 'YoutubeDL' not in globals():
            debug_log("YoutubeDL در دسترس نیست", "ERROR")
            return None

        # پاکسازی فایل‌های قدیمی
        try:
            clear_folder(VIDEO_FOLDER)
        except Exception as clear_error:
            debug_log("خطا در پاکسازی پوشه ویدیو", "WARNING", {"error": str(clear_error)})
            # ادامه می‌دهیم حتی اگر پاکسازی با خطا مواجه شود
            
        debug_log(f"شروع دانلود از یوتیوب: {link}", "INFO")

        ydl_opts = {
            'outtmpl': f'{VIDEO_FOLDER}/%(id)s.%(ext)s',
            'format': 'mp4/best',
            'quiet': False,
            'noplaylist': True,
            'ignoreerrors': True,  # نادیده گرفتن برخی خطاهای جزئی
        }

        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(link, download=True)
                
                if not info:
                    debug_log("اطلاعات دانلود خالی است", "WARNING")
                    return None
                    
                if not info.get('id'):
                    debug_log("شناسه ویدیو در اطلاعات دانلود یافت نشد", "WARNING", {"info": str(info)[:500]})
                    return None
                    
                # چک کردن چندین فرمت فایل
                possible_extensions = ['mp4', 'webm', 'mkv', 'mov', 'avi']
                for ext in possible_extensions:
                    video_path = f"{VIDEO_FOLDER}/{info['id']}.{ext}"
                    if os.path.exists(video_path):
                        debug_log(f"ویدیو با موفقیت دانلود شد: {video_path}", "INFO", {
                            "file_size": os.path.getsize(video_path) / (1024 * 1024),
                            "format": ext
                        })
                        return video_path
                
                # اگر هیچ فایلی با پسوندهای معمول یافت نشد، به دنبال فایل با پسوند موجود در اطلاعات می‌گردیم
                if info.get('ext'):
                    video_path = f"{VIDEO_FOLDER}/{info['id']}.{info['ext']}"
                    if os.path.exists(video_path):
                        debug_log(f"ویدیو با فرمت {info['ext']} دانلود شد: {video_path}", "INFO")
                        return video_path
                
                # جستجوی فایل در پوشه VIDEO_FOLDER با ID ویدیو
                try:
                    video_files = [f for f in os.listdir(VIDEO_FOLDER) if info['id'] in f]
                    if video_files:
                        video_path = os.path.join(VIDEO_FOLDER, video_files[0])
                        debug_log(f"ویدیو با نام {video_files[0]} یافت شد", "INFO")
                        return video_path
                except Exception as search_error:
                    debug_log("خطا در جستجوی فایل ویدیو", "WARNING", {"error": str(search_error)})
                
                # اگر هیچ فایلی یافت نشد
                debug_log("فایل ویدیو پس از دانلود یافت نشد", "WARNING", {"id": info['id']})
                return None
                
            except Exception as extract_error:
                debug_log("خطا در استخراج اطلاعات ویدیو", "ERROR", {
                    "error": str(extract_error),
                    "traceback": traceback.format_exc()
                })
                return None

    except Exception as e:
        debug_log(f"خطا در دانلود ویدیو از یوتیوب", "ERROR", {
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        
        try:
            # اطلاع به ادمین
            notify_admin(f"⚠️ خطا در دانلود ویدیو از یوتیوب:\n{traceback.format_exc()}")
        except Exception as notify_error:
            debug_log("خطا در اطلاع به ادمین", "ERROR", {"error": str(notify_error)})
            
        return None


# 📢 ارسال پیام به ادمین در صورت وقوع خطا
def notify_admin(message):
    try:
        if bot is None:
            print("⚠️ ربات تلگرام در دسترس نیست، پیام به ادمین ارسال نشد")
            return
            
        # محدود کردن طول پیام به 4000 کاراکتر برای رعایت محدودیت‌های تلگرام
        message_text = str(message)[:4000]
        
        # بررسی معتبر بودن ADMIN_CHAT_ID
        if not ADMIN_CHAT_ID:
            print("⚠️ آیدی چت ادمین تعریف نشده است")
            return
            
        bot.send_message(ADMIN_CHAT_ID, message_text)
    except Exception as e:
        print(f"⚠️ خطا در ارسال پیام به ادمین: {e}")
        debug_log(f"خطا در ارسال پیام به ادمین", "ERROR", {
            "error": str(e),
            "admin_id": ADMIN_CHAT_ID,
            "message_length": len(str(message))
        })


# 🎬 پردازش لینک‌های ویدیو برای دانلود
def process_video_link(message, link, processing_msg):
    """
    دانلود و ارسال ویدیو از لینک داده شده
    این تابع در یک ترد جداگانه اجرا می‌شود تا ربات حین دانلود پاسخگو باشد
    """
    global last_cleanup_time
    current_time = time.time()
    
    try:
        # پاکسازی خودکار - هر یک دقیقه یکبار پاکسازی کامل فایل‌ها
        if current_time - last_cleanup_time > 60:  # هر 60 ثانیه
            debug_log("پاکسازی اتوماتیک فولدرهای ویدیو", "INFO")
            clear_folder(VIDEO_FOLDER, 0)  # پاکسازی کامل
            clear_folder(INSTAGRAM_FOLDER, 0)  # پاکسازی کامل
            last_cleanup_time = current_time
            
        # دریافت کیفیت ویدیو انتخاب شده توسط کاربر
        user_id = str(message.from_user.id)
        quality = DEFAULT_VIDEO_QUALITY  # کیفیت پیش‌فرض
        
        if hasattr(bot, "user_video_quality") and user_id in bot.user_video_quality:
            quality = bot.user_video_quality[user_id]
            
        # اطلاع‌رسانی به کاربر
        bot.edit_message_text(
            f"⏳ در حال دانلود ویدیو با کیفیت <b>{quality}</b>...",
            message.chat.id,
            processing_msg.message_id,
            parse_mode="HTML"
        )
        
        # تلاش برای استفاده از لینک مستقیم برای کاهش مصرف منابع
        direct_url = get_direct_video_url(link)
        if direct_url and not "instagram.com" in link:  # برای یوتیوب و سایر سایت‌ها
            try:
                bot.edit_message_text(
                    f"✅ لینک مستقیم پیدا شد! ارسال با کیفیت <b>{quality}</b>...",
                    message.chat.id,
                    processing_msg.message_id,
                    parse_mode="HTML"
                )
                
                # ارسال ویدیو با لینک مستقیم
                bot.send_message(
                    message.chat.id,
                    f"🎬 <b>ویدیوی درخواستی شما</b>\n\n📊 کیفیت: <b>{quality}</b>\n\n🔗 <a href='{direct_url}'>لینک مستقیم دانلود</a>",
                    parse_mode="HTML",
                    disable_web_page_preview=False
                )
                
                # حذف پیام "در حال پردازش"
                bot.delete_message(message.chat.id, processing_msg.message_id)
                return
            except Exception as direct_error:
                debug_log(f"خطا در ارسال لینک مستقیم، ادامه روند دانلود", "WARNING", {"error": str(direct_error)})
                # در صورت خطا، به دانلود عادی ادامه می‌دهیم
        
        # تنظیم گزینه‌های دانلود با کیفیت انتخابی
        format_option = VIDEO_QUALITIES.get(quality, VIDEO_QUALITIES["240p"])["format"]
        
        # شناسایی نوع لینک
        if "instagram.com" in link:
            # اگر لینک اینستاگرام است
            ydl_opts = {
                'format': format_option,
                'outtmpl': f'{INSTAGRAM_FOLDER}/%(id)s.%(ext)s',
                'quiet': True,
                'noplaylist': True,
                'socket_timeout': 10,  # کاهش زمان انتظار برای اتصال
                'retries': 2,          # کاهش تعداد تلاش‌های مجدد
            }
            folder = INSTAGRAM_FOLDER
        else:
            # یوتیوب یا دیگر سایت‌ها
            ydl_opts = {
                'format': format_option,
                'outtmpl': f'{VIDEO_FOLDER}/%(id)s.%(ext)s',
                'quiet': True,
                'noplaylist': True,
                'socket_timeout': 10,  # کاهش زمان انتظار برای اتصال
                'retries': 2,          # کاهش تعداد تلاش‌های مجدد
            }
            folder = VIDEO_FOLDER
        
        # پاکسازی فایل‌های قدیمی
        clear_folder(folder)
        
        # دانلود ویدیو
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            
            # آماده‌سازی فایل ویدیو برای ارسال
            if info and info.get('id'):
                video_path = f"{folder}/{info['id']}.mp4"
                if not os.path.exists(video_path) and info.get('ext'):
                    video_path = f"{folder}/{info['id']}.{info['ext']}"
                
                # ارسال ویدیو
                if os.path.exists(video_path):
                    # اطلاع‌رسانی به کاربر
                    bot.edit_message_text(
                        f"✅ دانلود کامل شد! در حال ارسال ویدیو با کیفیت <b>{quality}</b>...",
                        message.chat.id,
                        processing_msg.message_id,
                        parse_mode="HTML"
                    )
                    
                    # بررسی سایز فایل
                    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
                    
                    # تلاش برای ارسال ویدیو به کاربر
                    try:
                        if file_size_mb < 50:  # فایل‌های کمتر از 50MB را مستقیم ارسال می‌کنیم
                            with open(video_path, 'rb') as video_file:
                                bot.send_video(
                                    message.chat.id,
                                    video_file,
                                    caption=f"🎬 <b>{info.get('title', 'ویدیوی دانلود شده')}</b>\n\n📊 کیفیت: <b>{quality}</b>\n📏 حجم: <b>{file_size_mb:.1f} MB</b>",
                                    parse_mode="HTML",
                                    timeout=60
                                )
                            # حذف پیام "در حال پردازش"
                            bot.delete_message(message.chat.id, processing_msg.message_id)
                            
                            # حذف فوری فایل پس از ارسال برای کاهش مصرف فضا
                            try:
                                os.remove(video_path)
                                debug_log(f"فایل {video_path} پس از ارسال حذف شد", "INFO")
                            except Exception as rm_error:
                                debug_log(f"خطا در حذف فایل پس از ارسال", "WARNING", {"error": str(rm_error)})
                                
                            return
                        else:
                            # برای فایل‌های بزرگتر، قطعه‌بندی یا روش دیگری نیاز است
                            bot.edit_message_text(
                                f"⚠️ سایز فایل ({file_size_mb:.1f} MB) بیشتر از محدودیت تلگرام است. لطفاً با کیفیت پایین‌تر امتحان کنید.",
                                message.chat.id,
                                processing_msg.message_id,
                                parse_mode="HTML"
                            )
                            # حذف فایل بزرگ
                            try:
                                os.remove(video_path)
                            except:
                                pass
                            return
                    except Exception as e:
                        bot.edit_message_text(
                            f"⚠️ خطا در ارسال ویدیو: {str(e)}\n\nلطفاً با کیفیت پایین‌تر امتحان کنید.",
                            message.chat.id,
                            processing_msg.message_id
                        )
                        notify_admin(f"خطا در ارسال ویدیو به کاربر {message.from_user.id}: {str(e)}")
                        return
                    
            # جستجوی فایل در پوشه با ID ویدیو
            try:
                if info and info.get('id'):
                    video_files = [f for f in os.listdir(folder) if info['id'] in f]
                    if video_files:
                        video_path = os.path.join(folder, video_files[0])
                        debug_log(f"ویدیو با نام {video_files[0]} یافت شد", "INFO")
                        
                        # اطلاع‌رسانی به کاربر
                        bot.edit_message_text(
                            f"✅ دانلود کامل شد! در حال ارسال ویدیو با کیفیت <b>{quality}</b>...",
                            message.chat.id,
                            processing_msg.message_id,
                            parse_mode="HTML"
                        )
                        
                        # بررسی سایز فایل
                        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
                        
                        # تلاش برای ارسال ویدیو به کاربر
                        if file_size_mb < 50:
                            with open(video_path, 'rb') as video_file:
                                bot.send_video(
                                    message.chat.id,
                                    video_file,
                                    caption=f"🎬 <b>{info.get('title', 'ویدیوی دانلود شده')}</b>\n\n📊 کیفیت: <b>{quality}</b>\n📏 حجم: <b>{file_size_mb:.1f} MB</b>",
                                    parse_mode="HTML",
                                    timeout=60
                                )
                            bot.delete_message(message.chat.id, processing_msg.message_id)
                            return
                        else:
                            bot.edit_message_text(
                                f"⚠️ سایز فایل ({file_size_mb:.1f} MB) بیشتر از محدودیت تلگرام است. لطفاً با کیفیت پایین‌تر امتحان کنید.",
                                message.chat.id,
                                processing_msg.message_id,
                                parse_mode="HTML"
                            )
                            return
            except Exception as search_error:
                debug_log("خطا در جستجوی فایل ویدیو", "WARNING", {"error": str(search_error)})
                
            # در صورت خطا در دانلود
            bot.edit_message_text(
                "⚠️ خطا در دانلود ویدیو. لطفاً با کیفیت پایین‌تر امتحان کنید یا لینک دیگری را ارسال کنید.",
                message.chat.id,
                processing_msg.message_id
            )
    except Exception as e:
        # در صورت هرگونه خطا
        error_msg = f"⚠️ خطا در پردازش ویدیو: {str(e)}"
        try:
            bot.edit_message_text(
                error_msg,
                message.chat.id,
                processing_msg.message_id
            )
        except:
            bot.send_message(message.chat.id, error_msg)
        
        # اطلاع به ادمین
        notify_admin(f"خطا در پردازش لینک ویدیو:\n{traceback.format_exc()}")


# 🎮 مدیریت کلیدهای میانبر (Callback Query) و انتخاب کیفیت ویدیو
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    try:
        # پاسخ سریع به کالبک برای جلوگیری از خطای ساعت شنی
        bot.answer_callback_query(call.id)
        
        # 🔖 راهنمای هشتگ
        if call.data == "hashtag_help":
            # ایجاد کیبورد اینلاین با دکمه‌های مختلف
            markup = telebot.types.InlineKeyboardMarkup()
            back_btn = telebot.types.InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_help")
            markup.add(back_btn)
            
            # ارسال راهنمای هشتگ
            bot.edit_message_text(
                "🔖 <b>راهنمای استفاده از هشتگ‌ها</b>\n\n"
                "با استفاده از قابلیت هشتگ، می‌توانید پیام‌های کانال‌های تلگرام را جستجو کنید.\n\n"
                "<b>دستورات مدیریت هشتگ:</b>\n"
                "• <code>/add_hashtag نام_هشتگ توضیحات</code> - افزودن یک هشتگ جدید\n"
                "• <code>/remove_hashtag نام_هشتگ</code> - حذف یک هشتگ\n"
                "• <code>/hashtags</code> - نمایش لیست هشتگ‌های موجود\n\n"
                "<b>دستورات مدیریت کانال:</b>\n"
                "• <code>/add_channel آیدی_کانال</code> - افزودن کانال برای جستجو\n"
                "• <code>/remove_channel آیدی_کانال</code> - حذف کانال از لیست جستجو\n"
                "• <code>/channels</code> - نمایش لیست کانال‌های موجود\n\n"
                "<b>جستجوی هشتگ:</b>\n"
                "• <code>/search نام_هشتگ</code> - جستجوی پیام‌های کانال با هشتگ مورد نظر\n\n"
                "<b>توجه:</b> برای استفاده از این قابلیت، ابتدا باید حداقل یک هشتگ و یک کانال را اضافه کنید.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=markup
            )
            return
            
        # 🔙 بازگشت به راهنما
        if call.data == "back_to_help":
            # ایجاد کیبورد اینلاین با دکمه‌های مختلف
            markup = telebot.types.InlineKeyboardMarkup(row_width=2)
            quality_btn = telebot.types.InlineKeyboardButton("📊 انتخاب کیفیت ویدیو", callback_data="select_quality")
            hashtag_btn = telebot.types.InlineKeyboardButton("🔖 راهنمای هشتگ", callback_data="hashtag_help")
            markup.add(quality_btn, hashtag_btn)
            
            # ارسال پیام راهنما
            bot.edit_message_text(
                "🔰 <b>راهنمای استفاده از ربات</b>\n\n"
                "📌 <b>دستورات اصلی:</b>\n"
                "/start - شروع کار با ربات\n"
                "/help - نمایش این راهنما\n"
                "/server_status - مشاهده وضعیت سرور\n\n"
                "📥 <b>دانلود ویدیو:</b>\n"
                "• کافیست لینک ویدیوی مورد نظر را از یوتیوب یا اینستاگرام ارسال کنید\n"
                "• می‌توانید کیفیت مورد نظر را از منوی زیر انتخاب کنید\n\n"
                "🔖 <b>جستجوی هشتگ:</b>\n"
                "• برای مدیریت هشتگ‌ها از دستورات /add_hashtag، /remove_hashtag و /hashtags استفاده کنید\n"
                "• برای مدیریت کانال‌ها از دستورات /add_channel، /remove_channel و /channels استفاده کنید\n"
                "• برای جستجوی هشتگ در کانال‌ها از دستور /search استفاده کنید\n\n"
                "⚠️ <b>نکات مهم:</b>\n"
                "• برای صرفه‌جویی در حجم اینترنت و سرعت بالاتر، از کیفیت‌های پایین‌تر استفاده کنید\n"
                "• کیفیت پیش‌فرض 240p است\n"
                "• ویدیوهای بالای 50MB قابل ارسال نیستند و باید با کیفیت پایین‌تر دانلود شوند",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=markup
            )
            return
        
        # 📊 تغییر کیفیت ویدیو
        if call.data.startswith("quality_"):
            quality = call.data.replace("quality_", "")
            
            # تایید تغییر کیفیت
            bot.edit_message_text(
                f"✅ کیفیت ویدیو به <b>{quality}</b> تغییر یافت!\n\n"
                "اکنون می‌توانید لینک ویدیوی مورد نظر را ارسال کنید.",
                call.message.chat.id, 
                call.message.message_id,
                parse_mode="HTML"
            )
            
            # ذخیره کیفیت انتخاب شده برای کاربر
            user_id = str(call.from_user.id)
            if not hasattr(bot, "user_video_quality"):
                bot.user_video_quality = {}
            bot.user_video_quality[user_id] = quality
            
            return
            
        # 🌐 نمایش وضعیت سرور
        elif call.data == "server_status":
            try:
                # ارسال پیام "در حال بررسی..."
                bot.edit_message_text(
                    "⏳ در حال بررسی وضعیت سرور...",
                    call.message.chat.id,
                    call.message.message_id
                )
                
                # بررسی وضعیت سرور از کش
                try:
                    cached_status = get_cached_server_status()
                    if cached_status:
                        bot.edit_message_text(
                            cached_status,
                            call.message.chat.id,
                            call.message.message_id,
                            parse_mode="Markdown"
                        )
                        return
                except Exception as cache_error:
                    print(f"خطا در بررسی کش وضعیت سرور: {cache_error}")
                
                # ساخت پیام وضعیت سیستم با مدیریت خطا برای هر بخش
                status_sections = []
                status_sections.append("📊 **وضعیت سرور:**\n")
                
                # سیستم عامل و پایتون
                try:
                    status_sections.append(f"🔹 **سیستم عامل:** `{platform.platform()}`\n")
                    status_sections.append(f"🔹 **پایتون:** `{platform.python_version()}`\n")
                except Exception as sys_error:
                    status_sections.append("🔹 **سیستم عامل:** `اطلاعات در دسترس نیست`\n")
                    print(f"خطا در دریافت اطلاعات سیستم: {sys_error}")
                    
                # وضعیت ربات
                status_sections.append(f"🔹 **وضعیت ربات:** `فعال ✅`\n")
                
                # اگر psutil موجود باشد، از آن استفاده کن
                if 'psutil' in globals():
                    # اطلاعات CPU
                    try:
                        cpu_usage = psutil.cpu_percent(interval=0.5)
                        status_sections.append(f"🔹 **CPU:** `{cpu_usage}%`\n")
                    except Exception as cpu_error:
                        status_sections.append("🔹 **CPU:** `اطلاعات در دسترس نیست`\n")
                        print(f"خطا در دریافت اطلاعات CPU: {cpu_error}")
                    
                    # اطلاعات حافظه
                    try:
                        ram = psutil.virtual_memory()
                        ram_used = ram.used / (1024**3)
                        ram_total = ram.total / (1024**3)
                        status_sections.append(f"🔹 **RAM:** `{ram_used:.2f}GB / {ram_total:.2f}GB`\n")
                    except Exception as ram_error:
                        status_sections.append("🔹 **RAM:** `اطلاعات در دسترس نیست`\n")
                        print(f"خطا در دریافت اطلاعات RAM: {ram_error}")
                else:
                    status_sections.append("🔹 **CPU/RAM:** `اطلاعات در دسترس نیست`\n")
                
                # اطلاعات دیسک با shutil
                if 'shutil' in globals():
                    try:
                        total, used, free = shutil.disk_usage("/")
                        free_gb = free / (1024**3)
                        status_sections.append(f"🔹 **فضای باقی‌مانده:** `{free_gb:.2f}GB`\n")
                    except Exception as disk_error:
                        status_sections.append("🔹 **فضای باقی‌مانده:** `اطلاعات در دسترس نیست`\n")
                        print(f"خطا در دریافت اطلاعات دیسک: {disk_error}")
                else:
                    status_sections.append("🔹 **فضای دیسک:** `اطلاعات در دسترس نیست`\n")
                
                # اطلاعات زمان
                try:
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    status_sections.append(f"🔹 **زمان سرور:** `{current_time}`\n")
                    
                    # مدت زمان روشن بودن سرور با psutil
                    if 'psutil' in globals():
                        try:
                            uptime_seconds = time.time() - psutil.boot_time()
                            uptime_hours = uptime_seconds // 3600
                            status_sections.append(f"🔹 **مدت روشن بودن:** `{int(uptime_hours)} ساعت`\n")
                        except Exception as uptime_error:
                            status_sections.append("🔹 **مدت روشن بودن:** `اطلاعات در دسترس نیست`\n")
                            print(f"خطا در دریافت اطلاعات uptime: {uptime_error}")
                except Exception as time_error:
                    status_sections.append("🔹 **زمان سرور:** `اطلاعات در دسترس نیست`\n")
                    print(f"خطا در دریافت اطلاعات زمان: {time_error}")
                
                # ترکیب بخش‌های پیام
                status_msg = "".join(status_sections)
                
                # ذخیره وضعیت سرور در یک فایل JSON برای کش کردن
                try:
                    with open("server_status.json", "w", encoding="utf-8") as file:
                        json.dump(
                            {
                                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "status": status_msg
                            }, file)
                except Exception as cache_write_error:
                    print(f"خطا در ذخیره کش وضعیت سرور: {cache_write_error}")
                
                # ایجاد دکمه بازگشت به منوی اصلی
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(telebot.types.InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_main"))
                
                bot.edit_message_text(
                    status_msg,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown",
                    reply_markup=markup
                )
            except Exception as e:
                error_message = f"⚠ خطا در دریافت وضعیت سرور: {str(e)}"
                try:
                    # تلاش برای ویرایش پیام فعلی
                    bot.edit_message_text(
                        error_message,
                        call.message.chat.id,
                        call.message.message_id
                    )
                except:
                    # اگر ویرایش پیام با خطا مواجه شد، پیام جدید ارسال کن
                    bot.send_message(call.message.chat.id, error_message)
            return
            
        # 🔙 بازگشت به منوی اصلی
        elif call.data == "back_to_main":
            # ایجاد کیبورد اینلاین با دکمه‌های مختلف
            markup = telebot.types.InlineKeyboardMarkup(row_width=2)
            help_btn = telebot.types.InlineKeyboardButton("📚 راهنما", callback_data="download_help")
            quality_btn = telebot.types.InlineKeyboardButton("📊 کیفیت ویدیو", callback_data="select_quality")
            status_btn = telebot.types.InlineKeyboardButton("📈 وضعیت سرور", callback_data="server_status")
            
            markup.add(help_btn, quality_btn)
            markup.add(status_btn)
            
            bot.edit_message_text(
                f"👋 سلام {call.from_user.first_name}!\n\n"
                "🎬 به ربات دانلود ویدیو خوش آمدید.\n\n"
                "🔸 <b>قابلیت‌های ربات:</b>\n"
                "• دانلود ویدیو از یوتیوب و اینستاگرام\n"
                "• امکان انتخاب کیفیت ویدیو\n"
                "• پاسخ‌گویی به سوالات متداول\n\n"
                "🔹 <b>روش استفاده:</b>\n"
                "کافیست لینک ویدیوی مورد نظر خود را از یوتیوب یا اینستاگرام ارسال کنید.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=markup
            )
            return
            
        # 📊 انتخاب کیفیت ویدیو
        elif call.data == "select_quality":
            # ایجاد دکمه‌های کیفیت
            markup = telebot.types.InlineKeyboardMarkup(row_width=3)
            quality_buttons = []
            for quality in ["144p", "240p", "360p", "480p", "720p", "1080p"]:
                quality_buttons.append(
                    telebot.types.InlineKeyboardButton(f"📺 {quality}", callback_data=f"quality_{quality}")
                )
            
            # افزودن دکمه‌ها در گروه‌های 3تایی
            for i in range(0, len(quality_buttons), 3):
                group = quality_buttons[i:i+3]
                markup.add(*group)
                
            # دکمه بازگشت
            markup.add(telebot.types.InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main"))
            
            bot.edit_message_text(
                "📊 <b>انتخاب کیفیت ویدیو</b>\n\n"
                "لطفاً کیفیت مورد نظر برای دانلود ویدیوها را انتخاب کنید:\n\n"
                "⚠️ <b>نکات مهم:</b>\n"
                "• کیفیت بالاتر = حجم بیشتر و زمان دانلود طولانی‌تر\n"
                "• کیفیت پایین‌تر = حجم کمتر و دانلود سریع‌تر\n"
                "• ویدیوهای با حجم بیش از 50MB قابل ارسال در تلگرام نیستند\n"
                "• کیفیت فعلی: <b>" + (bot.user_video_quality.get(str(call.from_user.id), DEFAULT_VIDEO_QUALITY) if hasattr(bot, "user_video_quality") else DEFAULT_VIDEO_QUALITY) + "</b>",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=markup
            )
            return
            
        # 📝 نمایش راهنمای دانلود
        elif call.data == "download_help":
            help_text = (
                "🎬 <b>راهنمای دانلود ویدیو</b>\n\n"
                "<b>🔹 انواع لینک‌های پشتیبانی شده:</b>\n"
                "• یوتیوب: لینک‌های معمولی، کوتاه و پلی‌لیست\n"
                "• اینستاگرام: پست‌ها، IGTV، ریلز\n\n"
                "<b>🔸 نکات مهم:</b>\n"
                "• <b>کیفیت:</b> برای صرفه‌جویی در مصرف داده و سرعت بیشتر، از کیفیت‌های پایین‌تر استفاده کنید\n"
                "• <b>زمان دانلود:</b> بسته به حجم ویدیو و کیفیت انتخابی، ممکن است تا 2 دقیقه زمان ببرد\n"
                "• <b>خطاها:</b> در صورت خطا، مجدداً با کیفیت پایین‌تر امتحان کنید\n\n"
                "<b>🔄 روش استفاده:</b>\n"
                "1. کیفیت موردنظر را انتخاب کنید\n"
                "2. لینک را کپی و برای ربات ارسال کنید\n"
                "3. منتظر دانلود و ارسال ویدیو باشید"
            )
            
            # ایجاد دکمه‌های کیفیت
            markup = telebot.types.InlineKeyboardMarkup(row_width=3)
            quality_buttons = []
            for quality in ["144p", "240p", "360p", "480p", "720p", "1080p"]:
                quality_buttons.append(
                    telebot.types.InlineKeyboardButton(f"📺 {quality}", callback_data=f"quality_{quality}")
                )
            
            # افزودن دکمه‌ها در گروه‌های 3تایی
            for i in range(0, len(quality_buttons), 3):
                group = quality_buttons[i:i+3]
                markup.add(*group)
            
            bot.edit_message_text(
                help_text,
                call.message.chat.id, 
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=markup
            )
            return
            
        # 💻 نمایش کد ربات برای ادمین
        elif call.data == "view_bot_code":
            # تنها برای ادمین
            if call.from_user.id != ADMIN_CHAT_ID:
                bot.send_message(call.message.chat.id, "⛔ شما دسترسی به کد ربات را ندارید!")
                return
                
            # فهرست فایل‌های قابل نمایش
            files = [
                ("bot.py", "کد اصلی ربات"),
                ("main.py", "فایل راه‌انداز"),
                ("utils.py", "توابع کمکی"),
                ("requirements.txt", "وابستگی‌ها")
            ]
            
            markup = telebot.types.InlineKeyboardMarkup(row_width=1)
            for file_name, description in files:
                if os.path.exists(file_name):
                    markup.add(telebot.types.InlineKeyboardButton(
                        f"📄 {file_name} - {description}", 
                        callback_data=f"show_file_{file_name}"
                    ))
            
            markup.add(telebot.types.InlineKeyboardButton("🔙 بازگشت", callback_data="bot_status"))
            
            bot.send_message(
                call.message.chat.id,
                "📂 <b>دسترسی به کد ربات</b>\n\n"
                "لطفاً فایل مورد نظر را برای نمایش انتخاب کنید:",
                parse_mode="HTML",
                reply_markup=markup
            )
            return
            
        # 📄 نمایش محتوای فایل برای ادمین
        elif call.data.startswith("show_file_"):
            # تنها برای ادمین
            if call.from_user.id != ADMIN_CHAT_ID:
                bot.send_message(call.message.chat.id, "⛔ شما دسترسی به کد ربات را ندارید!")
                return
                
            file_name = call.data.replace("show_file_", "")
            
            if os.path.exists(file_name):
                try:
                    with open(file_name, "r", encoding="utf-8") as f:
                        code = f.read()
                    
                    # ارسال کد با فرمت مناسب
                    if len(code) > 4000:
                        chunks = [code[i:i+4000] for i in range(0, len(code), 4000)]
                        for i, chunk in enumerate(chunks):
                            bot.send_message(
                                call.message.chat.id,
                                f"📄 <b>{file_name}</b> (بخش {i+1}/{len(chunks)})\n\n"
                                f"<pre><code>{chunk}</code></pre>",
                                parse_mode="HTML"
                            )
                    else:
                        bot.send_message(
                            call.message.chat.id,
                            f"📄 <b>{file_name}</b>\n\n"
                            f"<pre><code>{code}</code></pre>",
                            parse_mode="HTML"
                        )
                    
                    # دکمه بازگشت
                    markup = telebot.types.InlineKeyboardMarkup()
                    markup.add(telebot.types.InlineKeyboardButton("🔙 بازگشت", callback_data="view_bot_code"))
                    
                    bot.send_message(
                        call.message.chat.id,
                        "برای بازگشت به لیست فایل‌ها، دکمه زیر را بزنید:",
                        reply_markup=markup
                    )
                except Exception as e:
                    bot.send_message(
                        call.message.chat.id,
                        f"⚠️ خطا در نمایش فایل {file_name}: {str(e)}"
                    )
            else:
                bot.send_message(
                    call.message.chat.id,
                    f"⚠️ فایل {file_name} یافت نشد!"
                )
            return
    
        # 🔍 نمایش اطلاعات دقیق سیستم
        elif call.data == "detailed_system_info":
            # تنها برای ادمین
            if call.from_user.id != ADMIN_CHAT_ID:
                bot.send_message(call.message.chat.id, "⛔ شما دسترسی به این اطلاعات را ندارید!")
                return
                
            try:
                # جمع‌آوری اطلاعات دقیق سیستم
                import psutil
                import platform
                import datetime
                
                # اطلاعات سیستم
                system_info = {
                    "System": platform.system(),
                    "Platform": platform.platform(),
                    "Architecture": platform.architecture()[0],
                    "Machine": platform.machine(),
                    "Processor": platform.processor(),
                    "Python Version": platform.python_version(),
                }
                
                # اطلاعات CPU
                cpu_info = {
                    "Physical cores": psutil.cpu_count(logical=False),
                    "Logical cores": psutil.cpu_count(logical=True),
                    "Current frequency": f"{psutil.cpu_freq().current:.2f} MHz" if psutil.cpu_freq() else "N/A",
                    "Min frequency": f"{psutil.cpu_freq().min:.2f} MHz" if psutil.cpu_freq() and hasattr(psutil.cpu_freq(), 'min') else "N/A",
                    "Max frequency": f"{psutil.cpu_freq().max:.2f} MHz" if psutil.cpu_freq() and hasattr(psutil.cpu_freq(), 'max') else "N/A",
                    "CPU Usage Per Core": [f"{x}%" for x in psutil.cpu_percent(interval=1, percpu=True)],
                    "Total CPU Usage": f"{psutil.cpu_percent(interval=1)}%",
                }
                
                # اطلاعات حافظه
                memory = psutil.virtual_memory()
                memory_info = {
                    "Total": f"{memory.total / (1024**3):.2f} GB",
                    "Available": f"{memory.available / (1024**3):.2f} GB",
                    "Used": f"{memory.used / (1024**3):.2f} GB ({memory.percent}%)",
                    "Buffers": f"{memory.buffers / (1024**3):.2f} GB" if hasattr(memory, 'buffers') else "N/A",
                    "Cached": f"{memory.cached / (1024**3):.2f} GB" if hasattr(memory, 'cached') else "N/A", 
                }
                
                # اطلاعات دیسک
                disk_info = {}
                for partition in psutil.disk_partitions():
                    try:
                        partition_usage = psutil.disk_usage(partition.mountpoint)
                        disk_info[partition.mountpoint] = {
                            "Total": f"{partition_usage.total / (1024**3):.2f} GB",
                            "Used": f"{partition_usage.used / (1024**3):.2f} GB ({partition_usage.percent}%)",
                            "Free": f"{partition_usage.free / (1024**3):.2f} GB",
                            "File system": partition.fstype,
                        }
                    except:
                        pass
                
                # اطلاعات شبکه
                net_io = psutil.net_io_counters()
                network_info = {
                    "Bytes Sent": f"{net_io.bytes_sent / (1024**2):.2f} MB",
                    "Bytes Received": f"{net_io.bytes_recv / (1024**2):.2f} MB",
                    "Packets Sent": f"{net_io.packets_sent}",
                    "Packets Received": f"{net_io.packets_recv}",
                    "Errors (in/out)": f"{net_io.errin}/{net_io.errout}",
                    "Dropped (in/out)": f"{net_io.dropin}/{net_io.dropout}",
                }
                
                # پردازش‌های با بیشترین مصرف CPU
                processes_by_cpu = []
                for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'create_time']):
                    try:
                        if proc.info['cpu_percent'] > 0.5:  # فقط پردازش‌های با مصرف بالاتر از 0.5%
                            proc_info = proc.info
                            proc_info['create_time'] = datetime.datetime.fromtimestamp(proc_info['create_time']).strftime('%Y-%m-%d %H:%M:%S')
                            processes_by_cpu.append(proc_info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                # مرتب‌سازی پردازش‌ها بر اساس مصرف CPU (بیشترین اول)
                processes_by_cpu.sort(key=lambda x: x['cpu_percent'], reverse=True)
                
                # پردازش‌های با بیشترین مصرف حافظه
                processes_by_memory = []
                for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'create_time']):
                    try:
                        if proc.info['memory_percent'] > 0.5:  # فقط پردازش‌های با مصرف بالاتر از 0.5%
                            proc_info = proc.info
                            proc_info['create_time'] = datetime.datetime.fromtimestamp(proc_info['create_time']).strftime('%Y-%m-%d %H:%M:%S')
                            processes_by_memory.append(proc_info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                # مرتب‌سازی پردازش‌ها بر اساس مصرف حافظه (بیشترین اول)
                processes_by_memory.sort(key=lambda x: x['memory_percent'], reverse=True)
                
                # ایجاد متن گزارش
                report = "📊 <b>گزارش دقیق سیستم</b>\n\n"
                
                # اطلاعات سیستم
                report += "<b>💻 اطلاعات سیستم:</b>\n"
                for key, value in system_info.items():
                    report += f"• {key}: {value}\n"
                
                # اطلاعات CPU
                report += "\n<b>🔧 اطلاعات CPU:</b>\n"
                for key, value in cpu_info.items():
                    if key == "CPU Usage Per Core":
                        report += f"• مصرف هر هسته: {', '.join(value[:4])}... \n"
                    else:
                        report += f"• {key}: {value}\n"
                
                # اطلاعات حافظه
                report += "\n<b>🧠 اطلاعات حافظه:</b>\n"
                for key, value in memory_info.items():
                    report += f"• {key}: {value}\n"
                
                # اطلاعات دیسک (فقط ریشه)
                report += "\n<b>💽 اطلاعات دیسک:</b>\n"
                root_partition = '/' if '/' in disk_info else list(disk_info.keys())[0]
                for key, value in disk_info[root_partition].items():
                    report += f"• {key}: {value}\n"
                
                # اطلاعات شبکه
                report += "\n<b>🌐 اطلاعات شبکه:</b>\n"
                for key, value in network_info.items():
                    report += f"• {key}: {value}\n"
                
                # پردازش‌های برتر از نظر CPU
                report += "\n<b>🔄 پردازش‌های با بیشترین مصرف CPU:</b>\n"
                for i, proc in enumerate(processes_by_cpu[:5], 1):
                    report += f"• {i}. {proc['name']} (PID: {proc['pid']}): {proc['cpu_percent']:.1f}% CPU, {proc['memory_percent']:.1f}% RAM\n"
                
                # پردازش‌های برتر از نظر حافظه
                report += "\n<b>🔄 پردازش‌های با بیشترین مصرف حافظه:</b>\n"
                for i, proc in enumerate(processes_by_memory[:5], 1):
                    report += f"• {i}. {proc['name']} (PID: {proc['pid']}): {proc['memory_percent']:.1f}% RAM, {proc['cpu_percent']:.1f}% CPU\n"
                
                # اطلاعات زمان اجرا
                boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
                uptime = datetime.datetime.now() - boot_time
                uptime_str = f"{uptime.days} روز، {uptime.seconds // 3600} ساعت، {(uptime.seconds // 60) % 60} دقیقه"
                report += f"\n<b>⏱️ زمان اجرا:</b> {uptime_str}"
                report += f"\n<b>📅 زمان شروع سیستم:</b> {boot_time.strftime('%Y-%m-%d %H:%M:%S')}"
                
                # اضافه کردن دکمه بازگشت
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(telebot.types.InlineKeyboardButton("🔄 بروزرسانی", callback_data="detailed_system_info"))
                markup.add(telebot.types.InlineKeyboardButton("🔙 بازگشت", callback_data="bot_status"))
                
                # ارسال گزارش
                bot.send_message(
                    call.message.chat.id,
                    report,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception as e:
                bot.send_message(
                    call.message.chat.id,
                    f"⚠️ خطا در تهیه گزارش سیستم: {str(e)}"
                )
            return
            
        # در صورتی که پردازش نشد، به تابع handle_callback اصلی ارسال شود
        if hasattr(bot, "original_handle_callback"):
            bot.original_handle_callback(call)
    
    except Exception as e:
        notify_admin(f"⚠️ خطا در پردازش کالبک: {str(e)}")

# 📩 مدیریت پیام‌های دریافتی
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        # بررسی این که پیام متنی باشد
        if not hasattr(message, 'text') or not message.text:
            debug_log("پیام غیر متنی دریافت شد", "INFO", {
                "chat_id": message.chat.id, 
                "content_type": message.content_type if hasattr(message, 'content_type') else "نامشخص"
            })
            return

        # بررسی اینکه فرستنده‌ی پیام موجود باشد
        if not hasattr(message, 'from_user') or not message.from_user:
            debug_log("پیام بدون اطلاعات فرستنده دریافت شد", "WARNING")
            return
            
        text = message.text.strip()
        
        # لاگ کردن پیام دریافتی
        debug_log(f"پیام جدید دریافت شد", "INFO", {
            "chat_id": message.chat.id,
            "user_id": message.from_user.id,
            "text_length": len(text),
            "has_link": "instagram.com" in text or "youtube.com" in text or "youtu.be" in text
        })

        # پردازش لینک‌های ویدیو
        if "instagram.com" in text or "youtube.com" in text or "youtu.be" in text:
            # نمایش پیام در حال پردازش
            try:
                processing_msg = bot.reply_to(message, "⏳ درحال پردازش لینک ویدیو... (ممکن است تا 2 دقیقه طول بکشد)")
            except Exception as reply_error:
                debug_log("خطا در ارسال پیام پاسخ", "ERROR", {"error": str(reply_error)})
                try:
                    processing_msg = bot.send_message(message.chat.id, "⏳ درحال پردازش لینک ویدیو... (ممکن است تا 2 دقیقه طول بکشد)")
                except Exception as send_error:
                    debug_log("خطا در ارسال پیام جدید", "ERROR", {"error": str(send_error)})
                    return
            
            # دریافت کیفیت ویدیو انتخاب شده توسط کاربر
            user_id = str(message.from_user.id)
            quality = DEFAULT_VIDEO_QUALITY  # کیفیت پیش‌فرض
            
            try:
                if hasattr(bot, "user_video_quality") and user_id in bot.user_video_quality:
                    quality = bot.user_video_quality[user_id]
                    
                debug_log(f"پردازش لینک ویدیو آغاز شد", "INFO", {
                    "user_id": user_id,
                    "quality": quality,
                    "link": text[:100]  # محدود کردن طول لینک در لاگ
                })
            except Exception as quality_error:
                debug_log("خطا در دریافت کیفیت ویدیو", "WARNING", {"error": str(quality_error)})
            
            # تنظیم گزینه‌ها برای دانلود
            ydl_opts = {
                'format': VIDEO_QUALITIES.get(quality, VIDEO_QUALITIES["240p"])["format"],
                'quiet': True,
                'noplaylist': True,
                'ignoreerrors': True
            }
            
            # لینک مستقیم (سریع‌ترین روش)
            direct_method_success = False
            try:
                direct_url = get_direct_video_url(text)
                if direct_url:
                    debug_log("لینک مستقیم ویدیو با موفقیت دریافت شد", "INFO")
                    try:
                        bot.edit_message_text("✅ ویدیو یافت شد! در حال ارسال...", message.chat.id, processing_msg.message_id)
                        bot.send_video(chat_id=message.chat.id, video=direct_url, timeout=60)
                        bot.delete_message(message.chat.id, processing_msg.message_id)
                        direct_method_success = True
                        debug_log("ارسال ویدیو با روش مستقیم موفقیت‌آمیز بود", "INFO")
                        return
                    except Exception as send_error:
                        debug_log("خطا در ارسال ویدیو با روش مستقیم", "WARNING", {"error": str(send_error)})
                        bot.edit_message_text("⏳ روش مستقیم موفق نبود. در حال دانلود ویدیو با کیفیت انتخابی...", 
                                             message.chat.id, processing_msg.message_id)
            except Exception as direct_error:
                debug_log("خطا در دریافت لینک مستقیم", "WARNING", {"error": str(direct_error)})
            
            # اگر روش مستقیم ناموفق بود، از روش دانلود استفاده می‌کنیم
            if not direct_method_success:
                try:
                    # شروع دانلود در یک thread جداگانه برای جلوگیری از انسداد
                    debug_log("شروع دانلود ویدیو در ترد جداگانه", "INFO")
                    thread_pool.submit(process_video_link, message, text, processing_msg)
                except Exception as thread_error:
                    debug_log("خطا در راه‌اندازی ترد دانلود", "ERROR", {"error": str(thread_error)})
                    try:
                        bot.edit_message_text(f"⚠️ خطا در پردازش ویدیو: {str(thread_error)[:100]}", 
                                            message.chat.id, processing_msg.message_id)
                    except:
                        pass
            
            return

            elif "،" in text:
            try:
                question, answer = map(str.strip, text.split("،", 1))

                # بررسی معتبر بودن سوال و جواب
                if not question or not answer:
                    bot.reply_to(message, "⚠️ سوال یا جواب نمی‌تواند خالی باشد!")
                    return

                # محدود کردن طول سوال و جواب
                if len(question) > 100:
                    question = question[:100]
                if len(answer) > 500:
                    answer = answer[:500]

                # ذخیره در پاسخ‌ها
                responses[question.lower()] = answer
                debug_log(f"پاسخ جدید اضافه شد", "INFO", {"question": question, "answer": answer})

                # ذخیره پاسخ‌ها در فایل
                try:
                    save_responses()
                except Exception as save_error:
                    debug_log("خطا در ذخیره پاسخ‌ها", "ERROR", {"error": str(save_error)})
                    bot.reply_to(message, "⚠️ خطا در ذخیره پاسخ‌ها. دوباره تلاش کنید.")
                    return

                bot.reply_to(
                    message,
                    f"✅ سوال '{question}' با پاسخ '{answer}' اضافه شد!")
            except ValueError:
                bot.reply_to(message,
                             "⚠️ لطفاً فرمت 'سوال، جواب' را رعایت کنید.")
            except Exception as reply_error:
                debug_log("خطا در افزودن پاسخ جدید", "ERROR", {"error": str(reply_error)})
                try:
                    bot.reply_to(message, "⚠️ خطا در پردازش درخواست. لطفاً دوباره تلاش کنید.")
                except:
                    pass
            return

        else:
            # چک کردن اگر پیام مطابق با یکی از سوالات موجود است
            try:
                key = text.lower().strip()
                if key in responses:
                    debug_log(f"پاسخ خودکار ارسال شد", "INFO", {"question": key})
                    bot.reply_to(message, responses[key])
                else:
                    # اگر پیام شامل سلام، خوبی و ... باشد، پاسخ مناسب ارسال کنیم
                    greetings = ['سلام', 'درود', 'خوبی', 'چطوری', 'خوبین', 'چطوری', 'سلام', 'hi', 'hello']
                    if any(greeting in key for greeting in greetings):
                        debug_log("پاسخ به سلام کاربر", "INFO")
                        bot.reply_to(message, f"👋 سلام {message.from_user.first_name}!\n\n"
                              "🎬 لینک‌های یوتیوب یا اینستاگرام خود را ارسال کنید تا ویدیو برای شما دانلود شود.\n\n"
                              "✅ همه کاربران می‌توانند پاسخ‌های جدید اضافه کنند!")  
                    
                    # در غیر این صورت، لینک راهنما را نمایش دهیم (فقط برای پیام‌های خصوصی)
                    elif message.chat.type == 'private' and len(key) > 3:
                        debug_log("ارسال راهنما برای پیام ناشناخته", "INFO")
                        markup = telebot.types.InlineKeyboardMarkup()
                        help_btn = telebot.types.InlineKeyboardButton("📚 راهنما", callback_data="download_help")
                        quality_btn = telebot.types.InlineKeyboardButton("📊 کیفیت ویدیو", callback_data="select_quality")
                        markup.add(help_btn, quality_btn)
                        bot.reply_to(
                            message,
                            "برای دانلود ویدیو، کافیست لینک یوتیوب یا اینستاگرام را ارسال کنید 🎬",
                            reply_markup=markup
                        )
            except Exception as response_error:
                debug_log("خطا در ارسال پاسخ", "ERROR", {"error": str(response_error)})

    except Exception as e:
        error_msg = f"⚠️ خطا در پردازش پیام:\n{traceback.format_exc()}"
        debug_log("خطا در تابع handle_message", "ERROR", {
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        
        try:
            notify_admin(error_msg)
        except Exception as notify_error:
            debug_log("خطا در اطلاع به ادمین", "ERROR", {"error": str(notify_error)})


def keep_awake():
    while True:
        # بررسی مقدار استفاده از CPU
        cpu_usage = psutil.cpu_percent(interval=1)
        if cpu_usage < 5:  # اگر پردازش تقریباً غیرفعال شد، یک عملیات کوچک انجام بده
            print("✅ جلوگیری از خوابیدن ربات با افزایش پردازش")
            _ = [x**2 for x in range(10000)]  # انجام یک پردازش کوچک

        time.sleep(300)  # ⏳ هر 5 دقیقه یک‌بار بررسی شود


# اجرای تابع در یک ترد جداگانه
threading.Thread(target=keep_awake, daemon=True).start()
LAST_USAGE = {"cpu": 0, "ram": 0}
high_usage_alert = {"cpu": False, "ram": False}  # وضعیت هشدار CPU و RAM


def monitor_server():
    global LAST_USAGE, high_usage_alert
    while True:
        cpu_usage = psutil.cpu_percent(interval=1)
        ram_usage = psutil.virtual_memory().percent

        # اگر CPU بالای ۸۰٪ باشد و قبلاً هشدار نداده باشد
        if cpu_usage > 80:
            if not high_usage_alert["cpu"]:
                time.sleep(300)  # بررسی مجدد بعد از 5 دقیقه
                cpu_recheck = psutil.cpu_percent(interval=1)
                if cpu_recheck > 80:  # هنوز بالای ۸۰٪ است
                    bot.send_message(
                        ADMIN_CHAT_ID,
                        f"⚠ **هشدار: مصرف CPU بالای ۸۰٪ باقی مانده!**\n🔹 **CPU:** {cpu_recheck}%"
                    )
                    high_usage_alert["cpu"] = True  # ثبت هشدار
        else:
            high_usage_alert[
                "cpu"] = False  # اگر CPU کاهش یافت، هشدار را ریست کن

        # اگر RAM بالای ۸۰٪ باشد و قبلاً هشدار نداده باشد
        if ram_usage > 80:
            if not high_usage_alert["ram"]:
                time.sleep(300)  # بررسی مجدد بعد از 5 دقیقه
                ram_recheck = psutil.virtual_memory().percent
                if ram_recheck > 80:  # هنوز بالای ۸۰٪ است
                    bot.send_message(
                        ADMIN_CHAT_ID,
                        f"⚠ **هشدار: مصرف RAM بالای ۸۰٪ باقی مانده!**\n🔹 **RAM:** {ram_recheck}%"
                    )
                    high_usage_alert["ram"] = True  # ثبت هشدار
        else:
            high_usage_alert[
                "ram"] = False  # اگر RAM کاهش یافت، هشدار را ریست کن

        LAST_USAGE["cpu"] = cpu_usage
        LAST_USAGE["ram"] = ram_usage

        time.sleep(60)  # هر ۱ دقیقه بررسی شود


threading.Thread(target=monitor_server, daemon=True).start()


# 🔄 اجرای ایمن ربات
def safe_polling():
    while True:
        try:
            bot.polling(none_stop=True, interval=15,
                        timeout=30)  # ⬅ افزایش timeout برای کاهش مصرف CPU
        except (ReadTimeout, ProxyError, ConnectionResetError):
            time.sleep(
                30)  # ⬅ جلوگیری از درخواست‌های مکرر در صورت قطع شدن ارتباط
        except Exception as e:
            notify_admin(
                f"⚠️ خطای بحرانی در اجرای ربات:\n{traceback.format_exc()}")
            time.sleep(30)


# 📌 تابع شروع ربات برای اجرا از main.py
def start_bot():
    # متغیر محیطی برای تعیین حالت ربات: وب‌هوک یا polling
    # حالت polling را فعال می‌کنیم تا ربات همیشه روشن بماند
    WEBHOOK_MODE = False  # به جای استفاده از متغیر محیطی، مستقیماً false قرار می‌دهیم
    
    if WEBHOOK_MODE:
        # تنظیمات وب‌هوک
        try:
            # برای سرور ریل‌وی، آدرس دامنه را تنظیم می‌کنیم
            # از آدرس واقعی سرور ریل‌وی استفاده می‌کنیم
            webhook_host = os.environ.get('DOMAIN_URL')
            
            if not webhook_host:
                webhook_host = "https://telegram-production-cc29.up.railway.app"
                
            print(f"📌 آدرس وب‌هوک: {webhook_host}")
                
            webhook_path = f"/{TOKEN}/"
            webhook_url = f"{webhook_host}{webhook_path}"
            
            print(f"🔄 در حال تنظیم وب‌هوک با آدرس: {webhook_host}")
            
            # حذف وب‌هوک قبلی (اگر وجود داشته باشد)
            bot.remove_webhook()
            time.sleep(0.2)
            
            # تنظیم وب‌هوک جدید - بدون نمایش توکن در لاگ‌ها
            bot.set_webhook(url=webhook_url)
            masked_url = webhook_url.replace(TOKEN, "***TOKEN***")
            print(f"🔌 وب‌هوک با موفقیت در {masked_url} تنظیم شد")
            return True  # وب‌هوک با موفقیت تنظیم شد
        except Exception as e:
            print(f"⚠ خطا در تنظیم وب‌هوک: {e}")
            time.sleep(5)
            return False
    else:
        # حالت polling - برای زمانی که وب‌هوک در دسترس نیست
        while True:
            try:
                # حذف وب‌هوک قبلی (اگر وجود داشته باشد)
                bot.remove_webhook()
                time.sleep(0.2)
                
                # شروع polling
                print("🔄 ربات در حالت polling شروع به کار کرد")
                bot.polling(none_stop=True, interval=10, timeout=30)
            except Exception as e:
                print(f"⚠ خطای بحرانی در اجرای ربات:\n{e}")
                time.sleep(15)


if __name__ == "__main__":
    print("🚀 Webhook فعال شد!")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
