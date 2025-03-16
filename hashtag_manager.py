"""
ماژول مدیریت هشتگ‌ها

این ماژول شامل توابع و کلاس‌های مربوط به مدیریت هشتگ‌ها، 
جستجو در کانال‌ها و ذخیره‌سازی پیام‌های مرتبط است.
"""

import os
import time
import json
import threading
from typing import Dict, List, Any, Optional, Tuple, Union

try:
    from debug_logger import debug_log
except ImportError:
    def debug_log(message, level="DEBUG", context=None):
        """لاگ کردن ساده در صورت عدم وجود ماژول debug_logger"""
        print(f"{level}: {message}")

# مسیر فایل داده‌های هشتگ‌ها و کانال‌ها
HASHTAGS_FILE = "channel_links.json"
MAX_SEARCH_RESULTS = 50  # حداکثر تعداد نتایج جستجو

class HashtagManager:
    """
    کلاس مدیریت هشتگ‌ها و کانال‌ها
    """
    
    def __init__(self):
        """راه‌اندازی مدیریت هشتگ‌ها"""
        self.data = self.load_data()
        # اطمینان از وجود ساختار درست داده‌ها
        if "hashtags" not in self.data:
            self.data["hashtags"] = {}
        if "channels" not in self.data:
            self.data["channels"] = []
    
    def load_data(self) -> Dict[str, Any]:
        """
        بارگیری اطلاعات هشتگ‌ها و کانال‌ها از فایل
        
        Returns:
            دیکشنری داده‌های هشتگ‌ها و کانال‌ها
        """
        try:
            if os.path.exists(HASHTAGS_FILE):
                with open(HASHTAGS_FILE, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    
                    # اطمینان از ساختار درست داده‌ها
                    if not isinstance(data.get("hashtags"), dict):
                        data["hashtags"] = {}
                    if not isinstance(data.get("channels"), list):
                        data["channels"] = []
                    if not isinstance(data.get("messages"), dict):
                        # اگر بخش پیام‌ها وجود نداشت، داده‌های قدیمی را با ساختار جدید تطبیق می‌دهیم
                        messages = {}
                        for chat_id, msgs in data.items():
                            if isinstance(msgs, list) and chat_id not in ["hashtags", "channels", "messages"]:
                                messages[chat_id] = msgs
                        data["messages"] = messages
                    
                    debug_log(f"اطلاعات هشتگ‌ها با موفقیت بارگیری شد: {len(data.get('hashtags', {}))} هشتگ و {len(data.get('channels', []))} کانال")
                    return data
        except Exception as e:
            debug_log(f"خطا در بارگیری اطلاعات هشتگ‌ها: {e}", "ERROR")
        
        # اگر فایل وجود نداشت یا خطایی رخ داد، مقدار پیش‌فرض را برگردان
        return {"hashtags": {}, "channels": [], "messages": {}}
    
    def save_data(self) -> bool:
        """
        ذخیره اطلاعات هشتگ‌ها و کانال‌ها در فایل
        
        Returns:
            True در صورت موفقیت، False در صورت خطا
        """
        try:
            with open(HASHTAGS_FILE, "w", encoding="utf-8") as file:
                json.dump(self.data, file, ensure_ascii=False, indent=4)
            debug_log("اطلاعات هشتگ‌ها با موفقیت ذخیره شد")
            return True
        except Exception as e:
            debug_log(f"خطا در ذخیره اطلاعات هشتگ‌ها: {e}", "ERROR")
            return False
    
    def add_hashtag(self, hashtag: str, description: str, user_id: int) -> Tuple[bool, str]:
        """
        افزودن هشتگ جدید
        
        Args:
            hashtag: نام هشتگ (با یا بدون علامت #)
            description: توضیحات هشتگ
            user_id: شناسه کاربر ایجاد کننده
            
        Returns:
            (وضعیت موفقیت، پیام)
        """
        # اضافه کردن # به ابتدای هشتگ اگر وجود نداشته باشد
        if not hashtag.startswith("#"):
            hashtag = "#" + hashtag
        
        # بررسی کاراکترهای غیرمجاز
        if any(c in hashtag for c in [' ', '\n', '\t', '/', '@']):
            return False, "⚠️ هشتگ نباید شامل فاصله یا کاراکترهای خاص باشد"
        
        # بررسی تکراری بودن هشتگ
        if hashtag in self.data["hashtags"]:
            return False, f"⚠️ هشتگ {hashtag} قبلاً اضافه شده است"
        
        # افزودن هشتگ جدید
        self.data["hashtags"][hashtag] = {
            "description": description,
            "created_by": user_id,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "messages": []
        }
        
        # ذخیره تغییرات
        if self.save_data():
            return True, f"✅ هشتگ {hashtag} با موفقیت اضافه شد"
        else:
            return False, "⚠️ خطا در ذخیره اطلاعات هشتگ‌ها"
    
    def remove_hashtag(self, hashtag: str) -> Tuple[bool, str]:
        """
        حذف هشتگ موجود
        
        Args:
            hashtag: نام هشتگ (با یا بدون علامت #)
            
        Returns:
            (وضعیت موفقیت، پیام)
        """
        # اضافه کردن # به ابتدای هشتگ اگر وجود نداشته باشد
        if not hashtag.startswith("#"):
            hashtag = "#" + hashtag
        
        # بررسی وجود هشتگ
        if hashtag not in self.data["hashtags"]:
            return False, f"⚠️ هشتگ {hashtag} یافت نشد"
        
        # حذف هشتگ
        del self.data["hashtags"][hashtag]
        
        # ذخیره تغییرات
        if self.save_data():
            return True, f"✅ هشتگ {hashtag} با موفقیت حذف شد"
        else:
            return False, "⚠️ خطا در ذخیره اطلاعات هشتگ‌ها"
    
    def get_hashtags_list(self) -> List[Dict[str, Any]]:
        """
        دریافت لیست هشتگ‌ها
        
        Returns:
            لیست هشتگ‌ها با جزئیات
        """
        result = []
        for hashtag, info in self.data["hashtags"].items():
            result.append({
                "name": hashtag,
                "description": info.get("description", ""),
                "created_at": info.get("created_at", ""),
                "message_count": len(info.get("messages", [])),
                "timestamp": time.mktime(time.strptime(info.get("created_at", "2025-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")) if "created_at" in info else 0
            })
        
        # مرتب‌سازی بر اساس زمان ایجاد (جدیدترین‌ها اول)
        result.sort(key=lambda x: x["timestamp"], reverse=True)
        return result
    
    def add_channel(self, channel_id: Union[int, str]) -> Tuple[bool, str]:
        """
        افزودن کانال جدید برای جستجوی هشتگ
        
        Args:
            channel_id: شناسه کانال
            
        Returns:
            (وضعیت موفقیت، پیام)
        """
        # تبدیل channel_id به رشته برای ذخیره یکسان
        channel_id_str = str(channel_id)
        
        # بررسی تکراری بودن کانال
        if channel_id_str in self.data["channels"]:
            return False, "⚠️ این کانال قبلاً اضافه شده است"
        
        # افزودن کانال
        self.data["channels"].append(channel_id_str)
        
        # ذخیره تغییرات
        if self.save_data():
            return True, "✅ کانال با موفقیت اضافه شد"
        else:
            return False, "⚠️ خطا در ذخیره اطلاعات کانال‌ها"
    
    def remove_channel(self, channel_id: Union[int, str]) -> Tuple[bool, str]:
        """
        حذف کانال
        
        Args:
            channel_id: شناسه کانال
            
        Returns:
            (وضعیت موفقیت، پیام)
        """
        # تبدیل channel_id به رشته برای مقایسه
        channel_id_str = str(channel_id)
        
        # بررسی وجود کانال
        if channel_id_str not in self.data["channels"]:
            return False, "⚠️ این کانال در لیست موجود نیست"
        
        # حذف کانال
        self.data["channels"].remove(channel_id_str)
        
        # ذخیره تغییرات
        if self.save_data():
            return True, "✅ کانال با موفقیت حذف شد"
        else:
            return False, "⚠️ خطا در ذخیره اطلاعات کانال‌ها"
    
    def get_channels_list(self) -> List[str]:
        """
        دریافت لیست کانال‌ها
        
        Returns:
            لیست کانال‌ها
        """
        return self.data["channels"]

    def search_hashtag(self, hashtag: str) -> Tuple[bool, Dict[str, Any]]:
        """
        جستجو برای یک هشتگ
        
        Args:
            hashtag: نام هشتگ (با یا بدون علامت #)
            
        Returns:
            (وضعیت موفقیت، اطلاعات هشتگ)
        """
        # اضافه کردن # به ابتدای هشتگ اگر وجود نداشته باشد
        if not hashtag.startswith("#"):
            hashtag = "#" + hashtag
            
        # بررسی وجود هشتگ دقیق
        if hashtag in self.data["hashtags"]:
            return True, self.data["hashtags"][hashtag]
        
        # جستجوی فازی - اگر هشتگ دقیق پیدا نشد، هشتگ‌های مشابه را برگردان
        similar_hashtags = []
        for h in self.data["hashtags"]:
            # بررسی شباهت (ساده - شامل بودن)
            if hashtag[1:] in h[1:]:  # حذف # از ابتدای هر دو برای مقایسه بهتر
                similar_hashtags.append({
                    "name": h,
                    "description": self.data["hashtags"][h].get("description", ""),
                    "message_count": len(self.data["hashtags"][h].get("messages", []))
                })
        
        if similar_hashtags:
            return False, {"similar_hashtags": similar_hashtags}
        
        return False, {}
    
    def search_hashtag_in_channels(self, hashtag: str, progress_callback=None) -> List[Dict[str, Any]]:
        """
        جستجوی هشتگ در همه کانال‌ها
        
        Args:
            hashtag: نام هشتگ (با یا بدون علامت #)
            progress_callback: تابع کال‌بک برای گزارش پیشرفت
            
        Returns:
            لیست پیام‌های یافته شده
        """
        # اضافه کردن # به ابتدای هشتگ اگر وجود نداشته باشد
        if not hashtag.startswith("#"):
            hashtag = "#" + hashtag
        
        found_messages = []
        total_channels = len(self.data["channels"])
        
        # بررسی وجود کانال
        if not self.data["channels"]:
            if progress_callback:
                progress_callback(0, 0, total_channels, "⚠️ هنوز هیچ کانالی تعریف نشده است.")
            return found_messages
        
        # جستجو در هر کانال
        for idx, channel_id in enumerate(self.data["channels"]):
            try:
                # گزارش پیشرفت
                if progress_callback:
                    progress_callback(idx, len(found_messages), total_channels)
                
                # جستجو در پیام‌های کانال - با ساختار جدید
                if "messages" in self.data and channel_id in self.data["messages"]:
                    for msg in self.data["messages"].get(channel_id, []):
                        if "text" in msg and hashtag.lower() in msg["text"].lower():
                            found_messages.append({
                                "chat_id": msg.get("chat_id", channel_id),
                                "message_id": msg.get("message_id", 0),
                                "text": msg.get("text", ""),
                                "date": msg.get("date", "نامشخص")
                            })
                            
                            # محدود کردن تعداد نتایج
                            if len(found_messages) >= MAX_SEARCH_RESULTS:
                                break
            except Exception as e:
                debug_log(f"خطا در جستجوی کانال {channel_id}: {e}", "ERROR")
        
        # مرتب‌سازی پیام‌ها بر اساس تاریخ (جدیدترین‌ها اول)
        try:
            found_messages.sort(key=lambda x: x.get("date", ""), reverse=True)
        except Exception as e:
            debug_log(f"خطا در مرتب‌سازی پیام‌ها: {e}", "ERROR")
        
        # ذخیره نتایج در هشتگ
        if hashtag in self.data["hashtags"]:
            self.data["hashtags"][hashtag]["messages"] = found_messages
            self.save_data()
        
        return found_messages

    def fuzzy_search_hashtag(self, query: str) -> List[Dict[str, Any]]:
        """
        جستجوی فازی هشتگ
        
        Args:
            query: عبارت جستجو (با یا بدون #)
            
        Returns:
            لیست هشتگ‌های مشابه با امتیاز شباهت
        """
        # حذف # از ابتدای عبارت جستجو
        clean_query = query[1:] if query.startswith("#") else query
        
        # لیست نتایج
        results = []
        
        for hashtag, info in self.data["hashtags"].items():
            # حذف # از ابتدای هشتگ
            clean_hashtag = hashtag[1:]
            
            # مقایسه شباهت (ساده)
            if clean_query.lower() in clean_hashtag.lower():
                # محاسبه امتیاز (هر چه نسبت طول عبارت جستجو به طول هشتگ بیشتر، امتیاز بالاتر)
                similarity_score = len(clean_query) / len(clean_hashtag) if len(clean_hashtag) > 0 else 0
                
                results.append({
                    "name": hashtag,
                    "description": info.get("description", ""),
                    "message_count": len(info.get("messages", [])),
                    "similarity": similarity_score
                })
        
        # مرتب‌سازی نتایج بر اساس امتیاز
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        return results

# نمونه مدیریت هشتگ
hashtag_manager = HashtagManager()

# توابع واسط برای سازگاری با کد قبلی
def load_hashtags() -> Dict[str, Any]:
    """دریافت داده‌های هشتگ‌ها"""
    return hashtag_manager.data

def save_hashtags(data: Dict[str, Any]) -> bool:
    """ذخیره داده‌های هشتگ‌ها"""
    hashtag_manager.data = data
    return hashtag_manager.save_data()