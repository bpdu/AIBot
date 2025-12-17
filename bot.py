import logging
import requests
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from dotenv import load_dotenv
import os

# MCP imports
from mcp import ClientSession
from mcp.client.websocket import websocket_client

# Load environment variables from the secret files
load_dotenv(dotenv_path='.secrets/bot-token.env')
load_dotenv(dotenv_path='.secrets/deepseek-api-key.env')

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Get the bot token from environment variables
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# DeepSeek API configuration (using your paid account)
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'
# Using DeepSeek Chat - your paid model
MODEL_NAME = 'deepseek-chat'  # Main DeepSeek model

# MCP configuration
MCP_SERVER_URL = "ws://localhost:8080/mcp"

def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_text('Привет! Это бот с моделью DeepSeek Chat через DeepSeek API. Задавай любые вопросы!')

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        'Доступные команды:\n'
        '/start - Начать работу с ботом\n'
        '/help - Показать это сообщение\n'
        '/stats - Показать статистику использования токенов и сжатия\n'
        '/compress - Сжать историю разговора вручную\n'
        '/clear - Очистить историю разговора\n\n'
        '📋 Yandex Tracker интеграция:\n'
        'Спросите про "задачи" или "tracker" - бот получит актуальный список задач через MCP!\n\n'
        '⏰ Автоматические уведомления:\n'
        'Каждые 15 минут бот присылает сводку задач из Yandex Tracker\n\n'
        '💡 Автосжатие: Каждые 10 сообщений история автоматически сжимается для экономии токенов!\n\n'
        'Просто отправьте мне вопрос, и я отвечу с помощью модели DeepSeek Chat!'
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

    # Show compression statistics
    if 'compression_stats' in context.user_data and context.user_data['compression_stats']['total_compressions'] > 0:
        comp_stats = context.user_data['compression_stats']
        stats_text += f"\n{'=' * 35}\n"
        stats_text += "🗜️ Статистика сжатия:\n\n"
        stats_text += f"• Всего сжатий: {comp_stats['total_compressions']}\n"
        stats_text += f"• Сообщений сжато: {comp_stats['messages_compressed']}\n"
        stats_text += f"• Токенов сэкономлено: ~{comp_stats['tokens_saved']}\n"

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

def compress_command(update: Update, context: CallbackContext) -> None:
    """Manually compress conversation history."""
    if 'conversation_history' not in context.user_data:
        update.message.reply_text('❌ История разговора пуста!')
        return

    history = context.user_data['conversation_history']
    non_system_messages = [msg for msg in history if msg.get('role') != 'system']

    if len(non_system_messages) < 2:
        update.message.reply_text('❌ Недостаточно сообщений для сжатия (минимум 2)')
        return

    update.message.reply_text('🗜️ Сжимаю историю разговора...')

    compression_result = compress_conversation_history(context, force=True)

    if compression_result.get('compressed'):
        # Reset message counter after manual compression
        old_counter = context.user_data.get('message_counter', 0)
        context.user_data['message_counter'] = 0

        response = (
            f"✅ История успешно сжата!\n\n"
            f"📊 Статистика сжатия:\n"
            f"• Сообщений до: {compression_result['messages_before']}\n"
            f"• Сообщений после: {compression_result['messages_after']}\n"
            f"• Токенов до: ~{compression_result['tokens_before']}\n"
            f"• Токенов после: ~{compression_result['tokens_after']}\n"
            f"• Сэкономлено токенов: ~{compression_result['tokens_saved']}\n"
            f"• Коэффициент сжатия: {compression_result['compression_ratio']}%\n"
            f"• Экономия: {100 - compression_result['compression_ratio']:.0f}%\n\n"
            f"🔄 Счётчик сообщений сброшен (было: #{old_counter})"
        )
        update.message.reply_text(response)
    else:
        update.message.reply_text(f"❌ Не удалось сжать историю: {compression_result.get('reason', 'Неизвестная ошибка')}")

def ask_question(update: Update, context: CallbackContext) -> None:
    """Send the user's question to DeepSeek API and return the response."""
    if update.message is None or update.message.text is None:
        update.message.reply_text("Sorry, I couldn't process that message.")
        return

    user_question = update.message.text

    # Сохранить chat_id при первом сообщении
    if 'admin_chat_id' not in context.bot_data:
        context.bot_data['admin_chat_id'] = update.message.chat_id
        logger.info(f"Saved admin_chat_id: {update.message.chat_id}")

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

    # Initialize message counter
    if 'message_counter' not in context.user_data:
        context.user_data['message_counter'] = 0

    # Increment message counter
    context.user_data['message_counter'] += 1
    current_message_num = context.user_data['message_counter']

    # Проверка на ключевые слова про задачи из Tracker
    keywords = ["задач", "task", "tracker", "issue", "трекер"]
    message_lower = user_question.lower()

    logger.info(f"Checking message for tracker keywords: '{message_lower}'")
    keyword_found = any(keyword in message_lower for keyword in keywords)
    logger.info(f"Keyword found: {keyword_found}")

    if keyword_found:
        logger.info("Detected tracker-related question, calling MCP...")
        try:
            tasks_json = call_mcp_tool_sync("get-tracker-tasks")
            logger.info(f"MCP response received: {len(tasks_json) if tasks_json else 0} chars")

            if tasks_json:
                # Добавить задачи в контекст
                tracker_context = {
                    "role": "system",
                    "content": f"Список задач из Yandex Tracker:\n{tasks_json}\n\nИспользуй эти данные для ответа на вопрос пользователя."
                }
                # Вставить в начало истории
                context.user_data['conversation_history'].insert(0, tracker_context)
                logger.info("Added tracker tasks to conversation context")
            else:
                logger.error("Failed to get tasks from MCP")

        except Exception as e:
            logger.error(f"Error calling MCP: {e}")
            update.message.reply_text("⚠️ Не удалось получить задачи из Tracker")

    # Add user message to conversation history
    context.user_data['conversation_history'].append({
        "role": "user",
        "content": user_question
    })

    # Auto-compress every 10 messages (excluding system messages)
    non_system_messages = [msg for msg in context.user_data['conversation_history'] if msg.get('role') != 'system']
    if len(non_system_messages) >= 10:
        compression_result = compress_conversation_history(context)
        if compression_result.get('compressed'):
            # Reset message counter after compression
            context.user_data['message_counter'] = 0
            update.message.reply_text(
                f"🗜️ Автосжатие истории (после сообщения #{current_message_num}):\n"
                f"• Сжато сообщений: {compression_result['messages_before']}\n"
                f"• Токенов было: ~{compression_result['tokens_before']}\n"
                f"• Токенов стало: ~{compression_result['tokens_after']}\n"
                f"• Экономия: ~{compression_result['tokens_saved']} токенов ({100 - compression_result['compression_ratio']:.0f}%)\n"
                f"• Счётчик сообщений сброшен!"
            )

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

    # Call DeepSeek API with conversation history
    gpt_response, token_usage = call_deepseek_api(context.user_data['conversation_history'])

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
    from datetime import datetime
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
        f"\n\n📊 Сообщение #{current_message_num} | Использовано токенов:\n"
        f"• Запрос: {token_usage['prompt_tokens']}\n"
        f"• Ответ: {token_usage['completion_tokens']}\n"
        f"• Всего: {token_usage['total_tokens']}"
    )

    # Send the response directly to the user with token info
    full_response = gpt_response + token_info
    update.message.reply_text(full_response)

def create_conversation_summary(messages) -> str:
    """Create a summary of conversation history using DeepSeek API.

    Args:
        messages: List of conversation messages

    Returns:
        str: Summary of the conversation
    """
    if not messages:
        return ""

    # Prepare prompt for summarization
    conversation_text = "\n".join([
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in messages
    ])

    summary_prompt = f"""Создай краткое резюме следующего диалога.
Сохрани ВСЮ важную информацию, факты, контекст и выводы.
Резюме должно позволить продолжить разговор без потери контекста.

Диалог:
{conversation_text}

Краткое резюме (на русском):"""

    summary_messages = [
        {"role": "system", "content": "Ты помощник, который создаёт краткие резюме диалогов, сохраняя всю важную информацию."},
        {"role": "user", "content": summary_prompt}
    ]

    try:
        response_text, _ = call_deepseek_api(summary_messages)
        return response_text
    except Exception as e:
        logger.error(f"Error creating summary: {e}")
        # Fallback: create simple summary
        return f"Обсуждалось {len(messages)} сообщений. Темы: {', '.join(set([msg['content'][:30] + '...' for msg in messages[:3]]))}"

def compress_conversation_history(context: CallbackContext, force: bool = False) -> dict:
    """Compress conversation history by creating a summary.

    Args:
        context: Telegram context with user_data
        force: Force compression even if threshold not reached

    Returns:
        dict: Compression statistics
    """
    if 'conversation_history' not in context.user_data:
        return {'compressed': False, 'reason': 'No history'}

    history = context.user_data['conversation_history']

    # Skip if history is too short (unless forced)
    if len(history) < 10 and not force:
        return {'compressed': False, 'reason': 'History too short', 'messages': len(history)}

    # Calculate tokens before compression
    chars_before = sum(len(msg['content']) for msg in history)
    tokens_before = chars_before // 4

    # Create summary of all messages except system messages
    messages_to_summarize = [msg for msg in history if msg.get('role') != 'system']

    if not messages_to_summarize:
        return {'compressed': False, 'reason': 'No messages to compress'}

    logger.info(f"Compressing {len(messages_to_summarize)} messages...")
    summary = create_conversation_summary(messages_to_summarize)

    # Replace history with summary
    context.user_data['conversation_history'] = [
        {
            "role": "system",
            "content": f"Предыдущий контекст диалога (резюме {len(messages_to_summarize)} сообщений):\n{summary}"
        }
    ]

    # Calculate tokens after compression
    chars_after = len(summary)
    tokens_after = chars_after // 4

    # Update compression statistics
    if 'compression_stats' not in context.user_data:
        context.user_data['compression_stats'] = {
            'total_compressions': 0,
            'tokens_saved': 0,
            'messages_compressed': 0
        }

    context.user_data['compression_stats']['total_compressions'] += 1
    context.user_data['compression_stats']['tokens_saved'] += (tokens_before - tokens_after)
    context.user_data['compression_stats']['messages_compressed'] += len(messages_to_summarize)

    return {
        'compressed': True,
        'messages_before': len(messages_to_summarize),
        'messages_after': 1,
        'tokens_before': tokens_before,
        'tokens_after': tokens_after,
        'tokens_saved': tokens_before - tokens_after,
        'compression_ratio': round(tokens_after / tokens_before * 100, 1) if tokens_before > 0 else 0
    }

def call_deepseek_api(messages) -> tuple:
    """Call DeepSeek API and return the response with token usage.

    Returns:
        tuple: (response_text, token_usage_dict) where token_usage_dict contains:
            - total_tokens: total tokens used
            - prompt_tokens: tokens in the prompt
            - completion_tokens: tokens in the completion
    """
    if not DEEPSEEK_API_KEY:
        return ("DeepSeek API key not configured. Please check your environment variables.",
                {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0})

    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
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
        response = requests.post(DEEPSEEK_API_URL, headers=headers, data=json.dumps(payload))
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
        logger.error(f"Error calling DeepSeek API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
        error_msg = f"Sorry, I encountered an error while processing your request: {str(e)}"
        return (error_msg, {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0})

# MCP Client functions
async def call_mcp_tool(tool_name: str, arguments: dict = None):
    """Вызов MCP tool через WebSocket и получение результата."""
    try:
        logger.info(f"Connecting to MCP server at {MCP_SERVER_URL}")
        async with websocket_client(MCP_SERVER_URL) as (read, write):
            logger.info("WebSocket connection established")
            async with ClientSession(read, write) as session:
                logger.info("MCP session created")

                # Инициализация с timeout
                await asyncio.wait_for(session.initialize(), timeout=10.0)
                logger.info("Session initialized")

                # Вызов tool с timeout
                logger.info(f"Calling tool: {tool_name}")
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments or {}),
                    timeout=15.0
                )
                logger.info(f"Tool call completed")

                # Извлечь текст из результата
                if result.content and len(result.content) > 0:
                    logger.info(f"Result content: {len(result.content[0].text)} chars")
                    return result.content[0].text
                else:
                    logger.warning("No content in result")
                return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout calling MCP tool: {tool_name}")
        return None
    except Exception as e:
        logger.error(f"Error calling MCP tool: {e}", exc_info=True)
        return None


def call_mcp_tool_sync(tool_name: str, arguments: dict = None):
    """Синхронная обертка для вызова async MCP tool."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(call_mcp_tool(tool_name, arguments))
    finally:
        loop.close()


def send_tasks_summary(context: CallbackContext):
    """Отправка сводки задач каждые 30 минут."""
    if 'admin_chat_id' not in context.bot_data:
        logger.warning("admin_chat_id not set, skipping summary")
        return

    try:
        # Получаем задачи через MCP
        tasks_json = call_mcp_tool_sync("get-tracker-tasks")

        if not tasks_json:
            logger.error("Failed to get tasks from MCP")
            return

        # Парсим JSON
        tasks = json.loads(tasks_json)

        # Форматируем сводку
        if isinstance(tasks, dict) and 'error' in tasks:
            summary = f"⚠️ Ошибка получения задач:\n{tasks['error']}"
        elif isinstance(tasks, list):
            if len(tasks) == 0:
                summary = "📋 Задач в Yandex Tracker нет"
            else:
                summary = f"📋 Сводка задач из Yandex Tracker ({len(tasks)} шт.):\n\n"
                for task in tasks[:10]:  # Показываем максимум 10 задач
                    summary += f"🔹 {task.get('key')}: {task.get('summary')}\n"
                    summary += f"   Статус: {task.get('status')}\n"
                    summary += f"   Исполнитель: {task.get('assignee')}\n\n"

                if len(tasks) > 10:
                    summary += f"\n... и ещё {len(tasks) - 10} задач(и)"
        else:
            summary = f"📋 Получены данные:\n{tasks_json[:500]}"

        # Отправляем
        context.bot.send_message(
            chat_id=context.bot_data['admin_chat_id'],
            text=summary
        )
        logger.info(f"Sent tasks summary to {context.bot_data['admin_chat_id']}")

    except Exception as e:
        logger.error(f"Error in send_tasks_summary: {e}", exc_info=True)


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
    dispatcher.add_handler(CommandHandler("compress", compress_command))
    dispatcher.add_handler(CommandHandler("clear", clear_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, ask_question))

    # Add error handler
    dispatcher.add_error_handler(error_handler)

    # Add periodic job for tasks summary (every 30 minutes = 1800 seconds)
    job_queue = updater.job_queue
    job_queue.run_repeating(send_tasks_summary, interval=1800, first=1800)
    logger.info("Scheduled tasks summary job (every 30 minutes)")

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()
