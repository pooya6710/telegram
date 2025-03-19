import os
import re
import logging
import instaloader
from typing import Tuple, Optional

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InstagramDownloader:
    def __init__(self, temp_dir):
        """
        راه‌اندازی دانلود کننده اینستاگرام

        Args:
            temp_dir (str): مسیر دایرکتوری موقت برای ذخیره فایل‌ها
        """
        self.temp_dir = temp_dir
        logger.info("Initialized Instagram downloader")
        
        # اطمینان از وجود دایرکتوری موقت
        os.makedirs(temp_dir, exist_ok=True)
    
    async def download(self, url) -> Tuple[str, str]:
        """
        دانلود پست اینستاگرام
        
        Args:
            url: آدرس پست
            
        Returns:
            (file_path, title): مسیر فایل و عنوان
        """
        try:
            # استخراج شناسه پست از URL
            shortcode = None
            match = re.search(r'instagram.com/(?:p|reel)/([^/?]+)', url)
            if match:
                shortcode = match.group(1)
            
            if not shortcode:
                raise Exception("شناسه پست اینستاگرام یافت نشد")
            
            # ایجاد دایرکتوری منحصر به فرد برای این دانلود
            download_dir = os.path.join(self.temp_dir, shortcode)
            os.makedirs(download_dir, exist_ok=True)
            
            logger.info(f"Starting download for Instagram post: {shortcode}")
            
            # دانلود پست
            L = instaloader.Instaloader(
                dirname_pattern=download_dir,
                filename_pattern=shortcode,
                download_videos=True,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False
            )
            
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            L.download_post(post, target=shortcode)
            
            # یافتن فایل دانلود شده
            files = os.listdir(download_dir)
            media_files = [f for f in files if f.endswith(('.jpg', '.mp4', '.mov'))]
            
            if not media_files:
                raise Exception("No media found in the Instagram post")
            
            # ترجیح دادن فایل‌های ویدیویی به تصاویر
            video_files = [f for f in media_files if f.endswith(('.mp4', '.mov'))]
            if video_files:
                file_path = os.path.join(download_dir, video_files[0])
            else:
                file_path = os.path.join(download_dir, media_files[0])
            
            # ایجاد عنوان مناسب
            title = f"Post by {post.owner_username}"
            if post.caption:
                short_caption = post.caption[:50] + "..." if len(post.caption) > 50 else post.caption
                title = f"{title} - {short_caption}"
                
            logger.info(f"Instagram download completed: {file_path}")
            return file_path, title
            
        except Exception as e:
            logger.error(f"Error in Instagram download: {str(e)}")
            raise Exception(f"خطا در دانلود: {str(e)}")