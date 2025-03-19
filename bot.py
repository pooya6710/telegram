import os
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