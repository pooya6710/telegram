
import os
import telebot
import logging
import traceback
import threading

# تنظیم سیستم لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# تنظیم توکن ربات
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7338644071:AAEex9j0nMualdoywHSGFiBoMAzRpkFypPk")
OWNER_ID = os.environ.get("OWNER_ID", "")  # آیدی مالک ربات (اختیاری)

if not TOKEN:
    logger.error("❌ هیچ توکنی تنظیم نشده است! لطفا توکن را در متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم کنید.")
    exit(1)

# ایجاد نمونه ربات
bot = telebot.TeleBot(TOKEN)

# تعریف دستور /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "سلام! به ربات چندکاره خوش آمدید. 🤖\nبرای دیدن راهنما دستور /help را بفرستید.")

# تعریف دستور /help
@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = """
🤖 راهنمای استفاده از ربات:
/start - شروع کار با ربات
/help - نمایش این راهنما
/info - دریافت اطلاعات

همچنین می‌توانید لینک ویدیوی یوتیوب یا اینستاگرام را ارسال کنید تا دانلود شود.
    """
    bot.reply_to(message, help_text)

# تعریف دستور /info
@bot.message_handler(commands=['info'])
def handle_info(message):
    info_text = "🤖 این ربات چندکاره است و قابلیت‌های متنوعی دارد."
    bot.reply_to(message, info_text)

# پاسخ به پیام های معمولی
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text
    
    # بررسی لینک یوتیوب یا اینستاگرام
    if "youtube.com" in text or "youtu.be" in text:
        bot.reply_to(message, "لینک یوتیوب شناسایی شد. در حال پردازش...")
    elif "instagram.com" in text:
        bot.reply_to(message, "لینک اینستاگرام شناسایی شد. در حال پردازش...")
    else:
        bot.reply_to(message, f"پیام دریافت شد: {text}")

# پاکسازی فایل‌های قدیمی
def cleanup_old_videos():
    """پاکسازی ویدیوهای قدیمی برای صرفه‌جویی در فضای ذخیره‌سازی"""
    try:
        import os
        import time
        
        # حداکثر عمر فایل (2 روز)
        MAX_AGE = 2 * 24 * 60 * 60
        
        # بررسی پوشه‌های ویدیو
        for folder in ["videos", "instagram_videos"]:
            if not os.path.exists(folder):
                continue
                
            now = time.time()
            count = 0
            
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                
                # بررسی سن فایل
                if os.path.isfile(file_path) and (now - os.path.getctime(file_path)) > MAX_AGE:
                    os.remove(file_path)
                    count += 1
                    
            if count > 0:
                logger.info(f"🧹 {count} فایل قدیمی از پوشه {folder} پاک شد.")
                
    except Exception as e:
        logger.error(f"❌ خطا در پاکسازی فایل‌های قدیمی: {e}")

# تابع setup_bot برای راه‌اندازی ربات
def setup_bot():
    """راه‌اندازی ربات تلگرام و ثبت تمام هندلرها"""
    logger.info("🤖 ربات شروع به کار کرد!")

    try:
        # ایجاد پوشه‌های مورد نیاز
        os.makedirs("videos", exist_ok=True)
        os.makedirs("instagram_videos", exist_ok=True)
        
        # شروع پولینگ ربات در یک ترد جداگانه
        polling_thread = threading.Thread(target=bot.infinity_polling, kwargs={'none_stop': True})
        polling_thread.daemon = True  # اجازه می‌دهد برنامه اصلی بسته شود حتی اگر این ترد همچنان اجرا می‌شود
        polling_thread.start()

        # ارسال پیام به مالک در صورت راه‌اندازی مجدد
        if OWNER_ID:
            try:
                bot.send_message(OWNER_ID, "🔄 ربات مجدداً راه‌اندازی شد و آماده کار است!")
            except Exception as e:
                logger.error(f"خطا در ارسال پیام به مالک: {e}")

        # زمانبندی پاکسازی فایل‌های قدیمی
        def schedule_cleanup():
            cleanup_old_videos()
            # اجرای مجدد هر 6 ساعت
            threading.Timer(6 * 60 * 60, schedule_cleanup).start()
            
        # شروع زمانبندی پاکسازی
        schedule_cleanup()
        
        return True
    except Exception as e:
        logger.error(f"❌ خطا در راه‌اندازی ربات: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if setup_bot():
        # ادامه اجرای ربات
        logger.info("ربات در حال اجرا...")
        # جلوگیری از خاتمه برنامه
        import time
        while True:
            time.sleep(10)
