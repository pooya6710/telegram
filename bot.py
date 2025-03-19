import os
<<<<<<< HEAD
import asyncio
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)

# تنظیم لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# دریافت توکن از متغیرهای محیطی
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("توکن ربات تلگرام یافت نشد. لطفا متغیر محیطی TELEGRAM_BOT_TOKEN را تنظیم کنید.")
    exit(1)

# تنظیمات پایه
TEMP_DIR = 'temp_downloads'
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

QUALITY_MESSAGE = """
🎮 لطفا کیفیت مورد نظر برای دانلود ویدیوهای یوتیوب را انتخاب کنید:

- کیفیت بالا (1080p)
- کیفیت متوسط (720p) - پیش‌فرض
- کیفیت پایین (480p)

کیفیت فعلی: {quality}
"""

YT_QUALITIES = {
    'high': '1080',
    'medium': '720',
    'low': '480'
}

# وارد کردن ماژول‌های مورد نیاز
from utils import (
    is_youtube_url, is_instagram_url, format_size, 
    cleanup_temp_file, cleanup_temp_dir, ensure_temp_dir,
    setup_logging
)
from downloaders import YouTubeDownloader, InstagramDownloader

# Set up logging
logger = setup_logging()

# Initialize downloaders
youtube_downloader = YouTubeDownloader(TEMP_DIR)
instagram_downloader = InstagramDownloader(TEMP_DIR)

# User data dictionary to store user preferences
user_preferences = {}

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when the command /start is issued."""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")
    
    # Initialize user preferences if not exists
    if user_id not in user_preferences:
        user_preferences[user_id] = {
            'quality': 'medium'  # Default quality
        }
    
    await update.message.reply_text(WELCOME_MESSAGE)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message when the command /help is issued."""
    logger.info(f"User {update.effective_user.id} requested help")
    await update.message.reply_text(HELP_MESSAGE)

async def quality_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quality options for YouTube downloads."""
    user_id = update.effective_user.id
    
    # Initialize user preferences if not exists
    if user_id not in user_preferences:
        user_preferences[user_id] = {
            'quality': 'medium'  # Default quality
        }
    
    current_quality = user_preferences[user_id]['quality']
    logger.info(f"User {user_id} requested quality settings. Current quality: {current_quality}")
    
    await update.message.reply_text(
        QUALITY_MESSAGE.format(quality=YT_QUALITIES[current_quality])
    )

async def set_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the quality for YouTube downloads."""
    user_id = update.effective_user.id
    command = update.message.text[1:]  # Remove the '/' from command
    
    if command in YT_QUALITIES:
        # Update user preference
        if user_id not in user_preferences:
            user_preferences[user_id] = {}
        
        user_preferences[user_id]['quality'] = command
        youtube_downloader.set_quality(command)
        
        logger.info(f"User {user_id} set quality to {command} ({YT_QUALITIES[command]})")
        await update.message.reply_text(f"✅ کیفیت دانلود به {YT_QUALITIES[command]} تغییر یافت.")
    else:
        await update.message.reply_text("❌ کیفیت نامعتبر. لطفا از دستور /quality استفاده کنید.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle YouTube and Instagram URLs."""
    url = update.message.text
    chat_id = update.message.chat_id
    user_id = update.effective_user.id
    progress_message = None

    logger.info(f"Processing URL from user {user_id}: {url}")

    # Ensure temp directory exists
    ensure_temp_dir(TEMP_DIR)
    
    # Set quality according to user preference
    if user_id in user_preferences and 'quality' in user_preferences[user_id]:
        quality = user_preferences[user_id]['quality']
        youtube_downloader.set_quality(quality)
        logger.info(f"Using quality setting for user {user_id}: {quality}")

    try:
        # Send initial processing message
        progress_message = await update.message.reply_text("🔄 در حال پردازش درخواست شما...")

        if is_youtube_url(url):
            # Handle YouTube URL
            logger.info(f"Processing YouTube URL: {url}")
            await progress_message.edit_text("📥 در حال دانلود ویدیوی یوتیوب...")
            file_path, title = await youtube_downloader.download(url)

            # Send the file
            logger.info(f"Uploading YouTube video: {title}")
            await progress_message.edit_text("📤 در حال آپلود به تلگرام...")
            file_size = os.path.getsize(file_path)
            
            if file_size > 0:
                with open(file_path, 'rb') as video_file:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=video_file,
                        caption=f"📹 {title}\n\nحجم: {format_size(file_size)}"
                    )
            else:
                raise Exception("فایل دانلود شده خالی است")

            # Cleanup
            cleanup_temp_file(file_path)
            logger.info(f"Successfully processed YouTube video: {title}")

        elif is_instagram_url(url):
            # Handle Instagram URL
            logger.info(f"Processing Instagram URL: {url}")
            await progress_message.edit_text("📥 در حال دانلود محتوای اینستاگرام...")
            file_path, title = await instagram_downloader.download(url)

            # Send the file
            logger.info(f"Uploading Instagram content: {title}")
            await progress_message.edit_text("📤 در حال آپلود به تلگرام...")
            file_size = os.path.getsize(file_path)

            if file_path.endswith(('.mp4', '.mov')):
                with open(file_path, 'rb') as video_file:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=video_file,
                        caption=f"📷 {title}\n\nحجم: {format_size(file_size)}"
                    )
            else:
                with open(file_path, 'rb') as photo_file:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo_file,
                        caption=f"📷 {title}"
                    )

            # Cleanup
            cleanup_temp_dir(os.path.dirname(file_path))
            logger.info(f"Successfully processed Instagram content: {title}")

        else:
            logger.warning(f"Invalid URL received: {url}")
            await progress_message.edit_text("❌ لینک نامعتبر. لطفا یک لینک معتبر یوتیوب یا اینستاگرام ارسال کنید.")
            return

        # Delete progress message
        await progress_message.delete()

    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}")
        error_message = str(e)
        
        # Handle common errors with user-friendly messages
        if "Private profile" in error_message:
            error_message = "⛔ این پروفایل خصوصی است و قابل دانلود نیست."
        elif "No media found" in error_message:
            error_message = "⚠️ هیچ محتوای مدیایی در این لینک یافت نشد."
        elif "age restricted" in error_message.lower():
            error_message = "⚠️ این ویدیو دارای محدودیت سنی است و قابل دانلود نیست."
        elif "copyright" in error_message.lower():
            error_message = "⚠️ این محتوا به دلیل مسائل کپی‌رایت قابل دانلود نیست."
            
        # Update the progress message with error information
        if progress_message:
            await progress_message.edit_text(f"❌ خطا در دانلود: {error_message}")
        else:
            await update.message.reply_text(f"❌ خطا در دانلود: {error_message}")

async def error_handler(update, context):
    """Log errors caused by updates."""
    logger.error('Update "%s" caused error "%s"', update, context.error)
    
    # Send error message to user if possible
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ خطایی در پردازش درخواست شما رخ داد. لطفا دوباره تلاش کنید."
        )

def main():
    """Start the bot."""
    # Check if we should use the main bot or the one in telegram-main
    import os
    if os.environ.get("USE_LEGACY_BOT") == "1":
        # Create the Application instance - Legacy bot mode
        application = Application.builder().token(BOT_TOKEN).build()

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("quality", quality_command))
        
        # Add quality setting handlers
        for quality in YT_QUALITIES.keys():
            application.add_handler(CommandHandler(quality, set_quality))

        # Add URL handler - needs to be last to not override commands
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
        
        # Add error handler
        application.add_error_handler(error_handler)

        # Start the Bot
        application.run_polling()
    else:
        # Use the telegram-main implementation
        print("Using telegram-main/run_bot.py implementation...")
        import sys
        sys.path.append("telegram-main")
        import run_bot
        run_bot.main()

if __name__ == '__main__':
    main()
=======
import sys
import json
import time
import glob
import datetime
import shutil
import random
import threading
import traceback

from typing import Dict, Any, List, Optional, Tuple, Union
from requests.exceptions import ReadTimeout, ProxyError, ConnectionError

# برای لاگ کردن پیشرفته
try:
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler("bot_debug.log"), logging.StreamHandler()]
    )
    from debug_logger import debug_log, log_webhook_request, log_telegram_update, debug_decorator, format_exception_with_context
except ImportError as e:
    print(f"خطا در بارگذاری ماژول debug_logger: {e}")

    def debug_log(message, level="DEBUG", context=None):
        """
        لاگ کردن پیام‌ها در نسخه ساده
        """
        print(f"{level}: {message}")

    def log_webhook_request(data):
        """
        لاگ کردن درخواست‌های وب‌هوک
        """
        print(f"Webhook data: {data}")

    def log_telegram_update(update):
        """
        لاگ کردن آپدیت‌های تلگرام
        """
        print(f"Telegram update: {update}")

    def debug_decorator(func):
        """
        دکوراتور برای لاگ کردن ورودی و خروجی توابع
        """
        return func

    def format_exception_with_context(e):
        """
        فرمت‌بندی استثناها با اطلاعات بافت کامل
        """
        return str(e)

# سعی در بارگذاری وابستگی‌ها با مدیریت بهتر خطا
try:
    import telebot
    from telebot import types
except ImportError:
    print("خطا در بارگذاری telebot. لطفاً با دستور 'pip install pytelegrambotapi' آن را نصب کنید.")

try:
    import flask
    from flask import Flask, request, jsonify
except ImportError:
    print("خطا در بارگذاری flask. لطفاً با دستور 'pip install flask' آن را نصب کنید.")

try:
    import requests
except ImportError:
    print("خطا در بارگذاری requests. لطفاً با دستور 'pip install requests' آن را نصب کنید.")

try:
    import psutil
except ImportError:
    print("خطا در بارگذاری psutil. لطفاً با دستور 'pip install psutil' آن را نصب کنید.")

try:
    from yt_dlp import YoutubeDL
except ImportError:
    print("خطا در بارگذاری yt_dlp. لطفاً با دستور 'pip install yt-dlp' آن را نصب کنید.")

# تعاریف اولیه و متغیرهای سراسری
app = Flask(__name__)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # خواندن توکن از متغیرهای محیطی
MAX_VIDEOS_TO_KEEP = 10  # حداکثر تعداد ویدیوهای ذخیره شده
DEFAULT_VIDEO_QUALITY = "360p"  # کیفیت پیش‌فرض ویدیو
ADMIN_CHAT_ID = 110201728  # شناسه چت ادمین
HASHTAGS = {}  # دیکشنری هشتگ‌ها و کانال‌ها

# ایجاد نمونه ربات و تنظیم وب‌هوک
if TOKEN:
    bot = telebot.TeleBot(TOKEN)
    bot.user_video_quality = {}  # برای ذخیره تنظیمات کیفیت ویدیو کاربران
else:
    print("⚠️ توکن ربات یافت نشد. لطفاً متغیر محیطی TELEGRAM_BOT_TOKEN را تنظیم کنید.")
    bot = None

# ایجاد مسیرهای ذخیره‌سازی اگر وجود ندارند
for folder in ["videos", "instagram_videos"]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# تابع وب‌هوک برای فلسک
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    try:
        # دریافت داده‌های آپدیت
        update_json = request.get_data().decode("utf-8")

        try:
            log_webhook_request(update_json)  # لاگ کردن درخواست وب‌هوک
        except Exception as req_error:
            debug_log(f"خطا در لاگ کردن درخواست وب‌هوک: {req_error}", "ERROR")

        if update_json:
            # تبدیل رشته JSON به دیکشنری
            try:
                update = telebot.types.Update.de_json(update_json)

                # لاگ کردن آپدیت تلگرام
                try:
                    log_telegram_update(update)
                except Exception as log_error:
                    debug_log(f"خطا در لاگ کردن آپدیت تلگرام: {log_error}", "ERROR")

                # بررسی نوع پیام
                try:
                    if hasattr(update, "message") and update.message:
                        # لاگ کردن اطلاعات پیام
                        try:
                            message_info = {
                                "chat_id": update.message.chat.id,
                                "user_id": update.message.from_user.id if update.message.from_user else None,
                                "username": update.message.from_user.username if update.message.from_user else None,
                                "text": update.message.text if hasattr(update.message, "text") and update.message.text else "<بدون متن>",
                                "content_type": "متن" if hasattr(update.message, "text") else "محتوای چندرسانه‌ای"
                            }
                            debug_log(f"پیام دریافت شد: {json.dumps(message_info, ensure_ascii=False)}", "INFO")
                        except Exception:
                            debug_log("خطا در لاگ کردن اطلاعات پیام", "ERROR")

                        # ذخیره نام کاربری و نام برای ردیابی بهتر
                        try:
                            if update.message.from_user:
                                user_info = {
                                    "user_id": update.message.from_user.id,
                                    "username": update.message.from_user.username,
                                    "first_name": update.message.from_user.first_name,
                                    "last_name": update.message.from_user.last_name
                                }
                                debug_log(f"اطلاعات کاربر: {json.dumps(user_info, ensure_ascii=False)}", "INFO")
                        except Exception:
                            debug_log("خطا در لاگ کردن اطلاعات کاربر", "ERROR")

                    # پردازش آپدیت
                    try:
                        if bot:
                            bot.process_new_updates([update])
                    except Exception as process_error:
                        error_details = format_exception_with_context(process_error)
                        debug_log(f"خطا در پردازش آپدیت تلگرام: {error_details}", "ERROR")

                        # تلاش برای پاسخ به کاربر در صورت خطا
                        try:
                            if hasattr(update, "message") and update.message:
                                bot.send_message(update.message.chat.id, "⚠ خطایی در پردازش پیام شما رخ داد. لطفاً دوباره تلاش کنید.")
                        except Exception:
                            debug_log("خطا در ارسال پیام خطا به کاربر", "ERROR")

                except Exception as update_error:
                    error_details = format_exception_with_context(update_error)
                    debug_log(f"خطا در پردازش آپدیت: {error_details}", "ERROR")

                return "OK"
            except Exception as json_error:
                debug_log(f"خطا در تبدیل JSON آپدیت: {json_error}", "ERROR")
                return "JSON Error"

        return "No Data"
    except Exception as e:
        debug_log(f"خطای کلی در پردازش درخواست وب‌هوک: {e}", "ERROR")
        return "Error"

# تابع دریافت وضعیت سرور از کش
def get_cached_server_status():
    """دریافت وضعیت سرور از کش با مدیریت خطای بهتر"""
    try:
        from server_status import get_cached_server_status as get_status
        return get_status()
    except ImportError:
        debug_log("ماژول server_status یافت نشد", "WARNING")

        # اگر ماژول وجود نداشت، مستقیماً از کش فایل استفاده کن
        try:
            if os.path.exists("server_status.json"):
                file_time = os.path.getmtime("server_status.json")
                current_time = time.time()

                if current_time - file_time < 600:  # کمتر از 10 دقیقه
                    with open("server_status.json", "r", encoding="utf-8") as file:
                        data = json.load(file)
                        return data["status"]
        except Exception as e:
            debug_log(f"خطا در خواندن فایل کش وضعیت سرور: {e}", "ERROR")

    return None

# بارگیری اطلاعات هشتگ‌ها و کانال‌ها
def load_hashtags():
    """بارگیری اطلاعات هشتگ‌ها و کانال‌ها از فایل"""
    global HASHTAGS
    try:
        if os.path.exists("channel_links.json"):
            with open("channel_links.json", "r", encoding="utf-8") as file:
                HASHTAGS = json.load(file)
                debug_log(f"اطلاعات هشتگ‌ها با موفقیت بارگیری شد: {len(HASHTAGS.get('hashtags', []))} هشتگ و {len(HASHTAGS.get('channels', []))} کانال")
                return HASHTAGS
    except Exception as e:
        debug_log(f"خطا در بارگیری اطلاعات هشتگ‌ها: {e}", "ERROR")

    # اگر فایل وجود نداشت یا خطایی رخ داد، مقدار پیش‌فرض را برگردان
    HASHTAGS = {"hashtags": [], "channels": []}
    return HASHTAGS

# ذخیره اطلاعات هشتگ‌ها و کانال‌ها
def save_hashtags(data):
    """ذخیره اطلاعات هشتگ‌ها و کانال‌ها در فایل"""
    global HASHTAGS
    try:
        with open("channel_links.json", "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False)
        HASHTAGS = data
        debug_log("اطلاعات هشتگ‌ها با موفقیت ذخیره شد")
        return True
    except Exception as e:
        debug_log(f"خطا در ذخیره اطلاعات هشتگ‌ها: {e}", "ERROR")
        return False

# پاکسازی فایل‌های قدیمی و نگهداری حداکثر تعداد مشخصی فایل
def clear_folder(folder_path, max_files=MAX_VIDEOS_TO_KEEP):
    """حذف فایل‌های قدیمی و نگهداری حداکثر تعداد مشخصی فایل"""
    try:
        # دریافت همه فایل‌ها
        all_files = glob.glob(f"{folder_path}/*.*")

        # اگر تعداد فایل‌ها از حد مجاز بیشتر است
        if len(all_files) > max_files:
            # مرتب‌سازی فایل‌ها بر اساس زمان ویرایش
            files_with_time = [(f, os.path.getmtime(f)) for f in all_files]
            files_sorted = sorted(files_with_time, key=lambda x: x[1])

            # حذف فایل‌های قدیمی
            files_to_delete = files_sorted[:-max_files]  # نگهداری max_files فایل جدیدتر

            for file_path, _ in files_to_delete:
                try:
                    os.remove(file_path)
                    debug_log(f"فایل قدیمی حذف شد: {file_path}")
                except Exception as e:
                    debug_log(f"خطا در حذف فایل {file_path}: {e}", "ERROR")

            return len(files_to_delete)
    except Exception as e:
        debug_log(f"خطا در پاکسازی پوشه {folder_path}: {e}", "ERROR")

    return 0

# تابع شروع - Start command
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

        # ارسال پیام خوش‌آمدگویی
        bot.send_message(
            message.chat.id,
            f"👋 سلام {message.from_user.first_name}!\n\n"
            "🎬 به ربات دانلود ویدیو خوش آمدید.\n\n"
            "🔸 <b>قابلیت‌های ربات:</b>\n"
            "• دانلود ویدیو از یوتیوب و اینستاگرام\n"
            "• امکان انتخاب کیفیت ویدیو\n"
            "• جستجوی هشتگ در کانال‌های تلگرام\n"
            "• نمایش وضعیت سرور\n\n"
            "🔹 <b>روش استفاده:</b>\n"
            "• برای دانلود ویدیو، لینک ویدیوی مورد نظر را ارسال کنید\n"
            "• برای جستجوی هشتگ، از دستور /search_hashtag استفاده کنید\n"
            "• برای نمایش وضعیت سرور، از دستور /status استفاده کنید",
            parse_mode="HTML",
            reply_markup=markup
        )
        debug_log(f"کاربر {message.from_user.id} دستور /start را اجرا کرد")
    except Exception as e:
        debug_log(f"خطا در اجرای دستور start: {e}", "ERROR")
        bot.send_message(message.chat.id, f"⚠ خطایی رخ داد: {str(e)}")

# دستور راهنما - Help command
@bot.message_handler(commands=["help"])
def help_command(message):
    try:
        # ایجاد کیبورد اینلاین با دکمه‌های مختلف
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        video_help_btn = telebot.types.InlineKeyboardButton("🎬 راهنمای دانلود", callback_data="download_help")
        hashtag_help_btn = telebot.types.InlineKeyboardButton("#️⃣ راهنمای هشتگ", callback_data="hashtag_help")
        quality_btn = telebot.types.InlineKeyboardButton("📊 کیفیت ویدیو", callback_data="select_quality")

        markup.add(video_help_btn, hashtag_help_btn)
        markup.add(quality_btn)

        # ارسال پیام راهنما
        bot.send_message(
            message.chat.id,
            "📚 <b>راهنمای استفاده از ربات</b>\n\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            parse_mode="HTML",
            reply_markup=markup
        )
        debug_log(f"کاربر {message.from_user.id} دستور /help را اجرا کرد")
    except Exception as e:
        debug_log(f"خطا در اجرای دستور help: {e}", "ERROR")
        bot.send_message(message.chat.id, f"⚠ خطایی رخ داد: {str(e)}")

# تابع نمایش وضعیت سرور برای دستور /status
@bot.message_handler(commands=['status'])
def server_status_command(message):
    """دستور نمایش وضعیت سرور"""
    try:
        from bot_status_handler import handle_status_command
        handle_status_command(bot, message)
    except ImportError:
        # اگر ماژول موجود نبود، استفاده از نسخه پیش‌فرض
        try:
            from server_status import generate_server_status
            # تولید و نمایش وضعیت سرور
            status_text = generate_server_status()
            bot.send_message(message.chat.id, status_text, parse_mode="Markdown")
        except Exception as e:
            debug_log(f"خطای کلی در دریافت وضعیت سرور: {e}", "ERROR")
            bot.send_message(message.chat.id, f"⚠ خطا در دریافت وضعیت سرور: {str(e)}")

# پردازش دکمه‌های شیشه‌ای
def get_main_menu_markup():
    """ایجاد کیبورد منوی اصلی"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    help_btn = types.InlineKeyboardButton("📚 راهنما", callback_data="download_help")
    quality_btn = types.InlineKeyboardButton("📊 کیفیت ویدیو", callback_data="select_quality")
    status_btn = types.InlineKeyboardButton("📈 وضعیت سرور", callback_data="server_status")
    markup.add(help_btn, quality_btn)
    markup.add(status_btn)
    return markup

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """پردازش کلیک روی دکمه‌های شیشه‌ای"""
    try:
        # پاسخ به callback برای جلوگیری از خطای timeout
        bot.answer_callback_query(call.id)

        # دکمه بازگشت به منوی اصلی
        if call.data == "back_to_main":
            markup = types.InlineKeyboardMarkup(row_width=2)
            help_btn = types.InlineKeyboardButton("📚 راهنما", callback_data="download_help")
            quality_btn = types.InlineKeyboardButton("📊 کیفیت ویدیو", callback_data="select_quality")
            status_btn = types.InlineKeyboardButton("📈 وضعیت سرور", callback_data="server_status")
            back_btn = types.InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")

            markup.add(help_btn, quality_btn)
            markup.add(status_btn)
            markup.add(back_btn)

            bot.edit_message_text(
                "به منوی اصلی بازگشتید! از دکمه‌های زیر استفاده کنید:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
            return

        elif call.data == "download_help":
            markup = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_main")
            markup.add(back_btn)

            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                "🎥 *راهنمای دانلود ویدیو*\n\n"
                "1️⃣ لینک ویدیو را از یوتیوب یا اینستاگرام کپی کنید\n"
                "2️⃣ لینک را برای ربات ارسال کنید\n"
                "3️⃣ کیفیت مورد نظر را انتخاب کنید\n"
                "4️⃣ صبر کنید تا ویدیو دانلود و ارسال شود\n\n"
                "⚠️ *نکته:* حداکثر سایز فایل قابل ارسال نامحدود است",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=markup
            )

        elif call.data == "select_quality":
            markup = types.InlineKeyboardMarkup(row_width=3)
            qualities = ["144p", "240p", "360p", "480p", "720p", "1080p"]
            buttons = [types.InlineKeyboardButton(q, callback_data=f"quality_{q}") for q in qualities]
            back_btn = types.InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")
            markup.add(*buttons)
            markup.add(back_btn)

            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                "📊 کیفیت مورد نظر را انتخاب کنید:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )

        elif call.data.startswith("quality_"):
            quality = call.data.split("_")[1]
            user_id = str(call.from_user.id)
            bot.user_video_quality[user_id] = quality

            bot.answer_callback_query(call.id, f"✅ کیفیت {quality} انتخاب شد")
            bot.edit_message_text(
                f"✅ کیفیت پیش‌فرض شما به {quality} تغییر کرد",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )

        elif call.data == "server_status":
            from server_status import generate_server_status
            status_text = generate_server_status()

            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                status_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )

    except Exception as e:
        debug_log(f"خطا در پردازش callback query: {e}", "ERROR")
        try:
            bot.answer_callback_query(call.id, "⚠️ خطایی رخ داد")
        except:
            pass

# تابع راه‌اندازی ربات
def start_bot():
    """راه‌اندازی ربات تلگرام"""
    import os
    import sys
    import psutil
    import time

    # بررسی و توقف نمونه قبلی
    if os.path.exists("bot.lock"):
        try:
            with open("bot.lock", "r") as f:
                old_pid = f.read().strip()
                if old_pid and old_pid.isdigit():
                    old_pid = int(old_pid)
                    if psutil.pid_exists(old_pid):
                        # متوقف کردن پروسه قبلی
                        try:
                            old_process = psutil.Process(old_pid)
                            old_process.terminate()
                            # صبر برای اطمینان از توقف کامل
                            old_process.wait(timeout=3)
                            debug_log(f"نمونه قبلی ربات (PID: {old_pid}) متوقف شد", "INFO")
                        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                            pass
            # حذف فایل قفل قدیمی
            os.remove("bot.lock")
            time.sleep(1)  # کمی صبر برای اطمینان
        except Exception as e:
            debug_log(f"خطا در توقف نمونه قبلی: {e}", "ERROR")

    # ایجاد فایل قفل جدید با PID فرآیند فعلی
    try:
        with open("bot.lock", "w") as f:
            f.write(str(os.getpid()))
    except:
        pass

    # بارگیری اطلاعات هشتگ‌ها
    load_hashtags()

    # تنظیم وب‌هوک یا شروع پولینگ
    try:
        WEBHOOK_HOST = os.environ.get("WEBHOOK_HOST")

        if WEBHOOK_HOST and TOKEN:
            bot.remove_webhook()
            time.sleep(1)
            webhook_url = f"https://{WEBHOOK_HOST}/{TOKEN}"

            # تنظیم وب‌هوک
            bot.set_webhook(url=webhook_url.replace('http://', 'https://'))
            debug_log(f"وب‌هوک تنظیم شد: {webhook_url}")

            # اجرای سرور فلسک
            app.run(host="0.0.0.0", port=os.environ.get("PORT", 5000))
        else:
            # پولینگ
            bot.remove_webhook()
            debug_log("پولینگ شروع شد")
            bot.polling(none_stop=True, interval=3, timeout=30)
    except Exception as e:
        debug_log(f"خطا در راه‌اندازی ربات: {e}", "ERROR")

# اجرای مستقیم
if __name__ == "__main__":
    start_bot()
>>>>>>> 3b6692783d80f74482bf7577f1da04a3c3e8231f
