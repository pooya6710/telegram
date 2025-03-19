import os
import json
import datetime
import time

try:
    from debug_logger import debug_log
except ImportError:
    def debug_log(message, level="DEBUG", context=None):
        """لاگ کردن ساده در صورت عدم وجود ماژول debug_logger"""
        print(f"{level}: {message}")

try:
    from server_status import generate_server_status, get_cached_server_status
except ImportError:
    def get_cached_server_status():
        """نسخه ساده get_cached_server_status در صورت عدم وجود ماژول server_status"""
        try:
            if os.path.exists("server_status.json"):
                file_time = os.path.getmtime("server_status.json")
                current_time = time.time()
                
                if current_time - file_time < 600:  # کمتر از 10 دقیقه
                    with open("server_status.json", "r", encoding="utf-8") as file:
                        data = json.load(file)
                        return data["status"]
        except Exception as e:
            debug_log(f"خطا در خواندن فایل کش وضعیت سرور: {e}", "ERROR")
        return None
        
    def generate_server_status():
        """نسخه ساده generate_server_status در صورت عدم وجود ماژول server_status"""
        import platform
        import psutil
        
        status_sections = ["📊 **وضعیت سرور:**\n"]
        
        # وضعیت ربات
        status_sections.append(f"🔹 **وضعیت ربات:** `فعال ✅`\n")
        
        # سیستم‌عامل و پایتون
        try:
            status_sections.append(f"🔹 **سیستم عامل:** `{platform.platform()}`\n")
            status_sections.append(f"🔹 **پایتون:** `{platform.python_version()}`\n")
        except:
            status_sections.append("🔹 **سیستم عامل:** `اطلاعات در دسترس نیست`\n")
        
        # CPU
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            status_sections.append(f"🔹 **CPU:** `{cpu_usage}%`\n")
        except:
            status_sections.append("🔹 **CPU:** `اطلاعات در دسترس نیست`\n")
        
        # RAM
        try:
            ram = psutil.virtual_memory()
            status_sections.append(f"🔹 **RAM:** `{ram.used / (1024**3):.2f}GB / {ram.total / (1024**3):.2f}GB`\n")
        except:
            status_sections.append("🔹 **RAM:** `اطلاعات در دسترس نیست`\n")
        
        # زمان سرور
        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_sections.append(f"🔹 **زمان سرور:** `{current_time}`\n")
        except:
            status_sections.append("🔹 **زمان سرور:** `اطلاعات در دسترس نیست`\n")
        
        return "".join(status_sections)

# تابع رسیدگی به دستور status
def handle_status_command(bot, message):
    """
    رسیدگی به دستور /status در ربات تلگرام
    
    Args:
        bot: نمونه ربات تلگرام
        message: پیام دریافتی از کاربر
    """
    try:
        # تولید و نمایش وضعیت سرور
        status_text = generate_server_status()
        bot.send_message(message.chat.id, status_text, parse_mode="Markdown")
    except Exception as e:
        debug_log(f"خطای کلی در دریافت وضعیت سرور: {e}", "ERROR")
        bot.send_message(message.chat.id, f"⚠ خطا در دریافت وضعیت سرور: {str(e)}")

# تابع رسیدگی به کلیک دکمه وضعیت سرور
def handle_status_callback(bot, call):
    """
    رسیدگی به کلیک دکمه نمایش وضعیت سرور در کیبورد اینلاین
    
    Args:
        bot: نمونه ربات تلگرام
        call: داده‌های کال‌بک کوئری
    """
    try:
        # ارسال پیام "در حال بررسی..."
        bot.edit_message_text(
            "⏳ در حال بررسی وضعیت سرور...",
            call.message.chat.id,
            call.message.message_id
        )

        # بررسی وضعیت سرور از کش
        try:
            cached_status = get_cached_server_status()
            if cached_status:
                bot.edit_message_text(
                    cached_status,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown"
                )
                return
        except Exception as cache_error:
            debug_log(f"خطا در بررسی کش وضعیت سرور: {cache_error}", "ERROR")

        # تولید وضعیت سرور
        status_text = generate_server_status()
        
        # ایجاد دکمه بازگشت به منوی اصلی
        try:
            # تلاش برای بارگذاری telebot
            try:
                import telebot
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(telebot.types.InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_main"))
                
                bot.edit_message_text(
                    status_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown",
                    reply_markup=markup
                )
            except ImportError:
                # اگر telebot import نشد، بدون دکمه ارسال کن
                bot.edit_message_text(
                    status_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown"
                )
        except Exception as e:
            debug_log(f"خطا در ارسال پیام وضعیت سرور: {e}", "ERROR")
            bot.edit_message_text(
                status_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        error_message = f"⚠ خطا در دریافت وضعیت سرور: {str(e)}"
        debug_log(f"خطای کلی در رسیدگی به وضعیت سرور: {e}", "ERROR")
        try:
            # تلاش برای ویرایش پیام فعلی
            bot.edit_message_text(
                error_message,
                call.message.chat.id,
                call.message.message_id
            )
        except:
            # اگر ویرایش پیام با خطا مواجه شد، پیام جدید ارسال کن
            bot.send_message(call.message.chat.id, error_message)