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
    update.message.reply_text('Здравствуйте! Я приемщик автосервиса Петя. Я помогу составить план работ. Для начала, как вас зовут?')

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text('Send me a question and I will answer it using Yandex GPT!')

def ask_question(update: Update, context: CallbackContext) -> None:
    """Send the user's question directly to Yandex GPT and return the response."""
    if update.message is None or update.message.text is None:
        update.message.reply_text("Sorry, I couldn't process that message.")
        return
        
    user_question = update.message.text
    
    # Initialize conversation history and current date in context if it doesn't exist
    if 'conversation_history' not in context.user_data:
        context.user_data['conversation_history'] = []
    
    # Add user message to conversation history
    context.user_data['conversation_history'].append({
        "role": "user",
        "text": user_question
    })
    
    # Get current date in DDMMYYYY format
    from datetime import datetime
    current_date = datetime.now().strftime("%d%m%Y")
    context.user_data['current_date'] = current_date
    
    # Call Yandex GPT API with conversation history
    gpt_response = call_yandex_gpt(context.user_data['conversation_history'], current_date)
    
    # Add assistant response to conversation history
    context.user_data['conversation_history'].append({
        "role": "assistant",
        "text": gpt_response
    })
    
    # Send the response directly to the user
    update.message.reply_text(gpt_response)

def call_yandex_gpt(messages, current_date=None) -> str:
    """Call Yandex GPT API and return the response."""
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        return "Yandex API key or folder ID not configured. Please check your environment variables."
    
    headers = {
        'Authorization': f'Api-Key {YANDEX_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Format current date as DD-MM-YYYY if available
    formatted_date = current_date
    if current_date and len(current_date) == 8:
        formatted_date = f"{current_date[0:2]}-{current_date[2:4]}-{current_date[4:8]}"
    
    # System prompt for body repair service
    system_prompt = """
Ты — опытный сотрудник кузовного автосервиса. Твоя задача — вести диалог с посетителем, собрать данные и на их основе сформировать мнение о том, какие работы необходимо провести с автомобилем.

Собери следующую информацию:
-Марку, пробег и госномер автомобиля
-Замечания посетителя по состоянию автомобиля
-По каждому замечанию запрашивай также в течение какого срока оно возникло и как проявляется
-Определи могут ли замечания быть устранены кузовными работами или требуются другие специалисты

Задавай уточняющие вопросы по одному. Не делай предположений. Сначала запроси марку, пробег и госномер автомобиля. Только после получения этой информации спрашивай о замечаниях по состоянию автомобиля. После получения информации по каждому замечанию, обязательно спрашивай: "Есть ли ещё какие-то замечания по состоянию автомобиля?"

Как только вся необходимая информация собрана, самостоятельно заверши диалог и выдай структурированный план работ в формате Markdown с заголовком "План кузовных работ по автомобилю {вставь сюда госномер}", на новой строке укажи "Владелец автомобиля: {имя владельца}", на новой строке укажи "Приёмщик: Петя", на новой строке укажи "Дата приёмки: {current_date}" и перечисли в документе те работы, которые могут быть выполнены на сервисе. Форматируй дату как ДД-ММ-ГГГГ (например, 03-12-2025).

Не продолжай задавать вопросы, если данных достаточно. Если пользователь говорит «хватит» или «покажи план» — немедленно сформируй документ. Не используй фразы вроде «Уточните» — действуй самостоятельно при достаточном объёме данных.
"""

    # Prepare messages list with system prompt
    formatted_system_prompt = system_prompt
    if current_date:
        formatted_system_prompt = system_prompt.replace("{current_date}", current_date)
    
    formatted_messages = [
        {
            "role": "system",
            "text": formatted_system_prompt
        }
    ]
    
    # Add conversation history
    if isinstance(messages, list):
        formatted_messages.extend(messages)
    else:
        formatted_messages.append({
            "role": "user",
            "text": messages
        })
    
    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-5.1/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 2000
        },
        "messages": formatted_messages,
    }
    
    try:
        response = requests.post(YANDEX_GPT_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        return result['result']['alternatives'][0]['message']['text']
    except Exception as e:
        logger.error(f"Error calling Yandex GPT API: {e}")
        return f"Sorry, I encountered an error while processing your request: {str(e)}"

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