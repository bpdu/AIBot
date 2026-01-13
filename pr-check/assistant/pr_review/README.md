# 🤖 Automated PR Code Review System

**День 21 AI Advent Calendar**: Автоматизация ревью кода с использованием RAG, MCP и DeepSeek API.

## 📋 Описание

Система автоматического ревью Pull Requests, которая:
- ✅ Использует **RAG** (Retrieval-Augmented Generation) для поиска релевантных правил из [CODE_STYLE.md](../../CODE_STYLE.md)
- ✅ Получает diff и файлы через **MCP Server** (Model Context Protocol)
- ✅ Генерирует интеллектуальное ревью с помощью **DeepSeek API**
- ✅ Публикует результаты как комментарий в **GitHub PR**

## 🏗️ Архитектура

```
GitHub PR Event
    ↓
GitHub Actions Workflow
    ↓
review_orchestrator.py
    ├── mcp_client.py → Git MCP Server → Git операции
    ├── rag_code_style.py → Ollama → CODE_STYLE.md embeddings
    ├── deepseek_reviewer.py → DeepSeek API → Генерация ревью
    └── github_api.py → GitHub API → Публикация комментария
```

## 📦 Компоненты

### 1. **Git MCP Server Extension** ([../git_mcp_server.py](../git_mcp_server.py))
Расширенный MCP Server с новым инструментом:
- `get-pr-diff` - получение diff между ветками для PR review

### 2. **RAG System** ([rag_code_style.py](./rag_code_style.py))
- Индексация CODE_STYLE.md с chunking по секциям (800 chars)
- Hybrid filtering (strict 0.50 + adaptive 85%)
- Top-K = 5 для достаточного контекста

### 3. **MCP WebSocket Client** ([mcp_client.py](./mcp_client.py))
- Async клиент для Git MCP Server
- Retry logic с exponential backoff
- Graceful error handling

### 4. **DeepSeek Review Generator** ([deepseek_reviewer.py](./deepseek_reviewer.py))
- Structured prompting (system + user messages)
- Temperature 0.3 для consistency
- Max tokens 3000 для детального ревью

### 5. **GitHub API Integration** ([github_api.py](./github_api.py))
- Публикация review с event типами: APPROVE, REQUEST_CHANGES, COMMENT
- Rate limit checking
- Error handling

### 6. **Review Orchestrator** ([review_orchestrator.py](./review_orchestrator.py))
- Главный координатор всех компонентов
- Обработка edge cases
- Comprehensive logging

## 🚀 Установка и настройка

### 1. Установка зависимостей

```bash
# Основные зависимости (уже должны быть установлены)
pip install -r requirements.txt

# Дополнительно для PR review
pip install numpy requests python-dotenv
```

### 2. Установка Ollama (для embeddings)

```bash
# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh

# Запуск
ollama serve

# Установка модели для embeddings
ollama pull nomic-embed-text
```

См. подробную инструкцию: [docs/OLLAMA_SETUP.md](../../docs/OLLAMA_SETUP.md)

### 3. Индексация CODE_STYLE.md

```bash
# Создать embeddings для CODE_STYLE.md
python rag/index_code_style.py
```

Это создаст `rag/db.sqlite3` с embeddings всех правил стиля.

### 4. GitHub Secrets

Добавьте в Settings → Secrets and variables → Actions:

- `DEEPSEEK_API_KEY` - ваш API ключ от DeepSeek

`GITHUB_TOKEN` предоставляется автоматически GitHub Actions.

## 🎯 Использование

### Автоматическое ревью в CI

После настройки, система автоматически запускается при:
- Создании PR (`opened`)
- Обновлении PR (`synchronize`)
- Переоткрытии PR (`reopened`)

Workflow: [.github/workflows/pr_review.yml](../../.github/workflows/pr_review.yml)

### Локальное тестирование

#### 1. Запустить MCP Server

```bash
# В одном терминале
python assistant/git_mcp_server.py
```

#### 2. Запустить Ollama

```bash
# В другом терминале
ollama serve
```

#### 3. Запустить ревью

```bash
# Установить environment variables
export GITHUB_TOKEN="your_github_token"
export DEEPSEEK_API_KEY="your_deepseek_key"
export GITHUB_REPOSITORY="owner/repo"
export PR_NUMBER=123
export PR_BASE="main"
export PR_HEAD="feature/branch"

# Запустить
python assistant/pr_review/review_orchestrator.py
```

## 🧪 Тестирование компонентов

### Тест 1: RAG поиск правил

```bash
python assistant/pr_review/rag_code_style.py
```

Выводит результаты поиска для тестовых запросов.

### Тест 2: MCP Client

```bash
python assistant/pr_review/mcp_client.py
```

Тестирует подключение к MCP Server и все tools.

### Тест 3: DeepSeek Reviewer

```bash
# Требуется DEEPSEEK_API_KEY
python assistant/pr_review/deepseek_reviewer.py
```

Генерирует тестовое ревью.

### Тест 4: GitHub API

```bash
# Требуется GITHUB_TOKEN и GITHUB_REPOSITORY
python assistant/pr_review/github_api.py
```

Проверяет rate limit и получение PR информации.

## ⚙️ Конфигурация

Все параметры в [config.py](./config.py):

```python
# MCP Server
MCP_GIT_SERVER_URL = "ws://localhost:8082/mcp"
MCP_CONNECTION_TIMEOUT = 30

# RAG System
RAG_TOP_K = 5
RAG_MIN_SIMILARITY = 0.3
RAG_FILTERING_MODE = "hybrid"
RAG_CHUNK_SIZE = 800

# DeepSeek API
REVIEW_TEMPERATURE = 0.3
REVIEW_MAX_TOKENS = 3000

# Constraints
MAX_FILES_TO_REVIEW = 20
MAX_DIFF_SIZE_CHARS = 50000
SUPPORTED_FILE_EXTENSIONS = [".py"]
```

## 📊 Метрики успеха

**Технические:**
- ⏱️ Latency < 2 минуты для PR до 10 файлов
- 📊 Coverage 80%+ Python кода
- 🎯 RAG relevance 70%+ (правильные правила)
- ✅ False positive rate < 20%

**Бизнес:**
- ✨ Улучшение соблюдения CODE_STYLE.md
- ⚡ Ускорение ручного ревью
- 🐛 Раннее выявление проблем
- 📚 Обучение команды через комментарии

## 🐛 Troubleshooting

### Ошибка: "MCP Server connection timeout"

**Решение:**
```bash
# Проверить что MCP Server запущен
curl http://localhost:8082/

# Посмотреть логи
tail -f mcp_server.log
```

### Ошибка: "Ollama connection error"

**Решение:**
```bash
# Проверить что Ollama запущен
curl http://localhost:11434/api/tags

# Перезапустить
ollama serve
```

### Ошибка: "No code_style embeddings found"

**Решение:**
```bash
# Переиндексировать CODE_STYLE.md
python rag/index_code_style.py

# Проверить БД
ls -lh rag/db.sqlite3
```

### Ошибка: "GitHub API rate limit exceeded"

**Решение:**
- Подождать до reset времени (показывается в логах)
- Использовать authenticated token (5000 requests/hour vs 60)

## 📝 Примеры ревью

### Пример 1: APPROVED

```markdown
## ✅ Положительные моменты
- Код соответствует PEP 8
- Все функции имеют docstrings
- Type hints добавлены корректно

## 📊 Итого
Общая оценка: APPROVED

Код соответствует всем стандартам проекта.
```

### Пример 2: REQUEST_CHANGES

```markdown
## ✅ Положительные моменты
- Хорошая структура кода
- Понятные имена переменных

## ⚠️ Замечания

### Критические
- [bot.py:123] Отсутствует docstring для функции `calculate_sum`
  **Правило:** "Docstring обязательны для всех публичных функций" (CODE_STYLE.md, строка 158)
  **Рекомендация:** Добавить docstring в формате Google Style

## 📊 Итого
Общая оценка: CHANGES_REQUESTED

Необходимо добавить docstrings перед merge.
```

## 🔗 Связанные файлы

- [CODE_STYLE.md](../../CODE_STYLE.md) - Правила стиля для проекта
- [ARCHITECTURE.md](../../ARCHITECTURE.md) - Архитектура AIBot
- [docs/EMBEDDINGS_GUIDE.md](../../docs/EMBEDDINGS_GUIDE.md) - Руководство по RAG

## 🤝 Вклад

Для улучшения системы:
1. Добавьте больше правил в CODE_STYLE.md
2. Улучшите промпты в deepseek_reviewer.py
3. Настройте RAG параметры в config.py
4. Добавьте поддержку других языков

## 📄 Лицензия

Часть проекта AIBot - AI Advent Calendar Day 21
