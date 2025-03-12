import telebot
import os
import traceback
# ... other imports ...

# ... other code ...

# تابع setup_bot برای راه‌اندازی ربات
def setup_bot():
    """راه‌اندازی ربات تلگرام و ثبت تمام هندلرها"""
    print("🤖 ربات شروع به کار کرد!")

    try:
        # شروع پولینگ ربات در یک ترد جداگانه
        import threading
        polling_thread = threading.Thread(target=bot.polling, kwargs={'none_stop': True})
        polling_thread.daemon = True  # اجازه می‌دهد برنامه اصلی بسته شود حتی اگر این ترد همچنان اجرا می‌شود
        polling_thread.start()

        # ارسال پیام به مالک در صورت راه‌اندازی مجدد
        if OWNER_ID:
            try:
                bot.send_message(OWNER_ID, "🔄 ربات مجدداً راه‌اندازی شد و آماده کار است!")
            except Exception as e:
                print(f"خطا در ارسال پیام به مالک: {e}")

        return True
    except Exception as e:
        print(f"❌ خطا در راه‌اندازی ربات: {e}")
        traceback.print_exc()
        return False

# بهینه‌سازی فضای ذخیره‌سازی با تنظیم حداکثر تعداد فایل‌ها
MAX_VIDEOS_TO_KEEP = 50  # تعداد حداکثر ویدیوها در هر پوشه

# پاکسازی خودکار ویدیوهای قدیمی
def cleanup_old_videos():
    """پاکسازی ویدیوهای قدیمی برای کاهش فضای مصرفی"""
    for folder in ["videos", "instagram_videos"]:
        if not os.path.exists(folder):
            continue

        files = []
        for file in os.listdir(folder):
            file_path = os.path.join(folder, file)
            if os.path.isfile(file_path):
                file_stats = os.stat(file_path)
                files.append((file_path, file_stats.st_mtime))

        # مرتب‌سازی بر اساس زمان ایجاد (قدیمی‌ترین اول)
        files.sort(key=lambda x: x[1])

        # حذف فایل‌های اضافی
        files_to_remove = files[:-MAX_VIDEOS_TO_KEEP] if len(files) > MAX_VIDEOS_TO_KEEP else []
        for file_path, _ in files_to_remove:
            try:
                os.remove(file_path)
                print(f"🗑️ فایل قدیمی حذف شد: {file_path}")
            except Exception as e:
                print(f"❌ خطا در حذف فایل {file_path}: {e}")

# اجرای پاکسازی به صورت خودکار هر 6 ساعت
import threading
def schedule_cleanup():
    cleanup_old_videos()
    # اجرای مجدد هر 6 ساعت
    threading.Timer(6 * 60 * 60, schedule_cleanup).start()

# شروع زمانبندی پاکسازی
schedule_cleanup()

# ... rest of the bot code ...

if __name__ == "__main__":
    if setup_bot():
        # ادامه اجرای ربات
        print("Running...")
        # ... other code ...
        bot.infinity_polling()