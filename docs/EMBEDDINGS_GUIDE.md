# Руководство по Embeddings (Эмбеддингам)

## Что такое Embeddings?

**Embeddings (эмбеддинги)** - это векторное представление текста в многомерном пространстве. Простыми словами: превращение текста в массив чисел таким образом, чтобы похожие по смыслу тексты имели близкие числовые представления.

### Пример

**Текст:** "Привет, мир!"

**Embedding:** `[0.123, -0.456, 0.789, ..., 0.234]` (768 чисел для nomic-embed-text)

### Зачем это нужно?

Компьютеры не понимают смысл текста напрямую. Embeddings позволяют:
1. **Сравнивать тексты** по смыслу (не по буквам!)
2. **Искать похожие документы** (semantic search)
3. **Группировать** похожие тексты
4. **Классифицировать** тексты

## Как работают Embeddings?

### 1. Обучение модели

Модель (например, `nomic-embed-text`) обучается на огромном количестве текстов:
- Читает миллионы документов
- Учится понимать контекст и смысл слов
- Запоминает, какие слова часто встречаются вместе
- Понимает синонимы, антонимы, связи между понятиями

### 2. Генерация embedding

Когда вы даёте модели текст:
```
Вход: "Как получить список SIM карт?"
```

Модель:
1. Разбивает текст на токены (слова/части слов)
2. Обрабатывает каждый токен с учётом контекста
3. Создаёт единый вектор для всего текста
4. Возвращает массив из 768 чисел

```
Выход: [0.123, -0.456, 0.789, ..., 0.234]
       ↑      ↑      ↑          ↑
       768 чисел от -1 до 1
```

### 3. Сравнение embeddings

Для сравнения двух текстов используется **cosine similarity** (косинусное сходство):

```
Текст 1: "Как получить SIM карты?"
Embedding 1: [0.1, 0.5, 0.3, ...]

Текст 2: "Метод для получения списка SIM"
Embedding 2: [0.15, 0.48, 0.32, ...]

Cosine Similarity: 0.95 (очень похожи!)
```

```
Текст 3: "Погода сегодня"
Embedding 3: [-0.5, 0.1, -0.8, ...]

Cosine Similarity с Текстом 1: 0.12 (не похожи)
```

**Формула:**
```
similarity = (A · B) / (||A|| × ||B||)

где:
A · B = скалярное произведение векторов
||A|| = длина вектора A
||B|| = длина вектора B

Результат: от -1 до 1
1 = полностью похожи
0 = никак не связаны
-1 = противоположны
```

## Embeddings в AIBot

### Архитектура RAG системы

```
┌─────────────────────────────────────────┐
│         Документация проекта             │
│  (README, ARCHITECTURE, CODE_STYLE)      │
└──────────────┬──────────────────────────┘
               │
               ↓ Chunking (разбиение)
┌──────────────────────────────────────────┐
│  Chunks (фрагменты документации)         │
│  - Chunk 1: "AIBot - Telegram Bot..."    │
│  - Chunk 2: "Архитектура системы..."     │
│  - Chunk 3: "Стиль кода..."              │
│  ... (~45 chunks)                         │
└──────────────┬───────────────────────────┘
               │
               ↓ Ollama (nomic-embed-text)
┌──────────────────────────────────────────┐
│         Embeddings (векторы)             │
│  - Chunk 1 → [0.12, -0.45, ...]          │
│  - Chunk 2 → [0.34, 0.21, ...]           │
│  - Chunk 3 → [-0.11, 0.67, ...]          │
└──────────────┬───────────────────────────┘
               │
               ↓ Сохранение в SQLite
┌──────────────────────────────────────────┐
│     База данных (db.sqlite3)             │
│  Таблица: project_docs                   │
│  - id, chunk_text, embedding, ...        │
└──────────────────────────────────────────┘
```

### Процесс поиска

```
Пользователь вводит вопрос:
"Как добавить новый MCP сервер?"
        ↓
Генерация embedding для вопроса:
query_embedding = [0.25, -0.33, 0.41, ...]
        ↓
Сравнение с embeddings всех chunks:
- Chunk 1: similarity = 0.23
- Chunk 2: similarity = 0.87  ← Высокая похожесть!
- Chunk 3: similarity = 0.19
- ...
        ↓
Выбор top-K самых похожих:
Top-3: [Chunk 2, Chunk 15, Chunk 28]
        ↓
Формирование контекста для LLM:
"Relevant documentation:
Chunk 2: Как создать MCP сервер...
Chunk 15: Пример MCP сервера...
Chunk 28: Интеграция с bot.py..."
        ↓
DeepSeek API генерирует ответ с использованием контекста
        ↓
Пользователь получает точный ответ с ссылками на источники!
```

## Создание Embeddings в AIBot

### 1. Для документации проекта

**Скрипт:** `rag/create-project-docs-embeddings.py`

**Что делает:**
1. Читает README.md, ARCHITECTURE.md, CODE_STYLE.md
2. Разбивает на chunks (~1000 символов, по заголовкам)
3. Для каждого chunk:
   - Генерирует embedding через Ollama
   - Сохраняет в базу данных
4. Результат: ~45 chunks в таблице `project_docs`

**Запуск:**
```bash
cd rag
python create-project-docs-embeddings.py
```

**Вывод:**
```
Processing README.md...
Created 15 chunks from README.md
  Processing chunk 1/15: AIBot - Telegram Bot...
  ✓ Chunk 1 saved
  ...
✓ Indexing complete!
  Documents indexed: 3
  Total chunks: 45
```

### 2. Для API документации (Pond Mobile)

**Скрипт:** `rag/create-embeddings.py`

**Что делает:**
1. Парсит OpenAPI спецификацию (resources/dist.json)
2. Извлекает endpoints, методы, параметры
3. Создаёт chunks для каждого endpoint
4. Генерирует embeddings
5. Результат: ~200+ chunks в таблице `embeddings`

**Запуск:**
```bash
cd rag
python create-embeddings.py
```

## Поиск по Embeddings

### Алгоритм

```python
def search(query: str, top_k: int = 3):
    # 1. Генерировать embedding для запроса
    query_embedding = generate_embedding(query)

    # 2. Загрузить все embeddings из БД
    all_embeddings = load_from_database()

    # 3. Вычислить сходство с каждым chunk
    similarities = []
    for chunk in all_embeddings:
        similarity = cosine_similarity(query_embedding, chunk.embedding)
        similarities.append((chunk, similarity))

    # 4. Отсортировать по убыванию сходства
    similarities.sort(key=lambda x: x[1], reverse=True)

    # 5. Взять top-K результатов
    top_results = similarities[:top_k]

    return top_results
```

### Фильтрация результатов

В AIBot используется **hybrid фильтрация**:

1. **Минимальный порог** (min_similarity = 0.4)
   - Отсекает совсем не релевантные результаты

2. **Строгий порог** (strict_threshold = 0.5)
   - Только результаты с similarity >= 0.5

3. **Адаптивный порог** (adaptive = top_score * 0.85)
   - Оставляет результаты в пределах 85% от лучшего

**Пример:**
```
Query: "Как добавить MCP сервер?"

Результаты после первичного поиска:
1. Chunk 12: similarity = 0.92 (top score)
2. Chunk 34: similarity = 0.88
3. Chunk 7:  similarity = 0.85
4. Chunk 19: similarity = 0.75
5. Chunk 22: similarity = 0.42

Фильтрация (hybrid):
- Strict (>= 0.5): ✓ все кроме Chunk 22
- Adaptive (>= 0.92 * 0.85 = 0.78): ✓ Chunks 12, 34, 7

Финальный результат: Chunks 12, 34, 7
```

## Качество Embeddings

### Факторы влияющие на качество

1. **Модель:**
   - `nomic-embed-text` - хорошая для документации
   - `text-embedding-ada-002` (OpenAI) - лучше, но платная
   - Размерность: 768 (nomic) vs 1536 (OpenAI)

2. **Chunking (разбиение текста):**
   - Слишком маленькие chunks: теряется контекст
   - Слишком большие chunks: размывается смысл
   - **Оптимально:** ~500-1500 символов

3. **Качество исходных текстов:**
   - Хорошо структурированные документы
   - Чёткие заголовки
   - Последовательное изложение

### Оценка качества

**Метрики:**
- **Precision:** сколько из найденных релевантны
- **Recall:** сколько релевантных найдено
- **MRR (Mean Reciprocal Rank):** позиция первого релевантного результата

**Пример оценки:**
```
Query: "Как работает RAG?"

Ожидаемые релевантные chunks: [5, 12, 18]

Результаты поиска: [12, 5, 22, 18]

Precision@3: 2/3 = 66.7% (из первых 3, 2 релевантны)
Recall: 3/3 = 100% (все релевантные найдены)
MRR: 1/1 = 1.0 (первый результат релевантен)
```

## Оптимизация производительности

### 1. Кэширование embeddings

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def generate_embedding_cached(text: str):
    return generate_embedding(text)
```

### 2. Batch processing

```python
# Вместо:
for text in texts:
    embedding = generate_embedding(text)

# Лучше:
embeddings = generate_embeddings_batch(texts)  # За один запрос
```

### 3. Индексация (для больших баз)

Для баз >10000 документов использовать:
- **FAISS** (Facebook AI Similarity Search)
- **Annoy** (Approximate Nearest Neighbors)
- **Hnswlib** (Hierarchical Navigable Small World)

## Практические примеры

### Пример 1: Поиск похожих вопросов

```python
# База знаний FAQ
questions = [
    "Как установить бота?",
    "Где скачать Ollama?",
    "Что такое MCP сервер?",
    "Как настроить токен Telegram?"
]

# Новый вопрос пользователя
user_question = "Где взять Ollama?"

# Поиск похожего вопроса
similar = find_most_similar(user_question, questions)
# Результат: "Где скачать Ollama?" (similarity = 0.89)
```

### Пример 2: Категоризация

```python
# Embeddings категорий
categories = {
    "Установка": [0.1, 0.5, ...],
    "Использование": [0.3, -0.2, ...],
    "Troubleshooting": [-0.1, 0.7, ...]
}

# Новый документ
doc_embedding = generate_embedding("Ошибка при запуске бота")

# Найти категорию
best_category = max(categories.items(),
                   key=lambda x: cosine_similarity(doc_embedding, x[1]))
# Результат: "Troubleshooting"
```

### Пример 3: Дедупликация

```python
# Найти дубликаты документов
def find_duplicates(documents, threshold=0.95):
    embeddings = [generate_embedding(doc) for doc in documents]

    duplicates = []
    for i in range(len(embeddings)):
        for j in range(i+1, len(embeddings)):
            sim = cosine_similarity(embeddings[i], embeddings[j])
            if sim >= threshold:
                duplicates.append((i, j, sim))

    return duplicates
```

## Ограничения Embeddings

### 1. Потеря нюансов

Embeddings - это сжатие информации. Некоторые детали могут потеряться:
- Тонкие различия в значении
- Сарказм, ирония
- Контекст из других частей документа

### 2. Зависимость от обучающих данных

Модель хороша настолько, насколько хороши данные, на которых она обучена:
- Может не знать новых терминов
- Может быть смещена (bias)
- Может плохо работать на специфичных доменах

### 3. Вычислительная нагрузка

Генерация embeddings требует ресурсов:
- CPU/GPU время
- Память для хранения векторов
- Время на поиск по большой базе

## Лучшие практики

### 1. Chunking

✅ **Хорошо:**
- Разбивать по логическим блокам (заголовки, параграфы)
- Размер chunk: 500-1500 символов
- Перекрытие между chunks: 100-200 символов

❌ **Плохо:**
- Резать текст по фиксированному количеству символов
- Слишком маленькие chunks (<100 символов)
- Слишком большие chunks (>2000 символов)

### 2. Метаданные

Сохраняйте метаданные вместе с embeddings:
```python
chunk = {
    'text': "...",
    'embedding': [...],
    'source': 'README.md',
    'section': 'Installation',
    'created': '2026-01-12'
}
```

### 3. Регулярное переиндексирование

Когда документация обновляется:
```bash
# Переиндексировать документацию
python create-project-docs-embeddings.py
```

### 4. Мониторинг качества

Отслеживайте метрики:
- Средний similarity score
- Количество запросов без результатов
- Обратная связь от пользователей

## Дополнительные ресурсы

### Теория
- [Word2Vec paper](https://arxiv.org/abs/1301.3781) - основы word embeddings
- [BERT paper](https://arxiv.org/abs/1810.04805) - контекстные embeddings
- [Sentence-BERT](https://arxiv.org/abs/1908.10084) - embeddings для предложений

### Инструменты
- [Ollama](https://ollama.com) - локальное выполнение моделей
- [Hugging Face](https://huggingface.co) - библиотека моделей
- [FAISS](https://github.com/facebookresearch/faiss) - быстрый поиск

### Визуализация
- [Embedding Projector](https://projector.tensorflow.org/) - визуализация embeddings
- [t-SNE](https://lvdmaaten.github.io/tsne/) - уменьшение размерности

## Заключение

**Embeddings** - это мост между человеческим языком и машинным пониманием. В AIBot они обеспечивают:
- Интеллектуальный поиск по документации
- Релевантные ответы на вопросы
- Быструю навигацию по знаниям проекта

**Ключевые моменты:**
1. Embeddings превращают текст в векторы
2. Похожие по смыслу тексты имеют близкие векторы
3. Поиск = сравнение векторов (cosine similarity)
4. RAG = Retrieval (поиск) + Generation (генерация ответа)

**Следующие шаги:**
1. [Установка Ollama](OLLAMA_SETUP.md)
2. Создание embeddings для документации
3. Тестирование RAG поиска
4. Использование через команду `/help`
