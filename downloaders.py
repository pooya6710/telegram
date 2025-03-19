import os
import glob
import logging
import asyncio
import yt_dlp
import instaloader
from utils import ensure_temp_dir, clean_filename
import config

logger = logging.getLogger(__name__)

class YouTubeDownloader:
    def __init__(self, temp_dir, quality='medium'):
        self.temp_dir = temp_dir
        self.quality = quality
        ensure_temp_dir(self.temp_dir)
        
    def _get_format_string(self):
        """Get format string based on quality setting"""
        if self.quality == 'high':
            return 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best'
        elif self.quality == 'medium':
            return 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
        elif self.quality == 'low':
            return 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best'
        else:
            # Default to medium
            return 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
    
    def set_quality(self, quality):
        """Set video quality"""
        if quality in ['high', 'medium', 'low']:
            self.quality = quality
            return True
        return False

    async def download(self, url):
        try:
            logger.info(f"Starting YouTube download for URL: {url} with quality: {self.quality}")
            
            # Configure yt-dlp options
            ydl_opts = {
                'format': self._get_format_string(),
                'outtmpl': os.path.join(self.temp_dir, '%(title)s.%(ext)s'),
                'noplaylist': True,
                'writesubtitles': True,
                'subtitleslangs': ['en'],
                'quiet': True,
                'merge_output_format': 'mp4',
            }
            
            # Extract info first to get the title
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                video_title = info_dict.get('title', 'Unknown Title')
                video_title = clean_filename(video_title)
                
                # Download the video
                logger.info(f"Downloading video: {video_title}")
                ydl.download([url])
                
                # Find the downloaded file
                file_path = os.path.join(self.temp_dir, f"{video_title}.mp4")
                
                if not os.path.exists(file_path):
                    # Try to find any mp4 file if exact filename wasn't found
                    mp4_files = glob.glob(os.path.join(self.temp_dir, "*.mp4"))
                    if mp4_files:
                        file_path = mp4_files[0]
                    else:
                        raise FileNotFoundError("Downloaded video file not found")
                        
                logger.info(f"YouTube download completed: {file_path}")
                return file_path, video_title
                
        except yt_dlp.DownloadError as e:
            logger.error(f"yt-dlp DownloadError: {str(e)}")
            raise Exception(f"خطا در دانلود از یوتیوب: {str(e)}")
        except Exception as e:
            logger.error(f"General error during YouTube download: {str(e)}")
            raise Exception(f"خطا در دانلود از یوتیوب: {str(e)}")


class InstagramDownloader:
    def __init__(self, temp_dir):
        self.temp_dir = temp_dir
        ensure_temp_dir(self.temp_dir)
        self.L = instaloader.Instaloader(
            download_pictures=True,
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            filename_pattern="{shortcode}",
            dirname_pattern=self.temp_dir,
            quiet=False,
            max_connection_attempts=3
        )

    async def download(self, url):
        try:
            logger.info(f"Starting Instagram download for URL: {url}")

            # Handle both post and reel URLs
            if "/reel/" in url:
                shortcode = url.split("/reel/")[1].split("/")[0]
                logger.info(f"Detected reel with shortcode: {shortcode}")
            else:
                shortcode = url.split("/p/")[1].split("/")[0]
                logger.info(f"Detected post with shortcode: {shortcode}")

            shortcode = shortcode.split("?")[0]  # Remove query parameters

            # Create target directory
            target_dir = os.path.join(self.temp_dir, shortcode)
            ensure_temp_dir(target_dir)
            logger.info(f"Created target directory: {target_dir}")

            # Set download directory for this post
            self.L.dirname_pattern = target_dir
            logger.info(f"Set download directory to: {target_dir}")

            # Download post with error handling
            try:
                post = instaloader.Post.from_shortcode(self.L.context, shortcode)
                logger.info(f"Successfully fetched post info for shortcode: {shortcode}")

                # Download the post directly to target directory
                self.L.download_post(post, target=target_dir)
                logger.info("Post download completed")
            except Exception as e:
                logger.error(f"Error during post download: {str(e)}")
                raise

            # List all files in directory for debugging
            all_files = os.listdir(target_dir)
            logger.info(f"Files in target directory: {all_files}")

            # Find the downloaded file - support more extensions and case-insensitive
            media_files = []
            for ext in ['.mp4', '.jpg', '.jpeg', '.png', '.webp', '.mov']:
                media_files.extend(glob.glob(os.path.join(target_dir, f'*{ext}')))
                media_files.extend(glob.glob(os.path.join(target_dir, f'*{ext.upper()}')))

            logger.info(f"Found media files: {media_files}")

            if not media_files:
                logger.error("No media files found in the following directory structure:")
                for root, dirs, files in os.walk(target_dir):
                    logger.error(f"Directory: {root}")
                    for f in files:
                        logger.error(f"  File: {f}")
                raise Exception("هیچ فایل مدیایی در پست پیدا نشد")

            file_path = media_files[0]
            logger.info(f"Selected file for sending: {file_path}")

            if os.path.getsize(file_path) > config.MAX_TELEGRAM_FILE_SIZE:
                raise ValueError("فایل بزرگتر از محدودیت تلگرام است (50 مگابایت)")

            return file_path, f"پست اینستاگرام - {shortcode}"

        except instaloader.exceptions.InstaloaderException as e:
            logger.error(f"Instaloader error: {str(e)}")
            raise Exception(f"خطا در دانلود از اینستاگرام: {str(e)}")
        except Exception as e:
            logger.error(f"General error: {str(e)}")
            raise Exception(f"خطا در دانلود از اینستاگرام: {str(e)}")
