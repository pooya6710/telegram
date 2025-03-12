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
MAX_WORKERS = 4  # تعداد نخ‌ها برای دانلود همزمان

# تعداد تلاش‌های مجدد در صورت شکست
MAX_RETRIES = 3
RETRY_DELAY = 5  # ثانیه

# کارگر برای عملیات موازی
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)

# 📌 پاکسازی پوشه با حفظ فایل‌های جدید
def clear_folder(folder_path, max_files=5):
    files = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            files.append((file_path, os.path.getmtime(file_path)))
    
    # مرتب‌سازی بر اساس زمان تغییر (قدیمی‌ترین اول)
    files.sort(key=lambda x: x[1])
    
    # حذف فایل‌های قدیمی اگر تعداد از حد مجاز بیشتر است
    if len(files) > max_files:
        for file_path, _ in files[:-max_files]:
            try:
                os.unlink(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")

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

# 📌 استخراج لینک مستقیم ویدیو با کش
@lru_cache(maxsize=20)
def get_direct_video_url(link):
    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'noplaylist': True,
            'force_generic_extractor': False,
            'format': 'best[ext=mp4]/best',
            'socket_timeout': 30,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            return info.get('url', None)
    except Exception as e:
        notify_admin(f"⚠️ خطا در دریافت لینک مستقیم ویدیو: {str(e)}")
        return None

# 📌 دانلود ویدیو از اینستاگرام با کش
def download_instagram(link):
    # بررسی کش
    if link in RECENT_VIDEOS:
        if os.path.exists(RECENT_VIDEOS[link]):
            return RECENT_VIDEOS[link]
    
    try:
        # پاکسازی فایل‌های قدیمی، حفظ 5 فایل اخیر
        clear_folder(INSTAGRAM_FOLDER, 5)

        ydl_opts = {
            'outtmpl': f'{INSTAGRAM_FOLDER}/%(id)s.%(ext)s',
            'format': 'mp4/best[height<=720]/best',  # کیفیت متوسط برای سرعت بیشتر
            'quiet': True,
            'noplaylist': True,
            'socket_timeout': 30,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            video_path = f"{INSTAGRAM_FOLDER}/{info['id']}.mp4"
            
            # ذخیره در کش
            if os.path.exists(video_path):
                RECENT_VIDEOS[link] = video_path
                # محدود کردن اندازه کش
                if len(RECENT_VIDEOS) > MAX_CACHE_SIZE:
                    RECENT_VIDEOS.pop(next(iter(RECENT_VIDEOS)))
                return video_path
            return None

    except Exception as e:
        notify_admin(f"⚠️ خطا در دانلود ویدیو از اینستاگرام: {str(e)}")
        return None

# 📌 دانلود ویدیو از یوتیوب با کش
def download_youtube(link):
    # بررسی کش
    if link in RECENT_VIDEOS:
        if os.path.exists(RECENT_VIDEOS[link]):
            return RECENT_VIDEOS[link]
    
    try:
        # پاکسازی فایل‌های قدیمی، حفظ 5 فایل اخیر
        clear_folder(VIDEO_FOLDER, 5)

        ydl_opts = {
            'outtmpl': f'{VIDEO_FOLDER}/%(id)s.%(ext)s',
            'format': 'mp4/best[height<=720]/best',  # کیفیت متوسط برای سرعت بیشتر
            'quiet': True,
            'noplaylist': True,
            'socket_timeout': 30,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            video_path = f"{VIDEO_FOLDER}/{info['id']}.mp4"
            
            # ذخیره در کش
            if os.path.exists(video_path):
                RECENT_VIDEOS[link] = video_path
                # محدود کردن اندازه کش
                if len(RECENT_VIDEOS) > MAX_CACHE_SIZE:
                    RECENT_VIDEOS.pop(next(iter(RECENT_VIDEOS)))
                return video_path
            return None

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

# دستور شروع - با طراحی بهتر
@bot.message_handler(commands=['start'])
def handle_start(message):
    user = message.from_user
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("📚 راهنما", callback_data="help"),
        telebot.types.InlineKeyboardButton("🎬 دریافت ویدیو", callback_data="video_info")
    )
    markup.add(
        telebot.types.InlineKeyboardButton("🔍 جستجوی هشتگ", callback_data="hashtag_info")
    )
    
    bot.send_message(
        message.chat.id,
        f"سلام {user.first_name}! 👋\n\n"
        f"به ربات چندکاره خوش آمدید!\n\n"
        f"• لینک ویدیوی اینستاگرام یا یوتیوب را برای من ارسال کنید\n"
        f"• برای جستجوی هشتگ‌ها، کافیست #هشتگ را ارسال کنید\n"
        f"• از دکمه‌های زیر برای دسترسی سریع استفاده کنید:",
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
            "و به عنوان ادمین تنظیم گردد، سپس با دستور /add_channel آن را به لیست مانیتورینگ اضافه کنید.",
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

# 📩 مدیریت پیام‌های دریافتی - با پردازش بهتر
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
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
    """ارسال پینگ به ربات هر دقیقه برای جلوگیری از خاموش شدن"""
    import requests
    ping_url = f"https://api.telegram.org/bot{TOKEN}/getMe"
    ping_interval = 60  # هر دقیقه یکبار
    
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