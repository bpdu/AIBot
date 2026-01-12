# Архитектура проекта AIBot

## Обзор системы

AIBot - это комплексная система, состоящая из нескольких взаимодействующих компонентов:

```
┌─────────────────────────────────────────────────────────┐
│                    Пользователь                          │
└────────────────┬────────────────────────────────────────┘
                 │ Telegram
                 ↓
┌─────────────────────────────────────────────────────────┐
│              Telegram Bot (bot.py)                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Command Handlers (/start, /help, /stats)       │   │
│  │  Message Handler (ask_question)                  │   │
│  │  Keyword Detection (tracker, api, monitoring)    │   │
│  └─────────────────────────────────────────────────┘   │
└────┬──────────────┬──────────────┬───────────────┬──────┘
     │              │              │               │
     ↓              ↓              ↓               ↓
┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
│DeepSeek │  │   RAG    │  │   MCP    │  │ History Mgmt │
│   API   │  │ System   │  │ Servers  │  │  + Compress  │
└─────────┘  └──────────┘  └──────────┘  └──────────────┘
```

## Компоненты системы

### 1. Telegram Bot (bot.py)

**Ответственность:**
- Прием сообщений от пользователей
- Обработка команд
- Определение типа запроса по ключевым словам
- Управление историей диалога
- Координация работы других компонентов

**Основные модули:**

#### Command Handlers
- `start()` - инициализация бота
- `help_command()` - помощь по проекту
- `stats_command()` - статистика использования
- `compress_command()` - ручное сжатие истории
- `clear_command()` - очистка истории

#### Message Processing Pipeline
```python
ask_question()
  ↓
Keyword Detection
  ↓
┌─────────────┬───────────────┬──────────────┐
│   Tracker   │      API      │  Monitoring  │
│   Keywords  │   Keywords    │   Keywords   │
└─────────────┴───────────────┴──────────────┘
  ↓              ↓                ↓
MCP Pipeline    RAG Query      MCP Monitoring
  ↓              ↓                ↓
DeepSeek API ←──┴────────────────┘
  ↓
Response to User
```

### 2. RAG System (rag/)

**Компоненты:**

#### create-embeddings.py
- Парсинг документации (JSON, Markdown)
- Чанкинг текста
- Генерация embeddings (Ollama)
- Сохранение в SQLite

#### retrieval.py
- Генерация query embeddings
- Semantic search (cosine similarity)
- Фильтрация результатов (strict/adaptive/hybrid)
- Форматирование контекста для LLM

**Структура данных:**

```sql
CREATE TABLE embeddings (
    id INTEGER PRIMARY KEY,
    chunk_text TEXT,
    embedding BLOB,
    endpoint_path TEXT,
    method TEXT,
    tag TEXT,
    original_json TEXT
);
```

**Алгоритм поиска:**

1. Генерация embedding для query
2. Вычисление cosine similarity со всеми chunks
3. Первичная фильтрация (min_similarity = 0.3)
4. Вторичная фильтрация:
   - **Strict**: similarity >= 0.5
   - **Adaptive**: similarity >= top_score * 0.85
   - **Hybrid**: оба фильтра одновременно
5. Сортировка по релевантности
6. Возврат top-K результатов

### 3. MCP Servers (mcp/)

#### Архитектура MCP сервера

Все MCP серверы следуют единой архитектуре:

```python
# 1. Импорты
from mcp.server import Server
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute

# 2. Создание сервера
mcp_server = Server("server-name")

# 3. Определение инструментов
@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    return [Tool(...), Tool(...)]

# 4. Реализация инструментов
@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Логика обработки
    return [TextContent(type="text", text=result)]

# 5. WebSocket handler
async def handle_websocket(websocket: WebSocket):
    # JSON-RPC протокол
    # Методы: initialize, tools/list, tools/call

# 6. Starlette приложение
app = Starlette(routes=[WebSocketRoute("/mcp", handle_websocket)])
```

#### MCP Server 1: Yandex Tracker + Monitoring (port 8080)

**Инструменты:**
- `get-tracker-tasks`: Запрос к Yandex Tracker API
- `get-host-metrics`: Сбор метрик с помощью psutil

**Внешние API:**
- Yandex Tracker REST API
- psutil для системных метрик

#### MCP Server 2: Translation (port 8081)

**Инструменты:**
- `translate-to-esperanto`: Перевод через DeepSeek API

#### MCP Server 3: Git Integration (port 8082)

**Инструменты:**
- `get-current-branch`: Текущая ветка
- `get-git-status`: Статус репозитория
- `get-recent-commits`: История коммитов
- `get-changed-files`: Измененные файлы
- `get-file-content`: Содержимое файлов
- `get-git-diff`: Diff изменений

**Реализация через subprocess:**
```python
subprocess.run(['git', 'command'], capture_output=True, text=True)
```

### 4. DeepSeek API Integration

**Использование:**

1. **Основной чат:** Генерация ответов на вопросы
2. **RAG ответы:** Ответы с контекстом из документации
3. **Анализ задач:** Создание рекомендаций по задачам
4. **Суммаризация:** Сжатие истории диалога

**Формат запроса:**
```python
{
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ],
    "temperature": 0.7,
    "max_tokens": 2000
}
```

### 5. History Management

**Структура истории:**
```python
conversation_history = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
]
```

**Механизмы:**

#### Автосжатие
- Триггер: каждые 10 не-system сообщений
- Алгоритм:
  1. Извлечь все сообщения (кроме system)
  2. Создать summary через DeepSeek API
  3. Заменить историю на system message с summary
  4. Сброс счетчика сообщений

#### Статистика
- Подсчет токенов (по usage из API)
- История последних 20 запросов
- Статистика сжатия

## Потоки данных

### Поток 1: Обычный вопрос

```
User → Telegram
  ↓
bot.py: ask_question()
  ↓
Добавить в conversation_history
  ↓
call_deepseek_api(conversation_history)
  ↓
Response → User
  ↓
Добавить ответ в history
```

### Поток 2: RAG запрос

```
User → "api question"
  ↓
bot.py: Keyword detection (api_keywords)
  ↓
handle_rag_query()
  ↓
rag/retrieval.py: search_relevant_chunks()
  ↓
Генерация query embedding (Ollama)
  ↓
Cosine similarity со всеми chunks
  ↓
Фильтрация (hybrid mode)
  ↓
Format context + conversation history
  ↓
call_deepseek_api(system + context + history + question)
  ↓
Response → User
```

### Поток 3: Tracker pipeline

```
User → "задачи"
  ↓
bot.py: Keyword detection (tracker_keywords)
  ↓
execute_tasks_pipeline()
  ↓
┌────────────────────────────────────┐
│ 1. get-tracker-tasks (MCP Server1) │
│    ↓                                │
│ 2. analyze_tasks_order (DeepSeek)  │
│    ↓                                │
│ 3. translate-to-esperanto (MCP2)   │
└────────────────────────────────────┘
  ↓
Форматирование результатов
  ↓
Response (русский + эсперанто) → User
```

### Поток 4: Мониторинг

```
User → "мониторинг"
  ↓
bot.py: Keyword detection (monitoring_keywords)
  ↓
call_mcp_tool_sync_on_server(MCP_SERVER_URL, "get-host-metrics")
  ↓
MCP Server 1: get_host_metrics()
  ↓
psutil: CPU, Memory, Disk, Uptime, System info
  ↓
JSON response → Bot
  ↓
Форматирование с эмодзи
  ↓
Response → User
```

## Масштабирование

### Добавление нового MCP сервера

1. **Создать файл mcp/new_server.py:**

```python
"""MCP Server для [функционал]"""
from mcp.server import Server
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
import uvicorn

mcp_server = Server("new-server-name")

def business_logic():
    """Бизнес-логика инструмента."""
    pass

@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="tool-name",
            description="Описание инструмента",
            inputSchema={
                "type": "object",
                "properties": {
                    "param": {"type": "string", "description": "..."}
                },
                "required": ["param"]
            }
        )
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "tool-name":
        result = business_logic()
        return [TextContent(type="text", text=result)]

async def handle_websocket(websocket: WebSocket):
    # Стандартный JSON-RPC обработчик
    pass

app = Starlette(routes=[WebSocketRoute("/mcp", handle_websocket)])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8083)
```

2. **Добавить URL в bot.py:**

```python
MCP_SERVER3_URL = "ws://localhost:8083/mcp"
```

3. **Использовать в bot.py:**

```python
result = call_mcp_tool_sync_on_server(
    MCP_SERVER3_URL,
    "tool-name",
    {"param": "value"}
)
```

### Добавление новой документации в RAG

1. Положить файл в `resources/`
2. Обновить `rag/create-embeddings.py`:
   - Добавить парсер для нового формата
   - Обновить функцию chunking
3. Запустить `python rag/create-embeddings.py`
4. Добавить ключевые слова в `bot.py`:

```python
new_keywords = ["keyword1", "keyword2"]
keyword_found = any(keyword in message_lower for keyword in new_keywords)
```

## Безопасность

### Секретные данные
- Хранятся в `.secrets/` (не в git)
- Загружаются через `python-dotenv`
- Никогда не логируются полностью

### Валидация входных данных
- Проверка аргументов MCP инструментов
- Ограничение размера файлов (10KB для чтения)
- Timeout для внешних API (10-30 секунд)

### Изоляция
- Каждый MCP сервер на отдельном порту
- Git операции только через subprocess
- Ограничение размера diff/content

## Мониторинг и отладка

### Логирование

Все компоненты используют Python `logging`:

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Информация")
logger.warning("Предупреждение")
logger.error("Ошибка", exc_info=True)
```

**Уровни:**
- bot.py: INFO
- rag/retrieval.py: INFO
- mcp/*.py: INFO

### Метрики

**Token statistics:**
- Подсчет через API response
- Сохранение в context.user_data

**Compression statistics:**
- Tokens saved
- Compression ratio
- Messages compressed

### Отладка

1. **RAG:**
   ```bash
   cd rag
   python test_embeddings.py
   ```

2. **MCP:**
   ```bash
   cd mcp
   python mcp_client.py
   ```

3. **Token usage:**
   ```bash
   python test_tokens.py
   ```

## Производительность

### Оптимизации

1. **RAG:**
   - Минимальный порог similarity (0.3)
   - Двухэтапная фильтрация
   - Ограничение top-K

2. **History:**
   - Автоматическое сжатие каждые 10 сообщений
   - Оценка размера (1 token ≈ 4 chars)
   - Предупреждение при >7000 токенов

3. **MCP:**
   - Асинхронные WebSocket
   - Timeout на операции
   - Кэширование не применяется (real-time данные)

### Ограничения

- **Telegram:** 4096 символов на сообщение
- **DeepSeek API:** 2000 max_tokens для ответа
- **RAG файлы:** 10KB максимум при чтении
- **Git diff:** 5KB максимум

## Зависимости

### Внешние сервисы
- Telegram Bot API
- DeepSeek API
- Yandex Tracker API
- Ollama (локально)

### Python пакеты
- python-telegram-bot: Telegram интеграция
- requests: HTTP запросы
- mcp: Model Context Protocol
- starlette + uvicorn: WebSocket серверы
- numpy: Векторные операции
- psutil: Системные метрики
- python-dotenv: Environment variables

## Будущие улучшения

1. **RAG:**
   - Поддержка PDF документов
   - Re-ranking результатов
   - Увеличение context window

2. **MCP:**
   - Authentication для серверов
   - Rate limiting
   - Metrics endpoint

3. **Bot:**
   - Multimodal inputs (изображения)
   - Voice messages
   - Streaming ответов

4. **Мониторинг:**
   - Prometheus metrics
   - Grafana dashboards
   - Alerting
