import os
import sys
import telebot
import logging
import time
import signal
import json
from datetime import datetime
import psutil
import traceback

# تنظیم سیستم لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("توکن ربات تنظیم نشده است")
    sys.exit(1)
bot = telebot.TeleBot(TOKEN)

def kill_other_bot_instances():
    """حذف سایر نمونه‌های در حال اجرای ربات"""
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] != current_pid:
                cmdline = proc.info['cmdline']
                if cmdline and 'python' in cmdline[0] and 'run_bot.py' in ' '.join(cmdline):
                    proc.terminate()
                    logger.info(f"نمونه قبلی ربات با PID {proc.info['pid']} متوقف شد")
                    time.sleep(1)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def initialize_bot():
    """راه‌اندازی نمونه ربات با مدیریت خطا"""
    global bot
    try:
        # حذف سایر نمونه‌های ربات
        kill_other_bot_instances()

        # حذف وب‌هوک‌های قبلی
        temp_bot = telebot.TeleBot(TOKEN)
        temp_bot.remove_webhook()
        time.sleep(0.5)

        # ایجاد نمونه جدید ربات
        bot = telebot.TeleBot(TOKEN)
        logger.info("ربات با موفقیت راه‌اندازی شد")
        return True
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}")
        return False

def cleanup_resources():
    """پاکسازی منابع قبل از خروج"""
    try:
        # حذف فایل قفل
        if os.path.exists("bot.lock"):
            try:
                with open("bot.lock", "r") as f:
                    lock_data = json.load(f)
                    if lock_data.get("pid") == os.getpid():
                        os.remove("bot.lock")
                        logger.info("فایل قفل حذف شد")
            except:
                os.remove("bot.lock")
                logger.info("فایل قفل با خطا حذف شد")

    except Exception as e:
        logger.error(f"خطا در پاکسازی منابع: {e}")

def handle_termination(signum, frame):
    """مدیریت سیگنال‌های خاتمه"""
    logger.info(f"سیگنال {signum} دریافت شد")
    cleanup_resources()
    sys.exit(0)

def create_process_lock():
    """ایجاد و مدیریت فایل قفل با مدیریت خطا"""
    try:
        pid = os.getpid()
        lock_data = {
            "pid": pid,
            "start_time": datetime.now().isoformat(),
            "token_hash": hash(TOKEN)
        }

        with open("bot.lock", "w") as f:
            json.dump(lock_data, f)

        logger.info(f"فایل قفل با PID {pid} ایجاد شد")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد فایل قفل: {e}")
        return False

def check_instagram_url_direct(url: str) -> bool:
    """بررسی اینکه آیا آدرس مربوط به اینستاگرام است یا خیر (روش قدیمی)"""
    return 'instagram.com' in url and ('/p/' in url or '/reel/' in url or '/tv/' in url)

def process_instagram_download(message, url: str):
    """دانلود محتوا از اینستاگرام (روش قدیمی با instaloader مستقیم)"""
    try:
        # ارسال پیام در حال پردازش
        debug_msg = bot.reply_to(message, "🔄 در حال پردازش لینک اینستاگرام...")
        
        # استفاده از instaloader برای دانلود
        import instaloader
        from datetime import datetime
        
        # ایجاد یک نمونه از Instaloader
        L = instaloader.Instaloader(
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False
        )
        
        # تلاش برای استخراج کد پست از URL
        import re
        shortcode = None
        match = re.search(r'instagram.com/(?:p|reel|tv)/([^/?]+)', url)
        if match:
            shortcode = match.group(1)
            
        if not shortcode:
            bot.edit_message_text("❌ لینک اینستاگرام نامعتبر است", message.chat.id, debug_msg.message_id)
            return
            
        # تغییر پیام وضعیت
        bot.edit_message_text("⏳ در حال دانلود از اینستاگرام...", message.chat.id, debug_msg.message_id)
        
        # ایجاد مسیر ذخیره‌سازی موقت
        temp_dir = f"temp_downloads/instagram_{shortcode}_{int(datetime.now().timestamp())}"
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # دانلود پست
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            L.download_post(post, target=temp_dir)
            
            # یافتن فایل‌های دانلود شده
            media_files = []
            for file in os.listdir(temp_dir):
                if file.endswith(('.jpg', '.mp4', '.mov')):
                    media_files.append(os.path.join(temp_dir, file))
            
            if not media_files:
                bot.edit_message_text("⚠️ هیچ فایل رسانه‌ای در این پست یافت نشد", message.chat.id, debug_msg.message_id)
                return
                
            # بررسی نوع فایل (تصویر یا ویدیو) و ارسال آن
            bot.edit_message_text("📤 در حال ارسال فایل...", message.chat.id, debug_msg.message_id)
            
            for file_path in media_files:
                if file_path.endswith(('.mp4', '.mov')):
                    # ارسال ویدیو
                    with open(file_path, 'rb') as video_file:
                        bot.send_video(
                            message.chat.id, 
                            video_file,
                            caption=f"✅ دانلود شد از اینستاگرام\n👤 {post.owner_username}"
                        )
                else:
                    # ارسال تصویر
                    with open(file_path, 'rb') as photo_file:
                        bot.send_photo(
                            message.chat.id, 
                            photo_file,
                            caption=f"✅ دانلود شد از اینستاگرام\n👤 {post.owner_username}"
                        )
            
            # حذف پیام پردازش
            bot.delete_message(message.chat.id, debug_msg.message_id)
            
        except instaloader.exceptions.ProfileNotExistsException:
            bot.edit_message_text("❌ پروفایل مورد نظر وجود ندارد", message.chat.id, debug_msg.message_id)
        except instaloader.exceptions.PrivateProfileNotFollowedException:
            bot.edit_message_text("❌ این پروفایل خصوصی است و شما آن را دنبال نمی‌کنید", message.chat.id, debug_msg.message_id)
        except instaloader.exceptions.LoginRequiredException:
            bot.edit_message_text("❌ برای دانلود این محتوا نیاز به ورود به حساب کاربری است", message.chat.id, debug_msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"❌ خطا در دانلود: {str(e)}", message.chat.id, debug_msg.message_id)
        finally:
            # پاکسازی فایل‌های موقت
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                
    except Exception as e:
        logger.error(f"خطا در پردازش لینک اینستاگرام: {str(e)}\n{traceback.format_exc()}")
        try:
            bot.reply_to(message, f"⚠️ خطایی رخ داد: {str(e)}")
        except:
            pass

def is_instagram_url(url: str) -> bool:
    """بررسی اینکه آیا آدرس مربوط به اینستاگرام است یا خیر"""
    return 'instagram.com' in url and ('/p/' in url or '/reel/' in url or '/tv/' in url)

def process_instagram_url(message, url):
    """پردازش لینک اینستاگرام و دانلود آن"""
    try:
        from instagram_downloader import InstagramDownloader
        
        # ارسال پیام در حال پردازش
        debug_msg = bot.reply_to(message, "🔄 در حال پردازش لینک اینستاگرام...")
        
        # ایجاد دایرکتوری temp_downloads اگر وجود ندارد
        temp_dir = "temp_downloads"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
            
        # دانلود محتوا از اینستاگرام
        bot.edit_message_text("⏳ در حال دانلود از اینستاگرام...", message.chat.id, debug_msg.message_id)
        
        # ایجاد نمونه دانلودر
        downloader = InstagramDownloader(temp_dir)
        
        # استفاده از دانلودر برای دانلود محتوا (بصورت async)
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        file_path, caption = loop.run_until_complete(downloader.download(url))
        
        # بررسی نوع فایل و ارسال آن
        bot.edit_message_text("📤 در حال ارسال فایل...", message.chat.id, debug_msg.message_id)
        
        # ارسال ویدیو یا تصویر بر اساس پسوند فایل
        if file_path.endswith(('.mp4', '.mov')):
            with open(file_path, 'rb') as video_file:
                bot.send_video(
                    message.chat.id, 
                    video_file,
                    caption=f"✅ دانلود شد از اینستاگرام\n👤 {caption}"
                )
        else:  # ارسال تصویر یا ویدیو کوتاه به عنوان ویدیو
            with open(file_path, 'rb') as media_file:
                bot.send_video(
                    message.chat.id, 
                    media_file,
                    caption=f"✅ دانلود شد از اینستاگرام\n👤 {caption}"
                )
        
        # پاکسازی فایل‌های موقت
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            # پاکسازی پوشه والد
            parent_dir = os.path.dirname(file_path)
            if os.path.exists(parent_dir) and parent_dir != temp_dir:
                import shutil
                shutil.rmtree(parent_dir, ignore_errors=True)
        except Exception as e:
            logger.error(f"خطا در پاکسازی فایل‌های موقت: {str(e)}")
        
        # حذف پیام "در حال پردازش"
        bot.delete_message(message.chat.id, debug_msg.message_id)
        
    except ValueError as e:
        # خطاهای قابل پیش‌بینی (مانند لینک نامعتبر)
        error_message = str(e)
        if debug_msg:
            bot.edit_message_text(f"❌ {error_message}", message.chat.id, debug_msg.message_id)
        else:
            bot.reply_to(message, f"❌ {error_message}")
    except Exception as e:
        # سایر خطاها
        logger.error(f"خطا در پردازش لینک اینستاگرام: {str(e)}\n{traceback.format_exc()}")
        error_message = str(e)
        if "No module named 'instaloader'" in error_message:
            error_message = "ماژول instaloader نصب نیست. لطفا با ادمین تماس بگیرید."
        
        if debug_msg:
            bot.edit_message_text(f"⚠️ خطای سیستمی: {error_message}", message.chat.id, debug_msg.message_id)
        else:
            bot.reply_to(message, f"⚠️ خطای سیستمی: {error_message}")

def setup_bot_handlers():
    """تنظیم هندلرهای ربات"""
    @bot.message_handler(func=lambda message: is_instagram_url(message.text))
    def instagram_link_handler(message):
        """پردازش لینک‌های اینستاگرام"""
        try:
            url = message.text.strip()
            process_instagram_url(message, url)
        except Exception as e:
            logger.error(f"Error processing Instagram link: {str(e)}\n{traceback.format_exc()}")
            bot.reply_to(message, f"⚠️ خطا در پردازش لینک اینستاگرام: {str(e)}")

    @bot.message_handler(func=lambda message: 'youtube.com' in message.text or 'youtu.be' in message.text)
    def youtube_link_handler(message):
        try:
            debug_msg = None  # تعریف متغیر قبل از استفاده برای جلوگیری از خطا
            
            try:
                # ابتدا سعی می‌کنیم از ماژول youtube_downloader در همان پوشه استفاده کنیم
                import sys
                sys.path.append('.')  # اطمینان از وجود مسیر فعلی در sys.path
                from youtube_downloader import download_video, validate_youtube_url, extract_video_info
                
                # ارسال پیام در حال پردازش
                debug_msg = bot.reply_to(message, "🔄 در حال پردازش لینک یوتیوب...")
                
                url = message.text.strip()
                if not validate_youtube_url(url):
                    bot.edit_message_text("❌ لینک یوتیوب نامعتبر است", message.chat.id, debug_msg.message_id)
                    return

                video_info = extract_video_info(url)
                if not video_info:
                    bot.edit_message_text("❌ خطا در دریافت اطلاعات ویدیو", message.chat.id, debug_msg.message_id)
                    return

                bot.edit_message_text("⏳ در حال دانلود ویدیو...", message.chat.id, debug_msg.message_id)
                success, file_path, error = download_video(url, int(time.time()), message.from_user.id)

                if success and file_path:
                    with open(file_path, 'rb') as video_file:
                        bot.send_video(message.chat.id, video_file, caption=f"✅ دانلود شد\n🎥 {video_info.get('title', '')}")
                    os.remove(file_path)  # پاک کردن فایل پس از ارسال
                else:
                    error_msg = error.get('error', 'خطای نامشخص') if error else 'خطای نامشخص'
                    bot.edit_message_text(f"❌ {error_msg}", message.chat.id, debug_msg.message_id)
                    
            except ImportError as import_error:
                # اگر نتوانستیم ماژول را وارد کنیم، یک پیام ساده برمی‌گردانیم
                logger.error(f"خطا در وارد کردن ماژول youtube_downloader: {str(import_error)}")
                if debug_msg:
                    bot.edit_message_text("⚠️ این قابلیت در حال حاضر در دسترس نیست.", message.chat.id, debug_msg.message_id)
                else:
                    debug_msg = bot.reply_to(message, "⚠️ این قابلیت در حال حاضر در دسترس نیست.")

        except Exception as e:
            error_msg = str(e)
            detailed_error = traceback.format_exc()
            logger.error(f"Error processing YouTube link: {detailed_error}")

            error_response = "❌ خطا در پردازش لینک یوتیوب. لطفا دوباره تلاش کنید."
            
            # اگر پیام در حال پردازش داریم، آن را ویرایش می‌کنیم
            if debug_msg:
                try:
                    bot.edit_message_text(error_response, message.chat.id, debug_msg.message_id)
                except:
                    bot.reply_to(message, error_response)
            else:
                # اگر نداریم، یک پیام جدید می‌فرستیم
                bot.reply_to(message, error_response)

    @bot.message_handler(commands=['start'])
    def handle_start(message):
        try:
            markup = telebot.types.InlineKeyboardMarkup(row_width=2)
            help_btn = telebot.types.InlineKeyboardButton("📚 راهنما", callback_data="help")
            quality_btn = telebot.types.InlineKeyboardButton("📊 کیفیت ویدیو", callback_data="quality")
            status_btn = telebot.types.InlineKeyboardButton("📈 وضعیت سرور", callback_data="status")

            markup.add(help_btn, quality_btn)
            markup.add(status_btn)

            bot.reply_to(message, 
                "👋 سلام!\n\n"
                "🎬 به ربات دانلود ویدیو خوش آمدید.\n\n"
                "🔸 قابلیت‌های ربات:\n"
                "• دانلود ویدیو از یوتیوب و اینستاگرام\n"
                "• امکان انتخاب کیفیت ویدیو\n"
                "• نمایش وضعیت سرور\n\n"
                "🔹 روش استفاده:\n"
                "• برای دانلود ویدیو، لینک را ارسال کنید\n"
                "• برای تنظیم کیفیت، از دکمه کیفیت ویدیو استفاده کنید\n"
                "• برای مشاهده وضعیت، دکمه وضعیت سرور را بزنید",
                reply_markup=markup
            )
            logger.info(f"دستور start برای کاربر {message.from_user.id} اجرا شد")
        except Exception as e:
            logger.error(f"خطا در اجرای دستور start: {e}")
            bot.reply_to(message, "⚠️ خطایی رخ داد. لطفا دوباره تلاش کنید.")

    @bot.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        try:
            if call.data == "help":
                bot.answer_callback_query(call.id)
                bot.reply_to(call.message, "🔹 راهنمای استفاده از ربات:\n• برای دانلود ویدیو، لینک را ارسال کنید\n• برای تنظیم کیفیت، از منوی کیفیت ویدیو استفاده کنید")
            elif call.data == "quality":
                bot.answer_callback_query(call.id)
                bot.reply_to(call.message, "📊 کیفیت‌های موجود: 144p, 240p, 360p, 480p, 720p, 1080p")
            elif call.data == "status":
                from server_status import generate_server_status
                try:
                    bot.answer_callback_query(call.id)
                    status_text = generate_server_status()
                    bot.edit_message_text(
                        status_text,
                        call.message.chat.id,
                        call.message.message_id,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"خطا در نمایش وضعیت سرور: {e}")
                    bot.answer_callback_query(call.id, "⚠️ خطا در دریافت وضعیت سرور")
        except Exception as e:
            logger.error(f"خطا در پردازش callback: {e}")
            try:
                bot.answer_callback_query(call.id, "⚠️ خطایی رخ داد")
            except:
                pass

def generate_server_status():
    #  This function needs to be implemented to get the actual server status.
    #  Replace this with your logic to check server resources, etc.
    return "📈 سرور در حال اجرا است.  CPU: 50%, Memory: 75%"


# انتقال از debug_handler که ممکن است وجود نداشته باشد
try:
    from debug_handler import debugger
except ImportError:
    # اگر ماژول وجود نداشت، یک شیء ساده برای جلوگیری از خطا ایجاد می‌کنیم
    class SimpleDebugger:
        def debug(self, msg): 
            logger.debug(msg)
        def info(self, msg): 
            logger.info(msg)
        def warning(self, msg): 
            logger.warning(msg)
        def error(self, msg): 
            logger.error(msg)
    debugger = SimpleDebugger()

def main():
    """تابع اصلی اجرای ربات"""
    global bot
    try:
        logger.info("شروع راه‌اندازی ربات...")

        # تنظیم مدیریت خطای سراسری
        def handle_exception(exc_type, exc_value, exc_traceback):
            logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

        sys.excepthook = handle_exception

        # ایجاد نمونه جدید ربات
        bot = telebot.TeleBot(TOKEN)

        # تنظیم هندلرهای ربات
        setup_bot_handlers()

        # تست اتصال
        bot.get_me()
        logger.info("ربات با موفقیت به سرور تلگرام متصل شد")

        # راه‌اندازی ربات با تنظیمات بهینه
        bot.infinity_polling(timeout=60, long_polling_timeout=60)

    except Exception as e:
        logger.error(f"خطا در اجرای ربات: {str(e)}")
        logger.info("تلاش مجدد برای اتصال در 10 ثانیه...")
        time.sleep(10)
        main()  # تلاش مجدد

if __name__ == "__main__":
    main()