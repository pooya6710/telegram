import telebot
import os
import shutil  # برای دریافت وضعیت دیسک
import psutil  # برای دریافت اطلاعات CPU و RAM
import platform  # برای دریافت اطلاعات سیستم‌عامل
import json
import sqlite3
import datetime
import threading
from flask import Flask, request
import time
import traceback
from yt_dlp import YoutubeDL
from requests.exceptions import ReadTimeout, ProxyError, ConnectionError

app = Flask(__name__)


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode("UTF-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        print(f"❌ خطا در دریافت پیام: {e}")
    return "✅ Webhook دریافت شد!", 200


SERVER_CACHE = {"status": None, "timestamp": None}


def get_cached_server_status():
    global SERVER_CACHE
    if SERVER_CACHE["status"] and (datetime.datetime.now() -
                                   SERVER_CACHE["timestamp"]).seconds < 600:
        return SERVER_CACHE["status"]

    if os.path.exists("server_status.json"):
        try:
            with open("server_status.json", "r", encoding="utf-8") as file:
                data = json.load(file)
                SERVER_CACHE["status"] = data["status"]
                SERVER_CACHE["timestamp"] = datetime.datetime.strptime(
                    data["timestamp"], "%Y-%m-%d %H:%M:%S")
                return data["status"]
        except Exception:
            return None
    return None


MESSAGES_DB_TEXT = "channel_messages.json"
MESSAGES_DB_LINKS = "channel_links.json"
MAX_MESSAGES = 100000  # حداکثر تعداد لینک‌های ذخیره‌شده

# 📂 اگر فایل ذخیره‌ی پیام‌ها وجود نداشت، ایجادش کن
if not os.path.exists(MESSAGES_DB_LINKS):
    with open(MESSAGES_DB_LINKS, "w", encoding="utf-8") as file:
        json.dump({}, file, ensure_ascii=False, indent=4)

# 🔑 توکن ربات تلگرام
TOKEN = '7338644071:AAEex9j0nMualdoywHSGFiBoMAzRpkFypPk'
bot = telebot.TeleBot(TOKEN)

# 📢 آیدی عددی ادمین
ADMIN_CHAT_ID = 286420965

# 📂 مسیر ذخیره ویدیوها
VIDEO_FOLDER = "videos"
INSTAGRAM_FOLDER = "instagram_videos"
os.makedirs(VIDEO_FOLDER, exist_ok=True)
os.makedirs(INSTAGRAM_FOLDER, exist_ok=True)


# 📌 بررسی وضعیت سرور
@bot.message_handler(commands=["server_status"])
def server_status(message):
    try:
        cached_status = get_cached_server_status()
        if cached_status:
            bot.send_message(message.chat.id,
                             cached_status,
                             parse_mode="Markdown")
            return

        # اطلاعات دیسک
        total, used, free = shutil.disk_usage("/")
        total_gb = total / (1024**3)
        used_gb = used / (1024**3)
        free_gb = free / (1024**3)

        # مصرف CPU و RAM
        cpu_usage = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_used = ram.used / (1024**3)
        ram_total = ram.total / (1024**3)

        # مدت زمان روشن بودن سرور
        uptime_seconds = time.time() - psutil.boot_time()
        uptime_hours = uptime_seconds // 3600
        uptime_minutes = (uptime_seconds % 3600) // 60

        status_msg = (f"📊 **وضعیت سرور:**\n"
                      f"🔹 **CPU:** `{cpu_usage}%`\n"
                      f"🔹 **RAM:** `{ram_used:.2f}GB / {ram_total:.2f}GB`\n"
                      f"🔹 **فضای باقی‌مانده:** `{free_gb:.2f}GB`\n"
                      f"🔹 **مدت روشن بودن:** `{int(uptime_hours)} ساعت`\n")

        # ذخیره وضعیت سرور در یک فایل JSON برای کش کردن
        with open("server_status.json", "w", encoding="utf-8") as file:
            json.dump(
                {
                    "timestamp":
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status":
                    status_msg
                }, file)

        bot.send_message(message.chat.id, status_msg, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, "⚠ خطا در دریافت وضعیت سرور!")


# 📂 مدیریت پاسخ‌های متنی
def load_responses():
    try:
        with open("responses.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_responses():
    with open("responses.json", "w", encoding="utf-8") as file:
        json.dump(responses, file, ensure_ascii=False, indent=4)


responses = load_responses()


# 📌 استخراج لینک مستقیم ویدیو بدون دانلود
def get_direct_video_url(link):
    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'noplaylist': True,
            'force_generic_extractor': False,
            'format': 'best[ext=mp4]/best',
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            return info.get('url', None)
    except Exception as e:
        notify_admin(
            f"⚠️ خطا در دریافت لینک مستقیم ویدیو:\n{traceback.format_exc()}")
        return None


# 📌 دانلود ویدیو از اینستاگرام
def download_instagram(link):
    try:
        clear_folder(INSTAGRAM_FOLDER)  # حذف فایل‌های قدیمی

        ydl_opts = {
            'outtmpl': f'{INSTAGRAM_FOLDER}/%(id)s.%(ext)s',
            'format': 'mp4/best',
            'quiet': False,
            'noplaylist': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            video_path = f"{INSTAGRAM_FOLDER}/{info['id']}.mp4"
            return video_path if os.path.exists(video_path) else None

    except Exception as e:
        notify_admin(
            f"⚠️ خطا در دانلود ویدیو از اینستاگرام:\n{traceback.format_exc()}")
        return None


# 📌 دانلود ویدیو از یوتیوب
def download_youtube(link):
    try:
        clear_folder(VIDEO_FOLDER)  # حذف فایل‌های قدیمی

        ydl_opts = {
            'outtmpl': f'{VIDEO_FOLDER}/%(id)s.%(ext)s',
            'format': 'mp4/best',
            'quiet': False,
            'noplaylist': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            video_path = f"{VIDEO_FOLDER}/{info['id']}.mp4"
            return video_path if os.path.exists(video_path) else None

    except Exception as e:
        notify_admin(
            f"⚠️ خطا در دانلود ویدیو از یوتیوب:\n{traceback.format_exc()}")
        return None


# 📢 ارسال پیام به ادمین در صورت وقوع خطا
def notify_admin(message):
    try:
        bot.send_message(ADMIN_CHAT_ID, message[:4000])
    except Exception as e:
        print(f"⚠️ خطا در ارسال پیام به ادمین: {e}")


# 📩 مدیریت پیام‌های دریافتی
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        text = message.text.strip()

        if "instagram.com" in text or "youtube.com" in text or "youtu.be" in text:
            direct_url = get_direct_video_url(text)
            if direct_url:
                bot.send_video(chat_id=message.chat.id, video=direct_url)
            else:
                video_path = download_instagram(
                    text) if "instagram.com" in text else download_youtube(
                        text)
                if video_path and os.path.exists(video_path):
                    send_video_with_handling(message.chat.id, video_path)
                else:
                    bot.reply_to(
                        message,
                        "⚠️ ویدیوی موردنظر دانلود نشد. لطفاً لینک را بررسی کنید."
                    )
            return

        elif "،" in text:
            try:
                question, answer = map(str.strip, text.split("،", 1))
                responses[question.lower()] = answer
                save_responses()
                bot.reply_to(
                    message,
                    f"✅ سوال '{question}' با پاسخ '{answer}' اضافه شد!")
            except ValueError:
                bot.reply_to(message,
                             "⚠️ لطفاً فرمت 'سوال، جواب' را رعایت کنید.")
            return

        else:
            key = text.lower()
            if key in responses:
                bot.reply_to(message, responses[key])

    except Exception as e:
        notify_admin(f"⚠️ خطا در پردازش پیام:\n{traceback.format_exc()}")


def keep_awake():
    while True:
        # بررسی مقدار استفاده از CPU
        cpu_usage = psutil.cpu_percent(interval=1)
        if cpu_usage < 5:  # اگر پردازش تقریباً غیرفعال شد، یک عملیات کوچک انجام بده
            print("✅ جلوگیری از خوابیدن ربات با افزایش پردازش")
            _ = [x**2 for x in range(10000)]  # انجام یک پردازش کوچک

        time.sleep(300)  # ⏳ هر 5 دقیقه یک‌بار بررسی شود


# اجرای تابع در یک ترد جداگانه
threading.Thread(target=keep_awake, daemon=True).start()
LAST_USAGE = {"cpu": 0, "ram": 0}
high_usage_alert = {"cpu": False, "ram": False}  # وضعیت هشدار CPU و RAM


def monitor_server():
    global LAST_USAGE, high_usage_alert
    while True:
        cpu_usage = psutil.cpu_percent(interval=1)
        ram_usage = psutil.virtual_memory().percent

        # اگر CPU بالای ۸۰٪ باشد و قبلاً هشدار نداده باشد
        if cpu_usage > 80:
            if not high_usage_alert["cpu"]:
                time.sleep(300)  # بررسی مجدد بعد از 5 دقیقه
                cpu_recheck = psutil.cpu_percent(interval=1)
                if cpu_recheck > 80:  # هنوز بالای ۸۰٪ است
                    bot.send_message(
                        ADMIN_CHAT_ID,
                        f"⚠ **هشدار: مصرف CPU بالای ۸۰٪ باقی مانده!**\n🔹 **CPU:** {cpu_recheck}%"
                    )
                    high_usage_alert["cpu"] = True  # ثبت هشدار
        else:
            high_usage_alert[
                "cpu"] = False  # اگر CPU کاهش یافت، هشدار را ریست کن

        # اگر RAM بالای ۸۰٪ باشد و قبلاً هشدار نداده باشد
        if ram_usage > 80:
            if not high_usage_alert["ram"]:
                time.sleep(300)  # بررسی مجدد بعد از 5 دقیقه
                ram_recheck = psutil.virtual_memory().percent
                if ram_recheck > 80:  # هنوز بالای ۸۰٪ است
                    bot.send_message(
                        ADMIN_CHAT_ID,
                        f"⚠ **هشدار: مصرف RAM بالای ۸۰٪ باقی مانده!**\n🔹 **RAM:** {ram_recheck}%"
                    )
                    high_usage_alert["ram"] = True  # ثبت هشدار
        else:
            high_usage_alert[
                "ram"] = False  # اگر RAM کاهش یافت، هشدار را ریست کن

        LAST_USAGE["cpu"] = cpu_usage
        LAST_USAGE["ram"] = ram_usage

        time.sleep(60)  # هر ۱ دقیقه بررسی شود


threading.Thread(target=monitor_server, daemon=True).start()


# 🔄 اجرای ایمن ربات
def safe_polling():
    while True:
        try:
            bot.polling(none_stop=True, interval=15,
                        timeout=30)  # ⬅ افزایش timeout برای کاهش مصرف CPU
        except (ReadTimeout, ProxyError, ConnectionResetError):
            time.sleep(
                30)  # ⬅ جلوگیری از درخواست‌های مکرر در صورت قطع شدن ارتباط
        except Exception as e:
            notify_admin(
                f"⚠️ خطای بحرانی در اجرای ربات:\n{traceback.format_exc()}")
            time.sleep(30)


# 📌 تابع شروع ربات برای اجرا از main.py
def start_bot():
    while True:
        try:
            bot.polling(none_stop=True, interval=10, timeout=30)
        except Exception as e:
            print(f"⚠ خطای بحرانی در اجرای ربات:\n{e}")
            time.sleep(15)


if __name__ == "__main__":
    print("🚀 Webhook فعال شد!")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

