
import os
import sys
import json
import time
import datetime
import threading
import concurrent.futures
import logging
import traceback
import platform
from requests.exceptions import ReadTimeout, ProxyError, ConnectionError

# تنظیم لاگر اصلی
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# واردکردن ماژول‌های خارجی
try:
    import telebot
    from telebot import types
    import psutil
    import shutil
    from yt_dlp import YoutubeDL
    from flask import Flask, request, jsonify
except ImportError as e:
    logger.error(f"خطا در واردکردن ماژول‌ها: {e}")
    sys.exit(1)

# دریافت توکن از متغیرهای محیطی
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    logger.error("توکن تلگرام تنظیم نشده است")
    sys.exit(1)

# ایجاد نمونه‌های اصلی
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# تنظیمات اصلی
ADMIN_CHAT_ID = 286420965
VIDEO_FOLDER = "videos"
INSTAGRAM_FOLDER = "instagram_videos"
os.makedirs(VIDEO_FOLDER, exist_ok=True)
os.makedirs(INSTAGRAM_FOLDER, exist_ok=True)

# کیفیت‌های ویدیو
VIDEO_QUALITIES = {
    "144p": {"format": "160/17/18/597", "description": "کیفیت پایین (144p)"},
    "240p": {"format": "133+140/242+140/243+140/134+140/18", "description": "کیفیت معمولی (240p)"},
    "360p": {"format": "134+140/243+140/18/597/22", "description": "کیفیت متوسط (360p)"},
    "480p": {"format": "135+140/244+140/247+140/22", "description": "کیفیت خوب (480p)"},
    "720p": {"format": "136+140/247+140/22", "description": "کیفیت عالی (720p)"},
    "1080p": {"format": "137+140/248+140/22", "description": "کیفیت HD (1080p)"}
}

DEFAULT_VIDEO_QUALITY = "240p"

# دستور شروع
@bot.message_handler(commands=['start'])
def start_command(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    help_btn = telebot.types.InlineKeyboardButton("📚 راهنما", callback_data="help")
    quality_btn = telebot.types.InlineKeyboardButton("📊 کیفیت ویدیو", callback_data="select_quality")
    markup.add(help_btn, quality_btn)
    
    bot.reply_to(
        message,
        "👋 سلام! به ربات دانلود ویدیو خوش آمدید.\n\n"
        "🎥 می‌توانید لینک ویدیوهای یوتیوب و اینستاگرام را برای من ارسال کنید.",
        reply_markup=markup
    )

# دستور راهنما
@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(
        message,
        "📚 راهنمای استفاده:\n\n"
        "1️⃣ لینک ویدیو را ارسال کنید\n"
        "2️⃣ کیفیت مورد نظر را انتخاب کنید\n"
        "3️⃣ صبر کنید تا ویدیو دانلود و ارسال شود\n\n"
        "⚡️ دستورات:\n"
        "/start - شروع مجدد\n"
        "/help - نمایش راهنما\n"
        "/quality - تنظیم کیفیت"
    )

# مدیریت پیام‌های دریافتی
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if "youtube.com" in message.text or "youtu.be" in message.text:
        process_youtube_link(message)
    elif "instagram.com" in message.text:
        process_instagram_link(message)
    else:
        bot.reply_to(message, "❌ لینک معتبر نیست. لطفاً لینک یوتیوب یا اینستاگرام ارسال کنید.")

# پردازش لینک یوتیوب
def process_youtube_link(message):
    processing_msg = bot.reply_to(message, "⏳ در حال دانلود ویدیو...")
    try:
        with YoutubeDL() as ydl:
            info = ydl.extract_info(message.text, download=False)
            video_url = info['url']
            title = info.get('title', 'ویدیو')
            
            bot.edit_message_text(
                "✅ ویدیو یافت شد! در حال ارسال...",
                message.chat.id,
                processing_msg.message_id
            )
            
            bot.send_video(
                message.chat.id,
                video_url,
                caption=f"🎬 {title}\n\n🔗 {message.text}"
            )
    except Exception as e:
        bot.edit_message_text(
            f"❌ خطا در دانلود: {str(e)}",
            message.chat.id,
            processing_msg.message_id
        )

# پردازش لینک اینستاگرام
def process_instagram_link(message):
    processing_msg = bot.reply_to(message, "⏳ در حال دانلود ویدیو...")
    try:
        with YoutubeDL() as ydl:
            info = ydl.extract_info(message.text, download=False)
            video_url = info['url']
            
            bot.edit_message_text(
                "✅ ویدیو یافت شد! در حال ارسال...",
                message.chat.id,
                processing_msg.message_id
            )
            
            bot.send_video(
                message.chat.id,
                video_url,
                caption=f"📱 ویدیوی اینستاگرام\n\n🔗 {message.text}"
            )
    except Exception as e:
        bot.edit_message_text(
            f"❌ خطا در دانلود: {str(e)}",
            message.chat.id,
            processing_msg.message_id
        )

# مدیریت کالبک‌ها
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "help":
        help_command(call.message)
    elif call.data == "select_quality":
        show_quality_options(call.message)
    elif call.data.startswith("quality_"):
        set_quality(call)

def show_quality_options(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    for quality in VIDEO_QUALITIES:
        btn = telebot.types.InlineKeyboardButton(
            quality,
            callback_data=f"quality_{quality}"
        )
        markup.add(btn)
    
    bot.edit_message_text(
        "📊 کیفیت مورد نظر را انتخاب کنید:",
        message.chat.id,
        message.message_id,
        reply_markup=markup
    )

def set_quality(call):
    quality = call.data.replace("quality_", "")
    if not hasattr(bot, "user_quality"):
        bot.user_quality = {}
    bot.user_quality[call.from_user.id] = quality
    
    bot.answer_callback_query(
        call.id,
        f"✅ کیفیت {quality} انتخاب شد"
    )

# مسیر وب‌هوک
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'OK'

# تابع اصلی
def main():
    logger.info("🤖 ربات در حال راه‌اندازی...")
    
    if os.environ.get('WEBHOOK_ENABLED', 'false').lower() == 'true':
        webhook_url = os.environ.get('WEBHOOK_URL')
        if webhook_url:
            bot.remove_webhook()
            bot.set_webhook(url=webhook_url + TOKEN)
            return app
    else:
        bot.remove_webhook()
        bot.polling(none_stop=True)

if __name__ == "__main__":
    main()
