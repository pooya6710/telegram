import os
import logging
import telebot
from telebot import types
from user_data import save_user_data, load_user_data, get_all_users

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    # Save basic user data
    user_data = {
        'user_id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name
    }
    save_user_data(user.id, user_data)
    
    keyboard = [
        [
            InlineKeyboardButton("Help", callback_data='help'),
            InlineKeyboardButton("About", callback_data='about')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f"Hi {user.mention_html()}! I'm your Telegram Bot.\n\n"
        "What would you like to do today?",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message when the command /help is issued."""
    help_text = (
        "Here are the available commands:\n\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/about - About this bot\n"
        "/talk - Start a conversation\n"
        "/stats - Show bot statistics"
    )
    await update.message.reply_text(help_text)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send an about message when the command /about is issued."""
    about_text = (
        "🤖 This is a simple Telegram bot created with Python.\n\n"
        "Features:\n"
        "- Basic command handling\n"
        "- Simple conversation flows\n"
        "- User data storage\n\n"
        "Created as a demonstration of Python-based Telegram bot development."
    )
    await update.message.reply_text(about_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send statistics about the bot usage."""
    users = get_all_users()
    stats_text = (
        f"📊 Bot Statistics:\n\n"
        f"Total users: {len(users)}"
    )
    await update.message.reply_text(stats_text)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks from inline keyboards."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'help':
        help_text = (
            "Here are the available commands:\n\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/about - About this bot\n"
            "/talk - Start a conversation\n"
            "/stats - Show bot statistics"
        )
        await query.edit_message_text(text=help_text)
    
    elif query.data == 'about':
        about_text = (
            "🤖 This is a simple Telegram bot created with Python.\n\n"
            "Features:\n"
            "- Basic command handling\n"
            "- Simple conversation flows\n"
            "- User data storage\n\n"
            "Created as a demonstration of Python-based Telegram bot development."
        )
        await query.edit_message_text(text=about_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle normal text messages."""
    text = update.message.text
    user_id = update.effective_user.id
    
    # Load user data if available
    user_data = load_user_data(user_id) or {}
    
    # Simple echo functionality for regular messages
    await update.message.reply_text(f"You said: {text}\n\nType /help to see available commands.")

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unknown commands."""
    await update.message.reply_text(
        "Sorry, I didn't understand that command. Type /help to see available commands."
    )

def start_bot():
    """Start the bot."""
    # Get token from environment variable
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No TELEGRAM_BOT_TOKEN found in environment variables!")
        return
    
    # Create the Application
    application = Application.builder().token(token).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Add callback query handler for buttons
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Add conversation handlers
    for handler in get_conversation_handlers():
        application.add_handler(handler)
    
    # Add message handler for normal messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add unknown command handler (must be added last)
    application.add_handler(MessageHandler(filters.COMMAND, handle_unknown))
    
    # Start the Bot
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == "__main__":
    start_bot()
