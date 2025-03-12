import os
import logging
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
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
        
        # Define a function to run the bot in a separate thread
        def run_bot_polling():
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Build the application
            application = Application.builder().token(token).build()
            
            # Add conversation handler for survey
            survey_conv_handler = ConversationHandler(
                entry_points=[CommandHandler('survey', start_survey)],
                states={
                    NAME: [MessageHandler(TEXT & ~COMMAND, handle_name)],
                    AGE: [MessageHandler(TEXT & ~COMMAND, handle_age)],
                    FEEDBACK: [MessageHandler(TEXT & ~COMMAND, handle_feedback)],
                },
                fallbacks=[CommandHandler('cancel', cancel_conversation)]
            )
            
            # Add command handlers
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("help", help_command))
            application.add_handler(survey_conv_handler)
            
            # Add callback query handler for button clicks
            application.add_handler(CallbackQueryHandler(handle_button_click))
            
            # Add handler for unknown commands
            application.add_handler(MessageHandler(COMMAND, unknown_command))
            
            # Add handler for non-command messages
            application.add_handler(MessageHandler(TEXT & ~COMMAND, handle_name))
            
            # Start polling in non-blocking mode
            async def start_polling():
                await application.initialize()
                await application.start()
                await application.updater.start_polling(allowed_updates=["message", "callback_query"])
                logger.info("Bot polling started successfully")
                
            # Run the async function in the new event loop
            loop.run_until_complete(start_polling())
            
        # Start the bot in a separate thread
        bot_thread = threading.Thread(target=run_bot_polling)
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
