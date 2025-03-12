import os
import logging
from flask import Flask, render_template
from threading import Thread
from bot import setup_bot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

# Bot status variable
bot_status = {
    "running": False,
    "error": None
}

@app.route('/')
def home():
    """Route to render the home page."""
    token_available = os.environ.get("TELEGRAM_BOT_TOKEN") is not None
    status_message = "Running" if bot_status["running"] else "Waiting for Telegram Token"
    
    return render_template(
        'index.html', 
        bot_name="Telegram Bot",
        bot_status=status_message,
        token_available=token_available,
        error_message=bot_status["error"]
    )

def run_flask():
    """Run the Flask web server."""
    app.run(host='0.0.0.0', port=5000, debug=True)

def main():
    """Main function to start both the Flask server and the Telegram bot."""
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start the Telegram bot if token is available
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        try:
            bot = setup_bot()
            if bot:
                bot_status["running"] = True
                logger.info("Bot is running!")
            else:
                bot_status["error"] = "Failed to start the bot"
                logger.error("Failed to start the bot")
        except Exception as e:
            bot_status["error"] = str(e)
            logger.error(f"Error starting bot: {e}")
    else:
        logger.warning("No TELEGRAM_BOT_TOKEN found. Running in web-only mode.")
        bot_status["error"] = "No Telegram Bot Token provided"
    
    # Keep the main thread alive
    try:
        flask_thread.join()
    except KeyboardInterrupt:
        logger.info("Stopping the application...")

if __name__ == "__main__":
    main()
