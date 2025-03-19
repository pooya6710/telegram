import os
import time
import json
import re
import threading
from typing import Dict, Any, Optional, Tuple, List, Union, Callable
import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from debug_logger import debug_log, debug_decorator, format_exception_with_context
from config import (
    BOT_TOKEN, WEBHOOK_URL, BOT_MESSAGES, ADMIN_IDS, UserRole,
    MAX_VIDEO_SIZE_MB, MAX_DOWNLOAD_TIME, MAX_DOWNLOADS_PER_USER, MAX_VIDEO_DURATION
)
from database import add_download, get_download, update_download_status, get_user_downloads
from youtube_downloader import (
    validate_youtube_url, extract_video_info, download_video,
    get_download_progress, cancel_download, clean_old_downloads
)
from user_management import (
    update_user_info, is_user_blocked, is_admin, is_premium,
    check_user_limits, get_user_role, format_user_info
)
from system_info import get_system_status_text
from bot_commands import register_commands

# ایجاد نمونه ربات
bot = telebot.TeleBot(BOT_TOKEN)

# قفل‌ها برای مدیریت همزمانی
lock = threading.RLock()
user_state = {}  # ذخیره وضعیت کاربران

# تابع برای دریافت وب‌هوک
@debug_decorator
def webhook():
    json_str = None
    debug_log("شروع دریافت وب‌هوک جدید", "INFO")
    
    try:
        # دریافت داده‌های از درخواست با مدیریت خطا
        try:
            json_raw = request.get_data()
            debug_log(f"داده خام وب‌هوک دریافت شد: {len(json_raw)} بایت", "DEBUG")
            
            # تلاش برای رمزگشایی داده‌ها
            try:
                json_str = json_raw.decode("UTF-8")
            except UnicodeDecodeError:
                # اگر UTF-8 کار نکرد، روش‌های دیگر را امتحان کن
                try:
                    json_str = json_raw.decode("latin-1")
                    debug_log("داده وب‌هوک با latin-1 رمزگشایی شد", "WARNING")
                except Exception:
                    # اگر همه روش‌ها شکست خورد، فقط داده باینری را لاگ کن
                    debug_log("عدم توانایی در رمزگشایی داده وب‌هوک", "ERROR")
                    log_webhook_request(json_raw)
                    return "خطای رمزگشایی داده", 400
            
            # لاگ کردن بخشی از داده دریافتی
            if json_str:
                preview = json_str[:100] + ("..." if len(json_str) > 100 else "")
                debug_log(f"داده دریافتی وب‌هوک: {preview}", "INFO")
                log_webhook_request(json_str)
                
        except Exception as req_error:
            debug_log(f"خطا در دریافت داده از درخواست وب‌هوک", "ERROR", {
                "error_type": type(req_error).__name__,
                "error_message": str(req_error)
            })
            return "خطا در دریافت داده درخواست", 400
            
        # تبدیل JSON به آبجکت Update تلگرام با مدیریت خطا
        try:
            # اطمینان از وجود داده
            if not json_str:
                debug_log("JSON خالی یا نامعتبر", "ERROR")
                return "داده JSON نامعتبر است", 400
                
            # تبدیل به آبجکت Update
            try:
                update = telebot.types.Update.de_json(json_str)
                if not update:
                    debug_log("تبدیل JSON به آبجکت Update با مشکل مواجه شد", "ERROR")
                    return "تبدیل JSON ناموفق بود", 400
            except Exception as json_error:
                debug_log(f"خطا در تبدیل JSON به آبجکت Update", "ERROR", {
                    "error_type": type(json_error).__name__,
                    "error_message": str(json_error),
                    "json_sample": json_str[:200] if json_str else "None"
                })
                return "خطا در تبدیل JSON", 400
                
            # ثبت آپدیت تلگرام در لاگ با مدیریت خطا
            try:
                log_telegram_update(update)
            except Exception as log_error:
                debug_log(f"خطا در لاگ کردن آپدیت تلگرام", "ERROR", {
                    "error_type": type(log_error).__name__,
                    "error_message": str(log_error)
                })
                # ادامه می‌دهیم حتی اگر لاگینگ خطا داشته باشد
                
            # بررسی نوع پیام برای لاگ با مدیریت خطا
            try:
                if hasattr(update, 'message') and update.message is not None:
                    user_id = None
                    msg_text = None
                    
                    # استخراج اطلاعات کاربر با مدیریت خطا
                    try:
                        if hasattr(update.message, 'from_user') and update.message.from_user is not None:
                            user_id = update.message.from_user.id
                            username = update.message.from_user.username if hasattr(update.message.from_user, 'username') else None
                    except Exception:
                        debug_log("خطا در استخراج اطلاعات کاربر", "WARNING")
                    
                    # استخراج متن پیام با مدیریت خطا
                    try:
                        msg_text = update.message.text if hasattr(update.message, 'text') else "[NO_TEXT]"
                    except Exception:
                        debug_log("خطا در استخراج متن پیام", "WARNING")
                        msg_text = "[ERROR_EXTRACTING_TEXT]"
                        
                    # لاگ کردن پیام
                    log_data = {
                        "user_id": user_id,
                        "chat_id": update.message.chat.id if hasattr(update.message, 'chat') and hasattr(update.message.chat, 'id') else None,
                        "message_id": update.message.message_id if hasattr(update.message, 'message_id') else None
                    }
                    
                    # اضافه کردن یوزرنیم اگر موجود باشد
                    if hasattr(update.message, 'from_user') and update.message.from_user and hasattr(update.message.from_user, 'username'):
                        log_data["username"] = update.message.from_user.username
                        
                    debug_log(f"پیام جدید از کاربر {user_id}: {msg_text}", "INFO", log_data)
                
                elif hasattr(update, 'callback_query') and update.callback_query is not None:
                    # استخراج اطلاعات کالبک کوئری با مدیریت خطا
                    callback_info = {}
                    
                    try:
                        if hasattr(update.callback_query, 'from_user') and update.callback_query.from_user:
                            callback_info["user_id"] = update.callback_query.from_user.id
                    except Exception:
                        debug_log("خطا در استخراج شناسه کاربر از کالبک کوئری", "WARNING")
                        callback_info["user_id"] = None
                        
                    try:
                        callback_info["query_id"] = update.callback_query.id if hasattr(update.callback_query, 'id') else None
                    except Exception:
                        debug_log("خطا در استخراج شناسه کالبک کوئری", "WARNING")
                        
                    try:
                        callback_info["data"] = update.callback_query.data if hasattr(update.callback_query, 'data') else None
                    except Exception:
                        debug_log("خطا در استخراج داده کالبک کوئری", "WARNING")
                        
                    # لاگ کردن کالبک کوئری
                    user_id_str = str(callback_info.get("user_id", "نامشخص"))
                    debug_log(f"کالبک کوئری جدید از کاربر {user_id_str}", "INFO", callback_info)
            except Exception as msg_log_error:
                debug_log(f"خطا در لاگ کردن جزئیات پیام", "ERROR", {
                    "error_type": type(msg_log_error).__name__,
                    "error_message": str(msg_log_error)
                })
                # ادامه می‌دهیم حتی اگر لاگینگ خطا داشته باشد
                
            # پردازش پیام با مدیریت خطا
            try:
                bot.process_new_updates([update])
                debug_log("پیام با موفقیت پردازش شد", "INFO")
                return "✅ Webhook دریافت شد!", 200
            except Exception as process_error:
                error_details = format_exception_with_context(process_error)
                debug_log(f"خطا در پردازش پیام توسط ربات", "ERROR", {
                    "error_type": type(process_error).__name__,
                    "error_message": str(process_error),
                    "traceback": error_details
                })
                
                # اطلاع‌رسانی به ادمین با محدود کردن طول پیام
                try:
                    notify_admin(f"⚠️ خطا در پردازش پیام:\n{str(process_error)}\n\n{error_details[:2000]}...")
                except Exception:
                    debug_log("خطا در اطلاع‌رسانی به ادمین", "ERROR")
                    
                return f"خطا در پردازش پیام", 500
                
        except Exception as update_error:
            error_details = format_exception_with_context(update_error)
            debug_log(f"خطا در پردازش آپدیت تلگرام", "ERROR", {
                "error_type": type(update_error).__name__,
                "error_message": str(update_error),
                "traceback": error_details
            })
            return f"خطا در پردازش آپدیت", 500
            
    except Exception as outer_error:
        error_details = format_exception_with_context(outer_error)
        debug_log(f"خطای کلی در پردازش وب‌هوک", "ERROR", {
            "error_type": type(outer_error).__name__,
            "error_message": str(outer_error),
            "traceback": error_details
        })
        return "خطای سرور", 500

# ارسال پیام به ادمین
@debug_decorator
def notify_admin(message: str):
    """ارسال پیام به ادمین"""
    admin_id = ADMIN_IDS[0] if ADMIN_IDS else None
    if admin_id:
        try:
            bot.send_message(admin_id, message, parse_mode="Markdown")
            return True
        except Exception as e:
            debug_log(f"خطا در ارسال پیام به ادمین: {str(e)}", "ERROR")
    return False

# افزودن هندلرهای ربات
@debug_decorator
def register_handlers(bot_instance):
    """ثبت هندلرهای ربات"""
    
    # ثبت دستورات در منوی ربات
    register_commands(bot_instance)
    
    # هندلر دستور شروع
    @bot_instance.message_handler(commands=['start'])
    def start_command(message):
        try:
            # ثبت یا به‌روزرسانی اطلاعات کاربر
            user_id = message.from_user.id
            update_user_info(
                user_id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )
            
            # بررسی مسدود بودن کاربر
            if is_user_blocked(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['user_blocked'])
                return
                
            # ارسال پیام خوش‌آمدگویی
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            # دکمه‌های اینلاین
            help_button = types.InlineKeyboardButton("📚 راهنما", callback_data="help")
            status_button = types.InlineKeyboardButton("📊 وضعیت سیستم", callback_data="status")
            
            markup.add(help_button, status_button)
            
            # برای ادمین‌ها دکمه‌های ویژه اضافه می‌کنیم
            if is_admin(user_id):
                admin_help_button = types.InlineKeyboardButton("🛡 راهنمای ادمین", callback_data="admin_help")
                markup.add(admin_help_button)
            
            bot_instance.send_message(message.chat.id, BOT_MESSAGES['start'], reply_markup=markup, parse_mode="Markdown")
            
            debug_log(f"کاربر {user_id} ربات را شروع کرد", "INFO")
            
        except Exception as e:
            debug_log(f"خطا در دستور start: {str(e)}", "ERROR")
            bot_instance.reply_to(message, "متأسفانه خطایی رخ داده است. لطفا مجددا تلاش کنید.")
    
    # هندلر دستور راهنما
    @bot_instance.message_handler(commands=['help'])
    def help_command(message):
        try:
            # ثبت یا به‌روزرسانی اطلاعات کاربر
            user_id = message.from_user.id
            
            # بررسی مسدود بودن کاربر
            if is_user_blocked(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['user_blocked'])
                return
            
            # تنظیم پارامترهای پیام راهنما
            help_msg = BOT_MESSAGES['help'].format(
                max_size=MAX_VIDEO_SIZE_MB,
                max_duration=int(MAX_VIDEO_DURATION/60),
                max_downloads=MAX_DOWNLOADS_PER_USER
            )
            
            bot_instance.send_message(message.chat.id, help_msg, parse_mode="Markdown")
            
        except Exception as e:
            debug_log(f"خطا در دستور help: {str(e)}", "ERROR")
            bot_instance.reply_to(message, "متأسفانه خطایی رخ داده است. لطفا مجددا تلاش کنید.")
    
    # هندلر دستور admin_help (فقط برای ادمین‌ها)
    @bot_instance.message_handler(commands=['admin_help'])
    def admin_help_command(message):
        try:
            user_id = message.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['unauthorized'])
                return
                
            bot_instance.send_message(message.chat.id, BOT_MESSAGES['admin_help'], parse_mode="Markdown")
            
        except Exception as e:
            debug_log(f"خطا در دستور admin_help: {str(e)}", "ERROR")
            bot_instance.reply_to(message, "متأسفانه خطایی رخ داده است. لطفا مجددا تلاش کنید.")
    
    # هندلر دستور دانلود
    @bot_instance.message_handler(commands=['download'])
    def download_command(message):
        try:
            # ثبت یا به‌روزرسانی اطلاعات کاربر
            user_id = message.from_user.id
            
            # بررسی مسدود بودن کاربر
            if is_user_blocked(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['user_blocked'])
                return
            
            # بررسی محدودیت‌های کاربر
            allowed, limit_msg = check_user_limits(user_id, config)
            if not allowed:
                bot_instance.reply_to(message, limit_msg)
                return
            
            # استخراج لینک از پیام
            command_parts = message.text.split(' ', 1)
            
            if len(command_parts) < 2:
                bot_instance.reply_to(message, "لطفاً لینک یوتیوب را بعد از دستور وارد کنید:\n/download [YouTube URL]")
                return
            
            url = command_parts[1].strip()
            process_youtube_url(message, url)
            
        except Exception as e:
            debug_log(f"خطا در دستور download: {str(e)}", "ERROR")
            bot_instance.reply_to(message, "متأسفانه خطایی رخ داده است. لطفا مجددا تلاش کنید.")
    
    # هندلر دستور وضعیت
    @bot_instance.message_handler(commands=['status'])
    def status_command(message):
        try:
            # ثبت یا به‌روزرسانی اطلاعات کاربر
            user_id = message.from_user.id
            
            # بررسی مسدود بودن کاربر
            if is_user_blocked(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['user_blocked'])
                return
            
            # دریافت وضعیت سیستم
            status_text = get_system_status_text()
            
            bot_instance.send_message(message.chat.id, status_text, parse_mode="Markdown")
            
        except Exception as e:
            debug_log(f"خطا در دستور status: {str(e)}", "ERROR")
            bot_instance.reply_to(message, "متأسفانه خطایی رخ داده است. لطفا مجددا تلاش کنید.")
    
    # هندلر دستور دانلودهای من
    @bot_instance.message_handler(commands=['mydownloads'])
    def my_downloads_command(message):
        try:
            # ثبت یا به‌روزرسانی اطلاعات کاربر
            user_id = message.from_user.id
            
            # بررسی مسدود بودن کاربر
            if is_user_blocked(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['user_blocked'])
                return
            
            # دریافت دانلودهای کاربر
            downloads = get_user_downloads(user_id, limit=10)
            
            if not downloads:
                bot_instance.send_message(message.chat.id, "📂 شما هیچ دانلودی ندارید.")
                return
            
            # نمایش دانلودها
            result = "📋 *دانلودهای شما:*\n\n"
            
            for i, dl in enumerate(downloads, 1):
                # وضعیت دانلود
                status_emoji = "⏳" if dl['status'] in [0, 1] else ("✅" if dl['status'] == 2 else ("❌" if dl['status'] == 3 else "🚫"))
                status_text = ["در انتظار", "در حال پردازش", "تکمیل شده", "با خطا مواجه شد", "لغو شده"][dl['status']]
                
                # استخراج عنوان ویدیو
                title = "ویدیو ناشناس"
                if dl.get('metadata') and isinstance(dl['metadata'], dict) and dl['metadata'].get('title'):
                    title = dl['metadata']['title']
                
                # افزودن اطلاعات دانلود
                result += f"{i}. {status_emoji} *#{dl['id']}*\n"
                result += f"🎬 *عنوان:* {title[:30]}...\n"
                result += f"🔄 *وضعیت:* {status_text}\n"
                
                # اگر اندازه فایل موجود است
                if dl.get('file_size'):
                    from youtube_downloader import format_filesize
                    result += f"📦 *حجم:* {format_filesize(dl['file_size'])}\n"
                
                # افزودن زمان شروع
                if dl.get('start_time'):
                    start_time = dl['start_time'].split('T')[0] if 'T' in dl['start_time'] else dl['start_time']
                    result += f"🕒 *زمان شروع:* {start_time}\n"
                
                # دکمه‌ها برای دانلودهای در حال انجام
                if dl['status'] in [0, 1]:
                    result += f"برای لغو دانلود: /cancel_{dl['id']}\n"
                
                result += "\n"
                
                # محدودیت اندازه پیام
                if len(result) > 3500:
                    result += f"... و {len(downloads) - i} دانلود دیگر"
                    break
            
            bot_instance.send_message(message.chat.id, result, parse_mode="Markdown")
            
        except Exception as e:
            debug_log(f"خطا در دستور mydownloads: {str(e)}", "ERROR")
            bot_instance.reply_to(message, "متأسفانه خطایی رخ داده است. لطفا مجددا تلاش کنید.")
    
    # هندلر دستور لغو دانلود
    @bot_instance.message_handler(regexp=r"^/cancel_(\d+)$")
    def cancel_download_command(message):
        try:
            # ثبت یا به‌روزرسانی اطلاعات کاربر
            user_id = message.from_user.id
            
            # بررسی مسدود بودن کاربر
            if is_user_blocked(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['user_blocked'])
                return
            
            # استخراج شناسه دانلود
            match = re.match(r"^/cancel_(\d+)$", message.text)
            download_id = int(match.group(1))
            
            # بررسی وجود دانلود
            download_info = get_download(download_id)
            
            if not download_info:
                bot_instance.reply_to(message, "❌ دانلود مورد نظر یافت نشد.")
                return
            
            # بررسی مالکیت دانلود یا ادمین بودن
            if download_info['user_id'] != user_id and not is_admin(user_id):
                bot_instance.reply_to(message, "❌ شما اجازه لغو این دانلود را ندارید.")
                return
            
            # لغو دانلود
            success = cancel_download(download_id)
            
            if success:
                bot_instance.reply_to(message, f"✅ دانلود با شناسه {download_id} لغو شد.")
            else:
                bot_instance.reply_to(message, f"❌ لغو دانلود با شناسه {download_id} امکان‌پذیر نیست.")
            
        except Exception as e:
            debug_log(f"خطا در دستور cancel: {str(e)}", "ERROR")
            bot_instance.reply_to(message, "متأسفانه خطایی رخ داده است. لطفا مجددا تلاش کنید.")
    
    # هندلر برای دریافت مستقیم لینک
    @bot_instance.message_handler(func=lambda message: validate_youtube_url(message.text))
    def direct_youtube_url(message):
        try:
            # ثبت یا به‌روزرسانی اطلاعات کاربر
            user_id = message.from_user.id
            
            # بررسی مسدود بودن کاربر
            if is_user_blocked(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['user_blocked'])
                return
            
            # بررسی محدودیت‌های کاربر
            allowed, limit_msg = check_user_limits(user_id, config)
            if not allowed:
                bot_instance.reply_to(message, limit_msg)
                return
            
            # پردازش لینک یوتیوب
            url = message.text.strip()
            process_youtube_url(message, url)
            
        except Exception as e:
            debug_log(f"خطا در پردازش مستقیم لینک: {str(e)}", "ERROR")
            bot_instance.reply_to(message, "متأسفانه خطایی رخ داده است. لطفا مجددا تلاش کنید.")
    
    # پردازش لینک یوتیوب
    @debug_decorator
    def process_youtube_url(message, url):
        """پردازش لینک یوتیوب و شروع دانلود"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # بررسی اعتبار URL
        if not validate_youtube_url(url):
            bot_instance.reply_to(message, BOT_MESSAGES['invalid_url'])
            return
        
        # ارسال پیام در حال پردازش
        processing_msg = bot_instance.reply_to(message, BOT_MESSAGES['processing'])
        
        try:
            # استخراج اطلاعات ویدیو
            video_info = extract_video_info(url)
            
            if not video_info:
                bot_instance.edit_message_text(
                    "❌ امکان استخراج اطلاعات ویدیو وجود ندارد. لطفاً از لینک معتبر استفاده کنید.",
                    chat_id=chat_id,
                    message_id=processing_msg.message_id
                )
                return
            
            # بررسی محدودیت زمان ویدیو
            duration = video_info.get('duration', 0)
            if duration > MAX_VIDEO_DURATION:
                bot_instance.edit_message_text(
                    f"❌ مدت زمان ویدیو بیش از حد مجاز است ({video_info.get('duration_string')}).\nحداکثر مدت مجاز: {MAX_VIDEO_DURATION//60} دقیقه",
                    chat_id=chat_id,
                    message_id=processing_msg.message_id
                )
                return
            
            # نمایش اطلاعات ویدیو و گزینه‌های دانلود
            video_title = video_info.get('title', 'ویدیو ناشناس')
            video_uploader = video_info.get('uploader', 'ناشناس')
            video_duration = video_info.get('duration_string', 'نامشخص')
            
            # ساخت دکمه‌های کیفیت
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            # دکمه‌های کیفیت
            quality_buttons = []
            
            # افزودن فرمت‌های موجود
            formats = video_info.get('formats', [])
            
            # محدود کردن تعداد دکمه‌ها (حداکثر 8 گزینه)
            max_formats = min(len(formats), 8) if formats else 0
            
            for i in range(max_formats):
                format_info = formats[i]
                quality_label = format_info.get('quality', 'نامشخص')
                format_id = format_info.get('format_id', '')
                
                # برچسب دکمه
                if quality_label == 'audio':
                    button_text = f"🎵 فقط صدا - {format_info.get('filesize_human', 'نامشخص')}"
                else:
                    button_text = f"🎬 {quality_label} - {format_info.get('filesize_human', 'نامشخص')}"
                
                callback_data = f"download_{format_id}_{url[:30]}"  # محدود کردن اندازه callback_data
                quality_buttons.append(types.InlineKeyboardButton(button_text, callback_data=callback_data))
            
            # اگر فرمتی یافت نشد
            if not quality_buttons:
                quality_buttons.append(types.InlineKeyboardButton("🎬 کیفیت بهینه", callback_data=f"download_best_{url[:30]}"))
            
            # افزودن دکمه‌ها به markup
            markup.add(*quality_buttons)
            
            # اضافه کردن دکمه لغو
            markup.add(types.InlineKeyboardButton("❌ لغو", callback_data="cancel_download"))
            
            # نمایش پیش‌نمایش ویدیو
            preview_text = f"📹 *{video_title}*\n\n"
            preview_text += f"👤 *کانال:* {video_uploader}\n"
            preview_text += f"⏱ *مدت زمان:* {video_duration}\n\n"
            preview_text += "🔽 *لطفاً کیفیت دانلود را انتخاب کنید:*"
            
            # ارسال تصویر بندانگشتی اگر موجود باشد
            thumbnail = video_info.get('thumbnail')
            
            if thumbnail:
                try:
                    bot_instance.delete_message(chat_id=chat_id, message_id=processing_msg.message_id)
                    bot_instance.send_photo(
                        chat_id=chat_id,
                        photo=thumbnail,
                        caption=preview_text,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                except Exception as thumb_error:
                    debug_log(f"خطا در ارسال تصویر بندانگشتی: {str(thumb_error)}", "WARNING")
                    # ارسال بدون تصویر
                    bot_instance.edit_message_text(
                        preview_text,
                        chat_id=chat_id,
                        message_id=processing_msg.message_id,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
            else:
                # ارسال بدون تصویر
                bot_instance.edit_message_text(
                    preview_text,
                    chat_id=chat_id,
                    message_id=processing_msg.message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            
        except Exception as e:
            debug_log(f"خطا در پردازش لینک یوتیوب: {str(e)}", "ERROR")
            bot_instance.edit_message_text(
                f"❌ خطا در پردازش لینک: {str(e)}",
                chat_id=chat_id,
                message_id=processing_msg.message_id
            )
    
    # هندلر کال‌بک کوئری
    @bot_instance.callback_query_handler(func=lambda call: True)
    def callback_handler(call):
        try:
            # دریافت اطلاعات کاربر
            user_id = call.from_user.id
            
            # بررسی مسدود بودن کاربر
            if is_user_blocked(user_id):
                bot_instance.answer_callback_query(call.id, "شما مسدود شده‌اید و اجازه استفاده از ربات را ندارید.")
                return
            
            # دریافت داده کال‌بک
            data = call.data
            
            # پردازش براساس نوع کال‌بک
            if data == "help":
                # راهنما
                help_msg = BOT_MESSAGES['help'].format(
                    max_size=MAX_VIDEO_SIZE_MB,
                    max_duration=int(MAX_VIDEO_DURATION/60),
                    max_downloads=MAX_DOWNLOADS_PER_USER
                )
                
                bot_instance.answer_callback_query(call.id, "نمایش راهنما")
                bot_instance.send_message(call.message.chat.id, help_msg, parse_mode="Markdown")
                
            elif data == "admin_help":
                # راهنمای ادمین
                if not is_admin(user_id):
                    bot_instance.answer_callback_query(call.id, "شما دسترسی ادمین ندارید!", show_alert=True)
                    return
                
                bot_instance.answer_callback_query(call.id, "نمایش راهنمای ادمین")
                bot_instance.send_message(call.message.chat.id, BOT_MESSAGES['admin_help'], parse_mode="Markdown")
                
            elif data == "status":
                # وضعیت سیستم
                bot_instance.answer_callback_query(call.id, "دریافت وضعیت سیستم...")
                
                # دریافت وضعیت سیستم
                status_text = get_system_status_text()
                
                bot_instance.send_message(call.message.chat.id, status_text, parse_mode="Markdown")
                
            elif data == "cancel_download":
                # لغو انتخاب دانلود
                bot_instance.answer_callback_query(call.id, "درخواست دانلود لغو شد")
                bot_instance.edit_message_text(
                    "❌ درخواست دانلود توسط کاربر لغو شد.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
                
            elif data.startswith("download_"):
                # شروع دانلود
                # بررسی محدودیت‌های کاربر
                allowed, limit_msg = check_user_limits(user_id, config)
                if not allowed:
                    bot_instance.answer_callback_query(call.id, limit_msg, show_alert=True)
                    return
                
                # استخراج کیفیت و URL
                parts = data.split('_', 2)
                
                if len(parts) < 3:
                    bot_instance.answer_callback_query(call.id, "داده نامعتبر", show_alert=True)
                    return
                
                quality = parts[1]
                url_prefix = parts[2]
                
                # استخراج URL از پیام اصلی
                message_text = call.message.caption or call.message.text
                
                if message_text:
                    # یافتن URL در متن پیام یا درخواست URL کامل
                    url = None
                    urls = re.findall(r'https?://(?:www\.)?\S+', message_text)
                    
                    if urls:
                        for u in urls:
                            if validate_youtube_url(u):
                                url = u
                                break
                    
                    if not url:
                        # اگر URL در متن پیام نبود، از کاربر درخواست کنیم
                        with lock:
                            user_state[user_id] = {"action": "waiting_for_url", "quality": quality}
                        
                        bot_instance.answer_callback_query(call.id, "لطفاً URL کامل را مجددا ارسال کنید")
                        bot_instance.send_message(call.message.chat.id, "🔄 لطفاً URL کامل یوتیوب را مجددا ارسال کنید.")
                        return
                    
                    # شروع دانلود
                    start_download_process(call.message.chat.id, url, user_id, quality)
                    
                    # پاسخ به کاربر
                    bot_instance.answer_callback_query(call.id, "دانلود شروع شد")
                    
                    # به‌روزرسانی پیام
                    try:
                        bot_instance.edit_message_text(
                            message_text + "\n\n▶️ *دانلود شروع شد...*",
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass  # نادیده گرفتن خطای احتمالی در ویرایش پیام
                else:
                    bot_instance.answer_callback_query(call.id, "نمی‌توان URL را تشخیص داد", show_alert=True)
                    
        except Exception as e:
            debug_log(f"خطا در پردازش کال‌بک: {str(e)}", "ERROR")
            try:
                bot_instance.answer_callback_query(call.id, "خطایی رخ داده است", show_alert=True)
            except Exception:
                pass
    
    # تابع شروع دانلود
    @debug_decorator
    def start_download_process(chat_id, url, user_id, quality="best"):
        """شروع فرایند دانلود"""
        
        # ثبت در دیتابیس
        download_id = add_download(user_id, url, quality)
        
        if download_id == -1:
            bot_instance.send_message(
                chat_id,
                "❌ خطا در ثبت دانلود. لطفاً مجددا تلاش کنید."
            )
            return
        
        # ارسال پیام شروع دانلود
        message = bot_instance.send_message(
            chat_id,
            BOT_MESSAGES['download_started'].format(download_id=download_id),
            parse_mode="Markdown"
        )
        
        # تابع آپدیت پیشرفت
        def progress_callback(percent, status):
            try:
                # به‌روزرسانی پیام هر 10 درصد یا تغییر وضعیت
                if hasattr(progress_callback, 'last_update'):
                    last_percent, last_status = progress_callback.last_update
                    if percent - last_percent < 10 and status == last_status and percent < 100:
                        return
                
                # ذخیره آخرین به‌روزرسانی
                progress_callback.last_update = (percent, status)
                
                # به‌روزرسانی پیام
                progress_text = f"🔄 *دانلود در حال انجام...*\n\n"
                progress_text += f"🆔 شناسه دانلود: `{download_id}`\n"
                progress_text += f"📊 پیشرفت: {percent:.1f}%\n"
                progress_text += f"🔄 وضعیت: {status}\n\n"
                progress_text += "برای لغو دانلود: /cancel_" + str(download_id)
                
                bot_instance.edit_message_text(
                    progress_text,
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    parse_mode="Markdown"
                )
            except Exception as e:
                debug_log(f"خطا در به‌روزرسانی پیشرفت دانلود: {str(e)}", "WARNING")
        
        # تنظیم مقادیر اولیه
        progress_callback.last_update = (0, "در حال شروع...")
        
        # شروع دانلود در ترد جداگانه
        def download_thread():
            try:
                # دانلود ویدیو
                success, file_path, error = download_video(
                    url, 
                    download_id, 
                    user_id, 
                    quality, 
                    progress_callback
                )
                
                if success and file_path:
                    # آپلود فایل به تلگرام
                    try:
                        # دریافت اطلاعات دانلود از دیتابیس
                        download_info = get_download(download_id)
                        
                        if not download_info:
                            bot_instance.send_message(
                                chat_id,
                                "❌ خطا در دریافت اطلاعات دانلود. لطفاً با ادمین تماس بگیرید."
                            )
                            return
                        
                        # استخراج عنوان ویدیو
                        title = "ویدیو یوتیوب"
                        if (download_info.get('metadata') and 
                            isinstance(download_info['metadata'], dict) and 
                            download_info['metadata'].get('title')):
                            title = download_info['metadata']['title']
                        
                        # ارسال پیام نهایی
                        bot_instance.edit_message_text(
                            f"✅ *دانلود با موفقیت انجام شد!*\n\n"
                            f"🎬 *عنوان:* {title}\n"
                            f"🆔 *شناسه:* `{download_id}`\n"
                            f"💾 *فایل در حال آپلود...*",
                            chat_id=message.chat.id,
                            message_id=message.message_id,
                            parse_mode="Markdown"
                        )
                        
                        # آپلود فایل به تلگرام
                        if os.path.getsize(file_path) > 50 * 1024 * 1024 and not is_premium(user_id):
                            # اگر فایل بزرگتر از 50 مگابایت باشد و کاربر ویژه نباشد
                            bot_instance.send_message(
                                chat_id,
                                f"⚠️ حجم فایل بیشتر از 50 مگابایت است و امکان آپلود مستقیم وجود ندارد.\n\n"
                                f"🔗 *لینک دانلود:* فایل در سرور ذخیره شده و تا 24 ساعت آینده قابل دسترسی است.\n\n"
                                f"💎 برای دریافت فایل‌های بزرگتر، به اکانت ویژه ارتقا دهید.",
                                parse_mode="Markdown"
                            )
                        else:
                            # ارسال فایل
                            with open(file_path, 'rb') as video_file:
                                if file_path.endswith('.mp3') or 'audio' in quality:
                                    # ارسال به عنوان فایل صوتی
                                    bot_instance.send_audio(
                                        chat_id,
                                        video_file,
                                        caption=f"🎵 {title}\n\n🤖 @{bot_instance.get_me().username}",
                                        title=title,
                                        performer="YouTube Download Bot"
                                    )
                                else:
                                    # ارسال به عنوان ویدیو
                                    bot_instance.send_video(
                                        chat_id,
                                        video_file,
                                        caption=f"🎬 {title}\n\n🤖 @{bot_instance.get_me().username}",
                                        supports_streaming=True
                                    )
                            
                            # پیام تکمیل
                            bot_instance.send_message(
                                chat_id,
                                f"✅ *دانلود کامل شد*\n\n"
                                f"🎬 *عنوان:* {title}\n"
                                f"🆔 *شناسه دانلود:* `{download_id}`\n\n"
                                f"از استفاده شما متشکریم! 🙏",
                                parse_mode="Markdown"
                            )
                    except Exception as upload_error:
                        debug_log(f"خطا در آپلود فایل: {str(upload_error)}", "ERROR")
                        bot_instance.send_message(
                            chat_id,
                            f"⚠️ دانلود با موفقیت انجام شد اما خطایی در آپلود فایل رخ داد:\n{str(upload_error)}"
                        )
                else:
                    # خطا در دانلود
                    error_message = "خطای نامشخص"
                    if error and isinstance(error, dict):
                        error_message = error.get('error', 'خطای نامشخص')
                    
                    bot_instance.send_message(
                        chat_id,
                        BOT_MESSAGES['download_failed'].format(error=error_message),
                        parse_mode="Markdown"
                    )
            except Exception as thread_error:
                debug_log(f"خطا در ترد دانلود: {str(thread_error)}", "ERROR")
                try:
                    bot_instance.send_message(
                        chat_id,
                        f"❌ خطایی در فرایند دانلود رخ داد:\n{str(thread_error)}"
                    )
                except Exception:
                    pass
        
        # شروع ترد دانلود
        thread = threading.Thread(target=download_thread)
        thread.daemon = True
        thread.start()
    
    # هندلر دستورات مدیریتی برای ادمین‌ها
    
    # دستور مشاهده کاربران
    @bot_instance.message_handler(commands=['users'])
    def users_command(message):
        try:
            user_id = message.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['unauthorized'])
                return
                
            # دریافت لیست کاربران
            from user_management import format_users_list
            from database import get_all_users
            
            users = get_all_users(limit=50)
            users_text = format_users_list(users)
            
            bot_instance.send_message(message.chat.id, users_text, parse_mode="Markdown")
            
        except Exception as e:
            debug_log(f"خطا در دستور users: {str(e)}", "ERROR")
            bot_instance.reply_to(message, f"متأسفانه خطایی رخ داده است: {str(e)}")
    
    # دستور مسدود کردن کاربر
    @bot_instance.message_handler(commands=['block'])
    def block_command(message):
        try:
            user_id = message.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['unauthorized'])
                return
                
            # استخراج شناسه کاربر مورد نظر
            command_parts = message.text.split(' ', 1)
            
            if len(command_parts) < 2:
                bot_instance.reply_to(message, "لطفاً شناسه کاربر را وارد کنید:\n/block [user_id]")
                return
                
            try:
                target_user_id = int(command_parts[1].strip())
            except ValueError:
                bot_instance.reply_to(message, "شناسه کاربر باید عدد باشد.")
                return
                
            # مسدود کردن کاربر
            from user_management import block_user
            
            # بررسی عدم مسدود کردن ادمین توسط خودش یا ادمین دیگر
            if is_admin(target_user_id):
                bot_instance.reply_to(message, "❌ امکان مسدود کردن ادمین وجود ندارد.")
                return
                
            success = block_user(target_user_id)
            
            if success:
                bot_instance.reply_to(message, f"✅ کاربر {target_user_id} با موفقیت مسدود شد.")
                
                # اطلاع‌رسانی به کاربر مسدود شده
                try:
                    bot_instance.send_message(
                        target_user_id,
                        "⛔ شما توسط ادمین مسدود شده‌اید و امکان استفاده از ربات را ندارید."
                    )
                except Exception:
                    pass
            else:
                bot_instance.reply_to(message, f"❌ خطا در مسدود کردن کاربر {target_user_id}.")
                
        except Exception as e:
            debug_log(f"خطا در دستور block: {str(e)}", "ERROR")
            bot_instance.reply_to(message, f"متأسفانه خطایی رخ داده است: {str(e)}")
    
    # دستور رفع مسدودیت کاربر
    @bot_instance.message_handler(commands=['unblock'])
    def unblock_command(message):
        try:
            user_id = message.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['unauthorized'])
                return
                
            # استخراج شناسه کاربر مورد نظر
            command_parts = message.text.split(' ', 1)
            
            if len(command_parts) < 2:
                bot_instance.reply_to(message, "لطفاً شناسه کاربر را وارد کنید:\n/unblock [user_id]")
                return
                
            try:
                target_user_id = int(command_parts[1].strip())
            except ValueError:
                bot_instance.reply_to(message, "شناسه کاربر باید عدد باشد.")
                return
                
            # رفع مسدودیت کاربر
            from user_management import unblock_user
            
            success = unblock_user(target_user_id)
            
            if success:
                bot_instance.reply_to(message, f"✅ مسدودیت کاربر {target_user_id} با موفقیت رفع شد.")
                
                # اطلاع‌رسانی به کاربر
                try:
                    bot_instance.send_message(
                        target_user_id,
                        "🔓 مسدودیت شما رفع شده است و می‌توانید مجدداً از ربات استفاده کنید."
                    )
                except Exception:
                    pass
            else:
                bot_instance.reply_to(message, f"❌ خطا در رفع مسدودیت کاربر {target_user_id}.")
                
        except Exception as e:
            debug_log(f"خطا در دستور unblock: {str(e)}", "ERROR")
            bot_instance.reply_to(message, f"متأسفانه خطایی رخ داده است: {str(e)}")
    
    # دستور تنظیم کاربر به عنوان ادمین
    @bot_instance.message_handler(commands=['setadmin'])
    def setadmin_command(message):
        try:
            user_id = message.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['unauthorized'])
                return
                
            # استخراج شناسه کاربر مورد نظر
            command_parts = message.text.split(' ', 1)
            
            if len(command_parts) < 2:
                bot_instance.reply_to(message, "لطفاً شناسه کاربر را وارد کنید:\n/setadmin [user_id]")
                return
                
            try:
                target_user_id = int(command_parts[1].strip())
            except ValueError:
                bot_instance.reply_to(message, "شناسه کاربر باید عدد باشد.")
                return
                
            # تنظیم کاربر به عنوان ادمین
            from user_management import set_admin
            
            success = set_admin(target_user_id)
            
            if success:
                bot_instance.reply_to(message, f"✅ کاربر {target_user_id} با موفقیت به عنوان ادمین تنظیم شد.")
                
                # اطلاع‌رسانی به کاربر
                try:
                    bot_instance.send_message(
                        target_user_id,
                        "🛡 شما به عنوان ادمین ربات تنظیم شده‌اید.\n\nبرای دیدن دستورات ادمین، از /admin_help استفاده کنید."
                    )
                except Exception:
                    pass
            else:
                bot_instance.reply_to(message, f"❌ خطا در تنظیم کاربر {target_user_id} به عنوان ادمین.")
                
        except Exception as e:
            debug_log(f"خطا در دستور setadmin: {str(e)}", "ERROR")
            bot_instance.reply_to(message, f"متأسفانه خطایی رخ داده است: {str(e)}")
    
    # دستور تنظیم کاربر به عنوان ویژه
    @bot_instance.message_handler(commands=['setpremium'])
    def setpremium_command(message):
        try:
            user_id = message.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['unauthorized'])
                return
                
            # استخراج شناسه کاربر مورد نظر
            command_parts = message.text.split(' ', 1)
            
            if len(command_parts) < 2:
                bot_instance.reply_to(message, "لطفاً شناسه کاربر را وارد کنید:\n/setpremium [user_id]")
                return
                
            try:
                target_user_id = int(command_parts[1].strip())
            except ValueError:
                bot_instance.reply_to(message, "شناسه کاربر باید عدد باشد.")
                return
                
            # تنظیم کاربر به عنوان ویژه
            from user_management import set_premium
            
            success = set_premium(target_user_id)
            
            if success:
                bot_instance.reply_to(message, f"✅ کاربر {target_user_id} با موفقیت به عنوان کاربر ویژه تنظیم شد.")
                
                # اطلاع‌رسانی به کاربر
                try:
                    bot_instance.send_message(
                        target_user_id,
                        "⭐ تبریک! شما به عنوان کاربر ویژه ارتقا یافتید.\n\n"
                        "📊 امتیازات ویژه:\n"
                        "- امکان دانلود همزمان بیشتر\n"
                        "- دسترسی به دانلود فایل‌های با حجم بالاتر\n"
                        "- اولویت بالاتر در صف دانلود"
                    )
                except Exception:
                    pass
            else:
                bot_instance.reply_to(message, f"❌ خطا در تنظیم کاربر {target_user_id} به عنوان کاربر ویژه.")
                
        except Exception as e:
            debug_log(f"خطا در دستور setpremium: {str(e)}", "ERROR")
            bot_instance.reply_to(message, f"متأسفانه خطایی رخ داده است: {str(e)}")
    
    # دستور دریافت اطلاعات سیستم
    @bot_instance.message_handler(commands=['sysinfo'])
    def sysinfo_command(message):
        try:
            user_id = message.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['unauthorized'])
                return
                
            # دریافت اطلاعات سیستم
            from system_info import get_system_info, get_system_status_text
            
            # دریافت اطلاعات سیستم
            status_text = get_system_status_text()
            
            bot_instance.send_message(message.chat.id, status_text, parse_mode="Markdown")
            
        except Exception as e:
            debug_log(f"خطا در دستور sysinfo: {str(e)}", "ERROR")
            bot_instance.reply_to(message, f"متأسفانه خطایی رخ داده است: {str(e)}")
    
    # دستور دریافت لاگ‌های اخیر
    @bot_instance.message_handler(commands=['logs'])
    def logs_command(message):
        try:
            user_id = message.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['unauthorized'])
                return
                
            # استخراج تعداد لاگ‌های درخواستی
            command_parts = message.text.split(' ', 1)
            
            count = 10  # تعداد پیش‌فرض
            
            if len(command_parts) >= 2:
                try:
                    count = int(command_parts[1].strip())
                    if count < 1:
                        count = 10
                    elif count > 50:
                        count = 50  # محدودیت حداکثر تعداد
                except ValueError:
                    pass
            
            # دریافت لاگ‌های اخیر
            from debug_logger import get_recent_logs
            
            logs = get_recent_logs(count)
            
            if not logs:
                bot_instance.reply_to(message, "🔍 هیچ لاگی یافت نشد.")
                return
                
            # فرمت‌بندی لاگ‌ها
            logs_text = f"📋 *{len(logs)} لاگ اخیر:*\n\n"
            
            for log in logs:
                # فرمت‌بندی زمان
                timestamp = log.get('timestamp', 'نامشخص')
                
                if len(timestamp) > 19:
                    timestamp = timestamp[:19].replace('T', ' ')
                
                # سطح لاگ
                level = log.get('level', 'DEBUG')
                level_emoji = "🔵" if level == "DEBUG" else (
                    "🟢" if level == "INFO" else (
                    "🟡" if level == "WARNING" else "🔴"
                ))
                
                # پیام لاگ (محدود به 100 کاراکتر)
                message_text = log.get('message', '')
                if len(message_text) > 100:
                    message_text = message_text[:97] + "..."
                
                logs_text += f"{level_emoji} `{timestamp}` *{level}*: {message_text}\n\n"
                
                # محدودیت طول پیام تلگرام
                if len(logs_text) > 3500:
                    logs_text += f"... و {len(logs) - logs.index(log) - 1} لاگ دیگر"
                    break
            
            bot_instance.send_message(message.chat.id, logs_text, parse_mode="Markdown")
            
        except Exception as e:
            debug_log(f"خطا در دستور logs: {str(e)}", "ERROR")
            bot_instance.reply_to(message, f"متأسفانه خطایی رخ داده است: {str(e)}")
    
    # دستور ارسال پیام به همه کاربران
    @bot_instance.message_handler(commands=['broadcast'])
    def broadcast_command(message):
        try:
            user_id = message.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['unauthorized'])
                return
                
            # استخراج متن پیام
            command_parts = message.text.split(' ', 1)
            
            if len(command_parts) < 2:
                bot_instance.reply_to(message, "لطفاً متن پیام را وارد کنید:\n/broadcast [message]")
                return
                
            broadcast_message = command_parts[1].strip()
            
            # تأیید ارسال
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            confirm_button = types.InlineKeyboardButton("✅ تأیید", callback_data="broadcast_confirm")
            cancel_button = types.InlineKeyboardButton("❌ لغو", callback_data="broadcast_cancel")
            
            markup.add(confirm_button, cancel_button)
            
            # ذخیره پیام در وضعیت کاربر
            with lock:
                user_state[user_id] = {"action": "broadcast", "message": broadcast_message}
            
            # ارسال پیش‌نمایش و درخواست تأیید
            bot_instance.reply_to(
                message,
                f"📣 *پیش‌نمایش پیام:*\n\n{broadcast_message}\n\n"
                f"آیا از ارسال این پیام به همه کاربران اطمینان دارید؟",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            debug_log(f"خطا در دستور broadcast: {str(e)}", "ERROR")
            bot_instance.reply_to(message, f"متأسفانه خطایی رخ داده است: {str(e)}")
    
    # هندلر تأیید یا لغو broadcast
    @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("broadcast_"))
    def broadcast_callback(call):
        try:
            user_id = call.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.answer_callback_query(call.id, "شما دسترسی ادمین ندارید!", show_alert=True)
                return
                
            action = call.data.split("_")[1]
            
            # بررسی وجود اطلاعات broadcast
            with lock:
                if user_id not in user_state or user_state[user_id].get("action") != "broadcast":
                    bot_instance.answer_callback_query(call.id, "اطلاعات پیام یافت نشد", show_alert=True)
                    return
                
                broadcast_message = user_state[user_id].get("message", "")
            
            if action == "confirm":
                # تأیید ارسال
                bot_instance.answer_callback_query(call.id, "ارسال پیام آغاز شد")
                
                bot_instance.edit_message_text(
                    "📣 *ارسال پیام به همه کاربران...*\n\nاین فرایند ممکن است چند دقیقه طول بکشد.",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="Markdown"
                )
                
                # شروع ارسال در ترد جداگانه
                def broadcast_thread():
                    try:
                        from database import get_all_users
                        
                        users = get_all_users(limit=1000)
                        successful = 0
                        failed = 0
                        
                        for user in users:
                            user_id = user.get('id')
                            
                            if not user_id:
                                continue
                                
                            # عدم ارسال به کاربران مسدود شده
                            if user.get('role') == -1:
                                continue
                                
                            try:
                                bot_instance.send_message(
                                    user_id,
                                    f"📣 *پیام از طرف ادمین:*\n\n{broadcast_message}",
                                    parse_mode="Markdown"
                                )
                                successful += 1
                                
                                # تأخیر برای جلوگیری از محدودیت API
                                time.sleep(0.1)
                            except Exception:
                                failed += 1
                        
                        # گزارش نتیجه
                        bot_instance.send_message(
                            call.message.chat.id,
                            f"📣 *نتیجه ارسال پیام:*\n\n"
                            f"✅ ارسال موفق: {successful}\n"
                            f"❌ ارسال ناموفق: {failed}\n"
                            f"📊 مجموع: {successful + failed}",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        debug_log(f"خطا در ترد broadcast: {str(e)}", "ERROR")
                        bot_instance.send_message(
                            call.message.chat.id,
                            f"❌ خطا در ارسال پیام: {str(e)}"
                        )
                
                # شروع ترد
                broadcast_thread = threading.Thread(target=broadcast_thread)
                broadcast_thread.daemon = True
                broadcast_thread.start()
                
            elif action == "cancel":
                # لغو ارسال
                bot_instance.answer_callback_query(call.id, "ارسال پیام لغو شد")
                
                bot_instance.edit_message_text(
                    "📣 *ارسال پیام لغو شد.*",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="Markdown"
                )
                
                # پاکسازی وضعیت
                with lock:
                    if user_id in user_state:
                        del user_state[user_id]
            
        except Exception as e:
            debug_log(f"خطا در پردازش callback broadcast: {str(e)}", "ERROR")
            try:
                bot_instance.answer_callback_query(call.id, "خطایی رخ داده است", show_alert=True)
            except Exception:
                pass
    
    # دستور مشاهده همه دانلودها
    @bot_instance.message_handler(commands=['downloads'])
    def downloads_command(message):
        try:
            user_id = message.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['unauthorized'])
                return
                
            # دریافت همه دانلودها
            from database import get_all_downloads
            
            downloads = get_all_downloads(limit=20)
            
            if not downloads:
                bot_instance.reply_to(message, "📂 هیچ دانلودی یافت نشد.")
                return
                
            # نمایش دانلودها
            result = "📋 *لیست دانلودها:*\n\n"
            
            for i, dl in enumerate(downloads, 1):
                # وضعیت دانلود
                status_emoji = "⏳" if dl['status'] in [0, 1] else ("✅" if dl['status'] == 2 else ("❌" if dl['status'] == 3 else "🚫"))
                status_text = ["در انتظار", "در حال پردازش", "تکمیل شده", "با خطا مواجه شد", "لغو شده"][dl['status']]
                
                # استخراج عنوان ویدیو
                title = "ویدیو ناشناس"
                if dl.get('metadata') and isinstance(dl['metadata'], dict) and dl['metadata'].get('title'):
                    title = dl['metadata']['title']
                
                # افزودن اطلاعات دانلود
                result += f"{i}. {status_emoji} *#{dl['id']}* - کاربر: `{dl['user_id']}`\n"
                result += f"🎬 *عنوان:* {title[:30]}...\n"
                result += f"🔄 *وضعیت:* {status_text}\n"
                
                # اگر اندازه فایل موجود است
                if dl.get('file_size'):
                    from youtube_downloader import format_filesize
                    result += f"📦 *حجم:* {format_filesize(dl['file_size'])}\n"
                
                # افزودن زمان شروع
                if dl.get('start_time'):
                    start_time = dl['start_time'].split('T')[0] if 'T' in dl['start_time'] else dl['start_time']
                    result += f"🕒 *زمان شروع:* {start_time}\n"
                
                # دکمه‌ها برای دانلودهای در حال انجام
                if dl['status'] in [0, 1]:
                    result += f"برای لغو دانلود: /cancel_{dl['id']}\n"
                
                result += "\n"
                
                # محدودیت اندازه پیام
                if len(result) > 3500:
                    result += f"... و {len(downloads) - i} دانلود دیگر"
                    break
            
            bot_instance.send_message(message.chat.id, result, parse_mode="Markdown")
            
        except Exception as e:
            debug_log(f"خطا در دستور downloads: {str(e)}", "ERROR")
            bot_instance.reply_to(message, f"متأسفانه خطایی رخ داده است: {str(e)}")
    
    # دستور لغو همه دانلودهای در حال انجام
    @bot_instance.message_handler(commands=['cancelall'])
    def cancelall_command(message):
        try:
            user_id = message.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.reply_to(message, BOT_MESSAGES['unauthorized'])
                return
                
            # دریافت دانلودهای در حال انجام
            from database import get_all_downloads
            from youtube_downloader import cancel_download
            
            # دانلودهای در حال انتظار یا پردازش
            downloads = get_all_downloads(status=0) + get_all_downloads(status=1)
            
            if not downloads:
                bot_instance.reply_to(message, "📂 هیچ دانلود فعالی یافت نشد.")
                return
                
            # تأیید لغو
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            confirm_button = types.InlineKeyboardButton("✅ تأیید", callback_data="cancelall_confirm")
            cancel_button = types.InlineKeyboardButton("❌ لغو", callback_data="cancelall_cancel")
            
            markup.add(confirm_button, cancel_button)
            
            # ذخیره اطلاعات در وضعیت کاربر
            with lock:
                user_state[user_id] = {"action": "cancelall", "count": len(downloads)}
            
            # ارسال درخواست تأیید
            bot_instance.reply_to(
                message,
                f"⚠️ آیا از لغو {len(downloads)} دانلود فعال اطمینان دارید؟",
                reply_markup=markup
            )
            
        except Exception as e:
            debug_log(f"خطا در دستور cancelall: {str(e)}", "ERROR")
            bot_instance.reply_to(message, f"متأسفانه خطایی رخ داده است: {str(e)}")
    
    # هندلر تأیید یا لغو cancelall
    @bot_instance.callback_query_handler(func=lambda call: call.data.startswith("cancelall_"))
    def cancelall_callback(call):
        try:
            user_id = call.from_user.id
            
            # بررسی ادمین بودن کاربر
            if not is_admin(user_id):
                bot_instance.answer_callback_query(call.id, "شما دسترسی ادمین ندارید!", show_alert=True)
                return
                
            action = call.data.split("_")[1]
            
            # بررسی وجود اطلاعات
            with lock:
                if user_id not in user_state or user_state[user_id].get("action") != "cancelall":
                    bot_instance.answer_callback_query(call.id, "اطلاعات یافت نشد", show_alert=True)
                    return
                
                count = user_state[user_id].get("count", 0)
            
            if action == "confirm":
                # تأیید لغو
                bot_instance.answer_callback_query(call.id, "لغو دانلودها آغاز شد")
                
                bot_instance.edit_message_text(
                    "🔄 *در حال لغو دانلودها...*",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="Markdown"
                )
                
                # شروع لغو در ترد جداگانه
                def cancelall_thread():
                    try:
                        from database import get_all_downloads
                        from youtube_downloader import cancel_download
                        
                        # دانلودهای در حال انتظار یا پردازش
                        downloads = get_all_downloads(status=0) + get_all_downloads(status=1)
                        
                        successful = 0
                        failed = 0
                        
                        for dl in downloads:
                            download_id = dl.get('id')
                            
                            if not download_id:
                                continue
                                
                            try:
                                if cancel_download(download_id):
                                    successful += 1
                                else:
                                    failed += 1
                            except Exception:
                                failed += 1
                        
                        # گزارش نتیجه
                        bot_instance.send_message(
                            call.message.chat.id,
                            f"📋 *نتیجه لغو دانلودها:*\n\n"
                            f"✅ لغو موفق: {successful}\n"
                            f"❌ لغو ناموفق: {failed}\n"
                            f"📊 مجموع: {successful + failed}",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        debug_log(f"خطا در ترد cancelall: {str(e)}", "ERROR")
                        bot_instance.send_message(
                            call.message.chat.id,
                            f"❌ خطا در لغو دانلودها: {str(e)}"
                        )
                
                # شروع ترد
                cancelall_thread = threading.Thread(target=cancelall_thread)
                cancelall_thread.daemon = True
                cancelall_thread.start()
                
            elif action == "cancel":
                # لغو عملیات
                bot_instance.answer_callback_query(call.id, "عملیات لغو شد")
                
                bot_instance.edit_message_text(
                    "❌ *عملیات لغو دانلودها انجام نشد.*",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="Markdown"
                )
                
                # پاکسازی وضعیت
                with lock:
                    if user_id in user_state:
                        del user_state[user_id]
            
        except Exception as e:
            debug_log(f"خطا در پردازش callback cancelall: {str(e)}", "ERROR")
            try:
                bot_instance.answer_callback_query(call.id, "خطایی رخ داده است", show_alert=True)
            except Exception:
                pass
