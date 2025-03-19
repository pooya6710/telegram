"""
هندلرهای دستورات مرتبط با هشتگ‌ها
"""

import os
import time
import threading
from typing import Dict, List, Any, Optional, Tuple, Union

try:
    from debug_logger import debug_log
except ImportError:
    def debug_log(message, level="DEBUG", context=None):
        """لاگ کردن ساده در صورت عدم وجود ماژول debug_logger"""
        print(f"{level}: {message}")

from hashtag_manager import hashtag_manager, load_hashtags, save_hashtags

# حداکثر تعداد پیام‌ها برای ارسال
MAX_SEND_MESSAGES = 15

def register_hashtag_handlers(bot):
    """
    ثبت هندلرهای مربوط به هشتگ‌ها
    
    Args:
        bot: نمونه ربات تلگرام
    """
    try:
        # دستور اضافه کردن هشتگ
        @bot.message_handler(commands=["add_hashtag"])
        def add_hashtag_command(message):
            handle_add_hashtag(bot, message)
        
        # دستور حذف هشتگ
        @bot.message_handler(commands=["remove_hashtag"])
        def remove_hashtag_command(message):
            handle_remove_hashtag(bot, message)
        
        # دستور نمایش لیست هشتگ‌ها
        @bot.message_handler(commands=["hashtags", "list_hashtags"])
        def list_hashtags_command(message):
            handle_list_hashtags(bot, message)
        
        # دستور اضافه کردن کانال
        @bot.message_handler(commands=["add_channel"])
        def add_channel_command(message):
            handle_add_channel(bot, message)
        
        # دستور حذف کانال
        @bot.message_handler(commands=["remove_channel"])
        def remove_channel_command(message):
            handle_remove_channel(bot, message)
        
        # دستور نمایش لیست کانال‌ها
        @bot.message_handler(commands=["channels", "list_channels"])
        def list_channels_command(message):
            handle_list_channels(bot, message)
        
        # دستور جستجوی هشتگ
        @bot.message_handler(commands=["search", "search_hashtag"])
        def search_hashtag_command(message):
            handle_search_hashtag(bot, message)
        
        debug_log("هندلرهای هشتگ با موفقیت ثبت شدند")
    except Exception as e:
        debug_log(f"خطا در ثبت هندلرهای هشتگ: {e}", "ERROR")

def handle_add_hashtag(bot, message):
    """
    پردازش دستور اضافه کردن هشتگ
    
    Args:
        bot: نمونه ربات تلگرام
        message: پیام دریافتی از کاربر
    """
    try:
        # جداسازی آرگومان‌ها
        args = message.text.split(maxsplit=2)
        
        # بررسی آرگومان‌های لازم
        if len(args) < 3:
            bot.reply_to(message, "⚠️ فرمت دستور نادرست است.\n"
                        "📝 نحوه استفاده: `/add_hashtag نام_هشتگ توضیحات`\n"
                        "مثال: `/add_hashtag آموزش این هشتگ برای ویدیوهای آموزشی است`", parse_mode="Markdown")
            return
        
        # دریافت نام هشتگ و توضیحات
        hashtag = args[1]
        description = args[2]
        
        # افزودن هشتگ
        success, msg = hashtag_manager.add_hashtag(hashtag, description, message.from_user.id)
        
        # ارسال پاسخ
        bot.reply_to(message, msg)
        
    except Exception as e:
        debug_log(f"خطا در اضافه کردن هشتگ", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

def handle_remove_hashtag(bot, message):
    """
    پردازش دستور حذف هشتگ
    
    Args:
        bot: نمونه ربات تلگرام
        message: پیام دریافتی از کاربر
    """
    try:
        # جداسازی آرگومان‌ها
        args = message.text.split(maxsplit=1)
        
        # بررسی آرگومان‌های لازم
        if len(args) < 2:
            bot.reply_to(message, "⚠️ فرمت دستور نادرست است.\n"
                        "📝 نحوه استفاده: `/remove_hashtag نام_هشتگ`\n"
                        "مثال: `/remove_hashtag آموزش`", parse_mode="Markdown")
            return
        
        # دریافت نام هشتگ
        hashtag = args[1]
        
        # حذف هشتگ
        success, msg = hashtag_manager.remove_hashtag(hashtag)
        
        # ارسال پاسخ
        bot.reply_to(message, msg)
        
    except Exception as e:
        debug_log(f"خطا در حذف هشتگ", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

def handle_list_hashtags(bot, message):
    """
    پردازش دستور نمایش لیست هشتگ‌ها
    
    Args:
        bot: نمونه ربات تلگرام
        message: پیام دریافتی از کاربر
    """
    try:
        # دریافت لیست هشتگ‌ها
        hashtags = hashtag_manager.get_hashtags_list()
        
        # بررسی وجود هشتگ
        if not hashtags:
            bot.reply_to(message, "⚠️ هنوز هیچ هشتگی تعریف نشده است.")
            return
        
        # ساخت پیام پاسخ
        hashtags_list = ["🔖 <b>لیست هشتگ‌های تعریف شده:</b>\n"]
        for idx, hashtag in enumerate(hashtags, 1):
            name = hashtag["name"]
            description = hashtag["description"]
            message_count = hashtag["message_count"]
            created_at = hashtag["created_at"]
            
            hashtags_list.append(f"{idx}. <code>{name}</code> - {description}")
            hashtags_list.append(f"   📊 تعداد پیام: {message_count} | 🕒 {created_at}\n")
        
        # ارسال پاسخ
        bot.reply_to(message, "\n".join(hashtags_list), parse_mode="HTML")
        
    except Exception as e:
        debug_log(f"خطا در نمایش لیست هشتگ‌ها", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

def handle_add_channel(bot, message):
    """
    پردازش دستور اضافه کردن کانال
    
    Args:
        bot: نمونه ربات تلگرام
        message: پیام دریافتی از کاربر
    """
    try:
        # جداسازی آرگومان‌ها
        args = message.text.split(maxsplit=1)
        
        # بررسی آرگومان‌های لازم
        if len(args) < 2:
            bot.reply_to(message, "⚠️ فرمت دستور نادرست است.\n"
                        "📝 نحوه استفاده: `/add_channel شناسه_کانال`\n"
                        "مثال: `/add_channel -100123456789`", parse_mode="Markdown")
            return
        
        # دریافت شناسه کانال
        channel_id = args[1]
        
        # افزودن کانال
        success, msg = hashtag_manager.add_channel(channel_id)
        
        # ارسال پاسخ
        bot.reply_to(message, msg)
        
    except Exception as e:
        debug_log(f"خطا در اضافه کردن کانال", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

def handle_remove_channel(bot, message):
    """
    پردازش دستور حذف کانال
    
    Args:
        bot: نمونه ربات تلگرام
        message: پیام دریافتی از کاربر
    """
    try:
        # جداسازی آرگومان‌ها
        args = message.text.split(maxsplit=1)
        
        # بررسی آرگومان‌های لازم
        if len(args) < 2:
            bot.reply_to(message, "⚠️ فرمت دستور نادرست است.\n"
                        "📝 نحوه استفاده: `/remove_channel شناسه_کانال`\n"
                        "مثال: `/remove_channel -100123456789`", parse_mode="Markdown")
            return
        
        # دریافت شناسه کانال
        channel_id = args[1]
        
        # حذف کانال
        success, msg = hashtag_manager.remove_channel(channel_id)
        
        # ارسال پاسخ
        bot.reply_to(message, msg)
        
    except Exception as e:
        debug_log(f"خطا در حذف کانال", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

def handle_list_channels(bot, message):
    """
    پردازش دستور نمایش لیست کانال‌ها
    
    Args:
        bot: نمونه ربات تلگرام
        message: پیام دریافتی از کاربر
    """
    try:
        # دریافت لیست کانال‌ها
        channels = hashtag_manager.get_channels_list()
        
        # بررسی وجود کانال
        if not channels:
            bot.reply_to(message, "⚠️ هنوز هیچ کانالی تعریف نشده است.")
            return
        
        # ساخت پیام پاسخ
        channels_list = ["📢 <b>لیست کانال‌های تعریف شده:</b>\n"]
        for idx, channel_id in enumerate(channels, 1):
            channels_list.append(f"{idx}. <code>{channel_id}</code>")
        
        # ارسال پاسخ
        bot.reply_to(message, "\n".join(channels_list), parse_mode="HTML")
        
    except Exception as e:
        debug_log(f"خطا در نمایش لیست کانال‌ها", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

def handle_search_hashtag(bot, message):
    """
    پردازش دستور جستجوی هشتگ
    
    Args:
        bot: نمونه ربات تلگرام
        message: پیام دریافتی از کاربر
    """
    try:
        # جداسازی آرگومان‌ها
        args = message.text.split(maxsplit=1)
        
        # بررسی آرگومان‌های لازم
        if len(args) < 2:
            bot.reply_to(message, "⚠️ فرمت دستور نادرست است.\n"
                        "📝 نحوه استفاده: `/search نام_هشتگ`\n"
                        "مثال: `/search آموزش`", parse_mode="Markdown")
            return
        
        # دریافت نام هشتگ
        hashtag = args[1]
        
        # جستجوی هشتگ
        success, result = hashtag_manager.search_hashtag(hashtag)
        
        if success:
            # هشتگ دقیق پیدا شد
            # بررسی وجود پیام‌های ذخیره شده برای هشتگ
            if not result.get("messages", []):
                processing_msg = bot.reply_to(message, f"🔍 در حال جستجوی کانال‌ها برای هشتگ {hashtag}...")
                
                # ایجاد ترد برای جستجوی هشتگ در کانال‌ها
                search_thread = threading.Thread(
                    target=search_hashtag_in_channels,
                    args=(bot, message, hashtag, processing_msg.message_id)
                )
                search_thread.daemon = True
                search_thread.start()
            else:
                # نمایش پیام‌های ذخیره شده برای هشتگ
                show_hashtag_messages(bot, message, hashtag, result.get("messages", []))
        else:
            # هشتگ دقیق پیدا نشد
            similar_hashtags = result.get("similar_hashtags", [])
            if similar_hashtags:
                # نمایش هشتگ‌های مشابه
                show_similar_hashtags(bot, message, hashtag, similar_hashtags)
            else:
                # جستجوی فازی
                similar_results = hashtag_manager.fuzzy_search_hashtag(hashtag)
                if similar_results:
                    show_similar_hashtags(bot, message, hashtag, similar_results)
                else:
                    bot.reply_to(message, f"⚠️ هیچ هشتگ مشابه <code>{hashtag}</code> یافت نشد. لطفاً ابتدا با دستور `/add_hashtag {hashtag} توضیحات` یک هشتگ جدید تعریف کنید.", parse_mode="HTML")
        
    except Exception as e:
        debug_log(f"خطا در جستجوی هشتگ", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید.")

def search_hashtag_in_channels(bot, message, hashtag, processing_msg_id):
    """
    جستجوی هشتگ در کانال‌ها
    
    Args:
        bot: نمونه ربات تلگرام
        message: پیام دریافتی از کاربر
        hashtag: نام هشتگ
        processing_msg_id: شناسه پیام "در حال جستجو"
    """
    try:
        # تابع گزارش پیشرفت
        def progress_callback(processed, found_count, total, error_msg=None):
            try:
                if error_msg:
                    bot.edit_message_text(
                        error_msg,
                        chat_id=message.chat.id,
                        message_id=processing_msg_id
                    )
                    return
                
                bot.edit_message_text(
                    f"🔍 در حال جستجوی {total} کانال برای هشتگ {hashtag}...\n"
                    f"پیشرفت: {processed+1}/{total} کانال\n"
                    f"تعداد پیام‌های یافته شده: {found_count}",
                    chat_id=message.chat.id,
                    message_id=processing_msg_id
                )
            except Exception as e:
                debug_log(f"خطا در به‌روزرسانی پیام پیشرفت: {e}", "ERROR")
        
        # جستجو در کانال‌ها
        found_messages = hashtag_manager.search_hashtag_in_channels(hashtag, progress_callback)
        
        # نمایش نتایج
        if found_messages:
            show_hashtag_messages(bot, message, hashtag, found_messages)
            
            # حذف پیام "در حال جستجو"
            try:
                bot.delete_message(message.chat.id, processing_msg_id)
            except:
                pass
        else:
            bot.edit_message_text(
                f"⚠️ هیچ پیامی با هشتگ {hashtag} یافت نشد.",
                chat_id=message.chat.id,
                message_id=processing_msg_id
            )
        
    except Exception as e:
        debug_log(f"خطا در جستجوی هشتگ در کانال‌ها", "ERROR", {"error": str(e)})
        try:
            bot.edit_message_text(
                f"⚠️ خطا در جستجوی هشتگ: {str(e)}",
                chat_id=message.chat.id,
                message_id=processing_msg_id
            )
        except:
            bot.send_message(message.chat.id, f"⚠️ خطا در جستجوی هشتگ: {str(e)}")

def show_hashtag_messages(bot, message, hashtag, messages):
    """
    نمایش پیام‌های مرتبط با هشتگ
    
    Args:
        bot: نمونه ربات تلگرام
        message: پیام دریافتی از کاربر
        hashtag: نام هشتگ
        messages: لیست پیام‌های یافته شده
    """
    try:
        if not messages:
            bot.reply_to(message, f"⚠️ هیچ پیامی برای هشتگ {hashtag} یافت نشد.")
            return
        
        # محدود کردن تعداد پیام‌ها
        if len(messages) > MAX_SEND_MESSAGES:
            messages = messages[:MAX_SEND_MESSAGES]
        
        # ساخت پیام نتایج
        results = [f"🔖 <b>نتایج جستجو برای هشتگ {hashtag}:</b> ({len(messages)} پیام)\n"]
        
        for idx, msg in enumerate(messages, 1):
            chat_id = msg.get("chat_id", "نامشخص")
            message_id = msg.get("message_id", "نامشخص")
            text = msg.get("text", "")
            date = msg.get("date", "نامشخص")
            
            # کوتاه کردن متن طولانی
            if len(text) > 200:
                text = text[:200] + "..."
            
            # هایلایت کردن هشتگ در متن
            highlighted_text = text
            if hashtag.lower() in text.lower():
                # پیدا کردن موقعیت هشتگ در متن با حفظ کیس
                start_idx = text.lower().find(hashtag.lower())
                end_idx = start_idx + len(hashtag)
                hashtag_in_text = text[start_idx:end_idx]
                highlighted_text = text.replace(hashtag_in_text, f"<b>{hashtag_in_text}</b>")
            
            results.append(f"{idx}. <b>تاریخ:</b> {date}")
            results.append(f"<b>کانال:</b> {chat_id}")
            results.append(f"{highlighted_text}\n")
        
        # اضافه کردن لینک به پیام پیدا شده
        if len(messages) > MAX_SEND_MESSAGES:
            results.append(f"⚠️ <i>تعداد {len(messages) - MAX_SEND_MESSAGES} پیام دیگر به دلیل محدودیت نمایش داده نشد.</i>")
        
        # ارسال نتایج
        bot.reply_to(message, "\n".join(results), parse_mode="HTML")
    
    except Exception as e:
        debug_log(f"خطا در نمایش پیام‌های هشتگ", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی در نمایش نتایج رخ داد. لطفاً بعداً دوباره تلاش کنید.")

def show_similar_hashtags(bot, message, hashtag, similar_hashtags):
    """
    نمایش هشتگ‌های مشابه
    
    Args:
        bot: نمونه ربات تلگرام
        message: پیام دریافتی از کاربر
        hashtag: نام هشتگ جستجو شده
        similar_hashtags: لیست هشتگ‌های مشابه
    """
    try:
        # ساخت پیام نتایج
        results = [f"🔍 هشتگ <code>{hashtag}</code> یافت نشد، اما هشتگ‌های مشابه زیر پیدا شدند:\n"]
        
        # محدود کردن تعداد نتایج
        if len(similar_hashtags) > 10:
            similar_hashtags = similar_hashtags[:10]
        
        for idx, tag in enumerate(similar_hashtags, 1):
            name = tag["name"]
            description = tag.get("description", "")
            message_count = tag.get("message_count", 0)
            
            results.append(f"{idx}. <code>{name}</code> - {description}")
            results.append(f"   📊 تعداد پیام: {message_count}")
            # اضافه کردن دستور جستجو به صورت قابل کلیک
            results.append(f"   👉 <code>/search {name}</code>\n")
        
        # ارسال نتایج
        bot.reply_to(message, "\n".join(results), parse_mode="HTML")
    
    except Exception as e:
        debug_log(f"خطا در نمایش هشتگ‌های مشابه", "ERROR", {"error": str(e)})
        bot.reply_to(message, "⚠️ خطایی در نمایش نتایج رخ داد. لطفاً بعداً دوباره تلاش کنید.")