import os
import logging
import time
import threading
from flask import Flask, jsonify
from bot import start_bot
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# تنظیم لاگ‌ها
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ایجاد اپلیکیشن Flask
app = Flask(__name__)

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

threading.Thread(target=run_bot, daemon=True).start()

# اجرای سرور Flask
if __name__ == "__main__":
    logger.info("🚀 راه‌اندازی سرور Flask...")
    app.run(host="0.0.0.0", port=8080)
