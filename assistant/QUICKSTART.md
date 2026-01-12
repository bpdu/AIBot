# Быстрый старт - Ассистент разработчика

**5 минут до запуска!**

## ⚡ Быстрая установка

### 1. Установить зависимости (1 мин)

```bash
cd ..
pip install -r requirements.txt
```

### 2. Настроить Ollama (2 мин)

```bash
# Скачать и установить Ollama
# Windows: https://ollama.com/download
# Linux/Mac: curl -fsSL https://ollama.com/install.sh | sh

# Загрузить модель
ollama pull nomic-embed-text
```

### 3. Создать embeddings (2 мин)

```bash
cd assistant
python create-project-docs-embeddings.py
```

**Вывод:**
```
✓ Indexing complete!
  Documents indexed: 3
  Total chunks: 45
```

## 🚀 Запуск

### Терминал 1: Git MCP Server

```bash
cd assistant
python git_mcp_server.py
```

**Порт:** 8082

### Терминал 2: Демонстрация

```bash
cd assistant
python demo_developer_assistant.py
```

## ✅ Проверка

### Тест 1: Git MCP

```bash
curl http://localhost:8082/
```

**Ожидается:**
```json
{
  "name": "Git MCP Server",
  "version": "1.0.0",
  "tools": 6
}
```

### Тест 2: RAG

```bash
python project_docs_retrieval.py
```

**Ожидается:** 5 тестовых запросов с результатами

### Тест 3: Demo

```bash
python demo_developer_assistant.py
```

**Нажимайте Enter** для прохождения тестов

## 🤖 Интеграция с ботом

### В bot.py уже интегрировано!

Просто запустите бота:

```bash
cd ..
python bot.py
```

### В Telegram:

```
/help
/help как добавить MCP сервер
/help правила стиля кода
```

## 🎥 Для видео

### Запись демонстрации:

1. **Запустить Git MCP** (показать вывод)
   ```bash
   python git_mcp_server.py
   ```

2. **Запустить Demo** (показать тесты)
   ```bash
   python demo_developer_assistant.py
   ```

3. **Открыть Telegram** (показать команды)
   ```
   /help
   /help как работает RAG
   ```

## ❓ Проблемы?

### Ollama не отвечает
```bash
ollama list
# Перезапустить Ollama
```

### База данных не создана
```bash
python create-project-docs-embeddings.py
```

### Git MCP недоступен
```bash
# Проверить порт
netstat -an | grep 8082

# Перезапустить
python git_mcp_server.py
```

## 📦 Файлы в папке

- `git_mcp_server.py` - MCP сервер (480 строк)
- `create-project-docs-embeddings.py` - Индексация (240 строк)
- `project_docs_retrieval.py` - RAG поиск (270 строк)
- `demo_developer_assistant.py` - Демо (280 строк)
- `README.md` - Полная документация
- `SETUP.md` - Детальная инструкция
- `QUICKSTART.md` - Этот файл

## ✨ Готово!

Ассистент разработчика настроен и работает!
