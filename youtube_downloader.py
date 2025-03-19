import os
import sys
import yt_dlp
import logging
from datetime import datetime
from debug_handler import debug_log

# تنظیم مسیر ذخیره فایل‌ها
DOWNLOAD_PATH = './downloads'
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

def download_video(url, download_id, user_id):
    """

class DebugLogger:
    def debug(self, msg):
        debug_log(f"DEBUG: {msg}", "DEBUG")

    def warning(self, msg):
        debug_log(f"WARNING: {msg}", "WARNING")

    def error(self, msg):
        debug_log(f"ERROR: {msg}", "ERROR")
        with open('download_errors.log', 'a', encoding='utf-8') as f:
            f.write(f"{datetime.datetime.now()} - ERROR: {msg}\n")

    دانلود ویدیو با خطایابی پیشرفته
    """
    try:
        debug_log(f"شروع دانلود برای URL: {url}", "INFO")

        output_path = os.path.join(DOWNLOAD_PATH, f'video_{download_id}_{user_id}.%(ext)s')

        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_path,
            'noplaylist': True,
            'progress_hooks': [lambda d: debug_log(f"پیشرفت دانلود: {d['status']}", "INFO")],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            debug_log("استخراج اطلاعات ویدیو...", "INFO")
            info = ydl.extract_info(url, download=True)

            video_path = os.path.join(DOWNLOAD_PATH, f"video_{download_id}_{user_id}.{info['ext']}")

            if os.path.exists(video_path):
                debug_log(f"دانلود موفق - مسیر فایل: {video_path}", "INFO")
                return True, video_path, None
            else:
                debug_log("فایل دانلود شده پیدا نشد", "ERROR")
                return False, None, {"error": "فایل دانلود شده پیدا نشد"}

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        debug_log(f"خطای دانلود: {error_msg}", "ERROR")

        if "Video unavailable" in error_msg:
            return False, None, {"error": "ویدیو در دسترس نیست"}
        elif "Sign in" in error_msg:
            return False, None, {"error": "این ویدیو نیاز به ورود به حساب کاربری دارد"}
        else:
            return False, None, {"error": f"خطا در دانلود: {error_msg}"}

    except Exception as e:
        debug_log(f"خطای ناشناخته: {str(e)}", "ERROR")
        return False, None, {"error": f"خطای سیستمی: {str(e)}"}

def validate_youtube_url(url):
    """اعتبارسنجی URL یوتیوب"""
    return "youtube.com" in url or "youtu.be" in url

def extract_video_info(url):
    """استخراج اطلاعات ویدیو"""
    try:
        with yt_dlp.YoutubeDL() as ydl:
            return ydl.extract_info(url, download=False)
    except:
        return None

def clean_old_downloads():
    """پاکسازی فایل‌های قدیمی"""
    try:
        for file in os.listdir(DOWNLOAD_PATH):
            file_path = os.path.join(DOWNLOAD_PATH, file)
            if os.path.getctime(file_path) < (datetime.now().timestamp() - 3600):  # حذف فایل‌های قدیمی‌تر از 1 ساعت
                os.remove(file_path)
    except Exception as e:
        debug_log(f"خطا در پاکسازی فایل‌های قدیمی: {str(e)}", "ERROR")

import os
import time
import json
import re
import urllib.parse
import threading
import concurrent.futures
from typing import Dict, Any, Optional, Tuple, List, Union, Callable

# استفاده از yt-dlp با مدیریت خطا
try:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError, ExtractorError
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

from config import (
    YDL_OPTIONS, 
    MAX_VIDEO_SIZE_MB, 
    MAX_DOWNLOAD_TIME, 
    MAX_VIDEO_DURATION,
    DOWNLOADS_DIR
)
from debug_logger import debug_log, debug_decorator
from database import add_download, update_download_status, get_download
from config import DownloadStatus

# قفل‌ها برای مدیریت همزمانی
active_downloads_lock = threading.RLock()
active_downloads = {}  # نگهداری اطلاعات دانلودهای فعال

@debug_decorator
def validate_youtube_url(url: str) -> bool:
    """
    اعتبارسنجی URL یوتیوب
    Args:
        url: آدرس ویدیو
    Returns:
        True اگر URL معتبر باشد
    """
    return "youtube.com" in url or "youtu.be" in url


@debug_decorator
def extract_video_info(url: str) -> Optional[Dict[str, Any]]:
    """
    استخراج اطلاعات ویدیو بدون دانلود
    Args:
        url: آدرس ویدیو
    Returns:
        دیکشنری اطلاعات ویدیو یا None در صورت خطا
    """
    try:
        with yt_dlp.YoutubeDL() as ydl:
            return ydl.extract_info(url, download=False)
    except:
        return None

@debug_decorator
def format_duration(duration: Optional[int]) -> str:
    """
    فرمت‌بندی مدت زمان
    Args:
        duration: مدت زمان به ثانیه
    Returns:
        متن فرمت‌بندی شده
    """
    if duration is None:
        return "نامشخص"

    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    else:
        return f"{minutes:02}:{seconds:02}"

@debug_decorator
def get_best_thumbnail(info_dict: Dict[str, Any]) -> Optional[str]:
    """
    دریافت بهترین تصویر بندانگشتی
    Args:
        info_dict: دیکشنری اطلاعات ویدیو
    Returns:
        آدرس تصویر بندانگشتی یا None
    """
    if not info_dict:
        return None

    # بررسی تصاویر بندانگشتی
    thumbnails = info_dict.get('thumbnails', [])

    if not thumbnails:
        # روش قدیمی‌تر
        return info_dict.get('thumbnail')

    # انتخاب بهترین کیفیت
    best_thumbnail = None
    max_width = 0

    for thumb in thumbnails:
        width = thumb.get('width', 0)
        if width > max_width:
            max_width = width
            best_thumbnail = thumb.get('url')

    # اگر هیچ تصویری یافت نشد، از فیلد thumbnail استفاده کنیم
    if not best_thumbnail:
        best_thumbnail = info_dict.get('thumbnail')

    return best_thumbnail

@debug_decorator
def extract_formats(info_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    استخراج فرمت‌های موجود
    Args:
        info_dict: دیکشنری اطلاعات ویدیو
    Returns:
        لیست فرمت‌های موجود
    """
    formats = []

    if not info_dict or 'formats' not in info_dict:
        return formats

    # گروه‌بندی فرمت‌ها بر اساس کیفیت
    format_groups = {}

    for f in info_dict['formats']:
        # فقط فرمت‌های ویدیویی را در نظر بگیریم
        if f.get('vcodec') == 'none':
            continue

        # تنظیم برچسب کیفیت
        height = f.get('height')
        format_id = f.get('format_id', '')
        ext = f.get('ext', 'mp4')

        if height:
            quality_key = f"{height}p"
        else:
            quality_key = format_id

        # فیلتر کردن برخی فرمت‌های تکراری
        if quality_key not in format_groups:
            format_groups[quality_key] = {
                'format_id': format_id,
                'ext': ext,
                'height': height,
                'width': f.get('width'),
                'filesize': f.get('filesize'),
                'filesize_human': format_filesize(f.get('filesize')),
                'vcodec': f.get('vcodec'),
                'acodec': f.get('acodec'),
                'quality': quality_key
            }

    # تبدیل به لیست و مرتب‌سازی
    formats = list(format_groups.values())
    formats.sort(key=lambda x: x.get('height', 0) if x.get('height') else 0, reverse=True)

    # افزودن فرمت فقط صوتی
    for f in info_dict['formats']:
        if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
            # بهترین کیفیت صوتی را انتخاب می‌کنیم
            audio_format = {
                'format_id': f.get('format_id', ''),
                'ext': f.get('ext', 'mp3'),
                'filesize': f.get('filesize'),
                'filesize_human': format_filesize(f.get('filesize')),
                'vcodec': None,
                'acodec': f.get('acodec'),
                'quality': 'audio'
            }
            formats.append(audio_format)
            break

    return formats

@debug_decorator
def format_filesize(size: Optional[int]) -> str:
    """
    فرمت‌بندی حجم فایل
    Args:
        size: حجم به بایت
    Returns:
        متن فرمت‌بندی شده
    """
    if size is None:
        return "نامشخص"

    # تبدیل به مگابایت
    size_mb = size / (1024 * 1024)

    if size_mb < 1:
        # کمتر از 1 مگابایت
        size_kb = size / 1024
        return f"{size_kb:.1f} KB"
    elif size_mb < 1024:
        # کمتر از 1 گیگابایت
        return f"{size_mb:.1f} MB"
    else:
        # گیگابایت یا بیشتر
        size_gb = size_mb / 1024
        return f"{size_gb:.2f} GB"

from debug_handler import debug_download, debugger

@debug_download
def download_video(url: str, download_id: int, user_id: int, quality: str = "best", 
                  progress_callback: Optional[Callable[[float, str], None]] = None) -> Tuple[bool, Optional[str], Optional[Dict]]:
    # ثبت شروع دانلود در دیباگر
    debugger.log_download_start(download_id, url, user_id)

    # تنظیمات yt-dlp
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4' if 'youtube.com' in url else 'best',
        'outtmpl': f'downloads/{download_id}/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'writethumbnail': True,
        'ignoreerrors': True,
        'no_check_certificate': True,
        'cookiesfrombrowser': ('chrome',),
        'socket_timeout': 30,
        'retries': 3
    }

    if 'instagram.com' in url:
        debug_log(f"شروع پردازش لینک اینستاگرام: {url}", "INFO")
        
        # تنظیمات مخصوص اینستاگرام
        instagram_opts = {
            'format': 'best',
            'extract_flat': False,
            'quiet': False,
            'no_warnings': False,
            'verbose': True,
            'force_generic_extractor': False,
            'extract_flat': False,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Origin': 'https://www.instagram.com',
                'Connection': 'keep-alive',
                'Referer': 'https://www.instagram.com/',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'X-IG-App-ID': '936619743392459',
                'X-Requested-With': 'XMLHttpRequest'
            },
            'cookiesfrombrowser': ('chrome',),  # استفاده از کوکی‌های مرورگر
            'socket_timeout': 30,
            'retries': 3
        }
        
        ydl_opts.update(instagram_opts)
        
        try:
            # تلاش برای استخراج اطلاعات پست
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                debug_log("در حال استخراج اطلاعات پست اینستاگرام...", "INFO")
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    debug_log("خطا: اطلاعات پست استخراج نشد", "ERROR")
                    return False, None, {"error": "خطا در استخراج اطلاعات پست اینستاگرام"}
                
                # بررسی نوع محتوا
                if info.get('_type') == 'playlist':
                    debug_log("این یک پست چند رسانه‌ای است", "INFO")
                    # برای پست‌های چندتایی، اولین محتوا را دانلود می‌کنیم
                    if info.get('entries'):
                        info = info['entries'][0]
                
                debug_log(f"اطلاعات پست با موفقیت استخراج شد: {info.get('title', 'بدون عنوان')}", "INFO")
                
        except Exception as e:
            debug_log(f"خطا در پردازش پست اینستاگرام: {str(e)}", "ERROR")
            return False, None, {"error": f"خطا در پردازش پست اینستاگرام: {str(e)}"}
            
        debug_log("شروع دانلود پست اینستاگرام...", "INFO")
    """
    دانلود ویدیو
    Args:
        url: آدرس ویدیو
        download_id: شناسه دانلود
        user_id: شناسه کاربر
        quality: کیفیت دانلود
        progress_callback: تابع کال‌بک پیشرفت
    Returns:
        (وضعیت موفقیت، مسیر فایل، خطا)
    """
    if not YTDLP_AVAILABLE:
        debug_log("yt_dlp در دسترس نیست", "ERROR")
        update_download_status(download_id, DownloadStatus.FAILED, error_message="yt_dlp در دسترس نیست")
        return False, None, {"error": "yt_dlp در دسترس نیست"}

    # پاکسازی آدرس ویدیو
    url = url.strip()

    # بررسی اعتبار URL
    if not validate_youtube_url(url):
        debug_log(f"آدرس نامعتبر یوتیوب: {url}", "WARNING")
        update_download_status(download_id, DownloadStatus.FAILED, error_message="آدرس نامعتبر یوتیوب")
        return False, None, {"error": "آدرس نامعتبر یوتیوب"}

    # ثبت دانلود در دانلودهای فعال
    with active_downloads_lock:
        active_downloads[download_id] = {
            "url": url,
            "user_id": user_id,
            "start_time": time.time(),
            "progress": 0,
            "status": "در حال شروع...",
            "quality": quality
        }

    # تنظیم وضعیت به "در حال پردازش"
    update_download_status(download_id, DownloadStatus.PROCESSING)

    # نام فایل برای دانلود
    output_template = os.path.join(DOWNLOADS_DIR, f"{download_id}-%(title)s.%(ext)s")

    # تنظیمات yt-dlp
    ydl_opts = YDL_OPTIONS.copy()
    ydl_opts.update({
        'outtmpl': output_template,
        'format': quality if quality != "best" else 'best',
    })

    # کلاس برای دریافت پیشرفت دانلود
    class YTDLLogger:
        def debug(self, msg):
            # چک کردن اگر پیام حاوی اطلاعات پیشرفت است
            if "% of" in msg and "at" in msg:
                try:
                    parts = msg.split()
                    percent_str = next((p for p in parts if "%" in p), "0%")
                    percent = float(percent_str.replace("%", ""))

                    speed_str = parts[parts.index("at") + 1]

                    # به‌روزرسانی پیشرفت
                    with active_downloads_lock:
                        if download_id in active_downloads:
                            active_downloads[download_id]["progress"] = percent
                            active_downloads[download_id]["status"] = f"در حال دانلود ({speed_str})..."

                    # فراخوانی callback پیشرفت
                    if progress_callback:
                        progress_callback(percent, f"در حال دانلود ({speed_str})...")

                except Exception:
                    pass

        def warning(self, msg):
            debug_log(f"هشدار yt-dlp: {msg}", "WARNING")

        def error(self, msg):
            debug_log(f"خطای yt-dlp: {msg}", "ERROR")

    # بررسی زمانبندی دانلود
    deadline = time.time() + MAX_DOWNLOAD_TIME

    # در ابتدا اطلاعات ویدیو را استخراج می‌کنیم
    try:
        debug_log(f"شروع استخراج اطلاعات ویدیو با ID دانلود {download_id}", "INFO")

        # به‌روزرسانی وضعیت
        with active_downloads_lock:
            if download_id in active_downloads:
                active_downloads[download_id]["status"] = "در حال استخراج اطلاعات..."

        if progress_callback:
            progress_callback(0, "در حال استخراج اطلاعات...")

        # استخراج اطلاعات
        temp_ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
        with YoutubeDL(temp_ydl_opts) as ydl:
            video_info = ydl.extract_info(url, download=False)

            if not video_info:
                debug_log(f"اطلاعات ویدیو استخراج نشد: {url}", "ERROR")
                update_download_status(download_id, DownloadStatus.FAILED, error_message="اطلاعات ویدیو استخراج نشد")
                return False, None, {"error": "اطلاعات ویدیو استخراج نشد"}

            # بررسی مدت زمان ویدیو
            duration = video_info.get('duration', 0)

            if duration > MAX_VIDEO_DURATION:
                error_msg = f"مدت زمان ویدیو بیش از حد مجاز است ({format_duration(duration)})"
                debug_log(error_msg, "WARNING")
                update_download_status(download_id, DownloadStatus.FAILED, error_message=error_msg)
                return False, None, {"error": error_msg}

            # بررسی حجم ویدیو
            filesize = video_info.get('filesize') or video_info.get('filesize_approx')

            if filesize and filesize > (MAX_VIDEO_SIZE_MB * 1024 * 1024):
                error_msg = f"حجم ویدیو بیش از حد مجاز است ({format_filesize(filesize)})"
                debug_log(error_msg, "WARNING")
                update_download_status(download_id, DownloadStatus.FAILED, error_message=error_msg)
                return False, None, {"error": error_msg}

    except (DownloadError, ExtractorError) as e:
        error_msg = f"خطا در استخراج اطلاعات ویدیو: {str(e)}"
        debug_log(error_msg, "ERROR")
        update_download_status(download_id, DownloadStatus.FAILED, error_message=error_msg)
        return False, None, {"error": error_msg}

    # شروع دانلود ویدیو
    try:
        debug_log(f"شروع دانلود ویدیو با ID دانلود {download_id}", "INFO")

        # به‌روزرسانی وضعیت
        with active_downloads_lock:
            if download_id in active_downloads:
                active_downloads[download_id]["status"] = "در حال دانلود..."

        if progress_callback:
            progress_callback(0, "در حال دانلود...")

        # تنظیم لاگر
        ydl_opts['logger'] = YTDLLogger()

        with YoutubeDL(ydl_opts) as ydl:
            # دانلود ویدیو
            ydl.download([url])

            # بررسی پایان زمان
            if time.time() > deadline:
                error_msg = "زمان دانلود بیش از حد مجاز طول کشید"
                debug_log(error_msg, "WARNING")
                update_download_status(download_id, DownloadStatus.FAILED, error_message=error_msg)
                return False, None, {"error": error_msg}

            # یافتن فایل دانلود شده
            downloaded_file = None

            for file in os.listdir(DOWNLOADS_DIR):
                if file.startswith(str(download_id) + "-"):
                    downloaded_file = os.path.join(DOWNLOADS_DIR, file)
                    break

            if not downloaded_file:
                error_msg = "فایل دانلود شده یافت نشد"
                debug_log(error_msg, "ERROR")
                update_download_status(download_id, DownloadStatus.FAILED, error_message=error_msg)
                return False, None, {"error": error_msg}

            # دریافت حجم فایل
            file_size = os.path.getsize(downloaded_file)

            # به‌روزرسانی وضعیت
            with active_downloads_lock:
                if download_id in active_downloads:
                    active_downloads[download_id]["progress"] = 100
                    active_downloads[download_id]["status"] = "دانلود کامل شد"

            if progress_callback:
                progress_callback(100, "دانلود کامل شد")

            # به‌روزرسانی وضعیت دانلود در دیتابیس
            metadata = {
                "title": video_info.get('title', ''),
                "duration": video_info.get('duration', 0),
                "uploader": video_info.get('uploader', ''),
                "thumbnail": get_best_thumbnail(video_info)
            }

            update_download_status(
                download_id, 
                DownloadStatus.COMPLETED, 
                file_path=downloaded_file,
                file_size=file_size,
                metadata=metadata
            )

            debug_log(f"دانلود ویدیو با ID {download_id} با موفقیت انجام شد", "INFO")
            return True, downloaded_file, None

    except (DownloadError, ExtractorError) as e:
        error_msg = f"خطا در دانلود ویدیو: {str(e)}"
        detailed_error = str(e)

        if "Video unavailable" in detailed_error:
            error_msg = "این ویدیو در دسترس نیست یا حذف شده است"
        elif "Sign in" in detailed_error:
            error_msg = "این ویدیو نیاز به ورود به حساب کاربری دارد"
        elif "Private video" in detailed_error:
            error_msg = "این ویدیو خصوصی است"
        elif "copyright" in detailed_error.lower():
            error_msg = "این ویدیو به دلیل مسائل کپی‌رایت قابل دانلود نیست"

        debug_log(error_msg, "ERROR")
        update_download_status(download_id, DownloadStatus.FAILED, error_message=error_msg)
        return False, None, {"error": error_msg}
    except Exception as e:
        error_msg = f"خطای غیرمنتظره در دانلود ویدیو: {str(e)}"
        debug_log(error_msg, "ERROR")
        update_download_status(download_id, DownloadStatus.FAILED, error_message=error_msg)
        return False, None, {"error": error_msg}
    finally:
        # حذف از لیست دانلودهای فعال
        with active_downloads_lock:
            if download_id in active_downloads:
                del active_downloads[download_id]

@debug_decorator
def get_download_progress(download_id: int) -> Dict[str, Any]:
    """
    دریافت وضعیت پیشرفت دانلود
    Args:
        download_id: شناسه دانلود
    Returns:
        دیکشنری وضعیت پیشرفت
    """
    # دریافت اطلاعات از لیست دانلودهای فعال
    with active_downloads_lock:
        if download_id in active_downloads:
            download_info = active_downloads[download_id].copy()
            # محاسبه زمان سپری شده
            elapsed_time = time.time() - download_info.get("start_time", time.time())
            download_info["elapsed_time"] = int(elapsed_time)
            download_info["elapsed_time_human"] = format_duration(int(elapsed_time))
            return download_info

    # اگر در لیست فعال نبود، از دیتابیس دریافت کنیم
    db_info = get_download(download_id)

    if db_info:
        # تبدیل اطلاعات دیتابیس به فرمت مناسب
        status_text = "نامشخص"
        progress = 0

        if db_info["status"] == DownloadStatus.PENDING:
            status_text = "در انتظار"
        elif db_info["status"] == DownloadStatus.PROCESSING:
            status_text = "در حال پردازش"
            progress = 50  # مقدار تقریبی
        elif db_info["status"] == DownloadStatus.COMPLETED:
            status_text = "تکمیل شده"
            progress = 100
        elif db_info["status"] == DownloadStatus.FAILED:
            status_text = f"با خطا مواجه شد: {db_info.get('error_message', 'خطای نامشخص')}"
        elif db_info["status"] == DownloadStatus.CANCELED:
            status_text = "لغو شده"

        # محاسبه زمان سپری شده
        start_time = None
        try:
            if db_info.get("start_time"):
                start_time = datetime.datetime.fromisoformat(db_info["start_time"])
        except:
            start_time = None

        end_time = None
        try:
            if db_info.get("end_time"):
                end_time = datetime.datetime.fromisoformat(db_info["end_time"])
        except:
            end_time = None

        elapsed_time = 0
        if start_time:
            if end_time:
                elapsed_time = (end_time - start_time).total_seconds()
            else:
                elapsed_time = (datetime.datetime.now() - start_time).total_seconds()

        return {
            "url": db_info["url"],
            "user_id": db_info["user_id"],
            "progress": progress,
            "status": status_text,
            "quality": db_info.get("quality", "best"),
            "elapsed_time": int(elapsed_time),
            "elapsed_time_human": format_duration(int(elapsed_time)),
            "file_path": db_info.get("file_path"),
            "file_size": db_info.get("file_size"),
            "file_size_human": format_filesize(db_info.get("file_size")),
            "metadata": db_info.get("metadata", {})
        }

    # اگر هیچ اطلاعاتی یافت نشد
    return {
        "url": "نامشخص",
        "user_id": 0,
        "progress": 0,
        "status": "اطلاعات پیدا نشد",
        "quality": "نامشخص",
        "elapsed_time": 0,
        "elapsed_time_human": "0:00"
    }

@debug_decorator
def cancel_download(download_id: int) -> bool:
    """
    لغو دانلود
    Args:
        download_id: شناسه دانلود
    Returns:
        True در صورت موفقیت
    """
    # بررسی اگر دانلود فعال است
    with active_downloads_lock:
        if download_id in active_downloads:
            # حذف از لیست فعال
            del active_downloads[download_id]

            # به‌روزرسانی وضعیت در دیتابیس
            update_download_status(download_id, DownloadStatus.CANCELED, error_message="دانلود لغو شد")
            debug_log(f"دانلود با ID {download_id} لغو شد", "INFO")
            return True

    # بررسی وضعیت در دیتابیس
    db_info = get_download(download_id)

    if db_info:
        # لغو فقط برای دانلودهای در حال انجام و در انتظار
        if db_info["status"] in [DownloadStatus.PENDING, DownloadStatus.PROCESSING]:
            update_download_status(download_id, DownloadStatus.CANCELED, error_message="دانلود لغو شد")
            debug_log(f"دانلود با ID {download_id} لغو شد", "INFO")
            return True

    debug_log(f"دانلود با ID {download_id} برای لغو یافت نشد یا قابل لغو نیست", "WARNING")
    return False

@debug_decorator
def get_active_downloads_count() -> int:
    """
    دریافت تعداد دانلودهای فعال
    Returns:
        تعداد دانلودهای فعال
    """
    with active_downloads_lock:
        return len(active_downloads)

@debug_decorator
def get_all_active_downloads() -> Dict[int, Dict[str, Any]]:
    """
    دریافت همه دانلودهای فعال
    Returns:
        دیکشنری از همه دانلودهای فعال
    """
    with active_downloads_lock:
        return active_downloads.copy()

@debug_decorator
def clean_old_downloads(max_age_days: int = 1) -> int:
    """
    پاکسازی دانلودهای قدیمی
    Args:
        max_age_days: حداکثر عمر دانلودها به روز
    Returns:
        تعداد فایل‌های پاک شده
    """
    debug_log(f"پاکسازی دانلودهای قدیمی (حداکثر {max_age_days} روز)", "INFO")

    count = 0
    current_time = time.time()
    max_age_seconds = max_age_days * 24 * 60 * 60

    try:
        # پیمایش دایرکتوری دانلودها
        for file in os.listdir(DOWNLOADS_DIR):
            file_path = os.path.join(DOWNLOADS_DIR, file)

            # بررسی اگر فایل است (نه دایرکتوری)
            if os.path.isfile(file_path):
                # دریافت زمان آخرین تغییر
                file_time = os.path.getmtime(file_path)
                file_age = current_time - file_time

                # اگر قدیمی‌تر از زمان تعیین شده بود، حذف شود
                if file_age > max_age_seconds:
                    os.remove(file_path)
                    count += 1
                    debug_log(f"فایل {file} حذف شد", "INFO")

    except Exception as e:
        debug_log(f"خطا در پاکسازی دانلودهای قدیمی: {str(e)}", "ERROR")

    return count

import datetime
def process_youtube_url(message, url):
    """پردازش لینک یوتیوب و شروع دانلود"""
    debug_log(f"شروع پردازش URL: {url}", "INFO")
    try:
        debug_log("بررسی اعتبار URL", "INFO")
        # اعتبارسنجی URL
        if not validate_youtube_url(url):
            bot.reply_to(message, "❌ لینک یوتیوب نامعتبر است.")
            return

        # استخراج اطلاعات ویدیو
        video_info = extract_video_info(url)
        if not video_info:
            bot.reply_to(message, "❌ خطا در دریافت اطلاعات ویدیو.")
            return

        # شروع دانلود
        download_id = int(time.time())
        success, file_path, error = download_video(url, download_id, message.from_user.id)

        if success and file_path:
            # ارسال ویدیو به کاربر
            with open(file_path, 'rb') as video_file:
                bot.send_video(message.chat.id, video_file, caption=f"✅ دانلود شد\n🎥 {video_info.get('title', '')}")
        else:
            bot.reply_to(message, f"❌ خطا در دانلود: {error.get('error', 'خطای نامشخص')}")

    except Exception as e:
        logger.error(f"خطا در پردازش لینک یوتیوب: {str(e)}")
        bot.reply_to(message, "⚠️ خطایی رخ داد. لطفا دوباره تلاش کنید.")

clean_old_downloads()