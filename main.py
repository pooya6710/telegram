import os
import logging
import time
import threading
from flask import Flask, jsonify
from bot import start_bot  # ایمپورت تابعی که ربات را اجرا می‌کند

# ایجاد اپلیکیشن Flask
app = Flask(__name__)

# تنظیم لاگ‌ها
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# وضعیت ربات
bot_status = {
    "running": False,
    "start_time": time.time()
}

# بروزرسانی آمار ربات
def update_bot_status():
    uptime_seconds = int(time.time() - bot_status["start_time"])
    bot_status["uptime"] = f"{uptime_seconds // 3600} ساعت و {uptime_seconds % 3600 // 60} دقیقه"

# صفحه اصلی داشبورد
@app.route('/')
def home():
    update_bot_status()
    return jsonify({
        "status": "✅ ربات فعال است" if bot_status["running"] else "❌ ربات متوقف است",
        "uptime": bot_status["uptime"]
    })

# بررسی سلامت سرور
@app.route('/ping')
def ping():
    return "سرور فعال است!", 200

# اجرای ربات در یک ترد جداگانه
def run_bot():
    bot_status["running"] = True
    start_bot()  # اجرای ربات

from bot import app  # ایمپورت سرور Flask

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# اجرای سرور Flask
if __name__ == "__main__":
    logger.info("🚀 راه‌اندازی سرور Flask...")
    port = int(os.environ.get("PORT", 8080))  # استفاده از پورت متغیر محیطی
    app.run(host="0.0.0.0", port=port)
