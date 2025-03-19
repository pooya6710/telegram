import os
import re
import asyncio
import logging
from typing import Tuple, Optional

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YouTubeDownloader:
    def __init__(self, temp_dir, quality='medium'):
        """
        راه‌اندازی دانلود کننده یوتیوب

        Args:
            temp_dir (str): مسیر دایرکتوری موقت برای ذخیره فایل‌ها
            quality (str, optional): کیفیت پیش‌فرض دانلود. Defaults to 'medium'.
        """
        self.temp_dir = temp_dir
        self.quality = quality
        logger.info(f"Initialized YouTube downloader with quality: {quality}")
        
        # اطمینان از وجود دایرکتوری موقت
        os.makedirs(temp_dir, exist_ok=True)
    
    def _get_format_string(self):
        """Get format string based on quality setting"""
        if self.quality == 'high':
            return 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]'
        elif self.quality == 'medium':
            return 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]'
        elif self.quality == 'low':
            return 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]'
        else:
            return 'best[ext=mp4]'
    
    def set_quality(self, quality):
        """Set video quality"""
        if quality in ['high', 'medium', 'low']:
            self.quality = quality
            logger.info(f"YouTube downloader quality set to: {quality}")
            return True
        return False
    
    async def download(self, url) -> Tuple[str, str]:
        """
        دانلود ویدیوی یوتیوب

        Args:
            url (str): آدرس ویدیوی یوتیوب

        Returns:
            Tuple[str, str]: (مسیر فایل دانلود شده, عنوان ویدیو)

        Raises:
            Exception: در صورت بروز خطا در دانلود
        """
        format_string = self._get_format_string()
        filename_template = os.path.join(self.temp_dir, '%(title)s.%(ext)s')
        
        try:
            # استفاده از yt-dlp برای دانلود
            from yt_dlp import YoutubeDL

            ydl_opts = {
                'format': format_string,
                'outtmpl': filename_template,
                'noplaylist': True,
                'quiet': False,
                'no_warnings': False,
                'ignoreerrors': False,
                'restrictfilenames': True
            }
            
            # اجرای دانلود به صورت غیرهمزمان
            loop = asyncio.get_event_loop()
            logger.info(f"Starting download for URL: {url}")
            
            def extract_info():
                with YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=True)

            # اجرای عملیات دانلود در یک thread جداگانه
            info_dict = await loop.run_in_executor(None, extract_info)
            
            # دریافت اطلاعات ویدیو
            title = info_dict.get('title', 'Unknown')
            ext = info_dict.get('ext', 'mp4')
            
            # پاکسازی نام فایل
            clean_title = re.sub(r'[\\/*?:"<>|]', "", title)
            clean_title = clean_title.replace(' ', '_')
            
            # مسیر کامل فایل
            file_path = os.path.join(self.temp_dir, f"{clean_title}.{ext}")
            
            logger.info(f"Download completed: {file_path}")
            return file_path, title
            
        except Exception as e:
            logger.error(f"Error in YouTube download: {str(e)}")
            raise Exception(f"خطا در دانلود: {str(e)}")

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
            url (str): آدرس پست اینستاگرام
            
        Returns:
            Tuple[str, str]: (مسیر فایل دانلود شده, عنوان پست)
            
        Raises:
            Exception: در صورت بروز خطا در دانلود
        """
        try:
            import instaloader
            
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
            
            # اجرای دانلود به صورت غیرهمزمان
            loop = asyncio.get_event_loop()
            logger.info(f"Starting download for Instagram post: {shortcode}")
            
            def download_post():
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
                
                return post.owner_username, post.caption
            
            # اجرای عملیات دانلود در یک thread جداگانه
            username, caption = await loop.run_in_executor(None, download_post)
            
            # یافتن فایل دانلود شده
            files = os.listdir(download_dir)
            media_files = [f for f in files if f.endswith(('.jpg', '.mp4', '.mov'))]
            
            if not media_files:
                raise Exception("No media found in the Instagram post")

            # بررسی اعتبار فایل‌ها
            valid_files = []
            for file in media_files:
                file_path = os.path.join(download_dir, file)
                try:
                    # بررسی سایز فایل
                    if os.path.getsize(file_path) < 100:  # فایل خیلی کوچک است
                        continue
                        
                    # بررسی قابل خواندن بودن فایل
                    with open(file_path, 'rb') as f:
                        header = f.read(8)  # خواندن هدر فایل
                        if any(header.startswith(sig) for sig in [b'\xFF\xD8',  # JPEG
                                                                b'\x00\x00\x00',  # MP4
                                                                b'\x00\x00\x00\x14']):  # MOV
                            valid_files.append(file)
                except Exception as e:
                    logger.error(f"Error validating file {file}: {str(e)}")
                    continue
            
            if not valid_files:
                raise Exception("No valid media files found in the Instagram post")
                
            # استفاده از اولین فایل معتبر
            file_path = os.path.join(download_dir, valid_files[0])
            
            # ترجیح دادن فایل‌های ویدیویی به تصاویر
            video_files = [f for f in media_files if f.endswith(('.mp4', '.mov'))]
            if video_files:
                file_path = os.path.join(download_dir, video_files[0])
            else:
                file_path = os.path.join(download_dir, media_files[0])
            
            # ایجاد عنوان مناسب
            title = f"Post by {username}"
            if caption:
                short_caption = caption[:50] + "..." if len(caption) > 50 else caption
                title = f"{title} - {short_caption}"
                
            logger.info(f"Instagram download completed: {file_path}")
            return file_path, title
            
        except Exception as e:
            logger.error(f"Error in Instagram download: {str(e)}")
            raise Exception(f"خطا در دانلود: {str(e)}")