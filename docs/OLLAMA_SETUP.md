# Установка и настройка Ollama

## Что такое Ollama?

**Ollama** - это инструмент для запуска больших языковых моделей локально на вашем компьютере. В проекте AIBot используется для генерации embeddings (векторных представлений текста).

## Зачем нужна Ollama в AIBot?

Ollama используется для **RAG системы** (Retrieval-Augmented Generation):
- Генерирует embeddings для документации проекта
- Генерирует embeddings для API документации (Pond Mobile)
- Позволяет делать semantic search (семантический поиск) по документам

**Модель:** `nomic-embed-text` - специализированная модель для создания embeddings

## Установка Ollama

### Windows

1. **Скачать установщик:**
   - Перейти на https://ollama.com/download
   - Скачать `.exe` установщик для Windows
   - Размер: ~500 MB

2. **Запустить установщик:**
   - Двойной клик по скачанному файлу
   - Следовать инструкциям мастера установки
   - Ollama установится в `C:\Users\<Username>\AppData\Local\Programs\Ollama`

3. **Проверить установку:**
   ```cmd
   ollama --version
   ```
   Должно вывести версию, например: `ollama version is 0.1.20`

4. **Запуск:**
   - Ollama запускается автоматически при старте Windows
   - Иконка в системном трее (справа внизу)
   - Если не запущена: запустить из меню Пуск

### Linux

1. **Установка через скрипт:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Или через пакетный менеджер (Ubuntu/Debian):**
   ```bash
   # Добавить репозиторий
   curl -fsSL https://ollama.com/install.sh | sh

   # Или вручную
   wget https://ollama.com/download/ollama-linux-amd64
   sudo install -o root -g root -m 0755 ollama-linux-amd64 /usr/local/bin/ollama
   ```

3. **Запустить как сервис:**
   ```bash
   # Создать systemd service
   sudo systemctl enable ollama
   sudo systemctl start ollama
   ```

4. **Проверить статус:**
   ```bash
   systemctl status ollama
   # или
   ollama --version
   ```

### macOS

1. **Скачать:**
   - Перейти на https://ollama.com/download
   - Скачать `.dmg` для macOS
   - Или через Homebrew:
   ```bash
   brew install ollama
   ```

2. **Установить:**
   - Открыть `.dmg` файл
   - Перетащить Ollama в Applications
   - Запустить из Applications

3. **Проверить:**
   ```bash
   ollama --version
   ```

## Загрузка модели nomic-embed-text

После установки Ollama нужно скачать модель для embeddings:

```bash
ollama pull nomic-embed-text
```

**Что происходит:**
- Скачивается модель размером ~274 MB
- Модель сохраняется локально
- Время скачивания: 1-5 минут (зависит от скорости интернета)

**Ожидаемый вывод:**
```
pulling manifest
pulling 970aa74c0a90... 100% ▕████████████████▏ 274 MB
pulling c71d239df917... 100% ▕████████████████▏  11 KB
pulling ce4a164fc046... 100% ▕████████████████▏   17 B
pulling 31df23ea7daa... 100% ▕████████████████▏  420 B
verifying sha256 digest
writing manifest
removing any unused layers
success
```

## Проверка работы Ollama

### 1. Проверить список моделей

```bash
ollama list
```

**Должно показать:**
```
NAME                    ID              SIZE      MODIFIED
nomic-embed-text:latest 970aa74c0a90    274 MB    2 minutes ago
```

### 2. Тестовый запрос embeddings

```bash
curl http://localhost:11434/api/embeddings -d '{
  "model": "nomic-embed-text",
  "prompt": "Hello, world!"
}'
```

**Ожидаемый ответ:** JSON с полем `embedding` (массив из 768 чисел)

### 3. Python тест

```python
import requests

response = requests.post(
    'http://127.0.0.1:11434/api/embeddings',
    json={
        'model': 'nomic-embed-text',
        'prompt': 'Test text'
    }
)

print(f"Status: {response.status_code}")
print(f"Embedding dimension: {len(response.json()['embedding'])}")
# Должно вывести: Embedding dimension: 768
```

## API Ollama

### Endpoint для embeddings

**URL:** `http://127.0.0.1:11434/api/embeddings`

**Метод:** POST

**Формат запроса:**
```json
{
  "model": "nomic-embed-text",
  "prompt": "Текст для генерации embedding"
}
```

**Формат ответа:**
```json
{
  "embedding": [0.123, -0.456, 0.789, ...]
}
```

**Размерность:** 768 (для nomic-embed-text)

### Другие полезные команды

```bash
# Список всех доступных моделей в библиотеке
ollama list

# Удалить модель
ollama rm nomic-embed-text

# Показать информацию о модели
ollama show nomic-embed-text

# Запустить модель в интерактивном режиме (для LLM, не для embeddings)
ollama run llama2

# Остановить Ollama (Linux)
sudo systemctl stop ollama

# Перезапустить Ollama (Linux)
sudo systemctl restart ollama
```

## Использование в AIBot

### 1. Создание embeddings для документации

```bash
cd rag
python create-embeddings.py         # Для API документации (Pond Mobile)
python create-project-docs-embeddings.py  # Для документации проекта
```

### 2. Тестирование RAG

```bash
cd rag
python test_embeddings.py          # Тест API документации
python project_docs_retrieval.py   # Тест документации проекта
```

### 3. В коде бота

Ollama используется автоматически через модуль `rag/`:
- `rag/retrieval.py` - для API документации
- `rag/project_docs_retrieval.py` - для документации проекта

**Пример из кода:**
```python
from rag.retrieval import rag_query

# RAG запрос с использованием Ollama
context, chunks = rag_query("Как получить список SIM карт?", top_k=3)
```

## Требования к системе

### Минимальные
- **CPU:** 4+ ядра
- **RAM:** 8 GB
- **Disk:** 2 GB свободного места
- **OS:** Windows 10+, macOS 11+, Linux (modern distro)

### Рекомендуемые
- **CPU:** 8+ ядер
- **RAM:** 16 GB
- **GPU:** Опционально (ускоряет генерацию embeddings)
- **Disk:** SSD для быстрой работы

## Производительность

### Время генерации одного embedding:
- **CPU (Intel i5):** ~0.5-1 сек
- **CPU (Intel i7/AMD Ryzen):** ~0.2-0.5 сек
- **GPU (NVIDIA):** ~0.1-0.2 сек

### Создание embeddings для документации проекта:
- **~45 chunks** (README + ARCHITECTURE + CODE_STYLE)
- **Время:** 2-5 минут на обычном CPU
- **Размер базы:** ~50 MB (db.sqlite3)

## Troubleshooting

### Проблема: "Connection refused" на порту 11434

**Решение:**
1. Проверить, что Ollama запущена:
   ```bash
   # Windows: проверить в системном трее
   # Linux:
   systemctl status ollama
   # macOS: проверить в Activity Monitor
   ```

2. Перезапустить Ollama:
   ```bash
   # Linux
   sudo systemctl restart ollama

   # Windows/macOS: закрыть из трея и запустить снова
   ```

### Проблема: "Model not found"

**Решение:**
```bash
ollama pull nomic-embed-text
```

### Проблема: Медленная генерация embeddings

**Решения:**
1. Использовать GPU (если доступно)
2. Увеличить RAM выделенный для Ollama
3. Уменьшить batch size при создании embeddings
4. Использовать SSD вместо HDD

### Проблема: Ошибка "Out of memory"

**Решение:**
1. Закрыть другие приложения
2. Увеличить swap (Linux):
   ```bash
   sudo fallocate -l 4G /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```
3. Использовать меньшую модель (если возможно)

## Альтернативы Ollama

Если Ollama не подходит, можно использовать:

1. **OpenAI Embeddings API**
   - Платная
   - Быстрее
   - Не требует локальной установки

2. **Hugging Face Transformers**
   - Бесплатно
   - Локально
   - Требует больше настройки

3. **Sentence Transformers**
   - Бесплатно
   - Локально
   - Хорошая альтернатива

**Для AIBot рекомендуется Ollama** - простая установка и хорошая производительность.

## Дополнительные ресурсы

- **Официальный сайт:** https://ollama.com
- **GitHub:** https://github.com/ollama/ollama
- **Документация:** https://github.com/ollama/ollama/tree/main/docs
- **Модели:** https://ollama.com/library
- **Discord:** https://discord.gg/ollama

## Заключение

Ollama - ключевой компонент RAG системы в AIBot. После установки и настройки:
1. Ollama работает в фоне
2. Автоматически обрабатывает запросы на embeddings
3. Не требует дополнительной настройки

**Следующий шаг:** [Руководство по Embeddings](EMBEDDINGS_GUIDE.md)
