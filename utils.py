import os
import shutil
import re
import logging
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse
import config

# Configure logging
def setup_logging():
    """Set up logging configuration"""
    # Create logs directory if it doesn't exist
    if not os.path.exists(config.LOG_DIR):
        os.makedirs(config.LOG_DIR)
    
    # Configure file handler with rotation
    file_handler = RotatingFileHandler(
        os.path.join(config.LOG_DIR, 'bot.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=3
    )
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # Setup root logger
    logging.root.setLevel(logging.INFO)
    logging.root.addHandler(file_handler)
    logging.root.addHandler(console_handler)
    
    return logging.getLogger(__name__)

# URL validation functions
def is_youtube_url(url):
    """Check if the URL is a valid YouTube URL"""
    parsed = urlparse(url)
    if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
        return True
    return False

def is_instagram_url(url):
    """Check if the URL is a valid Instagram URL"""
    parsed = urlparse(url)
    if 'instagram.com' in parsed.netloc:
        return True
    return False

# File management functions
def clean_filename(filename):
    """Clean filename from invalid characters"""
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def get_file_size(file_path):
    """Get file size in bytes"""
    return os.path.getsize(file_path)

def ensure_temp_dir(temp_dir):
    """Ensure temporary directory exists"""
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

def cleanup_temp_file(file_path):
    """Remove temporary file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logging.error(f"Error cleaning up file {file_path}: {str(e)}")

def cleanup_temp_dir(temp_dir):
    """Clean up temporary directory"""
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    except Exception as e:
        logging.error(f"Error cleaning up directory {temp_dir}: {str(e)}")

def format_size(size):
    """Format file size to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"
