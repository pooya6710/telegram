import os
import logging
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Survey conversation states
NAME, AGE, FEEDBACK = range(3)

def setup_bot():
    """Set up and configure the Telegram bot with handlers."""
    # Get token from environment variables
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("No TELEGRAM_BOT_TOKEN found in environment variables! Running in web-only mode.")
        return None

    # Import dependencies only if a token is available, to allow web interface to work
    # even if the telegram bot libraries have issues
    try:
        import asyncio
        from telegram.ext import (
            Application, CommandHandler, MessageHandler, 
            CallbackQueryHandler, ConversationHandler
        )
        from telegram.ext.filters import TEXT, COMMAND
        from command_handlers import start, help_command, unknown_command
        from conversation_handlers import (
            start_survey, handle_name, handle_age, handle_feedback, 
            handle_button_click, cancel_conversation
        )
        
        # Create a direct method using telebot which is simpler and more reliable
        import telebot
        from telebot import types
        
        # Initialize the bot with the token
        bot = telebot.TeleBot(token)
        
        # Define command handlers
        @bot.message_handler(commands=['start'])
        def handle_start(message):
            user = message.from_user
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("Help", callback_data="help"),
                types.InlineKeyboardButton("Start Survey", callback_data="survey")
            )
            
            bot.send_message(
                message.chat.id,
                f"Hello, {user.first_name}! 👋\n\n"
                f"Welcome to the Telegram Bot! I can help you with various tasks.\n\n"
                f"Use /help to see available commands or click the buttons below:",
                reply_markup=markup
            )
            logger.info(f"User {user.id} started the bot")
        
        @bot.message_handler(commands=['help'])
        def handle_help(message):
            help_text = (
                "Here are the commands you can use:\n\n"
                "/start - Start the bot and get a welcome message\n"
                "/help - Show this help message\n"
                "/survey - Start a simple survey conversation\n"
                "/youtube [URL] - Get info about a YouTube video\n"
                "/cancel - Cancel the current conversation\n\n"
                "You can also just send me a message and I'll respond!"
            )
            bot.send_message(message.chat.id, help_text)
            logger.info(f"User {message.from_user.id} requested help")
            
        @bot.message_handler(commands=['youtube'])
        def handle_youtube(message):
            command_parts = message.text.split(' ', 1)
            if len(command_parts) < 2:
                bot.send_message(
                    message.chat.id,
                    "Please provide a YouTube URL after the command. Example:\n/youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                )
                return
                
            url = command_parts[1].strip()
            
            # Check if it looks like a YouTube URL
            if not ("youtube.com" in url or "youtu.be" in url):
                bot.send_message(
                    message.chat.id,
                    "That doesn't look like a YouTube URL. Please provide a valid YouTube link."
                )
                return
                
            # Let the user know we're processing
            status_message = bot.send_message(message.chat.id, "⏳ Fetching video information...")
            
            try:
                # Use yt-dlp to extract video information
                from yt_dlp import YoutubeDL
                
                with YoutubeDL({'quiet': True, 'no_warnings': True, 'noplaylist': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    # Format the response
                    response = (
                        f"📹 *{info['title']}*\n\n"
                        f"👤 Channel: {info['uploader']}\n"
                        f"⏱️ Duration: {info['duration_string']}\n"
                        f"👁️ Views: {info.get('view_count', 'N/A')}\n"
                        f"👍 Likes: {info.get('like_count', 'N/A')}\n"
                        f"📅 Upload date: {info.get('upload_date', 'N/A')}\n\n"
                        f"🔗 [Watch on YouTube]({url})"
                    )
                    
                    # Edit the status message with the video info
                    bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=status_message.message_id,
                        text=response,
                        parse_mode="Markdown"
                    )
                    logger.info(f"Fetched YouTube info for user {message.from_user.id}: {url}")
                    
            except Exception as e:
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=status_message.message_id,
                    text=f"❌ Error fetching video information: {str(e)}"
                )
                logger.error(f"YouTube info error: {e}")
            
        @bot.message_handler(commands=['survey'])
        def handle_survey(message):
            bot.send_message(
                message.chat.id,
                "Let's start the survey. What's your name?"
            )
            # Set up the next step handler
            bot.register_next_step_handler(message, process_name_step)
            
        def process_name_step(message):
            name = message.text
            if name:
                # Store name (would use user_data in a real application)
                # Here we just acknowledge and move to next step
                bot.send_message(
                    message.chat.id,
                    f"Nice to meet you, {name}! How old are you?"
                )
                bot.register_next_step_handler(message, process_age_step)
            
        def process_age_step(message):
            age = message.text
            if age and age.isdigit():
                bot.send_message(
                    message.chat.id,
                    f"Thanks! You're {age} years old. What feedback do you have for me?"
                )
                bot.register_next_step_handler(message, process_feedback_step)
            else:
                bot.send_message(
                    message.chat.id,
                    "Please enter a valid age (numbers only)."
                )
                bot.register_next_step_handler(message, process_age_step)
                
        def process_feedback_step(message):
            feedback = message.text
            if feedback:
                bot.send_message(
                    message.chat.id,
                    f"Thank you for your feedback! Your survey is complete."
                )
            
        @bot.message_handler(func=lambda message: True)
        def handle_all_messages(message):
            bot.reply_to(message, "I received your message. Send /help to see what I can do!")
            
        # Start the bot in a separate thread for non-blocking operation
        def polling_thread():
            logger.info("Starting bot polling")
            bot.infinity_polling()
            
        bot_thread = threading.Thread(target=polling_thread)
        bot_thread.daemon = True
        bot_thread.start()
        
        logger.info("Bot polling started in a separate thread")
        return True
        
    except ImportError as e:
        logger.error(f"Failed to import telegram bot libraries: {e}")
        return None
    except Exception as e:
        logger.error(f"Error setting up bot: {e}")
        return None
