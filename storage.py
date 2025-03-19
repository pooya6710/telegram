import json
import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Directory for storing data
DATA_DIR = "bot_data"
USER_DATA_FILE = os.path.join(DATA_DIR, "user_data.json")

def ensure_data_dir_exists():
    """Ensure that the data directory exists."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        logger.info(f"Created data directory: {DATA_DIR}")

def load_user_data():
    """Load user data from file."""
    ensure_data_dir_exists()
    
    if not os.path.exists(USER_DATA_FILE):
        logger.info(f"User data file does not exist, creating empty one: {USER_DATA_FILE}")
        return {}
    
    try:
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {USER_DATA_FILE}, returning empty data")
        return {}
    except Exception as e:
        logger.error(f"Error loading user data: {e}")
        return {}

def save_user_data(user_data):
    """Save user data to file."""
    ensure_data_dir_exists()
    
    # Add timestamp
    user_data['timestamp'] = datetime.now().isoformat()
    
    # Load existing data
    all_data = load_user_data()
    
    # Update or add user data
    user_id = str(user_data['user_id'])
    if user_id not in all_data:
        all_data[user_id] = []
    
    # Add the new entry to the user's data list
    all_data[user_id].append(user_data)
    
    try:
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(all_data, f, indent=2)
        logger.info(f"Saved user data for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving user data: {e}")
