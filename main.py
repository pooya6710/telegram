import os
import logging
import time
import threading
from flask import Flask, render_template, jsonify
from bot import setup_bot

# ⚙️ تنظیم سطح لاگ برای کاهش خروجی اضافی
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# کاهش سطح لاگ‌های غیرضروری
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# 🕸️ تنظیمات فلسک با بهینه‌سازی
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400  # کش 1 روزه برای فایل‌های استاتیک
app.config['TEMPLATES_AUTO_RELOAD'] = True  # در محیط توسعه

# 📊 وضعیت ربات با قابلیت بروزرسانی خودکار
bot_status = {
    "running": False,
    "error": None,
    "stats": {
        "videos_processed": 0,
        "youtube_downloads": 0,
        "instagram_downloads": 0,
        "response_count": 0
    },
    "start_time": time.time(),
    "last_update": time.time()
}

# 🚀 راه‌اندازی ربات تلگرام در هنگام شروع برنامه
token = os.environ.get("TELEGRAM_BOT_TOKEN")
if token:
    try:
        bot_running = setup_bot()
        if bot_running:
            bot_status["running"] = True
            logger.info("🤖 ربات با موفقیت راه‌اندازی شد!")
        else:
            bot_status["error"] = "ربات راه‌اندازی نشد"
            logger.error("⚠️ ربات راه‌اندازی نشد")
    except Exception as e:
        bot_status["error"] = str(e)
        logger.error(f"⚠️ خطا در راه‌اندازی ربات: {e}")
else:
    logger.warning("⚠️ توکن تلگرام یافت نشد. در حالت وب-فقط اجرا می‌شود.")
    bot_status["error"] = "توکن تلگرام موجود نیست"

# 🔄 بروزرسانی آمار ربات
def update_bot_stats():
    # بررسی پوشه‌های ویدیو
    youtube_folder = "videos"
    instagram_folder = "instagram_videos"
    
    # شمارش ویدیوها
    youtube_count = len(os.listdir(youtube_folder)) if os.path.exists(youtube_folder) else 0
    instagram_count = len(os.listdir(instagram_folder)) if os.path.exists(instagram_folder) else 0
    
    # بررسی تعداد پاسخ‌ها
    response_count = 0
    if os.path.exists("responses.json"):
        try:
            import json
            with open("responses.json", "r", encoding="utf-8") as f:
                response_count = len(json.load(f))
        except:
            pass
    
    # بررسی آمار هشتگ‌ها
    hashtag_count = 0
    registered_channels = 0
    hashtag_stats = {}
    if os.path.exists("hashtags.json"):
        try:
            import json
            with open("hashtags.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                hashtags = data.get("hashtags", {})
                hashtag_count = len(hashtags)
                registered_channels = len(data.get("channels", []))
                
                # پیدا کردن 5 هشتگ پرکاربرد
                sorted_hashtags = sorted(hashtags.items(), key=lambda x: len(x[1]), reverse=True)[:5]
                hashtag_stats = {tag: len(msgs) for tag, msgs in sorted_hashtags}
        except Exception as e:
            print(f"خطا در بارگذاری آمار هشتگ‌ها: {e}")
    
    # بروزرسانی آمار
    bot_status["stats"]["youtube_downloads"] = youtube_count
    bot_status["stats"]["instagram_downloads"] = instagram_count
    bot_status["stats"]["videos_processed"] = youtube_count + instagram_count
    bot_status["stats"]["response_count"] = response_count
    bot_status["stats"]["hashtag_count"] = hashtag_count
    bot_status["stats"]["registered_channels"] = registered_channels
    bot_status["stats"]["top_hashtags"] = hashtag_stats
    bot_status["last_update"] = time.time()

# 🏠 صفحه اصلی
@app.route('/')
def home():
    """صفحه اصلی داشبورد ربات"""
    # بروزرسانی آمار قبل از نمایش
    update_bot_stats()
    
    token_available = os.environ.get("TELEGRAM_BOT_TOKEN") is not None
    status_message = "فعال" if bot_status["running"] else "در انتظار توکن تلگرام"
    
    # محاسبه زمان آپتایم
    uptime_seconds = int(time.time() - bot_status["start_time"])
    days, remainder = divmod(uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime = f"{days} روز, {hours} ساعت, {minutes} دقیقه"
    
    # بررسی وضعیت پوشه‌ها و فایل‌ها
    video_folder_exists = os.path.exists("videos")
    instagram_folder_exists = os.path.exists("instagram_videos")
    responses_file_exists = os.path.exists("responses.json")
    hashtags_file_exists = os.path.exists("hashtags.json")
    
    # پردازش هشتگ‌های پرکاربرد برای نمودار
    top_hashtags = bot_status["stats"].get("top_hashtags", {})
    hashtag_labels = list(top_hashtags.keys())
    hashtag_values = list(top_hashtags.values())
    
    return render_template(
        'index.html', 
        bot_name="ربات چندکاره تلگرام",
        bot_status=status_message,
        token_available=token_available,
        error_message=bot_status["error"],
        video_folder_exists=video_folder_exists,
        instagram_folder_exists=instagram_folder_exists,
        responses_file_exists=responses_file_exists,
        hashtags_file_exists=hashtags_file_exists,
        stats=bot_status["stats"],
        uptime=uptime,
        hashtag_labels=hashtag_labels,
        hashtag_values=hashtag_values
    )

# 🔍 API برای دریافت وضعیت ربات
@app.route('/api/status')
def api_status():
    """API برای دریافت وضعیت ربات"""
    update_bot_stats()
    return jsonify({
        "status": "active" if bot_status["running"] else "inactive",
        "uptime": int(time.time() - bot_status["start_time"]),
        "stats": bot_status["stats"],
        "error": bot_status["error"]
    })

# 🩺 سلامت سرور
@app.route('/ping')
def ping():
    """بررسی سلامت سرور"""
    return "ربات فعال است!", 200

# 🚀 تابع اجرای سرور فلسک
def run_flask():
    """اجرای سرور وب فلسک"""
    # از حالت دیباگ در محیط تولید استفاده نمی‌کنیم
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host='0.0.0.0', port=5000, debug=debug_mode, threaded=True)

# ورودی اصلی برنامه
if __name__ == "__main__":
    logger.info("🌐 شروع سرور وب...")
    run_flask()
