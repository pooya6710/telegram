import os
import logging

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_bot_token() -> str:
    """
    Get the Telegram bot token from environment variables.
    
    Returns:
        str: Bot token or empty string if not found
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.warning("No TELEGRAM_BOT_TOKEN found in environment variables!")
    return token

def format_time_ago(seconds: int) -> str:
    """
    Format a seconds value into a human-readable time ago string.
    
    Args:
        seconds: Number of seconds
        
    Returns:
        str: Formatted time ago string
    """
    if seconds < 60:
        return f"{seconds} seconds ago"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    
    days = hours // 24
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    
    years = months // 12
    return f"{years} year{'s' if years != 1 else ''} ago"

def is_valid_telegram_username(username: str) -> bool:
    """
    Check if a string is a valid Telegram username.
    
    Args:
        username: String to check
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not username or len(username) < 5:
        return False
    
    # Telegram usernames must start with a letter
    if not username[0].isalpha():
        return False
    
    # Can only contain letters, numbers, and underscores
    for char in username:
        if not (char.isalnum() or char == '_'):
            return False
    
    return True
