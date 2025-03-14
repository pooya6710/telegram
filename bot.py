import telebot
import os
import shutil  # برای دریافت وضعیت دیسک
import psutil  # برای دریافت اطلاعات CPU و RAM
import platform  # برای دریافت اطلاعات سیستم‌عامل
import json
import sqlite3
import datetime
import threading
import concurrent.futures
from flask import Flask, request
import time
import traceback
from yt_dlp import YoutubeDL
from requests.exceptions import ReadTimeout, ProxyError, ConnectionError

app = Flask(__name__)

# ایجاد استخر ترد برای اجرای همزمان فرایندها
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode("UTF-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        print(f"❌ خطا در دریافت پیام: {e}")
    return "✅ Webhook دریافت شد!", 200


SERVER_CACHE = {"status": None, "timestamp": None}


def get_cached_server_status():
    global SERVER_CACHE
    if SERVER_CACHE["status"] and (datetime.datetime.now() -
                                   SERVER_CACHE["timestamp"]).seconds < 600:
        return SERVER_CACHE["status"]

    if os.path.exists("server_status.json"):
        try:
            with open("server_status.json", "r", encoding="utf-8") as file:
                data = json.load(file)
                SERVER_CACHE["status"] = data["status"]
                SERVER_CACHE["timestamp"] = datetime.datetime.strptime(
                    data["timestamp"], "%Y-%m-%d %H:%M:%S")
                return data["status"]
        except Exception:
            return None
    return None


MESSAGES_DB_TEXT = "channel_messages.json"
MESSAGES_DB_LINKS = "channel_links.json"
MAX_MESSAGES = 100000  # حداکثر تعداد لینک‌های ذخیره‌شده

# 📂 اگر فایل ذخیره‌ی پیام‌ها وجود نداشت، ایجادش کن
if not os.path.exists(MESSAGES_DB_LINKS):
    with open(MESSAGES_DB_LINKS, "w", encoding="utf-8") as file:
        json.dump({}, file, ensure_ascii=False, indent=4)

# 🔑 توکن ربات تلگرام
TOKEN = '7338644071:AAEex9j0nMualdoywHSGFiBoMAzRpkFypPk'
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


# 📌 بررسی وضعیت سرور
@bot.message_handler(commands=["server_status"])
def server_status(message):
    try:
        cached_status = get_cached_server_status()
        if cached_status:
            bot.send_message(message.chat.id,
                             cached_status,
                             parse_mode="Markdown")
            return

        # اطلاعات دیسک
        total, used, free = shutil.disk_usage("/")
        total_gb = total / (1024**3)
        used_gb = used / (1024**3)
        free_gb = free / (1024**3)

        # مصرف CPU و RAM
        cpu_usage = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_used = ram.used / (1024**3)
        ram_total = ram.total / (1024**3)

        # مدت زمان روشن بودن سرور
        uptime_seconds = time.time() - psutil.boot_time()
        uptime_hours = uptime_seconds // 3600
        uptime_minutes = (uptime_seconds % 3600) // 60

        status_msg = (f"📊 **وضعیت سرور:**\n"
                      f"🔹 **CPU:** `{cpu_usage}%`\n"
                      f"🔹 **RAM:** `{ram_used:.2f}GB / {ram_total:.2f}GB`\n"
                      f"🔹 **فضای باقی‌مانده:** `{free_gb:.2f}GB`\n"
                      f"🔹 **مدت روشن بودن:** `{int(uptime_hours)} ساعت`\n")

        # ذخیره وضعیت سرور در یک فایل JSON برای کش کردن
        with open("server_status.json", "w", encoding="utf-8") as file:
            json.dump(
                {
                    "timestamp":
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status":
                    status_msg
                }, file)

        bot.send_message(message.chat.id, status_msg, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, "⚠ خطا در دریافت وضعیت سرور!")


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

        elif "،" in text:
            try:
                question, answer = map(str.strip, text.split("،", 1))
                responses[question.lower()] = answer
                save_responses()
                bot.reply_to(
                    message,
                    f"✅ سوال '{question}' با پاسخ '{answer}' اضافه شد!")
            except ValueError:
                bot.reply_to(message,
                             "⚠️ لطفاً فرمت 'سوال، جواب' را رعایت کنید.")
            return

        else:
            key = text.lower()
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
    while True:
        try:
            bot.polling(none_stop=True, interval=10, timeout=30)
        except Exception as e:
            print(f"⚠ خطای بحرانی در اجرای ربات:\n{e}")
            time.sleep(15)


if __name__ == "__main__":
    print("🚀 Webhook فعال شد!")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
