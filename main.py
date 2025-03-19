import os
import sys
import logging
import time
import threading
from flask import Flask, jsonify, render_template
from debug_logger import debug_log, setup_logging # Retained from original
from bot import start_bot, TOKEN #Retained from original
from server_status import generate_server_status, get_cached_server_status #Retained from original

# Set up logging (Improved from original, using debug_logger if available)
try:
    setup_logging() # From debug_logger module - better logging setup
    logger = logging.getLogger(__name__)
    logger.info("✅ Advanced debugging system loaded successfully")
except ImportError as e:
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger = logging.getLogger(__name__)
    logger.error(f"⚠️ Error loading debug_logger module: {e}")

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key-for-development') #Retained from original

# -- Server Status Management (Retained and adapted from original) --
SERVER_STATUS_FILE = "server_status.json"
bot_status = {
    "running": False,
    "start_time": time.time(),
    "uptime": "0 ساعت و 0 دقیقه",
    "users_count": 0,
    "downloads_count": 0,
    "last_activity": "هنوز فعالیتی ثبت نشده"
}

def update_bot_status():
    uptime_seconds = int(time.time() - bot_status["start_time"])
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    bot_status["uptime"] = f"{hours} ساعت و {minutes} دقیقه"

    if os.path.exists(SERVER_STATUS_FILE):
        try:
            with open(SERVER_STATUS_FILE, 'r', encoding='utf-8') as f:
                saved_status = json.load(f)
                if "users_count" in saved_status:
                    bot_status["users_count"] = saved_status["users_count"]
                if "downloads_count" in saved_status:
                    bot_status["downloads_count"] = saved_status["downloads_count"]
                if "last_activity" in saved_status:
                    bot_status["last_activity"] = saved_status["last_activity"]
                server_status = get_cached_server_status()
                if server_status and "is_bot_running" in server_status:
                    bot_status["running"] = server_status["is_bot_running"]
        except Exception as e:
            logger.error(f"Error reading server status file: {e}")

# -- End of Server Status Management --

# Create routes (Simplified from original, retains essential routes)
@app.route('/')
def index():
    update_bot_status()
    return render_template('index.html', bot_status=bot_status)


@app.route('/status')
def status():
    update_bot_status()
    return render_template('status.html', bot_status=bot_status)


@app.route('/ping')
def ping():
    return "Server is alive!", 200

# -- Bot Startup and Error Handling (Improved from original) --
def run_bot():
    max_retries = 5
    retry_delay = 10
    retry_count = 0
    while retry_count < max_retries:
        try:
            bot_status["running"] = True
            with open(SERVER_STATUS_FILE, 'w', encoding='utf-8') as f:
                json.dump({"is_bot_running": True}, f)
            if start_bot():
                logger.info("🚀 Telegram bot started successfully!")
                return True
            else:
                raise Exception("Error in initial bot setup")
        except Exception as e:
            retry_count += 1
            logger.error(f"⚠️ Error starting bot (attempt {retry_count}/{max_retries}): {e}")
            bot_status["running"] = False
            if retry_count < max_retries:
                logger.info(f"🔄 Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 1.5
            else:
                logger.error("❌ All attempts to start the bot failed")
                return False


def main():
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # Start Flask server
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


if __name__ == '__main__':
    main()