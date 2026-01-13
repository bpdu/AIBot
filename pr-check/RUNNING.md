# 🚀 Running PR-Check - Complete Guide

## 🎯 Выбор сценария

### Сценарий 1: Быстрый тест компонентов (5 минут)
Для проверки что все работает.

### Сценарий 2: Полный локальный review (10 минут)
Для тестирования review на реальном PR.

### Сценарий 3: Production в GitHub Actions (настройка 15 минут)
Для автоматического review всех PR.

---

## 🎯 Сценарий 1: Быстрый тест компонентов

### Автоматический запуск (Linux/Mac):

```bash
cd /path/to/AIBot/pr-check
chmod +x run_local_test.sh
./run_local_test.sh
```

Скрипт автоматически:
- ✅ Проверит Python и зависимости
- ✅ Запустит Ollama
- ✅ Создаст embeddings
- ✅ Запустит MCP Server
- ✅ Протестирует все компоненты

### Ручной запуск (Windows/любая ОС):

#### 1. Установка зависимостей

```bash
cd /path/to/AIBot/pr-check
pip install -r requirements.txt
```

#### 2. Запуск Ollama

**Terminal 1:**
```bash
# Установка (если не установлен)
curl -fsSL https://ollama.com/install.sh | sh

# Запуск
ollama serve

# В другом терминале: установить модель
ollama pull nomic-embed-text
```

#### 3. Индексация CODE_STYLE.md

**Terminal 2:**
```bash
cd /path/to/AIBot
python pr-check/rag/index_code_style.py
```

Ожидаемый вывод:
```
Starting CODE_STYLE.md indexing...
Reading /path/to/AIBot/CODE_STYLE.md
File size: XXXXX chars, XXX lines
Chunking document...
Created XX chunks
✅ Indexing complete! XX chunks indexed
```

#### 4. Запуск MCP Server

**Terminal 3:**
```bash
cd /path/to/AIBot
python pr-check/git_mcp_server.py
```

Ожидаемый вывод:
```
INFO:__main__:Starting Git MCP Server on port 8082
INFO:uvicorn:Uvicorn running on http://0.0.0.0:8082
```

#### 5. Тестирование компонентов

**Terminal 4:**

Тест RAG:
```bash
cd /path/to/AIBot
python pr-check/assistant/pr_review/rag_code_style.py
```

Ожидаемый вывод:
```
================================================================================
Query: function without docstring
================================================================================
Searching CODE_STYLE rules for: 'function without docstring'...
Loaded 45 embeddings from database
Found 5 rules above similarity 0.3
Returning 3 rules after filtering

  1. Документация / Docstrings (similarity: 0.782, lines: 154-200)
  2. Форматирование / Функции (similarity: 0.654, lines: 85-103)
  ...
```

Тест MCP Client:
```bash
python pr-check/assistant/pr_review/mcp_client.py
```

Ожидаемый вывод:
```
=== Test 1: Current branch ===
Current branch: main

=== Test 2: Git status ===
Status: {'success': True, 'output': '...'}

=== Test 3: Changed files ===
Changed files: [...]
```

#### 6. Проверка что все работает

```bash
# Проверка Ollama
curl http://localhost:11434/api/tags

# Проверка MCP Server
curl http://localhost:8082/

# Проверка БД embeddings
ls -lh pr-check/rag/db.sqlite3
```

---

## 🎯 Сценарий 2: Полный локальный review

### Предварительные требования:

1. ✅ Ollama запущен (Terminal 1)
2. ✅ MCP Server запущен (Terminal 2)
3. ✅ Embeddings созданы
4. ✅ GitHub token получен
5. ✅ DeepSeek API key получен

### Получение токенов:

**GitHub Token:**
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token
3. Выбрать scopes: `repo`, `write:discussion`
4. Скопировать token (начинается с `ghp_`)

**DeepSeek API Key:**
1. https://platform.deepseek.com
2. API Keys → Create new key
3. Скопировать key (начинается с `sk-`)

### Настройка environment:

```bash
# В Terminal 3:
export GITHUB_TOKEN="ghp_ваш_токен_здесь"
export DEEPSEEK_API_KEY="sk-ваш_ключ_здесь"
export GITHUB_REPOSITORY="username/AIBot"
export PR_NUMBER=1
export PR_BASE="main"
export PR_HEAD="feature/test-branch"
```

### Запуск review:

```bash
cd /path/to/AIBot
python pr-check/assistant/pr_review/review_orchestrator.py
```

### Ожидаемый вывод:

```
================================================================================
Starting PR review: #1
Repository: username/AIBot
Branches: main...feature/test-branch
================================================================================

=== Phase 1: Configuration Validation ===
✅ Configuration valid

=== Phase 2: Fetching PR Details ===
✅ PR details: Add new feature

=== Phase 3: Fetching PR Diff via MCP ===
Connecting to MCP server at ws://localhost:8082/mcp
✅ Diff received: 150 lines, 4500 chars

=== Phase 4: Filtering Files ===
Total files changed: 3
Python files: 2

=== Phase 5: RAG Search for Style Rules ===
✅ Found 5 relevant rules
   1. Документация / Docstrings (similarity: 0.782)
   2. Type Hints (similarity: 0.721)
   ...

=== Phase 6: Generating Review with DeepSeek ===
✅ Review generated: 1250 chars
   Tokens: 450

=== Phase 7: Parsing Review Decision ===
✅ Decision: COMMENT

=== Phase 8: Publishing Review to GitHub ===
✅ Review published successfully (ID: 123456789)
   Event: COMMENT
   URL: https://github.com/username/AIBot/pull/1#pullrequestreview-123456789
```

### Очистка:

```bash
# Остановить MCP Server
kill $(cat /tmp/mcp_server.pid)

# Или найти процесс
ps aux | grep git_mcp_server
kill <PID>
```

---

## 🎯 Сценарий 3: Production (GitHub Actions)

### 1. Интеграция файлов

```bash
cd /path/to/AIBot

# Копировать модуль pr_review
cp -r pr-check/assistant/pr_review assistant/

# Копировать индексацию
cp pr-check/rag/index_code_style.py rag/

# Копировать workflow
mkdir -p .github/workflows
cp pr-check/.github/workflows/pr_review.yml .github/workflows/

# Обновить MCP Server (добавить get-pr-diff tool)
# Либо заменить полностью:
cp pr-check/git_mcp_server.py assistant/
```

### 2. Настройка GitHub Secrets

1. Открыть репозиторий на GitHub
2. **Settings** → **Secrets and variables** → **Actions**
3. **New repository secret**
4. Добавить:
   - Name: `DEEPSEEK_API_KEY`
   - Value: ваш ключ от DeepSeek

### 3. Включение Workflows

1. **Actions** tab
2. Если workflows отключены: **I understand my workflows, go ahead and enable them**

### 4. Создание тестового PR

```bash
# Создать ветку
git checkout -b test/pr-review-demo

# Создать файл с нарушениями стиля
cat << 'EOF' > test_for_review.py
def calculate(a,b):
    return a+b

def process_data(data):
    result=[]
    for item in data:
        result.append(item*2)
    return result

class MyClass:
    def method(self,x):
        return x
EOF

# Закоммитить
git add test_for_review.py
git commit -m "test: Add code for PR review demonstration"

# Запушить
git push origin test/pr-review-demo
```

### 5. Создать PR

1. GitHub → **Pull requests** → **New pull request**
2. Base: `main`, Compare: `test/pr-review-demo`
3. **Create pull request**
4. Добавить описание (опционально)
5. **Create pull request**

### 6. Проверить workflow

1. Перейти в **Actions** tab
2. Увидеть workflow "AI Code Review" в процессе
3. Кликнуть на workflow для просмотра логов
4. Ожидать ~2-3 минуты

### 7. Проверить результат

1. Вернуться в PR
2. Увидеть комментарий от бота с review
3. Комментарий будет содержать:
   - ✅ Положительные моменты
   - ⚠️ Замечания с указанием файла и строки
   - Ссылки на CODE_STYLE.md
   - 📊 Итоговую оценку

Пример комментария:
```markdown
# 🤖 Automated Code Review

## ⚠️ Замечания

### Критические
- [test_for_review.py:1] Нет пробелов вокруг операторов
  **Правило:** "Пробелы вокруг операторов обязательны" (CODE_STYLE.md)
  **Рекомендация:** `def calculate(a, b):`

- [test_for_review.py:1] Отсутствует docstring
  **Правило:** "Docstring обязательны для всех публичных функций"
  **Рекомендация:** Добавить docstring

## 📊 Итого
Общая оценка: REQUEST_CHANGES
```

---

## 🐛 Troubleshooting

### Проблема 1: "No module named 'mcp'"

**Решение:**
```bash
pip install mcp requests numpy python-dotenv starlette uvicorn
```

### Проблема 2: "Ollama connection error"

**Проверка:**
```bash
curl http://localhost:11434/api/tags
```

**Решение:**
```bash
# Запустить Ollama
ollama serve

# В другом терминале
ollama pull nomic-embed-text
```

### Проблема 3: "MCP Server connection timeout"

**Проверка:**
```bash
curl http://localhost:8082/
```

**Решение:**
```bash
# Проверить что сервер запущен
ps aux | grep git_mcp_server

# Перезапустить
pkill -f git_mcp_server
python pr-check/git_mcp_server.py
```

### Проблема 4: "No code_style embeddings found"

**Проверка:**
```bash
ls -lh pr-check/rag/db.sqlite3
```

**Решение:**
```bash
# Переиндексировать
python pr-check/rag/index_code_style.py
```

### Проблема 5: GitHub Actions не запускается

**Проверки:**
1. Workflow файл на месте: `.github/workflows/pr_review.yml`
2. Workflows включены: Settings → Actions → Allow all actions
3. PR создан в правильную ветку (main)

**Логи:**
- Actions → выбрать workflow → посмотреть детали

---

## 📊 Проверочный чек-лист

Перед запуском убедитесь:

- [ ] Python 3.11+ установлен
- [ ] Зависимости установлены (`pip list`)
- [ ] Ollama установлен и запущен (`ollama list`)
- [ ] nomic-embed-text модель загружена
- [ ] CODE_STYLE.md существует
- [ ] Embeddings созданы (`ls rag/db.sqlite3`)
- [ ] MCP Server запущен (порт 8082)
- [ ] Environment variables установлены (для локального теста)
- [ ] GitHub Secrets настроены (для Actions)

---

## 📚 Дополнительные ресурсы

- [README.md](./README.md) - Главная документация
- [QUICKSTART.md](./assistant/pr_review/QUICKSTART.md) - Быстрый старт
- [INTEGRATION.md](./INTEGRATION.md) - Интеграция в проект
- [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md) - Полное описание

---

**Успешного запуска!** 🚀
