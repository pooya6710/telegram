import os
import shutil
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse
import re
import yt_dlp
import instaloader
import glob
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging
LOG_FILE = 'bot.log'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure file handler with rotation
file_handler = RotatingFileHandler(
    os.path.join('logs', LOG_FILE),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=3
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# Configure console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# Setup root logger
logging.root.setLevel(logging.INFO)
logging.root.addHandler(file_handler)
logging.root.addHandler(console_handler)

# Get logger for this module
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN')
TEMP_DIR = 'temp_downloads'
MAX_TELEGRAM_FILE_SIZE = 50 * 1024 * 1024
YT_QUALITIES = {
    'high': '1080p',
    'medium': '720p',
    'low': '480p'
}

# Messages
WELCOME_MESSAGE = """
🎥 به ربات دانلود یوتیوب و اینستاگرام خوش آمدید!

کافیه لینک یوتیوب یا اینستاگرام رو برام بفرستید تا براتون دانلود کنم.

دستورات:
/start - نمایش این پیام خوش‌آمدگویی
/help - نمایش راهنما
"""

HELP_MESSAGE = """
📝 راهنمای استفاده از ربات:

1. فقط کافیه لینک یوتیوب یا اینستاگرام رو برام بفرستید
2. صبر کنید تا دانلود تموم بشه
3. فایل مدیا رو دریافت کنید

لینک‌های پشتیبانی شده:
- ویدیوهای یوتیوب (با بالاترین کیفیت موجود)
- پست‌های اینستاگرام
- ریلز اینستاگرام

نکته: امکان دانلود پست‌های خصوصی اینستاگرام وجود نداره.
"""

# Utility functions
def is_youtube_url(url):
    """Check if the URL is a valid YouTube URL"""
    parsed = urlparse(url)
    if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
        return True
    return False

def is_instagram_url(url):
    """Check if the URL is a valid Instagram URL"""
    parsed = urlparse(url)
    if 'instagram.com' in parsed.netloc:
        return True
    return False

def clean_filename(filename):
    """Clean filename from invalid characters"""
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def get_file_size(file_path):
    """Get file size in bytes"""
    return os.path.getsize(file_path)

def ensure_temp_dir(temp_dir):
    """Ensure temporary directory exists"""
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

def cleanup_temp_file(file_path):
    """Remove temporary file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Error cleaning up file {file_path}: {str(e)}")

def cleanup_temp_dir(temp_dir):
    """Clean up temporary directory"""
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"Error cleaning up directory {temp_dir}: {str(e)}")

def format_size(size):
    """Format file size to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

# Downloader classes
class YouTubeDownloader:
    def __init__(self, temp_dir):
        self.temp_dir = temp_dir
        ensure_temp_dir(self.temp_dir)  # Ensure temp directory exists
        self.ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(self.temp_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'writesubtitles': True,
            'subtitleslangs': ['en'],
            'quiet': True,
            'merge_output_format': 'mp4',
        }

    async def download(self, url):
        try:
            logger.info(f"Starting download for URL: {url}")
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                video_title = info_dict.get('title', 'Unknown Title')
                video_title = clean_filename(video_title)
                ydl.download([url])
                file_path = os.path.join(self.temp_dir, f"{video_title}.mp4")  # Assuming mp4
                return file_path, video_title

        except yt_dlp.DownloadError as e:
            logger.error(f"yt-dlp DownloadError: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"General error during YouTube download: {str(e)}")
            raise

class InstagramDownloader:
    def __init__(self, temp_dir):
        self.temp_dir = temp_dir
        ensure_temp_dir(self.temp_dir)  # Ensure temp directory exists
        self.L = instaloader.Instaloader(
            download_pictures=True,
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            filename_pattern="{shortcode}",
            dirname_pattern=self.temp_dir,
            quiet=False,  # Enable output for debugging
            max_connection_attempts=3
        )

    async def download(self, url):
        try:
            logger.info(f"Starting download for URL: {url}")

            # Handle both post and reel URLs
            if "/reel/" in url:
                shortcode = url.split("/reel/")[1].split("/")[0]
                logger.info(f"Detected reel with shortcode: {shortcode}")
            else:
                shortcode = url.split("/p/")[1].split("/")[0]
                logger.info(f"Detected post with shortcode: {shortcode}")

            shortcode = shortcode.split("?")[0]  # Remove query parameters

            # Create target directory
            target_dir = os.path.join(self.temp_dir, shortcode)
            ensure_temp_dir(target_dir)  # Ensure target directory exists
            logger.info(f"Created target directory: {target_dir}")

            # Set download directory for this post
            self.L.dirname_pattern = target_dir
            logger.info(f"Set download directory to: {target_dir}")

            # Download post with error handling
            try:
                post = instaloader.Post.from_shortcode(self.L.context, shortcode)
                logger.info(f"Successfully fetched post info for shortcode: {shortcode}")

                # Download the post directly to target directory
                self.L.download_post(post, target=target_dir)
                logger.info("Post download completed")
            except Exception as e:
                logger.error(f"Error during post download: {str(e)}")
                raise

            # List all files in directory for debugging
            all_files = os.listdir(target_dir)
            logger.info(f"Files in target directory: {all_files}")

            # Find the downloaded file - support more extensions and case-insensitive
            media_files = []
            for ext in ['.mp4', '.jpg', '.jpeg', '.png', '.webp', '.mov']:
                media_files.extend(glob.glob(os.path.join(target_dir, f'*{ext}')))
                media_files.extend(glob.glob(os.path.join(target_dir, f'*{ext.upper()}')))

            logger.info(f"Found media files: {media_files}")

            if not media_files:
                logger.error("No media files found in the following directory structure:")
                for root, dirs, files in os.walk(target_dir):
                    logger.error(f"Directory: {root}")
                    for f in files:
                        logger.error(f"  File: {f}")
                raise Exception("هیچ فایل مدیایی در پست پیدا نشد")

            file_path = media_files[0]
            logger.info(f"Selected file for sending: {file_path}")

            if os.path.getsize(file_path) > MAX_TELEGRAM_FILE_SIZE:
                raise ValueError("فایل بزرگتر از محدودیت تلگرام است (50 مگابایت)")

            return file_path, f"پست اینستاگرام - {shortcode}"

        except instaloader.exceptions.InstaloaderException as e:
            logger.error(f"Instaloader error: {str(e)}")
            raise Exception(f"خطا در دانلود از اینستاگرام: {str(e)}")
        except Exception as e:
            logger.error(f"General error: {str(e)}")
            raise Exception(f"خطا در دانلود از اینستاگرام: {str(e)}")

# Initialize downloaders
youtube_downloader = YouTubeDownloader(TEMP_DIR)
instagram_downloader = InstagramDownloader(TEMP_DIR)

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when the command /start is issued."""
    logger.info(f"User {update.effective_user.id} started the bot")
    await update.message.reply_text(WELCOME_MESSAGE)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message when the command /help is issued."""
    logger.info(f"User {update.effective_user.id} requested help")
    await update.message.reply_text(HELP_MESSAGE)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle YouTube and Instagram URLs."""
    url = update.message.text
    chat_id = update.message.chat_id
    progress_message = None

    logger.info(f"Processing URL from user {update.effective_user.id}: {url}")

    # Ensure temp directory exists
    ensure_temp_dir(TEMP_DIR)

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
            with open(file_path, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    caption=f"📹 {title}\n\nحجم: {format_size(os.path.getsize(file_path))}"
                )

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

            if file_path.endswith('.mp4'):
                with open(file_path, 'rb') as video_file:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=video_file,
                        caption=f"📷 {title}\n\nحجم: {format_size(os.path.getsize(file_path))}"
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
        error_message = str(e)
        logger.error(f"Error processing {url}: {error_message}")
        if progress_message:
            await progress_message.edit_text(f"❌ خطا: {error_message}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.message:
        await update.message.reply_text("❌ خطایی در پردازش درخواست شما رخ داد. لطفا بعدا دوباره تلاش کنید.")

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_error_handler(error_handler)

    # Start the Bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
