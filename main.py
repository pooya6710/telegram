import os
import sys

# تنظیم متغیرهای محیطی مورد نیاز
telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "7338644071:AAEex9j0nMualdoywHSGFiBoMAzRpkFypPk")

# Add telegram-main directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "telegram-main"))

# یک نمونه ساده Flask بسازیم تا ربات تلگرام بتواند به صورت webhook کار کند
from flask import Flask, request
app = Flask(__name__)

@app.route('/')
def index():
    return "ربات دانلود فایل از یوتیوب و اینستاگرام"

@app.route('/healthy')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    # راه‌اندازی برنامه وب
    app.run(host="0.0.0.0", port=5000, debug=True)