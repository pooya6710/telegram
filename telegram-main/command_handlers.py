import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    
    # Create inline keyboard with buttons
    keyboard = [
        [
            InlineKeyboardButton("Help", callback_data="help"),
            InlineKeyboardButton("Start Survey", callback_data="survey")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f"Hello, {user.mention_html()}! 👋\n\n"
        f"Welcome to the Telegram Bot! I can help you with various tasks.\n\n"
        f"Use /help to see available commands or click the buttons below:",
        reply_markup=reply_markup
    )
    
    logger.info(f"User {user.id} started the bot")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "Here are the commands you can use:\n\n"
        "/start - Start the bot and get a welcome message\n"
        "/help - Show this help message\n"
        "/survey - Start a simple survey conversation\n"
        "/cancel - Cancel the current conversation\n\n"
        "You can also just send me a message and I'll respond!"
    )
    await update.message.reply_text(help_text)
    
    logger.info(f"User {update.effective_user.id} requested help")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to an unknown command."""
    await update.message.reply_text(
        "Sorry, I don't understand that command. Use /help to see available commands."
    )
    
    logger.info(f"User {update.effective_user.id} used unknown command: {update.message.text}")
