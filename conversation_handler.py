import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from user_data import save_user_data, load_user_data

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define states for the conversation
NAME, AGE, HOBBIES, CONFIRM = range(4)

async def talk_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask for the user's name."""
    await update.message.reply_text(
        "Let's have a conversation! I'll ask you a few questions.\n\n"
        "What's your name? (You can type /cancel at any time to stop)"
    )
    return NAME

async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the name and ask for age."""
    user_name = update.message.text
    user_id = update.effective_user.id
    
    # Store the name in user_data
    user_data = load_user_data(user_id) or {}
    user_data['conversation_name'] = user_name
    save_user_data(user_id, user_data)
    
    # Store the name in context for later use
    context.user_data['name'] = user_name
    
    await update.message.reply_text(
        f"Nice to meet you, {user_name}! How old are you?"
    )
    return AGE

async def age_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the age and ask for hobbies."""
    try:
        user_age = int(update.message.text)
        if user_age < 0 or user_age > 120:
            await update.message.reply_text(
                "That doesn't seem like a valid age. Please enter a number between 0 and 120."
            )
            return AGE
    except ValueError:
        await update.message.reply_text(
            "That's not a valid number. Please enter your age as a number."
        )
        return AGE
    
    user_id = update.effective_user.id
    
    # Store the age in user_data
    user_data = load_user_data(user_id) or {}
    user_data['conversation_age'] = user_age
    save_user_data(user_id, user_data)
    
    # Store the age in context for later use
    context.user_data['age'] = user_age
    
    # Define some hobby options
    reply_keyboard = [
        ["Reading", "Sports"],
        ["Music", "Movies"],
        ["Cooking", "Travel"],
        ["Technology", "Art"],
        ["Other"]
    ]
    
    await update.message.reply_text(
        "What are your hobbies? You can select from the options or type your own.",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, input_field_placeholder="Your hobbies?"
        )
    )
    return HOBBIES

async def hobbies_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the hobbies and ask for confirmation."""
    user_hobbies = update.message.text
    user_id = update.effective_user.id
    
    # Store the hobbies in user_data
    user_data = load_user_data(user_id) or {}
    user_data['conversation_hobbies'] = user_hobbies
    save_user_data(user_id, user_data)
    
    # Store the hobbies in context for later use
    context.user_data['hobbies'] = user_hobbies
    
    # Create a summary of the conversation
    name = context.user_data.get('name', "Unknown")
    age = context.user_data.get('age', "Unknown")
    hobbies = context.user_data.get('hobbies', "Unknown")
    
    await update.message.reply_text(
        f"Great! Here's what I know about you:\n\n"
        f"Name: {name}\n"
        f"Age: {age}\n"
        f"Hobbies: {hobbies}\n\n"
        f"Is this information correct? (Yes/No)",
        reply_markup=ReplyKeyboardRemove()
    )
    return CONFIRM

async def confirm_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End the conversation based on user confirmation."""
    response = update.message.text.lower()
    
    if response in ["yes", "y", "correct", "right"]:
        name = context.user_data.get('name', "Unknown")
        age = context.user_data.get('age', "Unknown")
        hobbies = context.user_data.get('hobbies', "Unknown")
        
        # Give a personalized response based on the information
        await update.message.reply_text(
            f"Thanks for chatting with me, {name}! "
            f"At {age}, you've got plenty of time to enjoy {hobbies}.\n\n"
            f"If you ever want to chat again, just use the /talk command!"
        )
    else:
        await update.message.reply_text(
            "No problem! Let's try again later. Use /talk to start over."
        )
    
    # Clear the conversation data from context
    context.user_data.clear()
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel and end the conversation."""
    await update.message.reply_text(
        "Conversation cancelled. You can start a new one anytime with /talk.",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Clear the conversation data from context
    context.user_data.clear()
    
    return ConversationHandler.END

def get_conversation_handlers():
    """Return the conversation handlers for the bot."""
    # Talk conversation handler
    talk_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("talk", talk_start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_received)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age_received)],
            HOBBIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, hobbies_received)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_conversation)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    return [talk_conv_handler]
