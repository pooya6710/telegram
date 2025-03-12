import telebot
import os
import json
import time
import traceback
import threading
import concurrent.futures
from functools import lru_cache
from yt_dlp import YoutubeDL
from requests.exceptions import ReadTimeout, ProxyError, ConnectionError

# 🔑 توکن ربات تلگرام
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN, skip_pending=True, threaded=True)

# 📢 آیدی عددی ادمین برای دریافت خطاها
ADMIN_CHAT_ID = 286420965  

# 📂 مسیر ذخیره ویدیوها
VIDEO_FOLDER = "videos"
INSTAGRAM_FOLDER = "instagram_videos"
os.makedirs(VIDEO_FOLDER, exist_ok=True)
os.makedirs(INSTAGRAM_FOLDER, exist_ok=True)

# مدیریت ویدیوهای ذخیره شده اخیر - کش
RECENT_VIDEOS = {}
MAX_CACHE_SIZE = 5

# تنظیمات
DOWNLOAD_TIMEOUT = 300  # حداکثر زمان دانلود (ثانیه)
MAX_VIDEOS_PER_FOLDER = 3  # کاهش تعداد ویدئو ذخیره شده برای بهینه‌سازی فضا
VIDEO_MAX_SIZE_MB = 25  # حداکثر حجم ویدئو (مگابایت)
DEFAULT_VIDEO_QUALITY = "240p"  # کیفیت پیش‌فرض ویدئو برای کاهش فضای ذخیره‌سازی
# کیفیت‌های قابل انتخاب
VIDEO_QUALITIES = {
    "144p": {"height": "144", "format": "worst[height<=144]/worst"},
    "240p": {"height": "240", "format": "worst[height<=240]/worst"},
    "360p": {"height": "360", "format": "worst[height<=360]/worst"},
    "480p": {"height": "480", "format": "worst[height<=480]/worst"},
    "720p": {"height": "720", "format": "best[height<=720]/best"},
    "1080p": {"height": "1080", "format": "best[height<=1080]/best"}
}
MAX_WORKERS = 4  # تعداد نخ‌ها برای دانلود همزمان

# تعداد تلاش‌های مجدد در صورت شکست
MAX_RETRIES = 3
RETRY_DELAY = 5  # ثانیه

# کارگر برای عملیات موازی
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)

# 📊 ابزار نظارت بر فضای ذخیره‌سازی
def get_storage_stats():
    """محاسبه و برگرداندن آمار فضای ذخیره‌سازی"""
    stats = {
        "total_videos": 0,
        "total_size_mb": 0,
        "folders": {}
    }
    
    # محاسبه حجم هر پوشه
    for folder_name in [VIDEO_FOLDER, INSTAGRAM_FOLDER]:
        folder_size = 0
        file_count = 0
        
        if os.path.exists(folder_name):
            for filename in os.listdir(folder_name):
                file_path = os.path.join(folder_name, filename)
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    folder_size += file_size
                    file_count += 1
        
        folder_size_mb = folder_size / (1024 * 1024)
        stats["folders"][folder_name] = {
            "size_mb": round(folder_size_mb, 2),
            "file_count": file_count
        }
        
        stats["total_videos"] += file_count
        stats["total_size_mb"] += folder_size_mb
    
    stats["total_size_mb"] = round(stats["total_size_mb"], 2)
    return stats

# 🗜️ فشرده‌سازی ویدیو برای کاهش حجم
def compress_video(input_path, output_path=None, target_size_mb=20, quality="240p"):
    """
    فشرده‌سازی ویدیو برای کاهش حجم فایل
    
    Args:
        input_path: مسیر فایل ورودی
        output_path: مسیر فایل خروجی (اگر None باشد، فایل ورودی بازنویسی می‌شود)
        target_size_mb: حجم هدف به مگابایت
        quality: کیفیت ویدیو (144p, 240p, 360p, 480p, 720p, 1080p)
    
    Returns:
        مسیر فایل خروجی در صورت موفقیت، None در صورت شکست
    """
    import subprocess
    import tempfile
    
    try:
        # محاسبه حجم فعلی فایل
        current_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        
        # اگر فایل کوچکتر از حجم هدف است، آن را کپی کن
        if current_size_mb <= target_size_mb:
            if output_path and output_path != input_path:
                import shutil
                shutil.copy2(input_path, output_path)
            return output_path or input_path
            
        # تنظیم مسیر خروجی
        final_output = output_path or input_path
        temp_output = None
        
        if output_path is None:
            # ایجاد فایل موقت برای جلوگیری از بازنویسی فایل ورودی
            fd, temp_output = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
            output_path = temp_output
            
        # استخراج ارتفاع ویدیو بر اساس کیفیت
        height = VIDEO_QUALITIES.get(quality, VIDEO_QUALITIES["240p"])["height"]
        
        # محاسبه بیت‌ریت مناسب برای رسیدن به حجم هدف
        # فرمول: (حجم هدف به بایت * 8) / (مدت زمان به ثانیه)
        duration_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                         "-of", "default=noprint_wrappers=1:nokey=1", input_path]
        duration = float(subprocess.check_output(duration_cmd).decode().strip())
        
        # محاسبه بیت‌ریت با 10% حاشیه ایمنی
        target_bitrate = int(((target_size_mb * 8192) / duration) * 0.9)
        
        # فرمان ffmpeg با تنظیمات بهینه‌سازی شده
        cmd = [
            "ffmpeg", "-i", input_path, 
            "-y",  # بازنویسی فایل خروجی اگر وجود دارد
            "-c:v", "libx264",  # کدک ویدیو با فشرده‌سازی بالا
            "-preset", "medium",  # توازن بین سرعت فشرده‌سازی و کیفیت
            "-b:v", f"{target_bitrate}k",  # بیت‌ریت ویدیو
            "-maxrate", f"{int(target_bitrate * 1.5)}k",  # حداکثر بیت‌ریت
            "-bufsize", f"{target_bitrate * 2}k",  # اندازه بافر
            "-vf", f"scale=-2:{height}",  # تغییر سایز ویدیو با حفظ نسبت تصویر
            "-c:a", "aac",  # کدک صدا
            "-b:a", "128k",  # بیت‌ریت صدا
            "-ac", "2",  # کانال‌های صدا
            "-ar", "44100",  # فرکانس نمونه‌برداری صدا
            "-f", "mp4",  # فرمت خروجی
            output_path
        ]
        
        # فشرده‌سازی با محدودیت زمانی
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate(timeout=300)  # تایم‌اوت 5 دقیقه
            
            if process.returncode != 0:
                print(f"⚠️ خطا در فشرده‌سازی ویدیو: {stderr.decode()}")
                if temp_output and os.path.exists(temp_output):
                    os.unlink(temp_output)
                return None
                
            # اگر فایل موقت ایجاد شده است، آن را جایگزین فایل اصلی کن
            if temp_output:
                os.rename(temp_output, final_output)
                
            return final_output
            
        except subprocess.TimeoutExpired:
            process.kill()
            print("⚠️ خطا: فرآیند فشرده‌سازی ویدیو با تایم‌اوت مواجه شد")
            if temp_output and os.path.exists(temp_output):
                os.unlink(temp_output)
            return None
            
    except Exception as e:
        print(f"⚠️ خطا در فشرده‌سازی ویدیو: {str(e)}")
        return None

# 📌 پاکسازی پوشه با حفظ فایل‌های جدید
def clear_folder(folder_path, max_files=3):
    """
    پاکسازی پوشه با حفظ فایل‌های جدید و حذف قدیمی‌ترین فایل‌ها
    
    Args:
        folder_path: مسیر پوشه
        max_files: تعداد فایل‌های حداکثر برای نگهداری
        
    Returns:
        تعداد فایل‌های حذف شده
    """
    files = []
    total_size = 0
    deleted_count = 0
    
    # جمع‌آوری اطلاعات فایل‌ها
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            # اندازه فایل به مگابایت
            file_size = os.path.getsize(file_path) / (1024 * 1024)
            files.append((file_path, os.path.getmtime(file_path), file_size))
            total_size += file_size
    
    # مرتب‌سازی بر اساس زمان تغییر (قدیمی‌ترین اول)
    files.sort(key=lambda x: x[1])
    
    # حذف فایل‌های قدیمی اگر تعداد از حد مجاز بیشتر است
    if len(files) > max_files:
        for file_path, _, file_size in files[:-max_files]:
            try:
                os.unlink(file_path)
                deleted_count += 1
                print(f"✅ فایل {file_path} با حجم {file_size:.2f} MB حذف شد")
            except Exception as e:
                print(f"⚠️ خطا در حذف {file_path}: {e}")
    
    # گزارش وضعیت فضای ذخیره‌سازی
    print(f"📊 وضعیت پوشه {folder_path}: {len(files)} فایل، {total_size:.2f} MB")
    return deleted_count

# 📂 مدیریت پاسخ‌های متنی با کش
_responses_cache = {}

def load_responses():
    try:
        if not _responses_cache:
            with open("responses.json", "r", encoding="utf-8") as file:
                _responses_cache.update(json.load(file))
        return _responses_cache
    except FileNotFoundError:
        _responses_cache.clear()
        return {}

def save_responses():
    with open("responses.json", "w", encoding="utf-8") as file:
        json.dump(responses, file, ensure_ascii=False, indent=2)

responses = load_responses()

# 📌 استخراج لینک مستقیم ویدیو با کش و بهینه‌سازی مصرف CPU
@lru_cache(maxsize=50)  # افزایش ظرفیت کش برای کاهش درخواست‌های مجدد
def get_direct_video_url(link):
    try:
        # تنظیمات yt-dlp با بهینه‌سازی بیشتر
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'noplaylist': True,
            'force_generic_extractor': False,
            'format': 'best[ext=mp4]/best',
            'socket_timeout': 30,
            # اضافه کردن راهکارهای کاهش مصرف CPU
            'nocheckcertificate': True,
            'extract_flat': 'in_playlist',
            'ignoreerrors': True,
            'no_warnings': True,
            'lazy_playlist': True,  # کاهش مصرف حافظه و CPU
            'geo_bypass': True,     # دور زدن محدودیت‌های جغرافیایی که باعث پردازش اضافی می‌شود
        }
        with YoutubeDL(ydl_opts) as ydl:
            # محدود کردن زمان پردازش
            import signal
            class TimeoutException(Exception): pass
            
            def timeout_handler(signum, frame):
                raise TimeoutException("عملیات استخراج اطلاعات بیش از حد طول کشید")
            
            # تنظیم تایم اوت برای جلوگیری از اشغال CPU
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(20)  # حداکثر 20 ثانیه
            
            try:
                info = ydl.extract_info(link, download=False)
                signal.alarm(0)  # غیرفعال کردن تایمر
                return info.get('url', None)
            except TimeoutException as e:
                notify_admin(f"⚠️ تایم اوت در استخراج لینک: {str(e)}")
                return None
            finally:
                signal.alarm(0)  # اطمینان از غیرفعال شدن تایمر
                
    except Exception as e:
        notify_admin(f"⚠️ خطا در دریافت لینک مستقیم ویدیو: {str(e)}")
        return None

# 📌 دانلود ویدیو از اینستاگرام با کش و بهینه‌سازی CPU
def download_instagram(link):
    # بررسی کش
    if link in RECENT_VIDEOS:
        if os.path.exists(RECENT_VIDEOS[link]):
            return RECENT_VIDEOS[link]
    
    try:
        # پاکسازی فایل‌های قدیمی، حفظ 5 فایل اخیر
        clear_folder(INSTAGRAM_FOLDER, 5)

        # تنظیمات بهینه‌سازی شده برای کاهش مصرف CPU
        ydl_opts = {
            'outtmpl': f'{INSTAGRAM_FOLDER}/%(id)s.%(ext)s',
            'format': 'mp4/best[height<=480]/best', # کیفیت پایین‌تر برای سرعت بیشتر و CPU کمتر
            'quiet': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'nocheckcertificate': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'geo_bypass': True,
            'extract_flat': 'in_playlist',
            'postprocessors': [{  # کاهش حجم ویدیو در صورت نیاز
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            # کاهش مصرف حافظه و CPU
            'noprogress': True,
            'prefer_insecure': True,
        }

        # استفاده از زمان‌بندی برای جلوگیری از اشغال بیش از حد CPU
        import signal
        
        class TimeoutException(Exception): pass
        
        def timeout_handler(signum, frame):
            raise TimeoutException("عملیات دانلود بیش از حد طول کشید")
        
        # تنظیم تایم اوت برای جلوگیری از اشغال CPU
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(120)  # حداکثر 2 دقیقه برای دانلود
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                signal.alarm(0)  # غیرفعال کردن تایمر
                
                video_path = f"{INSTAGRAM_FOLDER}/{info['id']}.mp4"
                
                # ذخیره در کش
                if os.path.exists(video_path):
                    RECENT_VIDEOS[link] = video_path
                    # محدود کردن اندازه کش
                    if len(RECENT_VIDEOS) > MAX_CACHE_SIZE:
                        RECENT_VIDEOS.pop(next(iter(RECENT_VIDEOS)))
                    return video_path
                return None
        except TimeoutException as e:
            notify_admin(f"⚠️ تایم اوت در دانلود ویدیو از اینستاگرام: {str(e)}")
            return None
        finally:
            signal.alarm(0)  # اطمینان از غیرفعال شدن تایمر

    except Exception as e:
        notify_admin(f"⚠️ خطا در دانلود ویدیو از اینستاگرام: {str(e)}")
        return None

# 📌 دانلود ویدیو از یوتیوب با کش و بهینه‌سازی مصرف CPU
def download_youtube(link):
    # بررسی کش
    if link in RECENT_VIDEOS:
        if os.path.exists(RECENT_VIDEOS[link]):
            return RECENT_VIDEOS[link]
    
    try:
        # پاکسازی فایل‌های قدیمی، حفظ 5 فایل اخیر
        clear_folder(VIDEO_FOLDER, 5)

        # تنظیمات بهینه‌سازی شده برای کاهش مصرف CPU
        ydl_opts = {
            'outtmpl': f'{VIDEO_FOLDER}/%(id)s.%(ext)s',
            'format': 'mp4/best[height<=480]/best', # کیفیت پایین‌تر برای سرعت بیشتر و CPU کمتر
            'quiet': True,
            'noplaylist': True,
            'socket_timeout': 30,
            'nocheckcertificate': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'geo_bypass': True,
            'extract_flat': 'in_playlist',
            'postprocessors': [{  # کاهش حجم ویدیو در صورت نیاز
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            # کاهش مصرف حافظه و CPU
            'noprogress': True,
            'prefer_insecure': True,
        }

        # استفاده از زمان‌بندی برای جلوگیری از اشغال بیش از حد CPU
        import signal
        
        class TimeoutException(Exception): pass
        
        def timeout_handler(signum, frame):
            raise TimeoutException("عملیات دانلود بیش از حد طول کشید")
        
        # تنظیم تایم اوت برای جلوگیری از اشغال CPU
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(150)  # حداکثر 2.5 دقیقه برای دانلود
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                signal.alarm(0)  # غیرفعال کردن تایمر
                
                video_path = f"{VIDEO_FOLDER}/{info['id']}.mp4"
                
                # ذخیره در کش
                if os.path.exists(video_path):
                    RECENT_VIDEOS[link] = video_path
                    # محدود کردن اندازه کش
                    if len(RECENT_VIDEOS) > MAX_CACHE_SIZE:
                        RECENT_VIDEOS.pop(next(iter(RECENT_VIDEOS)))
                    return video_path
                return None
        except TimeoutException as e:
            notify_admin(f"⚠️ تایم اوت در دانلود ویدیو از یوتیوب: {str(e)}")
            return None
        finally:
            signal.alarm(0)  # اطمینان از غیرفعال شدن تایمر

    except Exception as e:
        notify_admin(f"⚠️ خطا در دانلود ویدیو از یوتیوب: {str(e)}")
        return None

# 📢 ارسال پیام به ادمین در صورت وقوع خطا - با محدودیت ارسال
_last_error_time = 0
_error_count = 0

def notify_admin(message):
    global _last_error_time, _error_count
    current_time = time.time()
    
    # محدودیت تعداد خطاهای ارسالی
    if current_time - _last_error_time < 300:  # 5 دقیقه
        _error_count += 1
        if _error_count > 5:  # حداکثر 5 خطا در 5 دقیقه
            return
    else:
        _error_count = 1
        _last_error_time = current_time
    
    try:
        # کوتاه کردن پیام خطا
        message = message[:1000] + "..." if len(message) > 1000 else message
        bot.send_message(ADMIN_CHAT_ID, message)
    except Exception as e:
        print(f"⚠️ خطا در ارسال پیام به ادمین: {e}")

# 📤 ارسال ویدیو یا فایل به کاربر
def send_video_with_handling(chat_id, video_path):
    try:
        file_size = os.path.getsize(video_path) / (1024 * 1024)  # اندازه فایل به مگابایت

        with open(video_path, 'rb') as video:
            if file_size > 50:  # اگر فایل بیش از 50MB باشد، به‌صورت فایل ارسال کن
                bot.send_document(chat_id=chat_id, document=video, timeout=60)
            else:
                bot.send_video(chat_id=chat_id, video=video, timeout=60)
        return True

    except (ConnectionResetError, ConnectionError):
        bot.send_message(chat_id, "⚠️ اتصال به تلگرام قطع شد، لطفاً دوباره امتحان کنید.")
        return False
    except Exception as e:
        notify_admin(f"⚠️ خطا در ارسال ویدیو: {str(e)}")
        bot.send_message(chat_id, "⚠️ مشکلی در ارسال ویدیو رخ داد. لطفاً دوباره امتحان کنید.")
        return False

# دستور شروع - با طراحی بهتر و دکمه‌های کاربری بیشتر
@bot.message_handler(commands=['start'])
def handle_start(message):
    user = message.from_user
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    # دکمه‌های اصلی - ردیف اول
    markup.add(
        telebot.types.InlineKeyboardButton("📚 راهنما", callback_data="help"),
        telebot.types.InlineKeyboardButton("🎬 دانلود ویدیو", callback_data="video_info")
    )
    
    # دکمه‌های هشتگ و مدیریت کانال - ردیف دوم
    markup.add(
        telebot.types.InlineKeyboardButton("🔍 جستجوی هشتگ", callback_data="hashtag_info"),
        telebot.types.InlineKeyboardButton("🖊️ ذخیره پاسخ", callback_data="auto_reply_info")
    )
    
    # برای ادمین دکمه‌های مدیریتی نمایش داده شود
    if message.from_user.id == ADMIN_CHAT_ID:
        markup.add(
            telebot.types.InlineKeyboardButton("📊 وضعیت ربات", callback_data="bot_status"),
            telebot.types.InlineKeyboardButton("📋 لیست کانال‌ها", callback_data="show_channels")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("➕ افزودن کانال جدید", callback_data="add_channel_start")
        )
    
    # متن خوش‌آمدگویی با اطلاعات جامع‌تر
    welcome_text = (
        f"🌟 سلام <b>{user.first_name}</b>! 👋\n\n"
        f"به ربات چندکاره خوش آمدید!\n\n"
        f"<b>✨ قابلیت‌های اصلی:</b>\n"
        f"• <b>دانلود ویدیو:</b> لینک اینستاگرام یا یوتیوب را ارسال کنید\n"
        f"• <b>جستجوی هشتگ:</b> #هشتگ_موردنظر را ارسال کنید\n"
        f"• <b>پاسخ خودکار:</b> با فرمت «سوال، جواب» ذخیره کنید\n\n"
        f"<b>🔄 به‌روزرسانی‌های جدید:</b>\n"
        f"• امکان استفاده از کانال‌های خصوصی\n"
        f"• مدیریت کانال‌ها با دکمه‌های شیشه‌ای\n"
        f"• بهینه‌سازی مصرف CPU و سرعت دانلود\n\n"
        f"از دکمه‌های زیر برای شروع استفاده کنید:"
    )
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode="HTML",
        reply_markup=markup
    )

# دستور راهنما - با فرمت بهتر
@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = (
        "📘 <b>راهنمای ربات چندکاره</b>\n\n"
        "<b>🔹 ویژگی‌های اصلی:</b>\n"
        "• دانلود ویدیو از یوتیوب و اینستاگرام\n"
        "• جستجوی پیام‌ها با هشتگ\n"
        "• ذخیره پاسخ‌های خودکار\n\n"
        "<b>🔸 دستورات:</b>\n"
        "• /start - شروع ربات\n"
        "• /help - نمایش این راهنما\n"
        "• /add_channel - افزودن کانال (فقط ادمین)\n"
        "• /remove_channel - حذف کانال (فقط ادمین)\n"
        "• /channels - نمایش کانال‌های ثبت شده\n\n"
        "<b>🔸 دانلود ویدیو:</b>\n"
        "فقط کافیست لینک ویدیو را ارسال کنید\n\n"
        "<b>🔸 جستجوی هشتگ:</b>\n"
        "کافیست #نام_هشتگ را ارسال کنید\n\n"
        "<b>🔸 پاسخ خودکار:</b>\n"
        "پیام با فرمت 'سوال، جواب' ارسال کنید"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="HTML")

# حالت‌های مختلف گفتگو
ADD_CHANNEL_WAITING_FOR_LINK = "waiting_for_channel_link"
ADD_RESPONSE_WAITING_FOR_QA = "waiting_for_qa"
STATES = {}  # نگهداری وضعیت کاربران در فرآیندهای مختلف

# پردازش کلیک روی دکمه‌ها - با پاسخ سریع‌تر
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    # پاسخ سریع به کالبک برای جلوگیری از خطای ساعت شنی
    bot.answer_callback_query(call.id)
    
    if call.data == "help":
        handle_help(call.message)
    elif call.data == "video_info":
        bot.send_message(
            call.message.chat.id,
            "🎥 <b>لطفاً لینک ویدیوی مورد نظر را ارسال کنید</b>\n\n"
            "• یوتیوب: https://youtube.com/...\n"
            "• اینستاگرام: https://instagram.com/...",
            parse_mode="HTML"
        )
    elif call.data == "hashtag_info":
        bot.send_message(
            call.message.chat.id,
            "🔍 <b>جستجوی هشتگ</b>\n\n"
            "برای جستجوی پیام‌ها با هشتگ کافیست هشتگ مورد نظر را ارسال کنید.\n"
            "مثال: #آناتومی\n\n"
            "<b>نکته:</b> برای استفاده از این قابلیت، ابتدا باید ربات در کانال مورد نظر عضو شود "
            "و به عنوان ادمین تنظیم گردد.",
            parse_mode="HTML"
        )
    elif call.data == "auto_reply_info":
        # راهنمای استفاده از پاسخ خودکار با دکمه اضافه کردن
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("➕ افزودن پاسخ جدید", callback_data="add_response_start"))
        markup.add(telebot.types.InlineKeyboardButton("📋 مشاهده پاسخ‌ها", callback_data="list_responses"))
        
        bot.send_message(
            call.message.chat.id,
            "🖊️ <b>پاسخ‌های خودکار</b>\n\n"
            "با این قابلیت می‌توانید پاسخ‌های خودکار تعریف کنید.\n"
            "هنگامی که کاربری سوالی مشابه سوالات تعریف شده بپرسد، ربات به صورت خودکار پاسخ می‌دهد.\n\n"
            "<b>روش افزودن پاسخ خودکار:</b>\n"
            "1. روی دکمه «افزودن پاسخ جدید» کلیک کنید\n"
            "2. پیامی با فرمت «سوال، جواب» ارسال کنید\n\n"
            "<b>مثال:</b> سلام، سلام! چطور می‌توانم کمک کنم؟",
            parse_mode="HTML",
            reply_markup=markup
        )
    elif call.data == "add_response_start":
        # شروع فرآیند افزودن پاسخ خودکار
        bot.send_message(
            call.message.chat.id,
            "🖊️ <b>افزودن پاسخ خودکار</b>\n\n"
            "لطفاً پیامی با فرمت زیر ارسال کنید:\n"
            "<code>سوال، جواب</code>\n\n"
            "<b>نکته:</b> از علامت ویرگول (،) برای جدا کردن سوال و جواب استفاده کنید.",
            parse_mode="HTML"
        )
        
        # ذخیره وضعیت کاربر
        STATES[call.from_user.id] = ADD_RESPONSE_WAITING_FOR_QA
    elif call.data == "list_responses":
        # نمایش لیست پاسخ‌های خودکار
        if not responses:
            bot.send_message(call.message.chat.id, "⚠️ هیچ پاسخ خودکاری تعریف نشده است!")
            return
            
        # ایجاد متن پاسخ‌ها با محدودیت طول
        responses_text = "📋 <b>پاسخ‌های خودکار تعریف شده:</b>\n\n"
        
        # ایجاد صفحه‌بندی برای پاسخ‌ها
        items_per_page = 5
        total_items = len(responses)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        
        # برای ساده‌سازی فقط صفحه اول را نمایش می‌دهیم
        page = 1
        start_idx = (page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, total_items)
        
        # ایجاد لیست پاسخ‌های خودکار
        items = list(responses.items())[start_idx:end_idx]
        for i, (question, answer) in enumerate(items, start=start_idx+1):
            responses_text += f"{i}. <b>س:</b> {question}\n<b>ج:</b> {answer}\n\n"
        
        # اضافه کردن اطلاعات صفحه‌بندی
        if total_pages > 1:
            responses_text += f"<i>صفحه {page} از {total_pages}</i>"
        
        # ایجاد دکمه‌های مدیریت پاسخ‌ها
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("➕ افزودن پاسخ جدید", callback_data="add_response_start"))
        
        # دکمه‌های صفحه‌بندی
        if total_pages > 1:
            pagination_buttons = []
            if page > 1:
                pagination_buttons.append(telebot.types.InlineKeyboardButton("◀️ قبلی", callback_data=f"responses_page_{page-1}"))
            if page < total_pages:
                pagination_buttons.append(telebot.types.InlineKeyboardButton("بعدی ▶️", callback_data=f"responses_page_{page+1}"))
            markup.add(*pagination_buttons)
        
        # ارسال پیام با دکمه‌ها
        bot.send_message(
            call.message.chat.id,
            responses_text,
            parse_mode="HTML",
            reply_markup=markup
        )
    elif call.data.startswith("responses_page_"):
        # پردازش صفحه‌بندی پاسخ‌ها
        try:
            page = int(call.data.split("_")[-1])
            
            # نمایش صفحه جدید
            if not responses:
                bot.send_message(call.message.chat.id, "⚠️ هیچ پاسخ خودکاری تعریف نشده است!")
                return
                
            # محاسبات صفحه‌بندی
            items_per_page = 5
            total_items = len(responses)
            total_pages = (total_items + items_per_page - 1) // items_per_page
            
            # محدود کردن شماره صفحه
            page = max(1, min(page, total_pages))
            
            start_idx = (page - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, total_items)
            
            # ایجاد متن پاسخ‌ها
            responses_text = "📋 <b>پاسخ‌های خودکار تعریف شده:</b>\n\n"
            
            # ایجاد لیست پاسخ‌های خودکار
            items = list(responses.items())[start_idx:end_idx]
            for i, (question, answer) in enumerate(items, start=start_idx+1):
                responses_text += f"{i}. <b>س:</b> {question}\n<b>ج:</b> {answer}\n\n"
            
            # اضافه کردن اطلاعات صفحه‌بندی
            if total_pages > 1:
                responses_text += f"<i>صفحه {page} از {total_pages}</i>"
            
            # ایجاد دکمه‌های مدیریت پاسخ‌ها
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("➕ افزودن پاسخ جدید", callback_data="add_response_start"))
            
            # دکمه‌های صفحه‌بندی
            if total_pages > 1:
                pagination_buttons = []
                if page > 1:
                    pagination_buttons.append(telebot.types.InlineKeyboardButton("◀️ قبلی", callback_data=f"responses_page_{page-1}"))
                if page < total_pages:
                    pagination_buttons.append(telebot.types.InlineKeyboardButton("بعدی ▶️", callback_data=f"responses_page_{page+1}"))
                markup.add(*pagination_buttons)
            
            # ویرایش پیام قبلی
            bot.edit_message_text(
                responses_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception as e:
            print(f"⚠️ خطا در صفحه‌بندی پاسخ‌ها: {str(e)}")
    elif call.data == "bot_status":
        # نمایش آمار و وضعیت ربات
        if call.from_user.id != ADMIN_CHAT_ID:
            bot.send_message(call.message.chat.id, "⛔ شما دسترسی به این قابلیت را ندارید!")
            return
            
        # جمع‌آوری اطلاعات
        import psutil
        import shutil
        
        # اطلاعات سیستم
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = shutil.disk_usage("/")
        
        # اطلاعات ربات
        channels_count = len(hashtag_manager.registered_channels)
        hashtags_count = len(hashtag_manager.hashtag_cache)
        responses_count = len(responses)
        
        # تبدیل مقادیر به واحدهای مناسب
        def convert_size(size_bytes):
            if size_bytes >= 1024 * 1024 * 1024:
                return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
            elif size_bytes >= 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.2f} MB"
            elif size_bytes >= 1024:
                return f"{size_bytes / 1024:.2f} KB"
            else:
                return f"{size_bytes} Bytes"
        
        # ایجاد متن اطلاعات
        status_text = (
            "📊 <b>وضعیت فعلی ربات:</b>\n\n"
            f"<b>🤖 آمار ربات:</b>\n"
            f"• کانال‌های مانیتورینگ: {channels_count}\n"
            f"• هشتگ‌های ذخیره شده: {hashtags_count}\n"
            f"• پاسخ‌های خودکار: {responses_count}\n\n"
            f"<b>💻 اطلاعات سیستم:</b>\n"
            f"• مصرف CPU: {cpu_percent}%\n"
            f"• حافظه: {convert_size(memory.used)} از {convert_size(memory.total)} ({memory.percent}%)\n"
            f"• فضای ذخیره‌سازی: {convert_size(disk.used)} از {convert_size(disk.total)} ({disk.used / disk.total * 100:.1f}%)\n\n"
            f"<b>⚙️ سیستم‌های فعال:</b>\n"
            f"• سیستم پینگ خودکار: هر 5 دقیقه\n"
            f"• حداکثر ویدیوهای ذخیره: {MAX_VIDEOS_PER_FOLDER}\n"
            f"• قابلیت کانال خصوصی: فعال"
        )
        
        # ایجاد دکمه‌های مدیریتی
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton("🧹 پاکسازی ویدیوها", callback_data="clear_videos"),
            telebot.types.InlineKeyboardButton("🔍 نمایش کانال‌ها", callback_data="show_channels")
        )
        
        bot.send_message(
            call.message.chat.id,
            status_text,
            parse_mode="HTML",
            reply_markup=markup
        )
    elif call.data == "clear_videos":
        # پاکسازی ویدیوهای ذخیره شده
        if call.from_user.id != ADMIN_CHAT_ID:
            bot.send_message(call.message.chat.id, "⛔ شما دسترسی به این قابلیت را ندارید!")
            return
            
        try:
            # پاکسازی پوشه‌های ویدیو
            cleared_youtube = clear_folder("videos", 0)
            cleared_instagram = clear_folder("instagram_videos", 0)
            
            bot.send_message(
                call.message.chat.id,
                f"✅ پاکسازی ویدیوها با موفقیت انجام شد!\n\n"
                f"• ویدیوهای یوتیوب پاک شده: {cleared_youtube}\n"
                f"• ویدیوهای اینستاگرام پاک شده: {cleared_instagram}",
                parse_mode="HTML"
            )
        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"⚠️ خطا در پاکسازی ویدیوها: {str(e)}",
                parse_mode="HTML"
            )
    elif call.data == "add_channel_start":
        # بررسی دسترسی ادمین
        if call.from_user.id != ADMIN_CHAT_ID:
            bot.send_message(call.message.chat.id, "⛔ شما دسترسی به این قابلیت را ندارید!")
            return
            
        # شروع فرآیند افزودن کانال
        bot.send_message(
            call.message.chat.id,
            "🔗 <b>افزودن کانال به مانیتورینگ</b>\n\n"
            "لطفاً یکی از موارد زیر را ارسال کنید:\n\n"
            "• آیدی کانال (مثال: @channel_id)\n"
            "• لینک دعوت کانال (مثال: https://t.me/+abcdef123456)\n"
            "• شناسه عددی کانال خصوصی (مثال: -1001234567890)\n\n"
            "<b>نکته:</b> برای کانال‌های خصوصی یا عمومی محدودیتی وجود ندارد.",
            parse_mode="HTML"
        )
        
        # ذخیره وضعیت کاربر برای دریافت لینک کانال
        STATES[call.from_user.id] = ADD_CHANNEL_WAITING_FOR_LINK
    elif call.data == "show_channels":
        # نمایش کانال‌های ثبت شده با دکمه
        channels = list(hashtag_manager.registered_channels)
        
        if not channels:
            bot.send_message(call.message.chat.id, "📢 هیچ کانالی در لیست مانیتورینگ ثبت نشده است.")
        else:
            channels_text = "📢 <b>کانال‌های ثبت شده:</b>\n\n"
            for i, channel in enumerate(channels, 1):
                channels_text += f"{i}. <code>{channel}</code>\n"
            
            # ایجاد دکمه‌های حذف کانال
            markup = telebot.types.InlineKeyboardMarkup(row_width=1)
            for channel in channels:
                btn_text = f"❌ حذف {channel}"
                markup.add(telebot.types.InlineKeyboardButton(
                    btn_text, 
                    callback_data=f"remove_channel_{channel}"
                ))
            
            markup.add(telebot.types.InlineKeyboardButton("➕ افزودن کانال جدید", callback_data="add_channel_start"))
            
            bot.send_message(
                call.message.chat.id, 
                channels_text, 
                parse_mode="HTML",
                reply_markup=markup
            )
    elif call.data.startswith("remove_channel_"):
        # حذف کانال با دکمه
        if call.from_user.id != ADMIN_CHAT_ID:
            bot.send_message(call.message.chat.id, "⛔ شما دسترسی به این قابلیت را ندارید!")
            return
            
        channel_id = call.data.replace("remove_channel_", "")
        
        if hashtag_manager.remove_channel(channel_id):
            bot.send_message(
                call.message.chat.id, 
                f"✅ کانال <code>{channel_id}</code> با موفقیت از لیست مانیتورینگ حذف شد.",
                parse_mode="HTML"
            )
        else:
            bot.send_message(
                call.message.chat.id, 
                f"⚠️ کانال <code>{channel_id}</code> در لیست مانیتورینگ یافت نشد!",
                parse_mode="HTML"
            )

# دستور نمایش کانال‌های ثبت شده
@bot.message_handler(commands=['channels'])
def handle_channels_command(message):
    """نمایش لیست کانال‌های ثبت شده"""
    # بررسی دسترسی ادمین
    if message.from_user.id != ADMIN_CHAT_ID:
        bot.reply_to(message, "⛔ شما دسترسی به این دستور را ندارید!")
        return
    
    # دریافت لیست کانال‌ها
    channels = list(hashtag_manager.registered_channels)
    
    if not channels:
        bot.reply_to(message, "📢 هیچ کانالی در لیست مانیتورینگ ثبت نشده است.")
    else:
        channels_text = "📢 <b>کانال‌های ثبت شده:</b>\n\n"
        for i, channel in enumerate(channels, 1):
            channels_text += f"{i}. <code>{channel}</code>\n"
        
        channels_text += "\n🔸 برای افزودن کانال: /add_channel @username\n"
        channels_text += "🔸 برای حذف کانال: /remove_channel @username"
        
        bot.reply_to(message, channels_text, parse_mode="HTML")

# دستور افزودن کانال
@bot.message_handler(commands=['add_channel'])
def handle_add_channel(message):
    """دستور افزودن کانال به لیست مانیتورینگ"""
    register_channel_command(message)

# دستور حذف کانال
@bot.message_handler(commands=['remove_channel'])
def handle_remove_channel(message):
    """دستور حذف کانال از لیست مانیتورینگ"""
    unregister_channel_command(message)

# 🔄 پردازش ویدیو به صورت ناهمزمان
def process_video_link(message, text, processing_msg):
    try:
        # ابتدا لینک مستقیم (سریع‌ترین)
        direct_url = get_direct_video_url(text)
        if direct_url:
            bot.edit_message_text("✅ ویدیو یافت شد! در حال ارسال...", message.chat.id, processing_msg.message_id)
            try:
                bot.send_video(chat_id=message.chat.id, video=direct_url, timeout=60)
                bot.delete_message(message.chat.id, processing_msg.message_id)
                return
            except Exception:
                bot.edit_message_text("⏳ روش مستقیم موفق نبود. در حال دانلود ویدیو...", message.chat.id, processing_msg.message_id)
        
        # دانلود و ارسال ویدیو
        video_path = download_instagram(text) if "instagram.com" in text else download_youtube(text)
        
        if video_path and os.path.exists(video_path):
            bot.edit_message_text("✅ دانلود کامل شد، در حال ارسال...", message.chat.id, processing_msg.message_id)
            if send_video_with_handling(message.chat.id, video_path):
                bot.delete_message(message.chat.id, processing_msg.message_id)
            else:
                bot.edit_message_text("⚠️ خطا در ارسال ویدیو. لطفاً دوباره تلاش کنید.", message.chat.id, processing_msg.message_id)
        else:
            bot.edit_message_text("⚠️ دانلود ویدیو ناموفق بود. لطفاً لینک را بررسی کنید.", message.chat.id, processing_msg.message_id)
    
    except Exception as e:
        notify_admin(f"⚠️ خطا در پردازش ویدیو: {str(e)}")
        try:
            bot.edit_message_text("⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.", message.chat.id, processing_msg.message_id)
        except:
            pass

# 🔍 ذخیره‌سازی هشتگ‌ها و پیام‌های مرتبط
class HashtagManager:
    def __init__(self):
        self.hashtag_cache = {}  # {hashtag: [message_id1, message_id2, ...]}
        self.message_cache = {}  # {message_id: message_object}
        self.registered_channels = set()  # کانال‌هایی که ربات در آن‌ها مانیتور می‌کند
        self.load_data()
    
    def load_data(self):
        """بارگذاری داده‌های ذخیره شده هشتگ‌ها"""
        try:
            if os.path.exists('hashtags.json'):
                with open('hashtags.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.hashtag_cache = data.get('hashtags', {})
                    self.registered_channels = set(data.get('channels', []))
        except Exception as e:
            print(f"⚠️ خطا در بارگذاری داده‌های هشتگ: {e}")
            # ایجاد فایل خالی در صورت عدم وجود
            self.save_data()
    
    def save_data(self):
        """ذخیره داده‌های هشتگ‌ها"""
        try:
            data = {
                'hashtags': self.hashtag_cache,
                'channels': list(self.registered_channels)
            }
            with open('hashtags.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ خطا در ذخیره داده‌های هشتگ: {e}")
    
    def add_channel(self, channel_id):
        """افزودن کانال به لیست مانیتورینگ"""
        self.registered_channels.add(str(channel_id))
        self.save_data()
        return True
    
    def remove_channel(self, channel_id):
        """حذف کانال از لیست مانیتورینگ"""
        if str(channel_id) in self.registered_channels:
            self.registered_channels.remove(str(channel_id))
            self.save_data()
            return True
        return False
    
    def extract_hashtags(self, text):
        """استخراج هشتگ‌ها از متن پیام"""
        if not text:
            return []
        # جستجوی الگوی #متن
        hashtags = []
        words = text.split()
        for word in words:
            if word.startswith('#'):
                # حذف # و افزودن به لیست
                hashtag = word[1:].lower()
                if hashtag and len(hashtag) > 1:  # هشتگ‌های با طول حداقل 2 کاراکتر
                    hashtags.append(hashtag)
        return hashtags
    
    def register_message(self, message):
        """ثبت یک پیام با هشتگ‌های آن"""
        if not message or not message.text:
            return False
            
        # بررسی این که پیام از کانال‌های ثبت شده است
        chat_id = str(message.chat.id)
        if chat_id not in self.registered_channels:
            return False
            
        # استخراج هشتگ‌ها
        hashtags = self.extract_hashtags(message.text)
        if not hashtags:
            return False
            
        # ذخیره پیام در کش
        message_id = f"{chat_id}_{message.message_id}"
        self.message_cache[message_id] = {
            'chat_id': chat_id,
            'message_id': message.message_id,
            'text': message.text,
            'date': message.date,
            'has_media': bool(message.photo or message.video or message.document or message.audio)
        }
        
        # ثبت پیام برای هر هشتگ
        for hashtag in hashtags:
            if hashtag not in self.hashtag_cache:
                self.hashtag_cache[hashtag] = []
            
            if message_id not in self.hashtag_cache[hashtag]:
                self.hashtag_cache[hashtag].append(message_id)
                
        # ذخیره به فایل هر 10 پیام
        if len(self.message_cache) % 10 == 0:
            self.save_data()
            
        return True
    
    def search_hashtag(self, hashtag, limit=5):
        """جستجوی پیام‌های مرتبط با یک هشتگ"""
        hashtag = hashtag.lower().replace('#', '')
        if not hashtag or hashtag not in self.hashtag_cache:
            return []
            
        # پیدا کردن آیدی پیام‌ها
        message_ids = self.hashtag_cache[hashtag][-limit:]  # آخرین X پیام
        
        # بازگشت اطلاعات پیام‌ها
        result = []
        for msg_id in message_ids:
            # اگر در کش موجود باشد، آن را برگردان
            if msg_id in self.message_cache:
                result.append(self.message_cache[msg_id])
        
        # مرتب‌سازی بر اساس تاریخ (جدیدترین اول)
        result.sort(key=lambda x: x['date'], reverse=True)
        return result

# ایجاد نمونه از مدیریت هشتگ
hashtag_manager = HashtagManager()

# 🔍 پردازش جستجوی هشتگ
def process_hashtag_search(message, hashtag):
    """جستجو و ارسال پیام‌های مرتبط با هشتگ"""
    search_results = hashtag_manager.search_hashtag(hashtag)
    
    if not search_results:
        bot.reply_to(message, f"⚠️ هیچ پیامی با هشتگ #{hashtag} یافت نشد!")
        return
        
    # ارسال تعداد نتایج
    bot.reply_to(message, f"🔍 {len(search_results)} پیام با هشتگ #{hashtag} یافت شد. در حال ارسال...")
    
    # ارسال نتایج جستجو
    for result in search_results:
        try:
            # ارسال پیام با فروارد
            bot.forward_message(
                chat_id=message.chat.id,
                from_chat_id=result['chat_id'],
                message_id=result['message_id']
            )
            time.sleep(0.5)  # کمی تاخیر برای جلوگیری از محدودیت تلگرام
        except Exception as e:
            error_msg = f"⚠️ خطا در ارسال پیام با هشتگ #{hashtag}: {str(e)}"
            bot.send_message(message.chat.id, error_msg)
            notify_admin(error_msg)
            
    # پیام پایان جستجو
    bot.send_message(message.chat.id, f"✅ جستجوی هشتگ #{hashtag} به پایان رسید.")

# 🔧 دستور مدیریت کانال‌ها
def register_channel_command(message):
    """ثبت یک کانال برای مانیتورینگ هشتگ‌ها"""
    # بررسی دسترسی ادمین
    if message.from_user.id != ADMIN_CHAT_ID:
        bot.reply_to(message, "⛔ شما دسترسی به این دستور را ندارید!")
        return
        
    # بررسی فرمت دستور
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "⚠️ فرمت صحیح: /add_channel @channel_username یا آیدی عددی کانال")
        return
        
    channel_id = command_parts[1]
    # حذف @ از ابتدای نام کاربری کانال
    if channel_id.startswith('@'):
        channel_id = channel_id[1:]
        
    # ثبت کانال
    if hashtag_manager.add_channel(channel_id):
        bot.reply_to(message, f"✅ کانال {channel_id} با موفقیت به لیست مانیتورینگ اضافه شد!")
    else:
        bot.reply_to(message, f"⚠️ خطا در ثبت کانال {channel_id}")

# 📂 دستور حذف کانال
def unregister_channel_command(message):
    """حذف یک کانال از مانیتورینگ هشتگ‌ها"""
    # بررسی دسترسی ادمین
    if message.from_user.id != ADMIN_CHAT_ID:
        bot.reply_to(message, "⛔ شما دسترسی به این دستور را ندارید!")
        return
        
    # بررسی فرمت دستور
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "⚠️ فرمت صحیح: /remove_channel @channel_username یا آیدی عددی کانال")
        return
        
    channel_id = command_parts[1]
    # حذف @ از ابتدای نام کاربری کانال
    if channel_id.startswith('@'):
        channel_id = channel_id[1:]
        
    # حذف کانال
    if hashtag_manager.remove_channel(channel_id):
        bot.reply_to(message, f"✅ کانال {channel_id} با موفقیت از لیست مانیتورینگ حذف شد!")
    else:
        bot.reply_to(message, f"⚠️ کانال {channel_id} در لیست مانیتورینگ وجود ندارد!")

# تشخیص و استخراج آیدی کانال از فرمت‌های مختلف
def extract_channel_id(text):
    """از متن ورودی، آیدی کانال را استخراج می‌کند"""
    import re
    
    # حذف فاصله‌های اضافی
    text = text.strip()
    
    # الگو برای آیدی منفی (کانال خصوصی)
    negative_id_pattern = r'-\d+'
    if re.match(negative_id_pattern, text):
        return text
    
    # الگو برای لینک دعوت تلگرام
    invite_link_pattern = r'(?:https?://)?(?:t(?:elegram)?\.(?:me|dog))/(?:\+|joinchat/)([\w-]+)'
    invite_match = re.search(invite_link_pattern, text)
    if invite_match:
        # برای کانال‌های خصوصی، از کد دعوت استفاده می‌کنیم
        return f"invite_{invite_match.group(1)}"
    
    # الگو برای لینک کانال عمومی
    public_link_pattern = r'(?:https?://)?(?:t(?:elegram)?\.(?:me|dog))/([a-zA-Z][\w_]{3,30}[a-zA-Z\d])'
    public_match = re.search(public_link_pattern, text)
    if public_match:
        return public_match.group(1)
    
    # الگو برای نام کاربری کانال با یا بدون @
    username_pattern = r'@?([a-zA-Z][\w_]{3,30}[a-zA-Z\d])'
    username_match = re.match(username_pattern, text)
    if username_match:
        return username_match.group(1)
    
    # الگوی دیگری پیدا نشد
    return None

# 📩 مدیریت پیام‌های دریافتی - با پردازش بهتر
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        # بررسی وضعیت کاربر - اگر منتظر دریافت آدرس کانال است
        if message.from_user.id in STATES and STATES[message.from_user.id] == ADD_CHANNEL_WAITING_FOR_LINK:
            # حذف وضعیت کاربر
            del STATES[message.from_user.id]
            
            # بررسی دسترسی ادمین
            if message.from_user.id != ADMIN_CHAT_ID:
                bot.reply_to(message, "⛔ شما دسترسی به این دستور را ندارید!")
                return
                
            # استخراج آیدی کانال
            channel_id = extract_channel_id(message.text)
            
            if not channel_id:
                bot.reply_to(message, "⚠️ فرمت آدرس کانال یا لینک دعوت نامعتبر است!\nلطفاً مجدداً تلاش کنید یا از دستور /add_channel استفاده نمایید.")
                return
                
            # اضافه کردن کانال به لیست مانیتورینگ
            hashtag_manager.add_channel(channel_id)
            
            # ایجاد دکمه برای نمایش کانال‌های فعلی
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("📋 مشاهده لیست کانال‌ها", callback_data="show_channels"))
            
            bot.reply_to(
                message, 
                f"✅ کانال <code>{channel_id}</code> با موفقیت به لیست مانیتورینگ اضافه شد!",
                parse_mode="HTML",
                reply_markup=markup
            )
            return
        
        if not message.text:
            # ثبت پیام برای هشتگ‌ها اگر از کانال مورد نظر باشد
            hashtag_manager.register_message(message)
            return
            
        text = message.text.strip()
        
        # ثبت پیام برای هشتگ‌ها اگر از کانال مورد نظر باشد
        hashtag_manager.register_message(message)

        # پردازش لینک‌های ویدیو
        if any(domain in text for domain in ["instagram.com", "youtube.com", "youtu.be"]):
            processing_msg = bot.send_message(message.chat.id, "⏳ در حال پردازش، لطفاً صبر کنید...")
            
            # اجرای ناهمزمان پردازش ویدیو
            thread_pool.submit(process_video_link, message, text, processing_msg)
            return
        
        # پردازش جستجوی هشتگ - اگر با # شروع شود
        elif text.startswith('#') and len(text) > 1:
            hashtag = text[1:].strip()
            if hashtag:
                thread_pool.submit(process_hashtag_search, message, hashtag)
                return
        
        # پردازش هشتگ‌های درون متن (چندین هشتگ)
        elif '#' in text and not text.startswith('/'):
            hashtags = hashtag_manager.extract_hashtags(text)
            if hashtags:
                # فقط هشتگ اول را جستجو کن
                bot.reply_to(message, f"🔍 در حال جستجوی هشتگ #{hashtags[0]}...")
                thread_pool.submit(process_hashtag_search, message, hashtags[0])
                return

        # پردازش پاسخ‌های خودکار
        elif "،" in text:
            try:
                question, answer = map(str.strip, text.split("،", 1))
                if len(question) < 2 or len(answer) < 2:
                    bot.reply_to(message, "⚠️ سوال و جواب باید حداقل 2 کاراکتر باشند.")
                    return
                
                responses[question.lower()] = answer
                save_responses()
                bot.reply_to(message, f"✅ سوال «{question}» با پاسخ «{answer}» ذخیره شد!")
            except ValueError:
                bot.reply_to(message, "⚠️ لطفاً فرمت درست 'سوال، جواب' را رعایت کنید.")

        # جستجوی پاسخ در دیتابیس
        else:
            key = text.lower()
            if key in responses:
                bot.reply_to(message, responses[key])
            else:
                similar_keys = [k for k in responses.keys() if key in k or k in key]
                if similar_keys:
                    suggestions = "\n".join([f"• {k}" for k in similar_keys[:3]])
                    bot.reply_to(message, 
                        f"🔍 سوال دقیقاً مطابق موارد ذخیره شده نیست.\n\n"
                        f"شاید منظورتان یکی از این‌ها بود:\n{suggestions}"
                    )
                else:
                    # بررسی اینکه آیا ممکن است کاربر هشتگ را بدون # ارسال کرده باشد
                    if key and len(key) > 1 and " " not in key and key in hashtag_manager.hashtag_cache:
                        bot.reply_to(message, f"🔍 به نظر می‌رسد دنبال هشتگ #{key} هستید. در حال جستجو...")
                        thread_pool.submit(process_hashtag_search, message, key)
                    else:
                        bot.reply_to(message, "🤖 این سوال در دیتابیس من نیست. می‌توانید با فرمت 'سوال، جواب' آن را اضافه کنید.")

    except Exception as e:
        notify_admin(f"⚠️ خطای کلی در پردازش پیام: {str(e)}")
        try:
            bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.")
        except:
            pass
            
# مدیریت پیام‌های گروهی یا کانال
@bot.channel_post_handler(func=lambda message: True)
def handle_channel_post(message):
    """پردازش پیام‌های کانال برای استخراج هشتگ‌ها"""
    try:
        # ثبت پیام برای استخراج هشتگ‌ها
        if hashtag_manager.register_message(message):
            print(f"✅ پیام کانال با هشتگ ثبت شد: {message.chat.id}")
    except Exception as e:
        notify_admin(f"⚠️ خطا در پردازش پیام کانال: {str(e)}")
        
# برای پیام‌های ویرایش شده نیز هشتگ‌ها را استخراج کن
@bot.edited_channel_post_handler(func=lambda message: True)
def handle_edited_channel_post(message):
    """پردازش پیام‌های ویرایش شده کانال"""
    try:
        # ثبت پیام برای استخراج هشتگ‌ها
        if hashtag_manager.register_message(message):
            print(f"✅ پیام ویرایش شده کانال با هشتگ ثبت شد: {message.chat.id}")
    except Exception as e:
        notify_admin(f"⚠️ خطا در پردازش پیام ویرایش شده کانال: {str(e)}")

# 🚀 اضافه کردن ربات به کانال‌های خصوصی
def join_private_channel(invite_link):
    """تلاش برای ورود به کانال خصوصی با لینک دعوت"""
    import requests
    
    try:
        # استخراج کد دعوت از لینک
        if invite_link.startswith("invite_"):
            invite_hash = invite_link[7:]  # حذف "invite_" از ابتدای رشته
        else:
            # الگو برای استخراج کد دعوت از لینک
            import re
            match = re.search(r'/\+([a-zA-Z0-9_-]+)', invite_link)
            if match:
                invite_hash = match.group(1)
            else:
                return None, False
            
        # API تلگرام برای پیوستن به چت
        join_url = f"https://api.telegram.org/bot{TOKEN}/joinChat"
        
        # تبدیل کد دعوت به فرمت مناسب
        invite_link = f"https://t.me/+{invite_hash}"
        
        # ارسال درخواست به API تلگرام
        response = requests.post(join_url, json={
            "invite_link": invite_link
        }, timeout=30)
        
        data = response.json()
        
        if data.get("ok", False):
            # موفقیت‌آمیز - اطلاعات چت را برگردان
            chat_id = data.get("result", {}).get("id")
            return chat_id, True
        else:
            # خطا - نمایش پیام خطا
            error = data.get("description", "خطای نامشخص")
            print(f"⚠️ خطا در پیوستن به کانال خصوصی: {error}")
            return None, False
            
    except Exception as e:
        print(f"⚠️ خطا در پیوستن به کانال خصوصی: {str(e)}")
        return None, False

# 🔍 تشخیص و ورود به کانال‌ها در زمان اضافه شدن
def register_channel_with_auto_join(user_id, channel_id):
    """با تشخیص نوع کانال (خصوصی یا عمومی) سعی در ورود می‌کند"""
    if not channel_id:
        return False, "آدرس کانال یا لینک دعوت نامعتبر است!"
        
    # بررسی اگر کانال خصوصی با لینک دعوت است
    if "t.me/+" in channel_id or "t.me/joinchat/" in channel_id or channel_id.startswith("invite_"):
        # تلاش برای ورود به کانال
        chat_id, success = join_private_channel(channel_id)
        
        if success and chat_id:
            # اضافه کردن با آیدی عددی
            hashtag_manager.add_channel(str(chat_id))
            return True, f"✅ با موفقیت به کانال خصوصی پیوست و آن را به لیست مانیتورینگ اضافه کرد."
        else:
            return False, "⚠️ خطا در پیوستن به کانال خصوصی. ممکن است دسترسی‌های لازم را نداشته باشید یا لینک منقضی شده باشد."
    
    # بررسی اگر آیدی عددی منفی است (کانال خصوصی)
    elif channel_id.startswith("-"):
        # مستقیماً به لیست اضافه کن
        hashtag_manager.add_channel(channel_id)
        return True, f"✅ کانال خصوصی با آیدی <code>{channel_id}</code> با موفقیت به لیست مانیتورینگ اضافه شد!"
        
    # در غیر این صورت، کانال عمومی است
    else:
        # حذف @ از ابتدای نام کاربری
        if channel_id.startswith('@'):
            channel_id = channel_id[1:]
            
        # اضافه کردن کانال عمومی
        hashtag_manager.add_channel(channel_id)
        return True, f"✅ کانال عمومی <code>{channel_id}</code> با موفقیت به لیست مانیتورینگ اضافه شد!"

# 🔄 اجرای ایمن ربات با تلاش مجدد هوشمند
def safe_polling():
    consecutive_failures = 0
    
    while True:
        try:
            if consecutive_failures > 0:
                print(f"🔄 تلاش مجدد شماره {consecutive_failures} برای اتصال به تلگرام...")
            
            # پاک کردن کش در صورت شکست‌های متوالی
            if consecutive_failures >= 3:
                get_direct_video_url.cache_clear()
                RECENT_VIDEOS.clear()
            
            bot.polling(none_stop=True, interval=1, timeout=30)
            # اگر موفقیت‌آمیز بود، ریست شمارنده
            consecutive_failures = 0
            
        except (ReadTimeout, ProxyError, ConnectionResetError, ConnectionError):
            consecutive_failures += 1
            # زمان انتظار را بر اساس تعداد شکست افزایش می‌دهیم
            wait_time = min(consecutive_failures * 5, 60)  # حداکثر 60 ثانیه
            print(f"⚠️ خطای اتصال. انتظار برای {wait_time} ثانیه...")
            time.sleep(wait_time)
            
        except Exception as e:
            consecutive_failures += 1
            error_msg = f"⚠️ خطای بحرانی در اجرای بات: {str(e)}"
            print(error_msg)
            
            if consecutive_failures <= 3:  # فقط 3 بار اطلاع‌رسانی کن
                notify_admin(error_msg)
                
            time.sleep(30)  # انتظار طولانی‌تر برای خطاهای بحرانی

# 🔄 تابع پینگ خودکار برای جلوگیری از خاموشی ربات
def keep_alive_ping():
    """ارسال پینگ به ربات هر 5 دقیقه برای جلوگیری از خاموش شدن"""
    import requests
    ping_url = f"https://api.telegram.org/bot{TOKEN}/getMe"
    ping_interval = 300  # هر 5 دقیقه یکبار
    
    while True:
        try:
            response = requests.get(ping_url, timeout=10)
            if response.status_code == 200:
                print(f"🔄 پینگ موفقیت‌آمیز به ربات در {time.strftime('%H:%M:%S')}")
            else:
                print(f"⚠️ خطا در پینگ: {response.status_code}")
        except Exception as e:
            print(f"⚠️ خطا در ارسال پینگ: {str(e)}")
        
        time.sleep(ping_interval)

def setup_bot():
    """Set up and configure the Telegram bot."""
    if not TOKEN:
        print("⚠️ توکن تلگرام یافت نشد! ربات در حالت وب-فقط اجرا می‌شود.")
        return None
        
    try:
        # سعی در حذف وبهوک قبلی - باعث افزایش پایداری می‌شود
        try:
            bot.remove_webhook()
        except:
            pass
            
        # شروع ربات در یک ترد جداگانه
        bot_thread = threading.Thread(target=safe_polling)
        bot_thread.daemon = True
        bot_thread.start()
        
        # شروع تابع نگهدارنده ربات در یک ترد جداگانه
        ping_thread = threading.Thread(target=keep_alive_ping)
        ping_thread.daemon = True
        ping_thread.start()
        
        print("🤖 ربات شروع به کار کرد!")
        return True
        
    except Exception as e:
        print(f"⚠️ خطا در راه‌اندازی ربات: {e}")
        return None

if __name__ == "__main__":
    print("🤖 ربات در حال اجراست...")
    safe_polling()