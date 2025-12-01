import logging
import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from dotenv import load_dotenv
import os

# Load environment variables from the secret files
load_dotenv(dotenv_path='.secrets/bot-token.env')
load_dotenv(dotenv_path='.secrets/yandex-api-key.env')

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Get the bot token from environment variables
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Yandex GPT API configuration
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY')
YANDEX_FOLDER_ID = os.getenv('YANDEX_FOLDER_ID')
YANDEX_GPT_API_URL = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'

def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_text(f'Hi {user.first_name}! I am your LLM assistant bot. Send me a question and I will answer it!')

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text('Send me a question and press the "Ask LLM" button to get an answer!')

def ask_question(update: Update, context: CallbackContext) -> None:
    """Store the user's question and show the 'Ask LLM' button."""
    if update.message is None or update.message.text is None:
        update.message.reply_text("Sorry, I couldn't process that message.")
        return
        
    user_question = update.message.text
    context.user_data['question'] = user_question
    
    # Create the "Ask LLM" button
    keyboard = [[InlineKeyboardButton("Ask LLM", callback_data='ask_llm')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(f'Your question: "{user_question}"\nPress the button below to get an answer:', reply_markup=reply_markup)

def call_yandex_gpt(prompt: str) -> str:
    """Call Yandex GPT API and return the response."""
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        return "Yandex API key or folder ID not configured. Please check your environment variables."
    
    headers = {
        'Authorization': f'Api-Key {YANDEX_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 2000
        },
        "messages": [
            {
                "role": "user",
                "text": prompt
            }
        ]
    }
    
    try:
        response = requests.post(YANDEX_GPT_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        return result['result']['alternatives'][0]['message']['text']
    except Exception as e:
        logger.error(f"Error calling Yandex GPT API: {e}")
        return f"Sorry, I encountered an error while processing your request: {str(e)}"

def button_handler(update: Update, context: CallbackContext) -> None:
    """Handle button presses."""
    query = update.callback_query
    query.answer()
    
    if query.data == 'ask_llm':
        user_question = context.user_data.get('question', 'No question provided')
        # Call Yandex GPT API
        gpt_response = call_yandex_gpt(user_question)
        response = f"{gpt_response}"
        query.edit_message_text(text=response)

def error_handler(update: Update, context: CallbackContext) -> None:
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}")

def main() -> None:
    """Start the bot."""
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        return
    
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Register handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, ask_question))
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    
    # Add error handler
    dispatcher.add_error_handler(error_handler)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()