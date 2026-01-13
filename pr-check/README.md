# 🤖 PR-Check: Automated Code Review System

**AI-powered Pull Request reviewer** using RAG, MCP, and DeepSeek API.

День 21 AI Advent Calendar - Автоматизация ревью кода.

## 🎯 Что это?

Система автоматического code review для Pull Requests, которая:
- ✅ Анализирует код на соответствие **CODE_STYLE.md**
- ✅ Использует **RAG** для поиска релевантных правил стиля
- ✅ Получает diff через **MCP Server** (Model Context Protocol)
- ✅ Генерирует интеллектуальное ревью через **DeepSeek API**
- ✅ Публикует результаты как комментарий в **GitHub PR**

## 📁 Структура проекта

```
pr-check/
├── assistant/
│   └── pr_review/          # Основной модуль ревью
│       ├── __init__.py
│       ├── config.py        # Конфигурация
│       ├── mcp_client.py    # WebSocket клиент для Git MCP
│       ├── rag_code_style.py      # RAG поиск правил
│       ├── deepseek_reviewer.py   # Генератор ревью
│       ├── github_api.py          # GitHub API интеграция
│       ├── review_orchestrator.py # Главный координатор
│       ├── README.md              # Детальная документация
│       └── QUICKSTART.md          # Быстрый старт
├── rag/
│   └── index_code_style.py  # Индексация CODE_STYLE.md
├── .github/
│   └── workflows/
│       └── pr_review.yml    # GitHub Actions CI
├── git_mcp_server.py        # Расширенный MCP Server (с get-pr-diff)
└── README.md                # Этот файл
```

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
# В корне проекта AIBot
pip install numpy requests python-dotenv

# Все остальные зависимости уже должны быть установлены
pip install -r ../requirements.txt
```

### 2. Установка Ollama (для embeddings)

```bash
# Linux/Mac
curl -fsSL https://ollama.com/install.sh | sh

# Запуск
ollama serve

# Установка модели
ollama pull nomic-embed-text
```

### 3. Индексация CODE_STYLE.md

```bash
# Создать embeddings (нужен CODE_STYLE.md в корне проекта AIBot)
python rag/index_code_style.py
```

### 4. Настройка GitHub Secrets

Добавьте в **Settings → Secrets and variables → Actions**:
- `DEEPSEEK_API_KEY` - ваш API ключ от https://platform.deepseek.com

### 5. Интеграция в ваш проект

#### Вариант A: Использовать как есть (в папке pr-check)

1. Скопируйте файлы:
   - `.github/workflows/pr_review.yml` → в ваш проект `.github/workflows/`
   - `assistant/pr_review/` → в ваш проект `assistant/`
   - `rag/index_code_style.py` → в ваш проект `rag/`
   - `git_mcp_server.py` → заменить ваш `assistant/git_mcp_server.py`

2. Убедитесь что в корне проекта есть `CODE_STYLE.md`

3. Готово! Создайте PR и система автоматически его проревьюит.

#### Вариант B: Запуск из папки pr-check

```bash
# Настроить пути в config.py
cd pr-check
export PROJECT_ROOT=/path/to/AIBot

# Запустить индексацию
python rag/index_code_style.py

# Запустить MCP Server
python git_mcp_server.py
```

## 🧪 Локальное тестирование

### Terminal 1: MCP Server
```bash
python git_mcp_server.py
```

### Terminal 2: Ollama
```bash
ollama serve
```

### Terminal 3: Тестирование компонентов
```bash
# Тест RAG
python assistant/pr_review/rag_code_style.py

# Тест MCP Client
python assistant/pr_review/mcp_client.py

# Тест DeepSeek (требуется DEEPSEEK_API_KEY)
export DEEPSEEK_API_KEY="sk-..."
python assistant/pr_review/deepseek_reviewer.py

# Тест GitHub API (требуется GITHUB_TOKEN)
export GITHUB_TOKEN="ghp_..."
export GITHUB_REPOSITORY="username/repo"
python assistant/pr_review/github_api.py
```

### Full review test
```bash
export GITHUB_TOKEN="ghp_..."
export DEEPSEEK_API_KEY="sk-..."
export GITHUB_REPOSITORY="username/AIBot"
export PR_NUMBER=1
export PR_BASE="main"
export PR_HEAD="feature/branch"

python assistant/pr_review/review_orchestrator.py
```

## 🏗️ Архитектура

```
GitHub PR Event
    ↓
GitHub Actions Workflow
    ↓
review_orchestrator.py
    ├── mcp_client.py → Git MCP Server → get-pr-diff
    ├── rag_code_style.py → Ollama → CODE_STYLE embeddings
    ├── deepseek_reviewer.py → DeepSeek API → Review text
    └── github_api.py → GitHub API → Post comment
```

## 📊 Технологии

- **RAG (Retrieval-Augmented Generation)**
  - Ollama nomic-embed-text для embeddings
  - SQLite для хранения vectors
  - Hybrid filtering (strict 0.50 + adaptive 85%)
  - Top-K = 5 для достаточного контекста

- **MCP (Model Context Protocol)**
  - WebSocket сервер для Git операций
  - Новый tool: `get-pr-diff` для сравнения веток
  - Async client с retry logic

- **DeepSeek API**
  - Structured prompting (system + user)
  - Temperature 0.3 для consistency
  - Max tokens 3000 для детального ревью
  - Parsing решения: APPROVE/REQUEST_CHANGES/COMMENT

- **GitHub Actions**
  - Автоматический запуск на PR events
  - Caching embeddings по hash CODE_STYLE.md
  - Background MCP server с health checks

## 📝 Примеры использования

### Пример ревью с APPROVE
```markdown
## ✅ Положительные моменты
- Код соответствует PEP 8
- Все функции имеют docstrings
- Type hints добавлены корректно

## 📊 Итого
Общая оценка: APPROVED

Код соответствует всем стандартам проекта.
```

### Пример ревью с REQUEST_CHANGES
```markdown
## ⚠️ Замечания

### Критические
- [bot.py:123] Отсутствует docstring
  **Правило:** "Docstring обязательны для всех публичных функций"
  **Рекомендация:** Добавить docstring в формате Google Style

## 📊 Итого
Общая оценка: CHANGES_REQUESTED
```

## ⚙️ Конфигурация

Все параметры в [assistant/pr_review/config.py](assistant/pr_review/config.py):

```python
# MCP Server
MCP_GIT_SERVER_URL = "ws://localhost:8082/mcp"

# RAG
RAG_TOP_K = 5
RAG_MIN_SIMILARITY = 0.3
RAG_CHUNK_SIZE = 800

# DeepSeek
REVIEW_TEMPERATURE = 0.3
REVIEW_MAX_TOKENS = 3000

# Constraints
MAX_FILES_TO_REVIEW = 20
SUPPORTED_FILE_EXTENSIONS = [".py"]
```

## 🐛 Troubleshooting

### "MCP Server connection timeout"
```bash
# Проверить что сервер запущен
curl http://localhost:8082/

# Перезапустить
python git_mcp_server.py
```

### "No code_style embeddings found"
```bash
# Переиндексировать
python rag/index_code_style.py

# Проверить БД
ls -lh rag/db.sqlite3
```

### "Ollama connection error"
```bash
# Проверить
curl http://localhost:11434/api/tags

# Перезапустить
ollama serve
```

## 📚 Документация

- **[assistant/pr_review/README.md](assistant/pr_review/README.md)** - Полная документация
- **[assistant/pr_review/QUICKSTART.md](assistant/pr_review/QUICKSTART.md)** - Быстрый старт
- **[.github/workflows/pr_review.yml](.github/workflows/pr_review.yml)** - CI workflow

## 🎓 Как это работает?

1. **PR создается** → GitHub Actions запускает workflow
2. **Setup** → Установка Python, Ollama, индексация CODE_STYLE.md
3. **MCP Server** → Запускается Git MCP Server для получения diff
4. **RAG Search** → Поиск релевантных правил из CODE_STYLE.md
5. **DeepSeek API** → Генерация интеллектуального ревью
6. **GitHub API** → Публикация комментария в PR

## 🔐 Требования

- Python 3.11+
- Ollama (для embeddings)
- DeepSeek API key
- GitHub token (предоставляется автоматически в Actions)
- CODE_STYLE.md в корне проекта

## 📦 Зависимости

```
mcp
requests
numpy
python-dotenv
starlette
uvicorn
```

## 🤝 Вклад

Для улучшения системы:
1. Добавьте больше правил в CODE_STYLE.md
2. Улучшите промпты в deepseek_reviewer.py
3. Настройте RAG параметры в config.py
4. Добавьте поддержку других языков программирования

## 📄 Лицензия

Часть проекта AIBot - AI Advent Calendar Day 21

---

**Made with ❤️ using AI technologies**

RAG + MCP + DeepSeek API = Intelligent Code Review 🚀
