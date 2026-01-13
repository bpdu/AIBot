# 🚀 Quick Start Guide - PR Review System

Быстрая инструкция для запуска системы автоматического ревью PR.

## ⚡ Быстрый старт (5 минут)

### Шаг 1: Установка зависимостей

```bash
# Перейти в корень проекта
cd /path/to/AIBot

# Установить зависимости (если еще не установлены)
pip install -r requirements.txt numpy requests python-dotenv

# Установить Ollama (для embeddings)
curl -fsSL https://ollama.com/install.sh | sh
```

### Шаг 2: Запуск Ollama

```bash
# В отдельном терминале
ollama serve

# Установка модели
ollama pull nomic-embed-text
```

### Шаг 3: Индексация CODE_STYLE.md

```bash
# Создать embeddings
python rag/index_code_style.py

# Должно вывести:
# ✅ Indexing complete! XX chunks indexed
```

### Шаг 4: Настройка GitHub

#### A. Добавить секрет DEEPSEEK_API_KEY

1. Перейти в Settings → Secrets and variables → Actions
2. New repository secret
3. Name: `DEEPSEEK_API_KEY`
4. Value: ваш API ключ от https://platform.deepseek.com

#### B. Включить Workflows

1. Перейти в Actions
2. Включить workflows для репозитория

### Шаг 5: Создать тестовый PR

```bash
# Создать тестовую ветку
git checkout -b test/pr-review

# Сделать изменения (например, добавить функцию без docstring)
echo "def test_function(a, b):
    return a + b" >> test_file.py

# Закоммитить
git add test_file.py
git commit -m "test: Add test function"

# Запушить
git push origin test/pr-review

# Создать PR через GitHub UI
```

### Шаг 6: Проверить результат

1. Открыть PR на GitHub
2. Перейти в Actions → посмотреть запущенный workflow "AI Code Review"
3. Дождаться завершения (1-2 минуты)
4. В PR появится комментарий с ревью

## 🧪 Локальное тестирование (без GitHub Actions)

### Terminal 1: MCP Server

```bash
python assistant/git_mcp_server.py
```

### Terminal 2: Ollama

```bash
ollama serve
```

### Terminal 3: Ревью (для текущей ветки)

```bash
# Настроить environment
export GITHUB_TOKEN="ghp_your_token_here"
export DEEPSEEK_API_KEY="sk-your_key_here"
export GITHUB_REPOSITORY="username/AIBot"
export PR_NUMBER=1  # Номер существующего PR
export PR_BASE="main"
export PR_HEAD="feature/your-branch"

# Запустить ревью
python assistant/pr_review/review_orchestrator.py
```

## 🔍 Проверка компонентов

### 1. Проверка RAG

```bash
python assistant/pr_review/rag_code_style.py
```

Вывод:
```
Query: function without docstring
Found 3 rules:
  1. Документация / Docstrings (similarity: 0.782)
  2. Форматирование / Функции (similarity: 0.654)
  ...
```

### 2. Проверка MCP Client

```bash
python assistant/pr_review/mcp_client.py
```

Вывод:
```
=== Test 1: Current branch ===
Current branch: main

=== Test 2: Git status ===
Status: {'success': True, ...}
```

### 3. Проверка DeepSeek

```bash
python assistant/pr_review/deepseek_reviewer.py
```

Вывод:
```
=== GENERATED REVIEW ===
## ✅ Положительные моменты
...
```

### 4. Проверка GitHub API

```bash
python assistant/pr_review/github_api.py
```

Вывод:
```
=== Rate Limit ===
Remaining: 4998/5000

=== PR #1 Details ===
Title: Add new feature
...
```

## 📋 Checklist перед первым PR

- [ ] Ollama установлен и запущен (`ollama list`)
- [ ] CODE_STYLE.md проиндексирован (`ls -lh rag/db.sqlite3`)
- [ ] DEEPSEEK_API_KEY добавлен в GitHub Secrets
- [ ] Workflows включены в Settings → Actions
- [ ] Git MCP Server запускается без ошибок
- [ ] Все компоненты тестируются успешно

## ⚠️ Частые проблемы

### Проблема: Workflow не запускается

**Решение:**
- Проверить что workflow файл в `.github/workflows/pr_review.yml`
- Проверить что workflows включены в Settings → Actions
- Проверить что PR создан в правильную ветку (main/master)

### Проблема: "No code_style embeddings found"

**Решение:**
```bash
# Переиндексировать
python rag/index_code_style.py

# Проверить что БД создалась
ls -lh rag/db.sqlite3

# Должно быть ~100-200 KB
```

### Проблема: "DeepSeek API key not configured"

**Решение:**
```bash
# Проверить локально
echo $DEEPSEEK_API_KEY

# Проверить в GitHub
Settings → Secrets → DEEPSEEK_API_KEY должен быть
```

### Проблема: "MCP Server connection timeout"

**Решение:**
```bash
# Проверить что сервер запустился
curl http://localhost:8082/

# Посмотреть порт
netstat -tulpn | grep 8082

# Перезапустить
pkill -f git_mcp_server
python assistant/git_mcp_server.py
```

## 📚 Дополнительные ресурсы

- [README.md](./README.md) - Полная документация
- [../../docs/OLLAMA_SETUP.md](../../docs/OLLAMA_SETUP.md) - Настройка Ollama
- [../../CODE_STYLE.md](../../CODE_STYLE.md) - Правила стиля
- [Plan file](../../../.claude/plans/lively-roaming-spring.md) - Детальный план реализации

## 💬 Помощь

Если что-то не работает:
1. Проверить логи workflow в Actions
2. Запустить компоненты локально для debugging
3. Посмотреть Troubleshooting в README.md
4. Проверить что все environment variables установлены

---

**Готово!** 🎉 Теперь каждый PR будет автоматически ревьюиться AI ассистентом.
