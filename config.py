import os

# Bot Configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7338644071:AAEex9j0nMualdoywHSGFiBoMAzRpkFypPk')

# Directories
TEMP_DIR = 'temp_downloads'
LOG_DIR = 'logs'

# File size limits (in bytes)
MAX_FILE_SIZE = float('inf')  # No file size limit

# Timeouts
DOWNLOAD_TIMEOUT = 600  # 10 minutes

# YouTube video quality options
YT_QUALITIES = {
    'high': '1080',
    'medium': '720',
    'low': '480'
}

# Messages
WELCOME_MESSAGE = """
🎥 به ربات دانلود یوتیوب و اینستاگرام خوش آمدید!

کافیه لینک یوتیوب یا اینستاگرام رو برام بفرستید تا براتون دانلود کنم.

دستورات:
/start - نمایش این پیام خوش‌آمدگویی
/help - نمایش راهنما
/quality - تنظیم کیفیت دانلود ویدیوهای یوتیوب
"""

HELP_MESSAGE = """
📝 راهنمای استفاده از ربات:

1. فقط کافیه لینک یوتیوب یا اینستاگرام رو برام بفرستید
2. صبر کنید تا دانلود تموم بشه
3. فایل مدیا رو دریافت کنید

لینک‌های پشتیبانی شده:
- ویدیوهای یوتیوب (با کیفیت قابل تنظیم)
- پست‌های اینستاگرام
- ریلز اینستاگرام

برای تغییر کیفیت دانلود از دستور /quality استفاده کنید.

نکته: امکان دانلود پست‌های خصوصی اینستاگرام وجود نداره.
"""

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