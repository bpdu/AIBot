# 🔧 Integration Guide - PR-Check

Инструкция по интеграции системы PR-Check в существующий проект.

## 📋 Варианты интеграции

### Вариант 1: Полная интеграция (Рекомендуется)

Копирование файлов в структуру основного проекта.

#### Шаг 1: Копирование файлов

```bash
# Из папки pr-check в корень вашего проекта

# 1. Копировать модуль pr_review
cp -r pr-check/assistant/pr_review YOUR_PROJECT/assistant/

# 2. Копировать скрипт индексации
cp pr-check/rag/index_code_style.py YOUR_PROJECT/rag/

# 3. Копировать GitHub Actions workflow
mkdir -p YOUR_PROJECT/.github/workflows
cp pr-check/.github/workflows/pr_review.yml YOUR_PROJECT/.github/workflows/

# 4. Заменить MCP Server (или добавить get-pr-diff tool вручную)
cp pr-check/git_mcp_server.py YOUR_PROJECT/assistant/

# 5. Обновить requirements.txt
cat pr-check/requirements.txt >> YOUR_PROJECT/requirements.txt
```

#### Шаг 2: Настройка

```bash
cd YOUR_PROJECT

# Установить зависимости
pip install -r requirements.txt

# Установить Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull nomic-embed-text

# Создать embeddings
python rag/index_code_style.py
```

#### Шаг 3: GitHub Secrets

Добавьте в **Settings → Secrets and variables → Actions**:
- `DEEPSEEK_API_KEY` - ваш API ключ

#### Шаг 4: Готово!

Создайте тестовый PR и проверьте работу системы.

---

### Вариант 2: Standalone использование

Использование pr-check как отдельного инструмента.

#### Структура:
```
YOUR_PROJECT/
├── ... (ваш код)
├── CODE_STYLE.md
└── pr-check/
    ├── assistant/
    ├── rag/
    └── ...
```

#### Настройка путей:

Отредактируйте `pr-check/assistant/pr_review/config.py`:

```python
# Изменить PROJECT_ROOT на ваш проект
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # Выйти из pr-check
CODE_STYLE_PATH = PROJECT_ROOT / "CODE_STYLE.md"
RAG_DB_PATH = PROJECT_ROOT / "pr-check" / "rag" / "db.sqlite3"
```

#### Запуск:

```bash
cd pr-check

# Индексация
python rag/index_code_style.py

# MCP Server
python git_mcp_server.py &

# Review
export GITHUB_TOKEN="..."
export DEEPSEEK_API_KEY="..."
export GITHUB_REPOSITORY="owner/repo"
export PR_NUMBER=1
export PR_BASE="main"
export PR_HEAD="feature/branch"

python assistant/pr_review/review_orchestrator.py
```

---

### Вариант 3: Docker контейнер

Запуск всей системы в Docker.

#### Dockerfile:

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Set working directory
WORKDIR /app

# Copy pr-check
COPY pr-check/ /app/
COPY CODE_STYLE.md /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create embeddings at build time
RUN ollama serve & sleep 5 && \
    ollama pull nomic-embed-text && \
    python rag/index_code_style.py

# Expose MCP Server port
EXPOSE 8082

# Start script
CMD ["python", "assistant/pr_review/review_orchestrator.py"]
```

#### docker-compose.yml:

```yaml
version: '3.8'

services:
  pr-check:
    build: .
    ports:
      - "8082:8082"
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - GITHUB_REPOSITORY=${GITHUB_REPOSITORY}
      - PR_NUMBER=${PR_NUMBER}
      - PR_BASE=${PR_BASE}
      - PR_HEAD=${PR_HEAD}
    volumes:
      - ./CODE_STYLE.md:/app/CODE_STYLE.md:ro
```

---

## 🔍 Проверка интеграции

### Checklist:

- [ ] Файлы скопированы в правильные места
- [ ] `requirements.txt` обновлен
- [ ] Ollama установлен и запущен (`ollama list`)
- [ ] CODE_STYLE.md проиндексирован (`ls -lh rag/db.sqlite3`)
- [ ] DEEPSEEK_API_KEY добавлен в GitHub Secrets
- [ ] GitHub Actions workflow на месте (`.github/workflows/pr_review.yml`)
- [ ] MCP Server имеет tool `get-pr-diff`

### Тестирование компонентов:

```bash
# 1. RAG
python assistant/pr_review/rag_code_style.py
# Ожидается: вывод тестовых запросов с найденными правилами

# 2. MCP Client (требуется запущенный MCP Server)
python assistant/pr_review/mcp_client.py
# Ожидается: информация о текущей ветке, статусе, etc.

# 3. DeepSeek (требуется API key)
export DEEPSEEK_API_KEY="sk-..."
python assistant/pr_review/deepseek_reviewer.py
# Ожидается: сгенерированное тестовое ревью

# 4. GitHub API (требуется token)
export GITHUB_TOKEN="ghp_..."
export GITHUB_REPOSITORY="owner/repo"
python assistant/pr_review/github_api.py
# Ожидается: rate limit info
```

### Создание тестового PR:

```bash
# Создать ветку с нарушением стиля
git checkout -b test/pr-review

# Добавить код без docstring
cat << 'EOF' > test_review.py
def calculate(a, b):
    return a + b
EOF

git add test_review.py
git commit -m "test: Add function for PR review test"
git push origin test/pr-review

# Создать PR через GitHub UI
# Проверить что workflow запустился в Actions
# Дождаться комментария с ревью
```

---

## 🎯 Настройка под ваш проект

### 1. Адаптация CODE_STYLE.md

Убедитесь что ваш `CODE_STYLE.md`:
- Структурирован с заголовками (`#`, `##`, `###`)
- Содержит конкретные правила с примерами
- Имеет размер не более 1MB (для эффективной индексации)

### 2. Настройка RAG параметров

В `config.py`:

```python
# Для строгого соответствия стилю
RAG_MIN_SIMILARITY = 0.4  # Увеличить порог

# Для более мягкого ревью
RAG_MIN_SIMILARITY = 0.2  # Снизить порог

# Количество правил в контексте
RAG_TOP_K = 5  # Увеличить для большего покрытия
```

### 3. Настройка промпта DeepSeek

В `deepseek_reviewer.py` отредактируйте `SYSTEM_PROMPT`:

```python
SYSTEM_PROMPT = """Ты — эксперт по code review для проекта YOUR_PROJECT.

ТВОЯ ЗАДАЧА:
1. Проверить код на соответствие CODE_STYLE.md
2. Найти потенциальные ошибки
3. Учитывать специфику проекта: [добавьте специфику]
...
"""
```

### 4. Фильтрация файлов

В `config.py` настройте поддерживаемые расширения:

```python
# Для Python проекта (по умолчанию)
SUPPORTED_FILE_EXTENSIONS = [".py"]

# Для JavaScript/TypeScript проекта
SUPPORTED_FILE_EXTENSIONS = [".js", ".ts", ".jsx", ".tsx"]

# Для мультиязычного проекта
SUPPORTED_FILE_EXTENSIONS = [".py", ".js", ".go", ".java"]
```

---

## 🚨 Troubleshooting

### Проблема: Workflow не запускается

**Причины:**
1. Workflow файл не в `.github/workflows/`
2. Workflows не включены (Settings → Actions)
3. PR создан не в ту ветку

**Решение:**
```bash
# Проверить файл
ls -la .github/workflows/pr_review.yml

# Проверить синтаксис
cat .github/workflows/pr_review.yml | head -20
```

### Проблема: Embeddings не создаются

**Причины:**
1. Ollama не запущен
2. CODE_STYLE.md не найден
3. Нет прав на запись в rag/db.sqlite3

**Решение:**
```bash
# Проверить Ollama
curl http://localhost:11434/api/tags

# Проверить CODE_STYLE.md
ls -lh CODE_STYLE.md

# Проверить права
ls -la rag/
mkdir -p rag/
chmod 755 rag/
```

### Проблема: MCP Server не подключается

**Причины:**
1. Сервер не запущен
2. Порт 8082 занят
3. Firewall блокирует подключение

**Решение:**
```bash
# Проверить процесс
ps aux | grep git_mcp_server

# Проверить порт
netstat -tulpn | grep 8082

# Перезапустить
pkill -f git_mcp_server
python git_mcp_server.py &
```

---

## 📚 Дополнительные ресурсы

- [README.md](./README.md) - Главная документация
- [assistant/pr_review/README.md](./assistant/pr_review/README.md) - Детальное описание
- [assistant/pr_review/QUICKSTART.md](./assistant/pr_review/QUICKSTART.md) - Быстрый старт

---

**Успешной интеграции!** 🚀

Если возникнут вопросы, проверьте логи в GitHub Actions или запустите компоненты локально для debugging.
