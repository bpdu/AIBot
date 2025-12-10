import logging
import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from dotenv import load_dotenv
import os

# Load environment variables from the secret files
load_dotenv(dotenv_path='.secrets/bot-token.env')
load_dotenv(dotenv_path='.secrets/openrouter-api-key.env')

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Get the bot token from environment variables
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# OpenRouter API configuration (using free model)
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'
# Using Mistral Small 3.1 - free model with 24B parameters
MODEL_NAME = 'mistralai/mistral-small-3.1-24b-instruct:free'  # Free model from OpenRouter

def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_text('Привет! Это бот с бесплатной моделью Mistral Small 3.1 (24B параметров) через OpenRouter. Задавай любые вопросы!')

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        'Доступные команды:\n'
        '/start - Начать работу с ботом\n'
        '/help - Показать это сообщение\n'
        '/stats - Показать статистику использования токенов\n'
        '/clear - Очистить историю разговора\n\n'
        'Просто отправьте мне вопрос, и я отвечу с помощью бесплатной модели Mistral Small 3.1!'
    )
    update.message.reply_text(help_text)

def stats_command(update: Update, context: CallbackContext) -> None:
    """Show token usage statistics."""
    if 'token_stats' not in context.user_data or context.user_data['token_stats']['total_requests'] == 0:
        update.message.reply_text('📊 Статистика пуста. Отправьте несколько запросов для начала.')
        return

    stats = context.user_data['token_stats']

    # Calculate averages
    avg_total = stats['total_tokens'] / stats['total_requests']
    avg_prompt = stats['total_prompt_tokens'] / stats['total_requests']
    avg_completion = stats['total_completion_tokens'] / stats['total_requests']

    stats_text = (
        f"📊 Статистика использования токенов\n"
        f"{'=' * 35}\n\n"
        f"Всего запросов: {stats['total_requests']}\n\n"
        f"Общее использование:\n"
        f"• Всего токенов: {stats['total_tokens']}\n"
        f"• Токенов в запросах: {stats['total_prompt_tokens']}\n"
        f"• Токенов в ответах: {stats['total_completion_tokens']}\n\n"
        f"Среднее на запрос:\n"
        f"• Всего: {avg_total:.1f} токенов\n"
        f"• Запрос: {avg_prompt:.1f} токенов\n"
        f"• Ответ: {avg_completion:.1f} токенов\n"
    )

    # Show last 5 requests
    if stats['requests_history']:
        stats_text += f"\n{'=' * 35}\n"
        stats_text += f"Последние {min(5, len(stats['requests_history']))} запросов:\n\n"

        for i, req in enumerate(stats['requests_history'][-5:], 1):
            stats_text += (
                f"{i}. {req['timestamp']}\n"
                f"   Длина вопроса: {req['question_length']} символов\n"
                f"   Длина ответа: {req['response_length']} символов\n"
                f"   Токены: {req['tokens']['total_tokens']} "
                f"({req['tokens']['prompt_tokens']}+{req['tokens']['completion_tokens']})\n\n"
            )

    update.message.reply_text(stats_text)

def clear_command(update: Update, context: CallbackContext) -> None:
    """Clear conversation history."""
    if 'conversation_history' in context.user_data:
        context.user_data['conversation_history'] = []
    update.message.reply_text('🗑️ История разговора очищена!')

def ask_question(update: Update, context: CallbackContext) -> None:
    """Send the user's question to OpenRouter API and return the response."""
    if update.message is None or update.message.text is None:
        update.message.reply_text("Sorry, I couldn't process that message.")
        return

    user_question = update.message.text

    # Initialize conversation history and current date in context if it doesn't exist
    if 'conversation_history' not in context.user_data:
        context.user_data['conversation_history'] = []

    # Initialize token statistics
    if 'token_stats' not in context.user_data:
        context.user_data['token_stats'] = {
            'total_requests': 0,
            'total_tokens': 0,
            'total_prompt_tokens': 0,
            'total_completion_tokens': 0,
            'requests_history': []
        }

    # Add user message to conversation history
    context.user_data['conversation_history'].append({
        "role": "user",
        "content": user_question
    })

    # Estimate input length for warning
    estimated_input_chars = sum(len(msg['content']) for msg in context.user_data['conversation_history'])
    estimated_input_tokens = estimated_input_chars // 4  # Rough estimate: 1 token ≈ 4 chars

    # Warn if input is very long
    if estimated_input_tokens > 7000:
        update.message.reply_text(
            "⚠️ Внимание: Очень длинный запрос!\n"
            f"Приблизительно {estimated_input_tokens} токенов в истории разговора.\n"
            "Модель может не обработать весь контекст."
        )

    # Call OpenRouter API with conversation history
    gpt_response, token_usage = call_openrouter_api(context.user_data['conversation_history'])

    # Add assistant response to conversation history
    context.user_data['conversation_history'].append({
        "role": "assistant",
        "content": gpt_response
    })

    # Update token statistics
    context.user_data['token_stats']['total_requests'] += 1
    context.user_data['token_stats']['total_tokens'] += token_usage['total_tokens']
    context.user_data['token_stats']['total_prompt_tokens'] += token_usage['prompt_tokens']
    context.user_data['token_stats']['total_completion_tokens'] += token_usage['completion_tokens']

    # Add to request history (keep last 20 requests)
    context.user_data['token_stats']['requests_history'].append({
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'question_length': len(user_question),
        'response_length': len(gpt_response),
        'tokens': token_usage
    })
    if len(context.user_data['token_stats']['requests_history']) > 20:
        context.user_data['token_stats']['requests_history'].pop(0)

    # Format response with token information
    token_info = (
        f"\n\n📊 Использовано токенов:\n"
        f"• Запрос: {token_usage['prompt_tokens']}\n"
        f"• Ответ: {token_usage['completion_tokens']}\n"
        f"• Всего: {token_usage['total_tokens']}"
    )

    # Send the response directly to the user with token info
    full_response = gpt_response + token_info
    update.message.reply_text(full_response)

def call_openrouter_api(messages) -> tuple:
    """Call OpenRouter API and return the response with token usage.

    Returns:
        tuple: (response_text, token_usage_dict) where token_usage_dict contains:
            - total_tokens: total tokens used
            - prompt_tokens: tokens in the prompt
            - completion_tokens: tokens in the completion
    """
    if not OPENROUTER_API_KEY:
        return ("OpenRouter API key not configured. Please check your environment variables.",
                {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0})

    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://github.com/your-username/telegram-bot',  # Optional
        'X-Title': 'Telegram AI Bot'  # Optional
    }

    # Add system message if not present
    formatted_messages = []
    if not any(msg.get('role') == 'system' for msg in messages):
        formatted_messages.append({
            "role": "system",
            "content": "Ты — полезный AI-ассистент. Отвечай на вопросы пользователя максимально точно и полезно."
        })

    # Add conversation history
    formatted_messages.extend(messages)

    payload = {
        "model": MODEL_NAME,
        "messages": formatted_messages,
        "temperature": 0.7,
        "max_tokens": 2000
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()

        # Extract response text
        response_text = result['choices'][0]['message']['content']

        # Extract token usage from response
        usage = result.get('usage', {})

        # Get token counts
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        total_tokens = usage.get('total_tokens', 0)

        token_usage = {
            'total_tokens': total_tokens,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens
        }

        logger.info(f"Token usage: Total={total_tokens}, Prompt={prompt_tokens}, Completion={completion_tokens}")

        return (response_text, token_usage)
    except Exception as e:
        logger.error(f"Error calling OpenRouter API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
        error_msg = f"Sorry, I encountered an error while processing your request: {str(e)}"
        return (error_msg, {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0})

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
    dispatcher.add_handler(CommandHandler("stats", stats_command))
    dispatcher.add_handler(CommandHandler("clear", clear_command))
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