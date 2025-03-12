import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from storage import save_user_data

# Define conversation states
NAME, AGE, FEEDBACK = range(3)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def start_survey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the survey conversation."""
    await update.message.reply_text(
        "Let's start a quick survey! 📝\n\n"
        "You can cancel at any time by typing /cancel.\n\n"
        "First, what's your name?"
    )
    return NAME

async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the user's name response."""
    user_name = update.message.text
    user_id = update.effective_user.id
    
    # Store the name in user data
    context.user_data['name'] = user_name
    
    await update.message.reply_text(
        f"Nice to meet you, {user_name}! 😊\n\n"
        f"Now, how old are you? (Just type a number)"
    )
    
    logger.info(f"User {user_id} provided name: {user_name}")
    return AGE

async def handle_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the user's age response."""
    user_text = update.message.text
    user_id = update.effective_user.id
    
    # Validate that the age is a number
    try:
        age = int(user_text)
        if age <= 0 or age > 120:
            await update.message.reply_text(
                "That doesn't seem like a valid age. Please enter a number between 1 and 120."
            )
            return AGE
        
        # Store the age in user data
        context.user_data['age'] = age
        
        await update.message.reply_text(
            f"Thanks! Last question: What do you think about this bot? Any feedback?"
        )
        
        logger.info(f"User {user_id} provided age: {age}")
        return FEEDBACK
    
    except ValueError:
        await update.message.reply_text(
            "That doesn't seem like a valid age. Please enter a number."
        )
        return AGE

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the user's feedback and complete the survey."""
    feedback = update.message.text
    user_id = update.effective_user.id
    
    # Store the feedback in user data
    context.user_data['feedback'] = feedback
    
    # Save the complete user data
    user_data = {
        'user_id': user_id,
        'name': context.user_data.get('name', 'Unknown'),
        'age': context.user_data.get('age', 0),
        'feedback': feedback
    }
    save_user_data(user_data)
    
    # Create an inline keyboard for next steps
    keyboard = [
        [
            InlineKeyboardButton("Start Again", callback_data="survey"),
            InlineKeyboardButton("Help", callback_data="help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Thank you for completing the survey! 🎉\n\n"
        f"Here's a summary of your responses:\n"
        f"Name: {context.user_data.get('name')}\n"
        f"Age: {context.user_data.get('age')}\n"
        f"Feedback: {feedback}\n\n"
        f"Your responses have been saved. What would you like to do next?",
        reply_markup=reply_markup
    )
    
    logger.info(f"User {user_id} completed survey with feedback: {feedback}")
    
    # Clear user data and end conversation
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    user_id = update.effective_user.id
    
    await update.message.reply_text(
        "Survey cancelled. You can start a new one anytime with /survey."
    )
    
    logger.info(f"User {user_id} cancelled the conversation")
    
    # Clear user data and end conversation
    context.user_data.clear()
    return ConversationHandler.END

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks from inline keyboards."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "help":
        help_text = (
            "Here are the commands you can use:\n\n"
            "/start - Start the bot and get a welcome message\n"
            "/help - Show this help message\n"
            "/survey - Start a simple survey conversation\n"
            "/cancel - Cancel the current conversation\n\n"
            "You can also just send me a message and I'll respond!"
        )
        await query.message.reply_text(help_text)
    
    elif query.data == "survey":
        await query.message.reply_text(
            "Let's start a quick survey! 📝\n\n"
            "You can cancel at any time by typing /cancel.\n\n"
            "First, what's your name?"
        )
        return NAME
    
    logger.info(f"User {update.effective_user.id} clicked button: {query.data}")
