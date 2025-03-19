import os
import re
import logging
from typing import Optional

def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    return logging.getLogger(__name__)

def is_youtube_url(url):
    """Check if the URL is a valid YouTube URL"""
    youtube_regex = (
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    youtube_match = re.match(youtube_regex, url)
    return youtube_match is not None

def is_instagram_url(url):
    """Check if the URL is a valid Instagram URL"""
    instagram_regex = r'(https?://)?(www\.)?instagram\.com/(p|reel|tv)/[^/]+'
    instagram_match = re.match(instagram_regex, url)
    return instagram_match is not None

def clean_filename(filename):
    """Clean filename from invalid characters"""
    # Remove invalid characters
    clean_name = re.sub(r'[\\/*?:"<>|]', "", filename)
    # Replace spaces with underscores
    clean_name = clean_name.replace(' ', '_')
    return clean_name

def get_file_size(file_path):
    """Get file size in bytes"""
    try:
        return os.path.getsize(file_path)
    except Exception:
        return 0

def ensure_temp_dir(temp_dir):
    """Ensure temporary directory exists"""
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def cleanup_temp_file(file_path):
    """Remove temporary file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        logging.error(f"Error removing file {file_path}: {e}")
    return False

def cleanup_temp_dir(temp_dir):
    """Clean up temporary directory"""
    try:
        if os.path.exists(temp_dir):
            # اگر دایرکتوری بود، همه فایل‌ها را پاک کنیم
            if os.path.isdir(temp_dir):
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        logging.error(f"Error removing file {file_path}: {e}")
                try:
                    os.rmdir(temp_dir)
                except Exception as e:
                    logging.error(f"Error removing directory {temp_dir}: {e}")
            # اگر فایل بود، مستقیم پاک کنیم
            elif os.path.isfile(temp_dir):
                os.remove(temp_dir)
            return True
    except Exception as e:
        logging.error(f"Error cleaning up directory {temp_dir}: {e}")
    return False

def format_size(size):
    """Format file size to human readable format"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size/1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size/(1024*1024):.1f} MB"
    else:
        return f"{size/(1024*1024*1024):.1f} GB"