import os
import json
import logging
from typing import Dict, Any, List, Optional

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# File to store user data
USER_DATA_FILE = 'user_data.json'

def save_user_data(user_id: int, data: Dict[str, Any]) -> bool:
    """
    Save user data to storage.
    
    Args:
        user_id: The user's Telegram ID
        data: Dictionary of data to save for the user
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Load existing data
        all_user_data = {}
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as f:
                all_user_data = json.load(f)
        
        # Update with new data
        user_id_str = str(user_id)  # Convert to string for JSON key
        if user_id_str in all_user_data:
            all_user_data[user_id_str].update(data)
        else:
            all_user_data[user_id_str] = data
        
        # Save back to file
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(all_user_data, f, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"Error saving user data: {e}")
        return False

def load_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Load user data from storage.
    
    Args:
        user_id: The user's Telegram ID
        
    Returns:
        Dict or None: User data dictionary or None if not found
    """
    try:
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as f:
                all_user_data = json.load(f)
            
            user_id_str = str(user_id)
            return all_user_data.get(user_id_str)
        
        return None
    except Exception as e:
        logger.error(f"Error loading user data: {e}")
        return None

def get_all_users() -> List[Dict[str, Any]]:
    """
    Get all users' data.
    
    Returns:
        List: List of all user data dictionaries
    """
    try:
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as f:
                all_user_data = json.load(f)
            
            return [data for data in all_user_data.values()]
        
        return []
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return []

def delete_user_data(user_id: int) -> bool:
    """
    Delete a user's data from storage.
    
    Args:
        user_id: The user's Telegram ID
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r') as f:
                all_user_data = json.load(f)
            
            user_id_str = str(user_id)
            if user_id_str in all_user_data:
                del all_user_data[user_id_str]
                
                with open(USER_DATA_FILE, 'w') as f:
                    json.dump(all_user_data, f, indent=2)
                
                return True
        
        return False
    except Exception as e:
        logger.error(f"Error deleting user data: {e}")
        return False
