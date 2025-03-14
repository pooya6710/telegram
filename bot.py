import os
import json
import datetime
import threading
import concurrent.futures
import time
import traceback
from requests.exceptions import ReadTimeout, ProxyError, ConnectionError

# واردکردن ماژول‌ها با مدیریت خطا
try:
    import telebot
except ImportError:
    print("⚠️ ماژول telebot نصب نشده است")
    exit(1)

try:
    from flask import Flask, request
except ImportError:
    print("⚠️ ماژول flask نصب نشده است")

try:
    import shutil  # برای دریافت وضعیت دیسک
except ImportError:
    print("⚠️ ماژول shutil در دسترس نیست")
    
try:
    import psutil  # برای دریافت اطلاعات CPU و RAM
except ImportError:
    print("⚠️ ماژول psutil نصب نشده است")
    
try:
    import platform  # برای دریافت اطلاعات سیستم‌عامل
except ImportError:
    print("⚠️ ماژول platform در دسترس نیست")
    
try:
    import sqlite3
except ImportError:
    print("⚠️ ماژول sqlite3 در دسترس نیست")
    
try:
    from yt_dlp import YoutubeDL
except ImportError:
    print("⚠️ ماژول yt_dlp نصب نشده است")

app = Flask(__name__)

# ایجاد استخر ترد برای اجرای همزمان فرایندها
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)


# برای دریافت وب‌هوک از فلسک استفاده می‌کنیم
def webhook():
    try:
        json_str = request.get_data().decode("UTF-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "✅ Webhook دریافت شد!", 200
    except Exception as e:
        print(f"❌ خطا در دریافت پیام: {e}")
        return f"❌ خطا: {e}", 500


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

# 🔑 توکن ربات تلگرام از متغیرهای محیطی
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
if not TOKEN:
    print("⚠️ خطا: متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم نشده است!")
    
bot = telebot.TeleBot(TOKEN)

# 📢 آیدی عددی ادمین
ADMIN_CHAT_ID = 286420965

# 📊 تنظیمات بهینه‌سازی فضا
MAX_VIDEOS_TO_KEEP = 3  # حداکثر تعداد ویدئو‌های ذخیره‌شده

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

# 🧹 پاکسازی فایل‌های قدیمی و نگهداری حداکثر تعداد مشخصی فایل
def clear_folder(folder_path, max_files=MAX_VIDEOS_TO_KEEP):
    """حذف فایل‌های قدیمی و نگهداری حداکثر تعداد مشخصی فایل"""
    try:
        files = os.listdir(folder_path)
        if len(files) >= max_files:
            # مرتب‌سازی فایل‌ها بر اساس زمان تغییر (قدیمی‌ترین اول)
            files = sorted(files, key=lambda x: os.path.getmtime(os.path.join(folder_path, x)))
            # حذف فایل‌های قدیمی
            for old_file in files[:-max_files+1]:  # یک فایل کمتر حذف می‌کنیم تا جا برای فایل جدید باشد
                file_path = os.path.join(folder_path, old_file)
                os.remove(file_path)
                print(f"🗑️ فایل قدیمی حذف شد: {file_path}")
    except Exception as e:
        print(f"❌ خطا در پاکسازی پوشه {folder_path}: {e}")


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
        
        markup.add(quality_btn)
        
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
    """بارگذاری سوال و پاسخ‌ها از فایل JSON"""
    try:
        with open("responses.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        # اگر فایل وجود نداشت، یک فایل خالی ایجاد کن
        empty_data = {}
        save_responses(empty_data)
        return empty_data
    except Exception as e:
        print(f"⚠️ خطا در بارگذاری فایل پاسخ‌ها: {e}")
        return {}


def save_responses(data=None):
    """ذخیره سوال و پاسخ‌ها در فایل JSON"""
    try:
        with open("responses.json", "w", encoding="utf-8") as file:
            json.dump(data if data is not None else responses, file, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"⚠️ خطا در ذخیره فایل پاسخ‌ها: {e}")
        return False


def add_response(question, answer, user_id=None):
    """افزودن یک سوال و پاسخ جدید"""
    if not question or not answer:
        return False, "سوال یا پاسخ نمی‌تواند خالی باشد!"
    
    # تمیز کردن سوال (حذف فاصله‌های اضافی، حروف بزرگ و...)
    clean_question = question.strip().lower()
    
    # بررسی تکراری نبودن سوال
    if clean_question in responses:
        return False, f"این سوال قبلاً اضافه شده است! پاسخ فعلی: {responses[clean_question]}"
    
    # افزودن به دیکشنری
    responses[clean_question] = answer
    
    # ذخیره تغییرات
    if save_responses():
        # ثبت اطلاعات کاربری که سوال را اضافه کرده (اختیاری)
        if user_id:
            print(f"✅ سوال و پاسخ جدید توسط کاربر {user_id} اضافه شد")
        return True, f"✅ سوال و پاسخ با موفقیت اضافه شد:\nسوال: {question}\nپاسخ: {answer}"
    else:
        return False, "❌ خطا در ذخیره سوال و پاسخ"


def delete_response(question):
    """حذف یک سوال و پاسخ"""
    clean_question = question.strip().lower()
    
    if clean_question in responses:
        deleted_answer = responses[clean_question]
        del responses[clean_question]
        
        if save_responses():
            return True, f"✅ سوال و پاسخ با موفقیت حذف شد:\nسوال: {question}\nپاسخ: {deleted_answer}"
        else:
            # در صورت خطا در ذخیره، سوال را برگردان
            responses[clean_question] = deleted_answer
            return False, "❌ خطا در حذف سوال و پاسخ"
    else:
        return False, "❌ این سوال در پایگاه داده وجود ندارد!"


def update_response(question, new_answer):
    """به‌روزرسانی پاسخ یک سوال موجود"""
    clean_question = question.strip().lower()
    
    if clean_question in responses:
        old_answer = responses[clean_question]
        responses[clean_question] = new_answer
        
        if save_responses():
            return True, f"✅ پاسخ با موفقیت به‌روزرسانی شد:\nسوال: {question}\nپاسخ قبلی: {old_answer}\nپاسخ جدید: {new_answer}"
        else:
            # در صورت خطا در ذخیره، پاسخ را برگردان
            responses[clean_question] = old_answer
            return False, "❌ خطا در به‌روزرسانی پاسخ"
    else:
        return False, "❌ این سوال در پایگاه داده وجود ندارد!"


def search_responses(query):
    """جستجو در سوالات موجود"""
    if not query or len(query) < 2:
        return []
    
    clean_query = query.strip().lower()
    results = []
    
    for question, answer in responses.items():
        if clean_query in question:
            results.append({"question": question, "answer": answer})
    
    return results


def get_all_responses(max_count=20):
    """دریافت لیست همه سوال و پاسخ‌ها"""
    items = list(responses.items())
    return items[:max_count]  # محدود کردن تعداد نتایج


# بارگیری سوالات و پاسخ‌ها
responses = load_responses()


# 📌 استخراج لینک مستقیم ویدیو بدون دانلود
def get_direct_video_url(link):
    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'noplaylist': True,
            'force_generic_extractor': False,
            'format': 'best[ext=mp4]/best',
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            return info.get('url', None)
    except Exception as e:
        notify_admin(
            f"⚠️ خطا در دریافت لینک مستقیم ویدیو:\n{traceback.format_exc()}")
        return None


# 📌 دانلود ویدیو از اینستاگرام
def download_instagram(link):
    try:
        clear_folder(INSTAGRAM_FOLDER)  # حذف فایل‌های قدیمی

        ydl_opts = {
            'outtmpl': f'{INSTAGRAM_FOLDER}/%(id)s.%(ext)s',
            'format': 'mp4/best',
            'quiet': False,
            'noplaylist': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            video_path = f"{INSTAGRAM_FOLDER}/{info['id']}.mp4"
            return video_path if os.path.exists(video_path) else None

    except Exception as e:
        notify_admin(
            f"⚠️ خطا در دانلود ویدیو از اینستاگرام:\n{traceback.format_exc()}")
        return None


# 📌 دانلود ویدیو از یوتیوب
def download_youtube(link):
    try:
        clear_folder(VIDEO_FOLDER)  # حذف فایل‌های قدیمی

        ydl_opts = {
            'outtmpl': f'{VIDEO_FOLDER}/%(id)s.%(ext)s',
            'format': 'mp4/best',
            'quiet': False,
            'noplaylist': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            video_path = f"{VIDEO_FOLDER}/{info['id']}.mp4"
            return video_path if os.path.exists(video_path) else None

    except Exception as e:
        notify_admin(
            f"⚠️ خطا در دانلود ویدیو از یوتیوب:\n{traceback.format_exc()}")
        return None


# 📢 ارسال پیام به ادمین در صورت وقوع خطا
def notify_admin(message):
    try:
        bot.send_message(ADMIN_CHAT_ID, message[:4000])
    except Exception as e:
        print(f"⚠️ خطا در ارسال پیام به ادمین: {e}")


# 🎬 پردازش لینک‌های ویدیو برای دانلود
def process_video_link(message, link, processing_msg):
    """
    دانلود و ارسال ویدیو از لینک داده شده
    این تابع در یک ترد جداگانه اجرا می‌شود تا ربات حین دانلود پاسخگو باشد
    """
    try:
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
            }
            folder = INSTAGRAM_FOLDER
        else:
            # یوتیوب یا دیگر سایت‌ها
            ydl_opts = {
                'format': format_option,
                'outtmpl': f'{VIDEO_FOLDER}/%(id)s.%(ext)s',
                'quiet': True,
                'noplaylist': True,
            }
            folder = VIDEO_FOLDER
        
        # پاکسازی فایل‌های قدیمی
        clear_folder(folder)
        
        # دانلود ویدیو
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            
            # آماده‌سازی فایل ویدیو برای ارسال
            if info.get('id'):
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
                            return
                        else:
                            # برای فایل‌های بزرگتر، قطعه‌بندی یا روش دیگری نیاز است
                            bot.edit_message_text(
                                f"⚠️ سایز فایل ({file_size_mb:.1f} MB) بیشتر از محدودیت تلگرام است. لطفاً با کیفیت پایین‌تر امتحان کنید.",
                                message.chat.id,
                                processing_msg.message_id,
                                parse_mode="HTML"
                            )
                            return
                    except Exception as e:
                        bot.edit_message_text(
                            f"⚠️ خطا در ارسال ویدیو: {str(e)}\n\nلطفاً با کیفیت پایین‌تر امتحان کنید.",
                            message.chat.id,
                            processing_msg.message_id
                        )
                        notify_admin(f"خطا در ارسال ویدیو به کاربر {message.from_user.id}: {str(e)}")
                        return
                    
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
        text = message.text.strip()

        if "instagram.com" in text or "youtube.com" in text or "youtu.be" in text:
            # نمایش پیام در حال پردازش
            processing_msg = bot.reply_to(message, "⏳ درحال پردازش لینک ویدیو... (ممکن است تا 2 دقیقه طول بکشد)")
            
            # دریافت کیفیت ویدیو انتخاب شده توسط کاربر
            user_id = str(message.from_user.id)
            quality = DEFAULT_VIDEO_QUALITY  # کیفیت پیش‌فرض
            
            if hasattr(bot, "user_video_quality") and user_id in bot.user_video_quality:
                quality = bot.user_video_quality[user_id]
            
            # تنظیم گزینه‌ها برای دانلود
            ydl_opts = {
                'format': VIDEO_QUALITIES.get(quality, VIDEO_QUALITIES["240p"])["format"],
                'quiet': True,
                'noplaylist': True
            }
            
            # لینک مستقیم (سریع‌ترین روش)
            try:
                direct_url = get_direct_video_url(text)
                if direct_url:
                    bot.edit_message_text("✅ ویدیو یافت شد! در حال ارسال...", message.chat.id, processing_msg.message_id)
                    try:
                        bot.send_video(chat_id=message.chat.id, video=direct_url, timeout=60)
                        bot.delete_message(message.chat.id, processing_msg.message_id)
                        return
                    except Exception:
                        bot.edit_message_text("⏳ روش مستقیم موفق نبود. در حال دانلود ویدیو با کیفیت انتخابی...", 
                                             message.chat.id, processing_msg.message_id)
            except Exception as e:
                print(f"خطا در دریافت لینک مستقیم: {e}")
            
            # دانلود و ارسال ویدیو
            try:
                # شروع دانلود در یک thread جداگانه برای جلوگیری از انسداد
                thread_pool.submit(process_video_link, message, text, processing_msg)
            except Exception as e:
                bot.edit_message_text(f"⚠️ خطا در پردازش ویدیو: {str(e)}", message.chat.id, processing_msg.message_id)
            
            return

        # بررسی دستورات مدیریت سوال و پاسخ
        elif text.startswith('/qa_add '):
            # دستور افزودن سوال و پاسخ
            try:
                command_parts = text[8:].strip().split('|', 1)
                if len(command_parts) != 2:
                    bot.reply_to(message, "⚠️ فرمت صحیح: /qa_add سوال | پاسخ")
                    return
                
                question, answer = map(str.strip, command_parts)
                success, result_msg = add_response(question, answer, message.from_user.id)
                bot.reply_to(message, result_msg)
            except Exception as e:
                bot.reply_to(message, f"⚠️ خطا در افزودن سوال و پاسخ: {str(e)}")
            return
            
        elif text.startswith('/qa_del ') or text.startswith('/qa_delete '):
            # دستور حذف سوال و پاسخ
            try:
                if text.startswith('/qa_del '):
                    question = text[8:].strip()
                else:
                    question = text[11:].strip()
                
                if not question:
                    bot.reply_to(message, "⚠️ لطفاً سوال مورد نظر برای حذف را وارد کنید.")
                    return
                
                success, result_msg = delete_response(question)
                bot.reply_to(message, result_msg)
            except Exception as e:
                bot.reply_to(message, f"⚠️ خطا در حذف سوال و پاسخ: {str(e)}")
            return
            
        elif text.startswith('/qa_update '):
            # دستور به‌روزرسانی پاسخ یک سوال
            try:
                command_parts = text[11:].strip().split('|', 1)
                if len(command_parts) != 2:
                    bot.reply_to(message, "⚠️ فرمت صحیح: /qa_update سوال | پاسخ جدید")
                    return
                
                question, new_answer = map(str.strip, command_parts)
                success, result_msg = update_response(question, new_answer)
                bot.reply_to(message, result_msg)
            except Exception as e:
                bot.reply_to(message, f"⚠️ خطا در به‌روزرسانی پاسخ: {str(e)}")
            return
            
        elif text.startswith('/qa_search '):
            # دستور جستجو در سوالات
            try:
                query = text[11:].strip()
                if not query or len(query) < 2:
                    bot.reply_to(message, "⚠️ لطفاً عبارت جستجو را با حداقل ۲ کاراکتر وارد کنید.")
                    return
                
                results = search_responses(query)
                if not results:
                    bot.reply_to(message, f"❌ هیچ سوالی با عبارت '{query}' یافت نشد.")
                    return
                
                # تهیه پیام نتایج
                result_message = f"🔍 نتایج جستجو برای '{query}':\n\n"
                for i, item in enumerate(results, 1):
                    result_message += f"{i}. سوال: {item['question']}\n   پاسخ: {item['answer']}\n\n"
                
                # ارسال نتایج
                bot.reply_to(message, result_message)
            except Exception as e:
                bot.reply_to(message, f"⚠️ خطا در جستجوی سوالات: {str(e)}")
            return
            
        elif text == '/qa_list' or text == '/qa_all':
            # نمایش همه سوال و پاسخ‌ها
            try:
                items = get_all_responses()
                if not items:
                    bot.reply_to(message, "❌ هیچ سوال و پاسخی در پایگاه داده وجود ندارد.")
                    return
                
                result_message = "📝 لیست همه سوال و پاسخ‌ها:\n\n"
                for i, (question, answer) in enumerate(items, 1):
                    result_message += f"{i}. سوال: {question}\n   پاسخ: {answer}\n\n"
                
                bot.reply_to(message, result_message)
            except Exception as e:
                bot.reply_to(message, f"⚠️ خطا در دریافت لیست سوالات: {str(e)}")
            return
            
        elif text == '/qa_help':
            # راهنمای استفاده از قابلیت سوال و پاسخ
            help_text = """
🔰 راهنمای قابلیت سوال و پاسخ:

🟢 افزودن سوال و پاسخ:
/qa_add سوال | پاسخ

🔴 حذف سوال و پاسخ:
/qa_del سوال

🔄 به‌روزرسانی پاسخ:
/qa_update سوال | پاسخ جدید

🔍 جستجو در سوالات:
/qa_search عبارت جستجو

📋 نمایش همه سوالات:
/qa_list

💡 برای دریافت پاسخ، کافیست سوال را به تنهایی ارسال کنید.
"""
            bot.reply_to(message, help_text)
            return
            
        elif "،" in text:
            # روش قدیمی افزودن سوال و پاسخ (با ویرگول فارسی)
            try:
                question, answer = map(str.strip, text.split("،", 1))
                success, result = add_response(question, answer, message.from_user.id)
                bot.reply_to(message, result)
            except ValueError:
                bot.reply_to(message, "⚠️ لطفاً فرمت 'سوال، جواب' را رعایت کنید یا از دستور /qa_add استفاده کنید.")
            return

        else:
            # چک کردن اگر پیام مطابق با یکی از سوالات موجود است
            key = text.lower().strip()
            if key in responses:
                bot.reply_to(message, responses[key])

    except Exception as e:
        notify_admin(f"⚠️ خطا در پردازش پیام:\n{traceback.format_exc()}")


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
    WEBHOOK_MODE = os.environ.get('WEBHOOK_MODE', 'true').lower() == 'true'
    
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
