# Руководство по стилю кода AIBot

## Общие принципы

### PEP 8
Следуем [PEP 8](https://peps.python.org/pep-0008/) с некоторыми дополнениями.

### Философия кода
- **Читаемость важнее краткости**
- **Явное лучше неявного**
- **Простое лучше сложного**
- **Документация обязательна**

## Форматирование

### Отступы
- **4 пробела** (не табы)
- Продолжение строк: выравнивать с открывающим символом

```python
# Хорошо
result = some_function_that_takes_arguments(
    'a', 'b', 'c',
    'd', 'e', 'f'
)

# Плохо
result = some_function_that_takes_arguments('a', 'b', 'c',
'd', 'e', 'f')
```

### Длина строки
- **Максимум 100 символов** (не 79 как в PEP 8)
- Исключение: длинные URL, пути к файлам

### Импорты

**Порядок:**
1. Стандартная библиотека
2. Сторонние библиотеки
3. Локальные импорты

**Группировка:**
```python
# Стандартная библиотека
import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

# Сторонние библиотеки
import requests
import numpy as np
from telegram import Update
from telegram.ext import CommandHandler

# Локальные импорты
from retrieval import rag_query
from mcp_client import call_mcp_tool
```

**Правила:**
- Один импорт на строку для `import`
- Можно группировать для `from ... import`
- Абсолютные импорты предпочтительнее относительных

### Пробелы

**Вокруг операторов:**
```python
# Хорошо
x = 1
y = x + 1
result = x * 2 - 1 / 2

# Плохо
x=1
y = x+1
result = x*2 - 1/2
```

**В функциях:**
```python
# Хорошо
def func(a, b, c=None):
    return a + b

result = func(1, 2, c=3)

# Плохо
def func( a,b,c = None ):
    return a+b

result = func (1,2,c=3)
```

### Пустые строки
- **2 пустые строки** между top-level функциями и классами
- **1 пустая строка** между методами класса
- **1 пустая строка** для логического разделения внутри функции

## Именование

### Общие правила

| Тип | Стиль | Примеры |
|-----|-------|---------|
| Модули | lowercase_with_underscores | `retrieval.py`, `mcp_client.py` |
| Классы | PascalCase | `TrackerClient`, `RAGSystem` |
| Функции | lowercase_with_underscores | `get_tracker_tasks()`, `call_deepseek_api()` |
| Переменные | lowercase_with_underscores | `user_question`, `tasks_json` |
| Константы | UPPERCASE_WITH_UNDERSCORES | `DEEPSEEK_API_KEY`, `TOP_K` |
| Приватные | _leading_underscore | `_internal_function()`, `_cache` |

### Специфичные правила

**Бот команды:**
```python
def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    pass

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    pass
```

**MCP инструменты:**
```python
def get_tracker_tasks():
    """Получить задачи из Yandex Tracker API."""
    pass

def get_host_metrics():
    """Собрать метрики хоста (CPU, RAM, Disk)."""
    pass
```

**RAG функции:**
```python
def generate_query_embedding(query: str) -> List[float]:
    """Генерировать эмбеддинг для запроса пользователя."""
    pass

def search_relevant_chunks(query: str, top_k: int = TOP_K) -> List[Dict]:
    """Поиск релевантных чанков документации."""
    pass
```

## Документация

### Docstrings

**Формат:** Google Style

**Обязательны для:**
- Всех публичных функций
- Всех классов
- Всех модулей

**Модуль:**
```python
"""
MCP Server для работы с Git репозиторием.

День 20: Ассистент разработчика

WebSocket сервер для получения информации о git репозитории.
"""
```

**Функция:**
```python
def search_relevant_chunks(
    query: str,
    top_k: int = TOP_K,
    min_similarity: float = MIN_SIMILARITY_ORIGINAL,
    enable_filtering: bool = True
) -> Tuple[List[Dict], Dict]:
    """
    Поиск релевантных чанков документации по запросу.

    Args:
        query: Вопрос пользователя
        top_k: Количество результатов для возврата
        min_similarity: Минимальное косинусное сходство (по умолчанию: 0.3)
        enable_filtering: Применить фильтрацию второго этапа (по умолчанию: True)

    Returns:
        Кортеж из:
        - Список релевантных чанков с метаданными
        - Словарь статистики фильтрации

    Raises:
        ConnectionError: Если Ollama недоступна
    """
    pass
```

**Класс:**
```python
class TrackerClient:
    """
    Клиент для работы с Yandex Tracker API.

    Attributes:
        token: OAuth токен
        org_id: ID организации
        api_url: URL API endpoint
    """

    def __init__(self, token: str, org_id: str):
        """
        Инициализация клиента.

        Args:
            token: OAuth токен для Yandex Tracker
            org_id: ID организации в Yandex Tracker
        """
        pass
```

### Комментарии

**Когда писать:**
- Сложная бизнес-логика
- Неочевидные решения
- Временные workarounds
- TODO/FIXME

**Формат:**
```python
# Хорошо: объясняет "почему"
# Используем hybrid mode для баланса между precision и recall
chunks = search_relevant_chunks(query, filtering_mode="hybrid")

# Плохо: объясняет "что" (и так видно из кода)
# Вызываем функцию search_relevant_chunks
chunks = search_relevant_chunks(query)

# TODO для будущих улучшений
# TODO: Добавить кэширование embeddings
# FIXME: Обработать edge case с пустым query
```

## Type Hints

**Обязательны для:**
- Параметров функций
- Возвращаемых значений
- Атрибутов классов (если не очевидно)

**Примеры:**
```python
from typing import List, Dict, Tuple, Optional, Union

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Вычислить косинусное сходство."""
    pass

def call_deepseek_api(messages: List[Dict]) -> Tuple[str, Dict[str, int]]:
    """Вызвать DeepSeek API."""
    pass

def get_file_content(file_path: str) -> Optional[str]:
    """Получить содержимое файла."""
    pass

def handle_message(text: Union[str, None]) -> bool:
    """Обработать сообщение."""
    pass
```

## Обработка ошибок

### Try-Except блоки

**Специфичные исключения:**
```python
# Хорошо
try:
    result = json.loads(data)
except json.JSONDecodeError as e:
    logger.error(f"Failed to parse JSON: {e}")
    return None

# Плохо
try:
    result = json.loads(data)
except Exception:
    return None
```

**Логирование:**
```python
# Всегда логируем ошибки с traceback
try:
    dangerous_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise
```

**Цепочка исключений:**
```python
try:
    process_data()
except ValueError as e:
    raise RuntimeError("Failed to process data") from e
```

### Возврат ошибок

**JSON формат для API:**
```python
def get_tracker_tasks():
    """Получить задачи из Yandex Tracker API."""
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return json.dumps({"success": True, "tasks": response.json()})
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching tasks: {e}")
        return json.dumps({"success": False, "error": str(e)})
```

## Логирование

### Настройка

```python
import logging

# В начале модуля
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
```

### Уровни

| Уровень | Когда использовать |
|---------|-------------------|
| DEBUG | Детальная отладочная информация |
| INFO | Общий прогресс работы |
| WARNING | Неожиданные ситуации, не критичные |
| ERROR | Ошибки, требующие внимания |
| CRITICAL | Критические ошибки, требующие остановки |

### Примеры

```python
# INFO: Ключевые точки выполнения
logger.info("Starting MCP server on port 8080")
logger.info(f"Retrieved {len(tasks)} tasks from Tracker")

# WARNING: Неожиданное, но обработанное
logger.warning("No embeddings found in database")
logger.warning(f"Large query: {len(query)} characters")

# ERROR: Ошибки с traceback
logger.error(f"Error calling MCP tool: {e}", exc_info=True)
logger.error(f"Failed to parse JSON: {e}")
```

### Что НЕ логировать

- Секретные данные (токены, пароли)
- Полное содержимое больших файлов
- Личные данные пользователей

```python
# Хорошо
logger.info(f"Token present: {bool(TRACKER_TOKEN)}")
logger.info(f"Retrieved {len(content)} chars")

# Плохо
logger.info(f"Token: {TRACKER_TOKEN}")
logger.info(f"Content: {content}")
```

## Конфигурация

### Константы

**Определяются в начале модуля:**
```python
# API configuration
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'
MODEL_NAME = 'deepseek-chat'

# MCP configuration
MCP_SERVER_URL = "ws://localhost:8080/mcp"
MCP_SERVER2_URL = "ws://localhost:8081/mcp"

# RAG configuration
DB_PATH = Path(__file__).parent / "db.sqlite3"
OLLAMA_API_URL = "http://127.0.0.1:11434/api/embeddings"
TOP_K = 3
MIN_SIMILARITY_STRICT = 0.50
```

### Environment Variables

```python
from dotenv import load_dotenv
import os

# Загрузка из файла
load_dotenv(dotenv_path='.secrets/bot-token.env')

# Получение с fallback
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found")
    exit(1)

# Опциональные переменные
TIMEOUT = int(os.getenv('API_TIMEOUT', '30'))
```

## Структура функций

### Порядок элементов

1. Docstring
2. Валидация входных данных
3. Инициализация переменных
4. Основная логика
5. Обработка ошибок
6. Возврат результата

**Пример:**
```python
def search_relevant_chunks(
    query: str,
    top_k: int = TOP_K
) -> List[Dict]:
    """
    Поиск релевантных чанков документации.

    Args:
        query: Вопрос пользователя
        top_k: Количество результатов

    Returns:
        Список релевантных чанков
    """
    # 1. Валидация
    if not query or not query.strip():
        logger.warning("Empty query provided")
        return []

    if top_k < 1:
        raise ValueError("top_k must be positive")

    # 2. Инициализация
    logger.info(f"Searching for: '{query}'")
    similarities = []

    # 3. Основная логика
    try:
        query_embedding = generate_query_embedding(query)
        similarities = calculate_similarities(query_embedding)
        filtered = filter_results(similarities)
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return []

    # 4. Возврат
    return filtered[:top_k]
```

### Размер функций

- **Максимум 50-100 строк**
- Если больше - разбить на вспомогательные функции
- Одна функция - одна ответственность

## Async/Await

### Когда использовать

- WebSocket обработчики (MCP серверы)
- Множественные I/O операции
- Интеграция с async библиотеками

### Правила

```python
# Async функции всегда с await
async def fetch_data():
    response = await client.get(url)  # Хорошо
    return response

# Не блокировать async функции
async def process():
    # Плохо - блокирующая операция
    time.sleep(5)

    # Хорошо - асинхронная операция
    await asyncio.sleep(5)

# Sync обертки для async кода
def sync_wrapper():
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(async_function())
    finally:
        loop.close()
```

## Тестирование

### Структура тестов

```python
def test_function_name():
    """Test description."""
    # Arrange
    input_data = "test"
    expected_output = "result"

    # Act
    actual_output = function_to_test(input_data)

    # Assert
    assert actual_output == expected_output
```

### Что тестировать

- **Обязательно:**
  - RAG retrieval
  - Keyword detection
  - Token counting
  - MCP tool calls

- **Опционально:**
  - UI handlers (Telegram)
  - API clients (внешние сервисы)

### Тестовые файлы

```
test_tokens.py       # Token usage tests
test_compression.py  # History compression tests
test_embeddings.py   # RAG system tests
mcp_client.py        # MCP integration tests
```

## Git

### Commit messages

**Формат:**
```
<type>: <subject>

<body>

<footer>
```

**Types:**
- `feat`: Новая функциональность
- `fix`: Исправление бага
- `docs`: Документация
- `style`: Форматирование кода
- `refactor`: Рефакторинг
- `test`: Тесты
- `chore`: Обслуживание

**Примеры:**
```
feat: Add Git MCP server for repository integration

Implements WebSocket server with 6 tools:
- get-current-branch
- get-git-status
- get-recent-commits
- get-changed-files
- get-file-content
- get-git-diff

Fixes #20
```

```
fix: Handle empty query in RAG search

Return empty list instead of raising exception when
query is None or empty string.
```

### Branch naming

```
feature/git-mcp-server
bugfix/rag-empty-query
docs/update-architecture
```

## Безопасность

### Секреты

```python
# НИКОГДА не коммитить секреты
# Плохо
TOKEN = "abc123xyz"

# Хорошо
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# НИКОГДА не логировать секреты
# Плохо
logger.info(f"Using token: {TOKEN}")

# Хорошо
logger.info(f"Token present: {bool(TOKEN)}")
```

### Валидация входных данных

```python
def get_file_content(file_path: str) -> str:
    """Получить содержимое файла."""
    # Проверка пути
    full_path = REPO_PATH / file_path

    # Защита от path traversal
    if not full_path.resolve().is_relative_to(REPO_PATH.resolve()):
        raise ValueError("Invalid file path")

    # Проверка существования
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Ограничение размера
    if full_path.stat().st_size > 10 * 1024:  # 10KB
        raise ValueError("File too large")

    return full_path.read_text()
```

## Производительность

### Оптимизация

```python
# Хорошо: генератор для больших данных
def process_large_file(file_path):
    with open(file_path) as f:
        for line in f:
            yield process_line(line)

# Плохо: загрузка всего файла в память
def process_large_file(file_path):
    with open(file_path) as f:
        lines = f.readlines()
    return [process_line(line) for line in lines]

# Хорошо: list comprehension
squares = [x * x for x in range(100)]

# Плохо: loop
squares = []
for x in range(100):
    squares.append(x * x)
```

### Кэширование

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_computation(n: int) -> int:
    """Дорогая функция с кэшированием."""
    return sum(range(n))
```

## Cheat Sheet

### Быстрая проверка кода

- [ ] Docstring для всех публичных функций
- [ ] Type hints для параметров и возвратов
- [ ] Логирование ошибок с exc_info=True
- [ ] Обработка специфичных исключений
- [ ] Константы в UPPER_CASE
- [ ] Функции не больше 100 строк
- [ ] Импорты сгруппированы правильно
- [ ] Нет секретов в коде
- [ ] Валидация входных данных
- [ ] Тесты для критичной логики
