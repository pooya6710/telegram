"""
ماژول ربات شیشه‌ای
این ماژول یک رابط کاربری ساده‌تر برای مدیریت هشتگ‌ها و کانال‌ها ارائه می‌دهد.
همچنین امکانات فراخوانی مطالب با هشتگ را تسهیل می‌کند.
"""

import os
import json
import time
import telebot
from telebot import types
from typing import Dict, List, Any, Tuple, Optional, Union, Callable

# مسیر فایل هشتگ‌ها
HASHTAGS_FILE = "hashtags.json"
# حداکثر تعداد نتایج جستجو
MAX_SEARCH_RESULTS = 20
# شناسه‌های ادمین
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", "0"))]

# تلاش برای وارد کردن ماژول‌های مدیریت هشتگ
try:
    from hashtag_manager import HashtagManager, load_hashtags, save_hashtags
    from debug_logger import debug_log
except ImportError:
    # در صورت عدم وجود ماژول‌های لازم، تعریف توابع ساده برای لاگینگ
    def debug_log(message, level="DEBUG", context=None):
        """لاگ کردن ساده در صورت عدم وجود ماژول debug_logger"""
        print(f"[{level}] {message}")

    # در صورت عدم وجود ماژول‌های لازم، تعریف کلاس‌های پیش‌فرض
    import json
    from typing import Dict, List, Any, Tuple, Optional, Union
    
    class HashtagManager:
        def __init__(self):
            self.data = {"hashtags": {}, "channels": [], "messages": {}}
            self.load_data()
        
        def load_data(self) -> Dict[str, Any]:
            """بارگیری اطلاعات هشتگ‌ها و کانال‌ها از فایل"""
            try:
                with open("hashtags.json", "r", encoding="utf-8") as file:
                    self.data = json.load(file)
                return self.data
            except (FileNotFoundError, json.JSONDecodeError) as e:
                debug_log(f"خطا در بارگیری فایل هشتگ‌ها: {e}", "ERROR")
                return self.data
        
        def save_data(self) -> bool:
            """ذخیره اطلاعات هشتگ‌ها و کانال‌ها در فایل"""
            try:
                with open("hashtags.json", "w", encoding="utf-8") as file:
                    json.dump(self.data, file, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                debug_log(f"خطا در ذخیره فایل هشتگ‌ها: {e}", "ERROR")
                return False
                
        def add_hashtag(self, hashtag: str, description: str, user_id: int) -> Tuple[bool, str]:
            """افزودن هشتگ جدید"""
            if not hashtag.startswith("#"):
                hashtag = "#" + hashtag
                
            if hashtag in self.data["hashtags"]:
                return False, f"هشتگ {hashtag} قبلاً اضافه شده است."
                
            self.data["hashtags"][hashtag] = {
                "description": description,
                "created_by": user_id,
                "created_at": "",
                "messages": []
            }
            
            self.save_data()
            return True, f"هشتگ {hashtag} با موفقیت اضافه شد."
            
        def remove_hashtag(self, hashtag: str) -> Tuple[bool, str]:
            """حذف هشتگ موجود"""
            if not hashtag.startswith("#"):
                hashtag = "#" + hashtag
                
            if hashtag not in self.data["hashtags"]:
                return False, f"هشتگ {hashtag} یافت نشد."
                
            del self.data["hashtags"][hashtag]
            self.save_data()
            return True, f"هشتگ {hashtag} با موفقیت حذف شد."
            
        def get_hashtags_list(self) -> List[Dict[str, Any]]:
            """دریافت لیست هشتگ‌ها"""
            result = []
            for hashtag, info in self.data["hashtags"].items():
                result.append({
                    "name": hashtag,
                    "description": info.get("description", ""),
                    "message_count": len(info.get("messages", []))
                })
            return result
            
        def add_channel(self, channel_id: Union[int, str]) -> Tuple[bool, str]:
            """افزودن کانال جدید برای جستجوی هشتگ"""
            # تبدیل شناسه کانال به رشته برای ذخیره‌سازی یکسان
            channel_id = str(channel_id)
            
            # اگر با @ شروع شده، بدون تغییر نگه می‌داریم
            if channel_id.startswith('@'):
                pass
            # اگر عدد منفی است، احتمالاً شناسه عددی کانال است
            elif channel_id.startswith('-'):
                # اطمینان از فرمت درست برای شناسه‌های عددی
                if not channel_id.startswith('-100'):
                    channel_id = '-100' + channel_id[1:]
            
            if channel_id in self.data["channels"]:
                return False, f"کانال {channel_id} قبلاً اضافه شده است."
                
            self.data["channels"].append(channel_id)
            self.save_data()
            return True, f"کانال {channel_id} با موفقیت اضافه شد."
            
        def remove_channel(self, channel_id: Union[int, str]) -> Tuple[bool, str]:
            """حذف کانال"""
            channel_id = str(channel_id)
            
            if channel_id not in self.data["channels"]:
                return False, f"کانال {channel_id} یافت نشد."
                
            self.data["channels"].remove(channel_id)
            self.save_data()
            return True, f"کانال {channel_id} با موفقیت حذف شد."
            
        def get_channels_list(self) -> List[str]:
            """دریافت لیست کانال‌ها"""
            return self.data["channels"]
            
        def search_hashtag(self, hashtag: str) -> Tuple[bool, Dict[str, Any]]:
            """جستجو برای یک هشتگ"""
            if not hashtag.startswith("#"):
                hashtag = "#" + hashtag
                
            if hashtag in self.data["hashtags"]:
                return True, self.data["hashtags"][hashtag]
                
            # جستجوی هشتگ‌های مشابه
            similar_hashtags = self.fuzzy_search_hashtag(hashtag)
            if similar_hashtags:
                return False, {"similar_hashtags": similar_hashtags}
                
            return False, {}
                
        def search_hashtag_in_channels(self, hashtag: str, progress_callback=None) -> List[Dict[str, Any]]:
            """جستجوی هشتگ در همه کانال‌ها"""
            if not hashtag.startswith("#"):
                hashtag = "#" + hashtag
                
            found_messages = []
            total_channels = len(self.data["channels"])
            
            if not self.data["channels"]:
                if progress_callback:
                    progress_callback(0, 0, total_channels, "⚠️ هنوز هیچ کانالی تعریف نشده است.")
                return found_messages
                
            for idx, channel_id in enumerate(self.data["channels"]):
                if progress_callback:
                    progress_callback(idx, len(found_messages), total_channels)
                    
                if "messages" in self.data and channel_id in self.data["messages"]:
                    for msg in self.data["messages"].get(channel_id, []):
                        if "text" in msg and hashtag.lower() in msg["text"].lower():
                            found_messages.append({
                                "chat_id": msg.get("chat_id", channel_id),
                                "message_id": msg.get("message_id", 0),
                                "text": msg.get("text", ""),
                                "date": msg.get("date", "نامشخص")
                            })
            
            return found_messages
            
        def fuzzy_search_hashtag(self, query: str) -> List[Dict[str, Any]]:
            """جستجوی فازی هشتگ"""
            clean_query = query[1:] if query.startswith("#") else query
            results = []
            
            for hashtag, info in self.data["hashtags"].items():
                clean_hashtag = hashtag[1:]
                if clean_query.lower() in clean_hashtag.lower():
                    similarity_score = len(clean_query) / len(clean_hashtag) if len(clean_hashtag) > 0 else 0
                    results.append({
                        "name": hashtag,
                        "description": info.get("description", ""),
                        "message_count": len(info.get("messages", [])),
                        "similarity": similarity_score
                    })
            
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results

    def load_hashtags():
        manager = HashtagManager()
        return manager.data
    
    def save_hashtags(data):
        manager = HashtagManager()
        manager.data = data
        return manager.save_data()

# ثابت‌ها قبلاً در بالای فایل تعریف شده‌اند

class TransparentBot:
    """
    کلاس اصلی ربات شیشه‌ای
    این کلاس رابط کاربری ساده‌تری برای مدیریت هشتگ‌ها و کانال‌ها ارائه می‌دهد.
    """
    
    def __init__(self, bot: telebot.TeleBot):
        """
        راه‌اندازی ربات شیشه‌ای
        
        Args:
            bot: نمونه ربات تلگرام
        """
        self.bot = bot
        self.hashtag_manager = HashtagManager()
        debug_log("ربات شیشه‌ای با موفقیت راه‌اندازی شد", "INFO")
    
    def register_handlers(self):
        """
        ثبت هندلرهای دستورات ربات شیشه‌ای
        """
        try:
            # ثبت دستورات اصلی
            self.bot.message_handler(commands=['transparent'])(self.show_transparent_menu)
            self.bot.message_handler(commands=['addchannel'])(self.add_channel_command)
            self.bot.message_handler(commands=['removechannel'])(self.remove_channel_command)
            self.bot.message_handler(commands=['channels'])(self.list_channels_command)
            self.bot.message_handler(commands=['tag'])(self.search_hashtag_simple)
            
            # ثبت هندلر برای دکمه‌های اینلاین
            self.bot.callback_query_handler(func=lambda call: call.data.startswith('transparent'))(self.handle_transparent_callbacks)
            
            debug_log("هندلرهای ربات شیشه‌ای با موفقیت ثبت شدند", "INFO")
            return True
        except Exception as e:
            debug_log(f"خطا در ثبت هندلرهای ربات شیشه‌ای: {e}", "ERROR")
            return False
    
    def show_transparent_menu(self, message):
        """
        نمایش منوی اصلی ربات شیشه‌ای
        
        Args:
            message: پیام دریافتی از کاربر
        """
        try:
            # ایجاد دکمه‌های منو
            markup = types.InlineKeyboardMarkup(row_width=2)
            items = [
                types.InlineKeyboardButton("➕ افزودن کانال", callback_data="transparent_add_channel"),
                types.InlineKeyboardButton("➖ حذف کانال", callback_data="transparent_remove_channel"),
                types.InlineKeyboardButton("📋 لیست کانال‌ها", callback_data="transparent_list_channels"),
                types.InlineKeyboardButton("🔍 جستجوی هشتگ", callback_data="transparent_search_hashtag"),
                types.InlineKeyboardButton("➕ افزودن هشتگ", callback_data="transparent_add_hashtag"),
                types.InlineKeyboardButton("➖ حذف هشتگ", callback_data="transparent_remove_hashtag"),
                types.InlineKeyboardButton("📋 لیست هشتگ‌ها", callback_data="transparent_list_hashtags")
            ]
            markup.add(*items)
            
            # ارسال پیام منو
            self.bot.send_message(
                message.chat.id,
                "🔮 *منوی ربات شیشه‌ای*\n\n"
                "با استفاده از این منو می‌توانید به راحتی کانال‌ها و هشتگ‌ها را مدیریت کنید.",
                parse_mode='Markdown',
                reply_markup=markup
            )
        except Exception as e:
            debug_log(f"خطا در نمایش منوی ربات شیشه‌ای: {e}", "ERROR")
            self.bot.reply_to(message, "❌ خطایی در نمایش منو رخ داد.")
    
    def handle_transparent_callbacks(self, call):
        """
        پردازش کال‌بک‌های دکمه‌های اینلاین
        
        Args:
            call: کال‌بک دریافتی از کاربر
        """
        try:
            # پاسخ به کال‌بک
            self.bot.answer_callback_query(call.id)
            
            # تشخیص نوع کال‌بک
            action = call.data.split('_', 1)[1] if '_' in call.data else ''
            
            if action == "add_channel":
                # درخواست افزودن کانال
                self.bot.send_message(
                    call.message.chat.id,
                    "🆕 *افزودن کانال جدید*\n\n"
                    "لطفاً شناسه کانال را وارد کنید. می‌توانید به یکی از این روش‌ها عمل کنید:\n"
                    "1️⃣ وارد کردن شناسه عددی کانال (مثال: `-1001234567890`)\n"
                    "2️⃣ وارد کردن نام کاربری کانال (مثال: `@mychannel`)\n\n"
                    "دستور: `/addchannel ID_CHANNEL`",
                    parse_mode='Markdown'
                )
            
            elif action == "remove_channel":
                # درخواست حذف کانال
                channels = self.hashtag_manager.get_channels_list()
                
                if not channels:
                    self.bot.send_message(
                        call.message.chat.id,
                        "❌ هیچ کانالی ثبت نشده است."
                    )
                    return
                
                # ایجاد دکمه‌های انتخاب کانال
                markup = types.InlineKeyboardMarkup(row_width=1)
                for channel in channels:
                    markup.add(types.InlineKeyboardButton(
                        f"🗑️ {channel}",
                        callback_data=f"transparent_delete_channel_{channel}"
                    ))
                
                self.bot.send_message(
                    call.message.chat.id,
                    "🗑️ *حذف کانال*\n\n"
                    "کانال مورد نظر برای حذف را انتخاب کنید:",
                    parse_mode='Markdown',
                    reply_markup=markup
                )
            
            elif action.startswith("delete_channel_"):
                # حذف کانال انتخاب شده
                channel_id = action.split('delete_channel_', 1)[1]
                success, message = self.hashtag_manager.remove_channel(channel_id)
                
                self.bot.edit_message_text(
                    f"🗑️ *حذف کانال*\n\n{message}",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown'
                )
            
            elif action == "list_channels":
                # نمایش لیست کانال‌ها
                self.list_channels_simple(call.message)
            
            elif action == "search_hashtag":
                # درخواست جستجوی هشتگ
                self.bot.send_message(
                    call.message.chat.id,
                    "🔍 *جستجوی هشتگ*\n\n"
                    "لطفاً هشتگ مورد نظر خود را وارد کنید (با یا بدون علامت #).\n\n"
                    "دستور: `/tag هشتگ_مورد_نظر`",
                    parse_mode='Markdown'
                )
            
            elif action == "add_hashtag":
                # درخواست افزودن هشتگ
                self.bot.send_message(
                    call.message.chat.id,
                    "➕ *افزودن هشتگ جدید*\n\n"
                    "لطفاً هشتگ و توضیحات آن را وارد کنید.\n"
                    "فرمت: `/addhashtag هشتگ توضیحات`\n\n"
                    "مثال: `/addhashtag برنامه_نویسی مطالب مربوط به برنامه نویسی و کدنویسی`",
                    parse_mode='Markdown'
                )
            
            elif action == "remove_hashtag":
                # درخواست حذف هشتگ
                hashtags = self.hashtag_manager.get_hashtags_list()
                
                if not hashtags:
                    self.bot.send_message(
                        call.message.chat.id,
                        "❌ هیچ هشتگی ثبت نشده است."
                    )
                    return
                
                # ایجاد دکمه‌های انتخاب هشتگ
                markup = types.InlineKeyboardMarkup(row_width=1)
                for hashtag in hashtags:
                    markup.add(types.InlineKeyboardButton(
                        f"🗑️ {hashtag['name']}",
                        callback_data=f"transparent_delete_hashtag_{hashtag['name']}"
                    ))
                
                self.bot.send_message(
                    call.message.chat.id,
                    "🗑️ *حذف هشتگ*\n\n"
                    "هشتگ مورد نظر برای حذف را انتخاب کنید:",
                    parse_mode='Markdown',
                    reply_markup=markup
                )
            
            elif action.startswith("delete_hashtag_"):
                # حذف هشتگ انتخاب شده
                hashtag = action.split('delete_hashtag_', 1)[1]
                success, message = self.hashtag_manager.remove_hashtag(hashtag)
                
                self.bot.edit_message_text(
                    f"🗑️ *حذف هشتگ*\n\n{message}",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown'
                )
            
            elif action == "list_hashtags":
                # نمایش لیست هشتگ‌ها
                self.list_hashtags_simple(call.message)
            
        except Exception as e:
            debug_log(f"خطا در پردازش کال‌بک‌های ربات شیشه‌ای: {e}", "ERROR")
            try:
                self.bot.send_message(
                    call.message.chat.id,
                    "❌ خطایی در پردازش درخواست رخ داد."
                )
            except:
                pass
    
    def add_channel_command(self, message):
        """
        افزودن کانال جدید برای جستجوی هشتگ
        
        Args:
            message: پیام دریافتی از کاربر
        """
        try:
            # بررسی فرمت پیام
            channel_id = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
            
            if not channel_id:
                self.bot.reply_to(
                    message,
                    "❌ لطفاً شناسه کانال را وارد کنید.\n"
                    "مثال: `/addchannel -1001234567890` یا `/addchannel @mychannel`",
                    parse_mode='Markdown'
                )
                return
            
            # اضافه کردن کانال
            success, result_message = self.hashtag_manager.add_channel(channel_id)
            
            # نمایش نتیجه
            self.bot.reply_to(
                message,
                f"{'✅' if success else '❌'} {result_message}"
            )
            
            # بروزرسانی لیست کانال‌ها
            if success:
                self.list_channels_simple(message)
            
        except Exception as e:
            debug_log(f"خطا در افزودن کانال: {e}", "ERROR")
            self.bot.reply_to(message, "❌ خطایی در افزودن کانال رخ داد.")
    
    def remove_channel_command(self, message):
        """
        حذف کانال از لیست جستجوی هشتگ
        
        Args:
            message: پیام دریافتی از کاربر
        """
        try:
            # بررسی فرمت پیام
            channel_id = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
            
            if not channel_id:
                # نمایش لیست کانال‌ها برای انتخاب
                channels = self.hashtag_manager.get_channels_list()
                
                if not channels:
                    self.bot.reply_to(message, "❌ هیچ کانالی ثبت نشده است.")
                    return
                
                # ایجاد دکمه‌های انتخاب کانال
                markup = types.InlineKeyboardMarkup(row_width=1)
                for channel in channels:
                    markup.add(types.InlineKeyboardButton(
                        f"🗑️ {channel}",
                        callback_data=f"transparent_delete_channel_{channel}"
                    ))
                
                self.bot.reply_to(
                    message,
                    "🗑️ *حذف کانال*\n\n"
                    "کانال مورد نظر برای حذف را انتخاب کنید:",
                    parse_mode='Markdown',
                    reply_markup=markup
                )
                return
            
            # حذف کانال
            success, result_message = self.hashtag_manager.remove_channel(channel_id)
            
            # نمایش نتیجه
            self.bot.reply_to(
                message,
                f"{'✅' if success else '❌'} {result_message}"
            )
            
            # بروزرسانی لیست کانال‌ها
            if success:
                self.list_channels_simple(message)
            
        except Exception as e:
            debug_log(f"خطا در حذف کانال: {e}", "ERROR")
            self.bot.reply_to(message, "❌ خطایی در حذف کانال رخ داد.")
    
    def list_channels_command(self, message):
        """
        نمایش لیست کانال‌های ثبت شده
        
        Args:
            message: پیام دریافتی از کاربر
        """
        try:
            self.list_channels_simple(message)
        except Exception as e:
            debug_log(f"خطا در نمایش لیست کانال‌ها: {e}", "ERROR")
            self.bot.reply_to(message, "❌ خطایی در نمایش لیست کانال‌ها رخ داد.")
    
    def list_channels_simple(self, message):
        """
        نمایش لیست کانال‌های ثبت شده به صورت ساده
        
        Args:
            message: پیام دریافتی از کاربر
        """
        try:
            # دریافت لیست کانال‌ها
            channels = self.hashtag_manager.get_channels_list()
            
            if not channels:
                self.bot.reply_to(message, "❌ هیچ کانالی ثبت نشده است.")
                return
            
            # ایجاد متن پاسخ
            channel_list_text = "\n".join([f"🔹 `{channel}`" for channel in channels])
            
            # ایجاد دکمه‌ها
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("➕ افزودن کانال", callback_data="transparent_add_channel"),
                types.InlineKeyboardButton("➖ حذف کانال", callback_data="transparent_remove_channel")
            )
            
            # ارسال پاسخ
            self.bot.reply_to(
                message,
                f"📋 *لیست کانال‌های ثبت شده ({len(channels)} کانال):*\n\n"
                f"{channel_list_text}",
                parse_mode='Markdown',
                reply_markup=markup
            )
            
        except Exception as e:
            debug_log(f"خطا در نمایش لیست کانال‌ها: {e}", "ERROR")
            self.bot.reply_to(message, "❌ خطایی در نمایش لیست کانال‌ها رخ داد.")
    
    def list_hashtags_simple(self, message):
        """
        نمایش لیست هشتگ‌های ثبت شده به صورت ساده
        
        Args:
            message: پیام دریافتی از کاربر
        """
        try:
            # دریافت لیست هشتگ‌ها
            hashtags = self.hashtag_manager.get_hashtags_list()
            
            if not hashtags:
                self.bot.reply_to(message, "❌ هیچ هشتگی ثبت نشده است.")
                return
            
            # ایجاد متن پاسخ
            hashtag_list_text = "\n\n".join([
                f"🔸 *{h['name']}*\n"
                f"📝 {h['description']}\n"
                f"🔢 تعداد پیام: {h['message_count']}"
                for h in hashtags
            ])
            
            # ایجاد دکمه‌ها
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("➕ افزودن هشتگ", callback_data="transparent_add_hashtag"),
                types.InlineKeyboardButton("➖ حذف هشتگ", callback_data="transparent_remove_hashtag")
            )
            
            # ارسال پاسخ
            self.bot.reply_to(
                message,
                f"📋 *لیست هشتگ‌های ثبت شده ({len(hashtags)} هشتگ):*\n\n"
                f"{hashtag_list_text}",
                parse_mode='Markdown',
                reply_markup=markup
            )
            
        except Exception as e:
            debug_log(f"خطا در نمایش لیست هشتگ‌ها: {e}", "ERROR")
            self.bot.reply_to(message, "❌ خطایی در نمایش لیست هشتگ‌ها رخ داد.")
    
    def search_hashtag_simple(self, message):
        """
        جستجوی ساده هشتگ
        
        Args:
            message: پیام دریافتی از کاربر
        """
        try:
            # بررسی فرمت پیام
            hashtag = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
            
            if not hashtag:
                self.bot.reply_to(
                    message,
                    "❌ لطفاً هشتگ مورد نظر را وارد کنید.\n"
                    "مثال: `/tag برنامه_نویسی`",
                    parse_mode='Markdown'
                )
                return
            
            # اضافه کردن # به ابتدای هشتگ اگر وجود نداشته باشد
            if not hashtag.startswith("#"):
                hashtag = "#" + hashtag
            
            # بررسی وجود هشتگ
            success, result = self.hashtag_manager.search_hashtag(hashtag)
            
            if not success:
                # بررسی هشتگ‌های مشابه
                if "similar_hashtags" in result and result["similar_hashtags"]:
                    similar_text = "\n".join([
                        f"🔹 `{h['name']}` (شباهت: {h['similarity']:.2f})"
                        for h in result["similar_hashtags"][:5]
                    ])
                    
                    self.bot.reply_to(
                        message,
                        f"❌ هشتگ `{hashtag}` یافت نشد.\n\n"
                        f"🔍 هشتگ‌های مشابه:\n{similar_text}",
                        parse_mode='Markdown'
                    )
                else:
                    self.bot.reply_to(
                        message,
                        f"❌ هشتگ `{hashtag}` یافت نشد و هشتگ مشابهی نیز پیدا نشد.",
                        parse_mode='Markdown'
                    )
                return
            
            # ارسال پیام جستجو
            processing_msg = self.bot.reply_to(
                message,
                f"🔍 در حال جستجوی هشتگ `{hashtag}` در کانال‌ها...",
                parse_mode='Markdown'
            )
            
            # جستجوی هشتگ در کانال‌ها
            def search_and_display():
                try:
                    # ایجاد تابع گزارش پیشرفت
                    def progress_callback(processed, found_count, total, error_msg=None):
                        try:
                            # بروزرسانی پیام پیشرفت هر 10 کانال یا در صورت خطا
                            if error_msg or processed % 10 == 0 or processed == total:
                                progress_percentage = int((processed / total) * 100) if total > 0 else 0
                                progress_bar = "▰" * (progress_percentage // 10) + "▱" * (10 - (progress_percentage // 10))
                                
                                status_text = (
                                    f"🔍 جستجوی هشتگ `{hashtag}`\n\n"
                                    f"📊 پیشرفت: {progress_bar} {progress_percentage}%\n"
                                    f"🔢 کانال‌های بررسی شده: {processed}/{total}\n"
                                    f"✅ نتایج یافت شده: {found_count}"
                                )
                                
                                if error_msg:
                                    status_text += f"\n\n⚠️ {error_msg}"
                                
                                self.bot.edit_message_text(
                                    status_text,
                                    message.chat.id,
                                    processing_msg.message_id,
                                    parse_mode='Markdown'
                                )
                        except Exception as e:
                            debug_log(f"خطا در گزارش پیشرفت جستجو: {e}", "ERROR")
                    
                    # انجام جستجو با گزارش پیشرفت
                    messages = self.hashtag_manager.search_hashtag_in_channels(hashtag, progress_callback)
                    
                    # نمایش نتایج جستجو
                    self.show_hashtag_messages_simple(message, hashtag, messages, processing_msg.message_id)
                    
                except Exception as e:
                    debug_log(f"خطا در جستجوی هشتگ: {e}", "ERROR")
                    try:
                        self.bot.edit_message_text(
                            f"❌ خطایی در جستجوی هشتگ `{hashtag}` رخ داد:\n{str(e)}",
                            message.chat.id,
                            processing_msg.message_id,
                            parse_mode='Markdown'
                        )
                    except:
                        pass
            
            # اجرای جستجو در یک ترد جداگانه
            import threading
            threading.Thread(target=search_and_display).start()
            
        except Exception as e:
            debug_log(f"خطا در جستجوی هشتگ: {e}", "ERROR")
            self.bot.reply_to(message, f"❌ خطایی در جستجوی هشتگ رخ داد: {str(e)}")
    
    def show_hashtag_messages_simple(self, message, hashtag, messages, processing_msg_id=None):
        """
        نمایش پیام‌های یافته شده برای هشتگ به صورت ساده
        
        Args:
            message: پیام دریافتی از کاربر
            hashtag: هشتگ جستجو شده
            messages: لیست پیام‌های یافت شده
            processing_msg_id: شناسه پیام "در حال جستجو"
        """
        try:
            if not messages:
                # نمایش پیام خطا
                error_message = f"❌ هیچ پیامی با هشتگ `{hashtag}` یافت نشد."
                
                if processing_msg_id:
                    self.bot.edit_message_text(
                        error_message,
                        message.chat.id,
                        processing_msg_id,
                        parse_mode='Markdown'
                    )
                else:
                    self.bot.reply_to(message, error_message, parse_mode='Markdown')
                return
            
            # ساخت لیست پیام‌ها با دکمه برای مشاهده
            result_text = f"✅ نتایج جستجوی هشتگ `{hashtag}`\n\n"
            result_text += f"🔢 تعداد نتایج: {len(messages)}"
            
            # ایجاد دکمه‌های اینلاین برای هر پیام
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            # اضافه کردن دکمه برای هر پیام (حداکثر 10 پیام)
            for idx, msg in enumerate(messages[:10]):
                # استخراج بخشی از متن پیام
                text_preview = msg.get("text", "").replace(hashtag, f"**{hashtag}**")
                if len(text_preview) > 50:
                    text_preview = text_preview[:47] + "..."
                
                # اضافه کردن دکمه
                markup.add(types.InlineKeyboardButton(
                    f"{idx+1}. {text_preview}",
                    url=f"https://t.me/c/{msg['chat_id'].replace('-100', '')}/{msg['message_id']}"
                    if str(msg['chat_id']).startswith('-100') else f"https://t.me/{msg['chat_id']}/{msg['message_id']}"
                ))
            
            # اضافه کردن دکمه "بیشتر" اگر تعداد پیام‌ها بیشتر از 10 باشد
            if len(messages) > 10:
                # دکمه برای نمایش نتایج بیشتر
                markup.add(types.InlineKeyboardButton(
                    f"مشاهده {len(messages) - 10} نتیجه بیشتر...",
                    callback_data=f"transparent_more_results_{hashtag}"
                ))
            
            # بروزرسانی پیام جستجو یا ارسال پیام جدید
            if processing_msg_id:
                self.bot.edit_message_text(
                    result_text,
                    message.chat.id,
                    processing_msg_id,
                    parse_mode='Markdown',
                    reply_markup=markup
                )
            else:
                self.bot.reply_to(
                    message,
                    result_text,
                    parse_mode='Markdown',
                    reply_markup=markup
                )
            
        except Exception as e:
            debug_log(f"خطا در نمایش نتایج هشتگ: {e}", "ERROR")
            try:
                if processing_msg_id:
                    self.bot.edit_message_text(
                        f"❌ خطایی در نمایش نتایج هشتگ `{hashtag}` رخ داد.",
                        message.chat.id,
                        processing_msg_id,
                        parse_mode='Markdown'
                    )
                else:
                    self.bot.reply_to(
                        message,
                        f"❌ خطایی در نمایش نتایج هشتگ `{hashtag}` رخ داد."
                    )
            except:
                pass

# تابع راه‌اندازی ربات شیشه‌ای
def setup_transparent_bot(bot):
    """
    راه‌اندازی و ثبت هندلرهای ربات شیشه‌ای
    
    Args:
        bot: نمونه ربات تلگرام
        
    Returns:
        نمونه ربات شیشه‌ای
    """
    transparent_bot = TransparentBot(bot)
    transparent_bot.register_handlers()
    return transparent_bot