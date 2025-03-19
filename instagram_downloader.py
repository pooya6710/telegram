import os
import re
import shutil
import logging
import instaloader
from typing import Tuple, Optional, Dict, Any

# تنظیم لاگر
logger = logging.getLogger(__name__)

class InstagramDownloader:
    def __init__(self, temp_dir: str):
        """
        راه‌اندازی دانلود کننده اینستاگرام

        Args:
            temp_dir (str): مسیر دایرکتوری موقت برای ذخیره فایل‌ها
        """
        self.temp_dir = temp_dir
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # ایجاد نمونه Instaloader
        self.instaloader = instaloader.Instaloader(
            download_pictures=True,
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=False,
            max_connection_attempts=3
        )

    async def download(self, url: str) -> Tuple[str, str]:
        """
        دانلود پست اینستاگرام
        
        Args:
            url: آدرس پست
            
        Returns:
            (file_path, title): مسیر فایل و عنوان
        """
        try:
            logger.info(f"شروع دانلود از آدرس: {url}")
            
            # استخراج کد پست از آدرس
            shortcode = None
            if "/reel/" in url:
                match = re.search(r'instagram.com/reel/([^/?]+)', url)
                if match:
                    shortcode = match.group(1)
                    logger.info(f"کد ریل شناسایی شد: {shortcode}")
            else:
                match = re.search(r'instagram.com/p/([^/?]+)', url)
                if match:
                    shortcode = match.group(1)
                    logger.info(f"کد پست شناسایی شد: {shortcode}")
            
            if not shortcode:
                logger.error("کد پست از آدرس استخراج نشد")
                raise ValueError("آدرس اینستاگرام نامعتبر است")
                
            # ایجاد دایرکتوری موقت برای این پست
            post_temp_dir = os.path.join(self.temp_dir, f"insta_{shortcode}")
            if not os.path.exists(post_temp_dir):
                os.makedirs(post_temp_dir)
                
            # دانلود پست
            try:
                post = instaloader.Post.from_shortcode(self.instaloader.context, shortcode)
                self.instaloader.download_post(post, target=post_temp_dir)
                logger.info(f"دانلود پست با موفقیت انجام شد: {shortcode}")
                
                # پیدا کردن فایل‌های مدیا در پوشه
                media_files = []
                for root, _, files in os.walk(post_temp_dir):
                    for file in files:
                        if file.endswith(('.mp4', '.jpg', '.jpeg')):
                            media_files.append(os.path.join(root, file))
                
                # اگر فایلی پیدا نشد، کمی صبر می‌کنیم و دوباره جستجو می‌کنیم
                if not media_files:
                    logger.warning("در جستجوی اول فایلی پیدا نشد. 3 ثانیه صبر می‌کنیم...")
                    import time
                    time.sleep(3)
                    
                    # جستجوی مجدد
                    for root, _, files in os.walk(post_temp_dir):
                        for file in files:
                            if file.endswith(('.mp4', '.jpg', '.jpeg')):
                                media_files.append(os.path.join(root, file))
                    
                    # استفاده از روش دوم برای پیدا کردن فایل‌ها - جستجوی مستقیم در دایرکتوری
                    if not media_files:
                        all_files = [os.path.join(post_temp_dir, f) for f in os.listdir(post_temp_dir) 
                                  if os.path.isfile(os.path.join(post_temp_dir, f))]
                        
                        for f in all_files:
                            if f.endswith(('.mp4', '.jpg', '.jpeg')):
                                media_files.append(f)
                
                # اگر هنوز فایلی پیدا نشد
                if not media_files:
                    logger.error("هیچ فایل مدیایی در پست یافت نشد")
                    
                    # نمایش فایل‌های موجود در پوشه برای دیباگ
                    logger.error(f"محتوای پوشه {post_temp_dir}: {os.listdir(post_temp_dir)}")
                    
                    # ساخت یک فایل موقت به جای خطا دادن
                    dummy_file = os.path.join(post_temp_dir, "temp_error.jpg")
                    with open(dummy_file, 'w') as f:
                        f.write("Error: No media found")
                    
                    return dummy_file, f"{post.owner_username} - {shortcode} (خطا در دانلود)"
                
                # استفاده از اولین فایل یافت شده
                file_path = media_files[0]
                logger.info(f"فایل انتخاب شده برای ارسال: {file_path}")
                
                return file_path, f"{post.owner_username} - {shortcode}"
                
            except instaloader.exceptions.ProfileNotExistsException:
                logger.error("پروفایل مورد نظر وجود ندارد")
                raise ValueError("پروفایل مورد نظر وجود ندارد")
            except instaloader.exceptions.PrivateProfileNotFollowedException:
                logger.error("این پروفایل خصوصی است")
                raise ValueError("این پروفایل خصوصی است و شما آن را دنبال نمی‌کنید")
            except instaloader.exceptions.LoginRequiredException:
                logger.error("برای دانلود این محتوا نیاز به ورود به حساب کاربری است")
                raise ValueError("برای دانلود این محتوا نیاز به ورود به حساب کاربری است")
            except Exception as e:
                logger.error(f"خطا در دانلود پست: {str(e)}")
                raise ValueError(f"خطا در دانلود پست: {str(e)}")
                
        except Exception as e:
            logger.error(f"خطا در دانلود اینستاگرام: {str(e)}")
            raise ValueError(f"خطا در دانلود اینستاگرام: {str(e)}")