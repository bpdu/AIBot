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

# RAG imports
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'rag'))
try:
    from retrieval import rag_query
    from project_docs_retrieval import query_project_docs
    RAG_AVAILABLE = True
    PROJECT_DOCS_RAG_AVAILABLE = True
except ImportError as e:
    logger.warning(f"RAG module not available: {e}")
    RAG_AVAILABLE = False
    PROJECT_DOCS_RAG_AVAILABLE = False

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
MCP_SERVER_URL = "ws://localhost:8080/mcp"  # Yandex Tracker
MCP_SERVER2_URL = "ws://localhost:8081/mcp"  # Translation
MCP_GIT_SERVER_URL = "ws://localhost:8082/mcp"  # Git Integration

def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_text('Привет! Это бот с моделью DeepSeek Chat через DeepSeek API. Задавай любые вопросы!')

def help_command(update: Update, context: CallbackContext) -> None:
    """
    Send a message when the command /help is issued.

    Supports two modes:
    1. /help - Shows basic help message
    2. /help <question> - Searches project documentation using RAG and Git MCP
    """
    # Получить текст после /help
    message_text = update.message.text
    question = message_text.replace('/help', '').strip()

    # Режим 1: Базовая справка
    if not question:
        help_text = (
            '🤖 AIBot - Ассистент разработчика\n\n'
            'Доступные команды:\n'
            '/start - Начать работу с ботом\n'
            '/help - Показать это сообщение\n'
            '/help <вопрос> - Поиск по документации проекта\n'
            '/stats - Показать статистику использования токенов и сжатия\n'
            '/compress - Сжать историю разговора вручную\n'
            '/clear - Очистить историю разговора\n\n'
            '📋 Yandex Tracker интеграция:\n'
            'Спросите про "задачи" или "tracker" - бот получит актуальный список задач через MCP!\n\n'
            '💡 Автосжатие: Каждые 10 сообщений история автоматически сжимается для экономии токенов!\n\n'
            '🔍 Примеры использования /help:\n'
            '/help как добавить новый MCP сервер\n'
            '/help правила стиля кода\n'
            '/help архитектура RAG системы\n\n'
            'Просто отправьте мне вопрос, и я отвечу с помощью модели DeepSeek Chat!'
        )
        update.message.reply_text(help_text)
        return

    # Режим 2: Поиск по документации проекта
    if not PROJECT_DOCS_RAG_AVAILABLE:
        update.message.reply_text(
            "⚠️ Документация проекта недоступна.\n"
            "Запустите: python rag/create-project-docs-embeddings.py"
        )
        return

    update.message.reply_text(
        f"🔍 Ищу информацию в документации проекта...\n"
        f"Вопрос: {question}"
    )

    try:
        # Получить информацию о Git репозитории
        git_context = ""
        try:
            git_branch_result = call_mcp_tool_sync_on_server(
                MCP_GIT_SERVER_URL,
                "get-current-branch"
            )
            if git_branch_result:
                git_data = json.loads(git_branch_result)
                if git_data.get("success"):
                    git_context = f"\n\nТекущая ветка: {git_data.get('branch', 'unknown')}"
        except Exception as e:
            logger.warning(f"Failed to get git context: {e}")

        # Поиск в документации проекта
        logger.info(f"Searching project docs for: '{question}'")
        docs_context, docs_chunks = query_project_docs(question, top_k=5)

        if not docs_chunks:
            update.message.reply_text(
                "❌ Не найдено релевантной информации в документации проекта.\n"
                "Попробуйте переформулировать вопрос."
            )
            return

        # Построить промпт для DeepSeek
        system_message = {
            "role": "system",
            "content": (
                "Ты — AI-ассистент разработчика для проекта AIBot. "
                "Используй только информацию из документации проекта для ответа. "
                "Отвечай на русском языке, чётко и структурированно. "
                "Если в документации нет нужной информации, честно скажи об этом."
            )
        }

        user_message = {
            "role": "user",
            "content": (
                f"=== ДОКУМЕНТАЦИЯ ПРОЕКТА ===\n{docs_context}\n\n"
                f"=== КОНТЕКСТ РЕПОЗИТОРИЯ ==={git_context}\n\n"
                f"=== ВОПРОС ПОЛЬЗОВАТЕЛЯ ===\n{question}"
            )
        }

        messages = [system_message, user_message]

        # Вызвать DeepSeek API
        logger.info("Calling DeepSeek API with project docs context...")
        answer, tokens = call_deepseek_api(messages)

        # Форматировать ответ
        response_parts = [answer]

        # Добавить источники
        response_parts.append("\n" + "="*40)
        response_parts.append("📚 ИСТОЧНИКИ")
        response_parts.append("="*40)

        # Группировать по документам
        docs_map = {}
        for chunk in docs_chunks:
            doc_name = chunk['doc_name']
            if doc_name not in docs_map:
                docs_map[doc_name] = []
            docs_map[doc_name].append(chunk['heading'])

        for doc_name, headings in docs_map.items():
            response_parts.append(f"\n📄 {doc_name}")
            for heading in headings:
                response_parts.append(f"  • {heading}")

        # Добавить статистику
        response_parts.append(f"\n{'='*40}")
        response_parts.append("📊 СТАТИСТИКА")
        response_parts.append("="*40)
        response_parts.append(f"• Найдено фрагментов: {len(docs_chunks)}")
        response_parts.append(f"• Токенов использовано: {tokens['total_tokens']}")

        full_response = "\n".join(response_parts)

        # Отправить ответ (с разбиением, если длинный)
        send_long_message(update, full_response)

        logger.info("Project docs help query completed successfully")

    except Exception as e:
        logger.error(f"Error in project docs help: {e}", exc_info=True)
        update.message.reply_text(
            f"⚠️ Ошибка при поиске в документации: {str(e)}"
        )

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
    # День 22: Расширенные keywords для поддержки пользователей
    keywords = [
        # Tracker/issue keywords
        "задач", "task", "tracker", "issue", "трекер", "ticket", "тикет",
        # Problem keywords
        "error", "problem", "not working", "fail", "bug", "ошибк",
        # HTTP errors
        "401", "403", "404", "429", "500",
        # Support keywords
        "alert", "warning", "90%", "threshold", "custom", "support"
    ]
    message_lower = user_question.lower()

    logger.info(f"Checking message for tracker keywords: '{message_lower}'")
    keyword_found = any(keyword in message_lower for keyword in keywords)
    logger.info(f"Keyword found: {keyword_found}")

    # День 22: Получить задачи из Tracker (если есть keywords)
    tracker_info = None
    if keyword_found:
        logger.info("Detected tracker-related question, fetching tasks...")
        update.message.reply_text("🔄 Проверяю открытые задачи в Yandex Tracker...")

        try:
            # Простой вызов MCP для получения задач (не полный pipeline)
            tasks_json = call_mcp_tool_sync("get-tracker-tasks")

            if tasks_json:
                # Парсим задачи
                tasks_data = json.loads(tasks_json)

                # MCP возвращает либо массив задач, либо объект с ошибкой
                if isinstance(tasks_data, list):
                    # Успешно получили массив задач
                    tasks = tasks_data
                    logger.info(f"Retrieved {len(tasks)} tasks from Tracker")

                    # Форматируем краткую информацию о задачах для контекста
                    tracker_info = "Открытые задачи из Yandex Tracker:\n"
                    for task in tasks[:10]:  # Максимум 10 задач
                        key = task.get("key", "N/A")
                        summary = task.get("summary", "")
                        status = task.get("status", "Unknown")  # status уже строка в formatted_task
                        tracker_info += f"• {key}: {summary}\n  Статус: {status}\n"
                elif isinstance(tasks_data, dict) and "error" in tasks_data:
                    # Получили ошибку
                    logger.warning(f"Tracker returned error: {tasks_data['error']}")
                    tracker_info = f"Ошибка Tracker: {tasks_data['error']}"
                else:
                    logger.warning("Unexpected response format from Tracker")
                    tracker_info = "Неожиданный формат ответа от Tracker."
            else:
                logger.warning("MCP call returned empty result")
                tracker_info = "Не удалось получить задачи из Tracker."

        except Exception as e:
            logger.error(f"Error fetching tracker tasks: {e}", exc_info=True)
            tracker_info = f"Ошибка при получении задач из Tracker: {str(e)}"

        # НЕ возвращаемся! Продолжаем обработку для комбинированного ответа

    # Проверка на ключевые слова про мониторинг
    monitoring_keywords = ["мониторинг", "health", "состояние сервера", "метрики", "monitoring", "статус сервера"]
    monitoring_keyword_found = any(keyword in message_lower for keyword in monitoring_keywords)

    if monitoring_keyword_found:
        logger.info("Detected monitoring-related question, collecting host metrics...")
        update.message.reply_text("🔄 Собираю метрики хоста...")

        try:
            # Вызвать MCP tool для получения метрик
            monitoring_result_json = call_mcp_tool_sync_on_server(
                MCP_SERVER_URL,
                "get-host-metrics"
            )

            if not monitoring_result_json:
                update.message.reply_text("⚠️ Не удалось получить метрики. MCP сервер недоступен.")
                return

            # Парсим результат
            try:
                metrics = json.loads(monitoring_result_json)

                if metrics.get("success"):
                    # Форматируем красивое сообщение с метриками
                    cpu = metrics.get("cpu", {})
                    memory = metrics.get("memory", {})
                    disk = metrics.get("disk", {})
                    uptime = metrics.get("uptime", {})
                    system = metrics.get("system", {})
                    timestamp = metrics.get("timestamp", "")

                    # Определяем эмодзи для уровня загрузки
                    cpu_emoji = "🟢" if cpu.get("percent", 0) < 50 else "🟡" if cpu.get("percent", 0) < 80 else "🔴"
                    mem_emoji = "🟢" if memory.get("percent", 0) < 50 else "🟡" if memory.get("percent", 0) < 80 else "🔴"
                    disk_emoji = "🟢" if disk.get("percent", 0) < 50 else "🟡" if disk.get("percent", 0) < 80 else "🔴"

                    metrics_msg = (
                        f"📊 Метрики хоста\n"
                        f"{'=' * 30}\n"
                        f"🕐 {timestamp}\n\n"
                        f"{cpu_emoji} CPU:\n"
                        f"  • Загрузка: {cpu.get('percent', 0):.1f}%\n"
                        f"  • Ядра: {cpu.get('cores', 'N/A')}\n"
                        f"  • Частота: {cpu.get('frequency_mhz', 0)} MHz\n\n"
                        f"{mem_emoji} Память:\n"
                        f"  • Загрузка: {memory.get('percent', 0):.1f}%\n"
                        f"  • Использовано: {memory.get('used_gb', 0):.2f} GB\n"
                        f"  • Всего: {memory.get('total_gb', 0):.2f} GB\n\n"
                        f"{disk_emoji} Диск:\n"
                        f"  • Загрузка: {disk.get('percent', 0):.1f}%\n"
                        f"  • Использовано: {disk.get('used_gb', 0):.2f} GB\n"
                        f"  • Всего: {disk.get('total_gb', 0):.2f} GB\n\n"
                        f"⏱️ Uptime: {uptime.get('formatted', 'N/A')}\n"
                        f"🔄 Запуск: {uptime.get('boot_time', 'N/A')}\n\n"
                        f"💻 Система:\n"
                        f"  • Хост: {system.get('hostname', 'N/A')}\n"
                        f"  • ОС: {system.get('platform', 'N/A')}\n"
                        f"  • Архитектура: {system.get('architecture', 'N/A')}\n"
                        f"  • IP: {system.get('ip_address', 'N/A')}\n"
                        f"  • Температура: {system.get('temperature', 'N/A')}"
                    )
                    update.message.reply_text(metrics_msg)
                else:
                    # Ошибка при получении метрик
                    error = metrics.get("error", "Unknown error")
                    update.message.reply_text(f"⚠️ Ошибка при получении метрик: {error}")

            except json.JSONDecodeError:
                # Не JSON ответ
                update.message.reply_text(f"Результат: {monitoring_result_json[:500]}")

            logger.info("Monitoring request completed")
            return

        except Exception as e:
            logger.error(f"Error getting metrics: {e}", exc_info=True)
            update.message.reply_text(
                f"⚠️ Критическая ошибка при получении метрик: {str(e)}"
            )
            return

    # Проверка на вопросы про API (День 17: RAG, День 22: комбинация с Tracker)
    api_keywords = ["api", "endpoint", "sim", "esim", "inventory", "pond mobile", "msisdn",
                    "transfer", "webhook", "country", "countries", "group", "whitelist"]
    api_keyword_found = any(keyword in message_lower for keyword in api_keywords)

    if api_keyword_found and RAG_AVAILABLE:
        logger.info("Detected API-related question, using RAG with conversation history...")
        update.message.reply_text("🔍 Ищу информацию в документации Pond Mobile API...")

        try:
            # Выполнить RAG-запрос с передачей истории диалога и tracker info
            rag_result = handle_rag_query(
                question=user_question,
                conversation_history=context.user_data.get('conversation_history', []),
                tracker_info=tracker_info  # День 22: Добавляем информацию из Tracker
            )

            if not rag_result["success"]:
                error_msg = f"⚠️ Ошибка RAG: {rag_result.get('error', 'Unknown error')}"
                update.message.reply_text(error_msg)
                # Продолжить с обычным ответом (fallback)
            else:
                # Форматировать и отправить единое сообщение
                response_message = format_rag_response_for_telegram(rag_result)
                send_long_message(update, response_message)

                # ВАЖНО: Добавить ответ в историю диалога
                context.user_data['conversation_history'].append({
                    "role": "assistant",
                    "content": rag_result['answer']  # Только текст ответа
                })

                logger.info("RAG query completed successfully with tracker context")
                return

        except Exception as e:
            logger.error(f"Error in RAG processing: {e}", exc_info=True)
            update.message.reply_text(
                f"⚠️ Ошибка при обработке RAG-запроса: {str(e)}\n"
                "Продолжаю с обычным ответом..."
            )

    # День 22: Если есть только tracker_info (без API keywords), используем его в обычном DeepSeek запросе
    if tracker_info and not api_keyword_found:
        logger.info("Adding tracker context to conversation for non-API question")
        # Добавляем информацию из Tracker как system message в начало контекста
        tracker_system_msg = {
            "role": "system",
            "content": f"=== ИНФОРМАЦИЯ ИЗ YANDEX TRACKER ===\n{tracker_info}"
        }
        context.user_data['conversation_history'].insert(0, tracker_system_msg)

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


def analyze_tasks_order(tasks_json: str) -> str:
    """
    Анализ задач и создание рекомендованного порядка выполнения через DeepSeek.

    Args:
        tasks_json: JSON строка с задачами из Yandex Tracker

    Returns:
        Структурированный отчёт с анализом и рекомендованным порядком задач
    """
    analysis_prompt = f"""Проанализируй следующий список задач из Yandex Tracker.

Задачи:
{tasks_json}

Твоя задача:
1. Определи логический порядок выполнения задач
2. Найди зависимости (например, "Уточнить потребность" должно быть перед "Заказать")
3. Учти приоритеты и статусы задач
4. Создай структурированный отчёт с рекомендованным порядком

Формат ответа:
# Анализ задач из Yandex Tracker

## Рекомендованный порядок выполнения:

1. [KEY] - Название задачи
   Причина: [объяснение почему эта задача должна быть первой]
   Статус: [текущий статус]

2. [KEY] - Название задачи
   Причина: [объяснение]
   Статус: [текущий статус]

[и так далее...]

## Выводы:
[Краткие выводы о зависимостях и приоритетах]
"""

    messages = [
        {
            "role": "system",
            "content": "Ты - эксперт по управлению проектами. Анализируешь задачи и определяешь оптимальный порядок их выполнения."
        },
        {
            "role": "user",
            "content": analysis_prompt
        }
    ]

    try:
        logger.info("Analyzing tasks with DeepSeek...")
        response_text, token_usage = call_deepseek_api(messages)
        logger.info(f"Task analysis completed. Tokens used: {token_usage['total_tokens']}")
        return response_text
    except Exception as e:
        logger.error(f"Error analyzing tasks: {e}")
        return f"Ошибка анализа задач: {str(e)}"


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


def call_mcp_tool_sync_on_server(server_url: str, tool_name: str, arguments: dict = None):
    """
    Синхронная обертка для вызова MCP tool на конкретном сервере.

    Args:
        server_url: WebSocket URL МCP сервера (например, ws://localhost:8081/mcp)
        tool_name: Имя инструмента для вызова
        arguments: Аргументы инструмента (опционально)

    Returns:
        Текст результата или None при ошибке
    """
    async def call_tool_async():
        try:
            logger.info(f"Connecting to MCP server at {server_url}")
            async with websocket_client(server_url) as (read, write):
                logger.info("WebSocket connection established")
                async with ClientSession(read, write) as session:
                    logger.info("MCP session created")

                    # Инициализация с timeout
                    await asyncio.wait_for(session.initialize(), timeout=10.0)
                    logger.info("Session initialized")

                    # Вызов tool с увеличенным timeout для перевода
                    logger.info(f"Calling tool: {tool_name}")
                    result = await asyncio.wait_for(
                        session.call_tool(tool_name, arguments or {}),
                        timeout=30.0  # Длинный timeout для перевода
                    )
                    logger.info(f"Tool call completed")

                    if result.content and len(result.content) > 0:
                        return result.content[0].text
                    else:
                        logger.warning("No content in result")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout calling {tool_name} on {server_url}")
            return None
        except Exception as e:
            logger.error(f"Error calling {tool_name} on {server_url}: {e}", exc_info=True)
            return None

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(call_tool_async())
    finally:
        loop.close()


def execute_tasks_pipeline() -> dict:
    """
    Выполнить полный пайплайн: Получить задачи -> Проанализировать -> Перевести.

    Returns:
        dict со структурой:
        {
            "success": bool,
            "step": str,  # Последний успешный шаг
            "tasks_json": str,
            "analysis": str,
            "translation": str,
            "error": str  # Если произошла ошибка
        }
    """
    result = {
        "success": False,
        "step": "none",
        "tasks_json": None,
        "analysis": None,
        "translation": None,
        "error": None
    }

    try:
        # Шаг 1: Получить задачи из Yandex Tracker через MCP Server 1
        logger.info("Pipeline Step 1: Fetching tasks from Yandex Tracker")
        tasks_json = call_mcp_tool_sync_on_server(
            MCP_SERVER_URL,
            "get-tracker-tasks"
        )

        if not tasks_json or "error" in tasks_json.lower():
            result["error"] = "Не удалось получить задачи из Yandex Tracker"
            result["step"] = "fetch_tasks"
            return result

        result["tasks_json"] = tasks_json
        result["step"] = "fetch_tasks"
        logger.info(f"Step 1 complete: Retrieved {len(tasks_json)} chars")

        # Шаг 2: Анализ задач с помощью DeepSeek
        logger.info("Pipeline Step 2: Analyzing tasks with DeepSeek")
        analysis = analyze_tasks_order(tasks_json)

        if not analysis or "ошибка" in analysis.lower()[:100]:
            result["error"] = "Не удалось проанализировать задачи"
            result["step"] = "analyze_tasks"
            return result

        result["analysis"] = analysis
        result["step"] = "analyze_tasks"
        logger.info(f"Step 2 complete: Analysis {len(analysis)} chars")

        # Шаг 3: Перевод на эсперанто через MCP Server 2
        logger.info("Pipeline Step 3: Translating to Esperanto")
        translation_response = call_mcp_tool_sync_on_server(
            MCP_SERVER2_URL,
            "translate-to-esperanto",
            {"text": analysis}
        )

        if not translation_response:
            # Перевод опционален - не критическая ошибка
            logger.warning("Translation failed, using Russian version")
            result["translation"] = None
            result["error"] = "Перевод недоступен"
        else:
            # Проверяем, не вернулась ли ошибка в JSON формате
            try:
                error_check = json.loads(translation_response)
                if isinstance(error_check, dict) and "error" in error_check:
                    logger.warning(f"Translation error: {error_check['error']}")
                    result["translation"] = None
                    result["error"] = "Перевод недоступен"
                else:
                    result["translation"] = translation_response
                    logger.info(f"Step 3 complete: Translation {len(translation_response)} chars")
            except (json.JSONDecodeError, ValueError):
                # Не JSON - значит это обычный переведенный текст
                result["translation"] = translation_response
                logger.info(f"Step 3 complete: Translation {len(translation_response)} chars")

        result["success"] = True
        result["step"] = "complete"
        return result

    except Exception as e:
        logger.error(f"Pipeline error at step {result['step']}: {e}", exc_info=True)
        result["error"] = str(e)
        return result


def handle_rag_query(question: str, conversation_history: list = None, tracker_info: str = None) -> dict:
    """
    Обработать запрос с использованием RAG с учётом истории диалога и информации из Tracker.

    Args:
        question: Вопрос пользователя
        conversation_history: История диалога (опционально)
                            Формат: [{"role": "user"|"assistant"|"system", "content": str}]
        tracker_info: Информация о задачах из Yandex Tracker (опционально, День 22)

    Returns:
        dict с ответом и метаданными:
        {
            "success": bool,
            "question": str,
            "answer": str,                  # Единый ответ с RAG
            "relevant_chunks": list,        # Отфильтрованные chunks
            "context": str,                 # RAG контекст
            "tokens": dict,                 # Статистика токенов
            "sources_formatted": str,       # Отформатированные источники
            "error": str
        }
    """
    result = {
        "success": False,
        "question": question,
        "answer": None,
        "relevant_chunks": [],
        "context": "",
        "tokens": {},
        "sources_formatted": "",
        "error": None
    }

    try:
        # Проверить доступность RAG
        if not RAG_AVAILABLE:
            result["error"] = "RAG module not available"
            return result

        logger.info(f"Processing RAG query with conversation history: '{question}'")

        # Найти релевантные чанки С фильтрацией (hybrid mode)
        logger.info("Searching for relevant chunks with filtering...")
        context_text, chunks, filter_stats = rag_query(
            question,
            top_k=3,
            enable_filtering=True,
            filtering_mode="hybrid"
        )

        # Проверить, есть ли релевантные документы
        if not chunks:
            logger.warning("All chunks filtered out - no relevant documentation found")
            result["success"] = True
            result["answer"] = (
                "К сожалению, я не нашёл релевантной информации в документации "
                "Pond Mobile API для вашего вопроса. Попробуйте переформулировать "
                "запрос или уточнить детали."
            )
            result["sources_formatted"] = "\n📚 Источники: не найдены"
            result["tokens"] = {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
            return result

        result["relevant_chunks"] = chunks
        result["context"] = context_text
        logger.info(f"Found {len(chunks)} relevant chunks")

        # Подготовить контекст истории диалога
        history_context = ""
        if conversation_history:
            # Ограничить количество сообщений
            MAX_HISTORY_MESSAGES = 10
            recent_history = conversation_history[-MAX_HISTORY_MESSAGES:]

            # Взять только user/assistant сообщения (исключить system)
            recent_messages = [
                msg for msg in recent_history
                if msg.get('role') in ['user', 'assistant']
            ]

            if recent_messages:
                history_parts = []
                for msg in recent_messages:
                    role = "Пользователь" if msg['role'] == 'user' else "Ассистент"
                    history_parts.append(f"{role}: {msg['content']}")

                history_context = "\n".join(history_parts)
                logger.info(f"Using conversation history: {len(recent_messages)} messages")

        # Построить промпт с учётом истории и tracker info (День 22)
        system_message = {
            "role": "system",
            "content": (
                "Ты — AI-ассистент для работы с Pond Mobile API. "
                "Используй информацию из предоставленной документации для ответа. "
                "Если есть информация из Yandex Tracker о связанных задачах, обязательно упомяни её. "
                "Учитывай контекст предыдущего диалога, если он есть. "
                "Если в документации нет нужной информации, честно скажи об этом, "
                "но проверь, есть ли открытая задача в Tracker по этой теме. "
                "Формат ответа: сначала информация из документации, затем статус задач из Tracker. "
                "Отвечай на русском языке, чётко и структурированно."
            )
        }

        # Собрать user message
        user_content_parts = []

        # Добавить историю (если есть)
        if history_context:
            user_content_parts.append(
                "=== КОНТЕКСТ ПРЕДЫДУЩЕГО ДИАЛОГА ===\n" + history_context
            )

        # Добавить RAG контекст
        user_content_parts.append(
            "=== РЕЛЕВАНТНАЯ ДОКУМЕНТАЦИЯ ===\n" + context_text
        )

        # День 22: Добавить информацию из Tracker (если есть)
        if tracker_info:
            user_content_parts.append(
                "=== ОТКРЫТЫЕ ЗАДАЧИ ИЗ YANDEX TRACKER ===\n" + tracker_info
            )
            logger.info("Added Tracker context to RAG query")

        # Добавить текущий вопрос
        user_content_parts.append(
            f"=== ТЕКУЩИЙ ВОПРОС ПОЛЬЗОВАТЕЛЯ ===\n{question}"
        )

        user_message = {
            "role": "user",
            "content": "\n\n".join(user_content_parts)
        }

        messages = [system_message, user_message]

        # Вызвать DeepSeek API
        logger.info("Calling DeepSeek API with RAG context and conversation history...")
        answer, tokens = call_deepseek_api(messages)

        result["answer"] = answer
        result["tokens"] = tokens
        logger.info(f"Answer generated: {len(answer)} chars, {tokens['total_tokens']} tokens")

        # Форматировать источники
        result["sources_formatted"] = format_sources_for_telegram(chunks)

        result["success"] = True
        return result

    except Exception as e:
        logger.error(f"Error in RAG query with conversation history: {e}", exc_info=True)
        result["error"] = str(e)
        return result


def format_sources_for_telegram(chunks: list) -> str:
    """
    Форматировать источники для вывода пользователю в Telegram.

    Args:
        chunks: Список релевантных чанков с метаданными

    Returns:
        Отформатированная строка с источниками
    """
    if not chunks:
        return "\n📚 Источники: не найдены"

    sources_parts = ["\n" + "="*40]
    sources_parts.append("📚 ИСТОЧНИКИ")
    sources_parts.append("="*40)

    # Показать общий источник документации
    sources_parts.append("\n📖 Источник: OpenAPI спецификация Pond Mobile API")
    sources_parts.append("📁 Файл: resources/dist.json")

    return "\n".join(sources_parts)


def format_rag_response_for_telegram(rag_result: dict) -> str:
    """
    Форматировать результат RAG-запроса для вывода в Telegram.

    Args:
        rag_result: Результат handle_rag_query()

    Returns:
        Отформатированное сообщение для Telegram
    """
    parts = []

    # 1. Ответ от LLM
    parts.append(rag_result['answer'])

    # 2. Источники
    parts.append(rag_result['sources_formatted'])

    # 3. Статистика токенов
    tokens = rag_result['tokens']
    parts.append(
        f"\n{'='*40}\n"
        f"📊 СТАТИСТИКА\n"
        f"{'='*40}\n"
        f"• Токенов в запросе: {tokens['prompt_tokens']}\n"
        f"• Токенов в ответе: {tokens['completion_tokens']}\n"
        f"• Всего токенов: {tokens['total_tokens']}"
    )

    return "\n".join(parts)


def send_long_message(update: Update, message: str, max_length: int = 4000):
    """
    Отправить длинное сообщение, разбивая по необходимости.

    Args:
        update: Telegram update
        message: Сообщение для отправки
        max_length: Максимальная длина одного сообщения
    """
    if len(message) <= max_length:
        update.message.reply_text(message)
        return

    # Разбить по секциям (по разделителям "===")
    sections = message.split("="*40)

    current_part = ""
    for i, section in enumerate(sections):
        section_with_separator = ("="*40 + section) if i > 0 else section

        if len(current_part) + len(section_with_separator) > max_length:
            if current_part:
                update.message.reply_text(current_part)
            current_part = section_with_separator
        else:
            current_part += section_with_separator

    if current_part:
        update.message.reply_text(current_part)


def send_tasks_summary(context: CallbackContext):
    """Отправка сводки задач каждые N минут."""
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

    # Add periodic job for tasks summary (every 2 minutes = 120 seconds)
    # DISABLED: Regular task updates are disabled
    # job_queue = updater.job_queue
    # job_queue.run_repeating(send_tasks_summary, interval=120, first=120)
    # logger.info("Scheduled tasks summary job (every 2 minutes)")

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()
