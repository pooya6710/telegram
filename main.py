import os
import logging
from flask import Flask, render_template
from threading import Thread
import bot

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

@app.route('/')
def home():
    """Render the home page with information about the bot."""
    return render_template('index.html')

def run_flask():
    """Run the Flask app to keep the bot alive."""
    app.run(host='0.0.0.0', port=5000, debug=True)

def main():
    """Main function to start the bot and the web server."""
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start the Telegram bot
    bot.start_bot()

if __name__ == "__main__":
    main()
