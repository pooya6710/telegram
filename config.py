import os

# تنظیمات اصلی ربات
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")  # توکن ربات از BotFather
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")  # آدرس وب‌هوک (مثال: https://example.com/webhook)
ADMIN_IDS = list(map(int, os.environ.get("ADMIN_IDS", "0").split(",")))  # شناسه‌های ادمین‌ها با کاما جدا شده

# تنظیمات وب‌هوک
WEBHOOK_HOST = '0.0.0.0'  # آدرس سرور
WEBHOOK_PORT = 5000  # پورت وب‌هوک برای دسترسی خارجی
BACKEND_PORT = 8000  # پورت برای سرویس‌های داخلی

# تنظیمات دیتابیس
DATABASE_PATH = os.environ.get("DATABASE_PATH", "bot_database.db")

# محدودیت‌های دانلود
MAX_VIDEO_SIZE_MB = float('inf')  # بدون محدودیت حجم
MAX_RETRIES = 3  # تعداد تلاش‌های مجدد برای دانلود
DOWNLOAD_TIMEOUT = 600  # زمان انتظار برای دانلود (10 دقیقه)
MAX_DOWNLOAD_TIME = int(os.environ.get("MAX_DOWNLOAD_TIME", "300"))  # حداکثر زمان دانلود به ثانیه
MAX_DOWNLOADS_PER_USER = int(os.environ.get("MAX_DOWNLOADS_PER_USER", "10"))  # حداکثر تعداد دانلود همزمان برای هر کاربر
MAX_VIDEO_DURATION = int(os.environ.get("MAX_VIDEO_DURATION", "600"))  # حداکثر مدت ویدیو به ثانیه

# تنظیمات لاگینگ
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# سطوح دسترسی کاربران
class UserRole:
    BLOCKED = -1    # کاربر مسدود شده
    NORMAL = 0      # کاربر عادی
    PREMIUM = 1     # کاربر ویژه
    ADMIN = 2       # ادمین
    SUPERADMIN = 3  # سوپر ادمین

# وضعیت‌های مختلف دانلود
class DownloadStatus:
    PENDING = 0     # در انتظار
    PROCESSING = 1  # در حال پردازش
    COMPLETED = 2   # تکمیل شده
    FAILED = 3      # شکست خورده
    CANCELED = 4    # لغو شده

# تنظیمات yt-dlp
YDL_OPTIONS = {
    'format': 'best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'no_warnings': True,
    'quiet': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'outtmpl': 'downloads/%(title)s-%(id)s.%(ext)s',
}

# پیام‌های ربات
BOT_MESSAGES = {
    'start': """🎬 به ربات دانلود ویدیو یوتیوب خوش آمدید!

برای دانلود ویدیو، لینک یوتیوب را ارسال کنید یا از دستورات زیر استفاده کنید:

/download [YouTube URL] - دانلود ویدیو
/status - وضعیت سیستم
/help - راهنمای استفاده از ربات""",

    'help': """🔍 راهنمای استفاده از ربات دانلود ویدیو یوتیوب:

◾️ برای دانلود ویدیو، لینک یوتیوب را ارسال کنید.
◾️ برای دانلود با کیفیت خاص، از دستور زیر استفاده کنید:
  /download [YouTube URL]

◾️ دستورات مدیریتی:
  /status - مشاهده وضعیت سیستم
  /mydownloads - مشاهده دانلودهای من
  /cancel [download_id] - لغو دانلود

◾️ محدودیت‌ها:
  • حداکثر مدت ویدیو: {max_duration} دقیقه
  • حداکثر تعداد دانلود همزمان: {max_downloads}

📌 در صورت بروز مشکل با ادمین تماس بگیرید.""",

    'admin_help': """🔍 راهنمای دستورات مدیریتی:

◾️ مدیریت کاربران:
  /users - مشاهده لیست کاربران
  /block [user_id] - مسدود کردن کاربر
  /unblock [user_id] - رفع مسدودیت کاربر
  /setadmin [user_id] - تنظیم کاربر به عنوان ادمین
  /setpremium [user_id] - تنظیم کاربر به عنوان ویژه

◾️ مدیریت سیستم:
  /sysinfo - مشاهده اطلاعات سیستم
  /logs [count] - مشاهده لاگ‌های اخیر
  /broadcast [message] - ارسال پیام به همه کاربران

◾️ مدیریت دانلودها:
  /downloads - مشاهده همه دانلودها
  /cancelall - لغو همه دانلودهای در حال انجام""",

    'invalid_url': "❌ لینک نامعتبر است. لطفاً یک لینک یوتیوب معتبر ارسال کنید.",
    'processing': "⏳ درحال پردازش لینک...",
    'download_started': "🔄 دانلود شروع شد. شناسه دانلود: {download_id}",
    'download_success': "✅ دانلود با موفقیت انجام شد!",
    'download_failed': "❌ دانلود با خطا مواجه شد: {error}",
    'unauthorized': "⛔ شما اجازه استفاده از این دستور را ندارید.",
    'user_blocked': "⛔ دسترسی شما به ربات مسدود شده است.",
}

# تنظیمات سیستم
DOWNLOADS_DIR = "downloads"
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)