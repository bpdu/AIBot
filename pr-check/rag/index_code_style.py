#!/usr/bin/env python3
"""
День 21: Индексация CODE_STYLE.md для PR Review

Создает embeddings для CODE_STYLE.md с оптимальной chunking стратегией
для поиска релевантных правил стиля во время ревью PR.

Стратегия chunking:
- Размер chunk: 800 символов
- Разбивка по секциям (headings)
- Сохранение примеров кода вместе с объяснениями
- Метаданные: heading, level, line_range для точных ссылок
"""

import sqlite3
import pickle
import requests
from pathlib import Path
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Пути
PROJECT_ROOT = Path(__file__).parent.parent
CODE_STYLE_PATH = PROJECT_ROOT / "CODE_STYLE.md"
DB_PATH = Path(__file__).parent / "db.sqlite3"

# Ollama Configuration
OLLAMA_API_URL = "http://127.0.0.1:11434/api/embeddings"
OLLAMA_MODEL = "nomic-embed-text"

# Chunking Configuration
CHUNK_SIZE = 800  # Оптимальный размер для баланса контекста и точности


def generate_embedding(text: str) -> list:
    """
    Генерировать embedding через Ollama.

    Args:
        text: Текст для embedding

    Returns:
        Вектор embedding
    """
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                'model': OLLAMA_MODEL,
                'prompt': text
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        return result['embedding']
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise


def chunk_code_style_document(content: str) -> list:
    """
    Разбить CODE_STYLE.md на чанки с сохранением контекста.

    Стратегия:
    - Разбивка по заголовкам
    - Сохранение примеров кода с их объяснениями
    - Ограничение размера chunk: 800 символов
    - Метаданные: heading, level, line_range

    Args:
        content: Содержимое CODE_STYLE.md

    Returns:
        Список чанков с метаданными
    """
    chunks = []
    lines = content.split('\n')

    current_chunk = []
    current_heading = "Introduction"
    current_level = 0
    chunk_start_line = 1
    line_number = 1

    in_code_block = False
    code_block_lines = []

    for line in lines:
        # Отслеживание code blocks
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            if in_code_block:
                # Начало code block
                code_block_lines = [line]
            else:
                # Конец code block - добавить весь блок
                code_block_lines.append(line)
                current_chunk.extend(code_block_lines)
                code_block_lines = []
                line_number += 1
                continue

        if in_code_block:
            code_block_lines.append(line)
            line_number += 1
            continue

        # Обнаружение заголовка
        if line.startswith('#') and not in_code_block:
            # Сохранить предыдущий чанк
            if current_chunk:
                chunk_text = '\n'.join(current_chunk)
                chunks.extend(
                    process_chunk(
                        chunk_text,
                        current_heading,
                        current_level,
                        chunk_start_line,
                        line_number - 1
                    )
                )
                current_chunk = []
                chunk_start_line = line_number

            # Новый заголовок
            level = len(line.split()[0])  # Количество #
            heading = line.lstrip('#').strip()
            current_heading = heading
            current_level = level

        current_chunk.append(line)
        line_number += 1

    # Последний чанк
    if current_chunk:
        chunk_text = '\n'.join(current_chunk)
        chunks.extend(
            process_chunk(
                chunk_text,
                current_heading,
                current_level,
                chunk_start_line,
                line_number - 1
            )
        )

    return chunks


def process_chunk(text: str, heading: str, level: int, start_line: int, end_line: int) -> list:
    """
    Обработать чанк: разбить на части если слишком большой.

    Args:
        text: Текст чанка
        heading: Заголовок секции
        level: Уровень заголовка
        start_line: Начальная строка
        end_line: Конечная строка

    Returns:
        Список обработанных чанков
    """
    if len(text) <= CHUNK_SIZE:
        return [{
            'text': text,
            'heading': heading,
            'level': level,
            'line_range': f"{start_line}-{end_line}"
        }]

    # Разбить большой чанк на части
    # Стратегия: пытаться разбивать по параграфам, затем по предложениям
    sub_chunks = smart_split_chunk(text, CHUNK_SIZE)

    result = []
    for i, sub in enumerate(sub_chunks):
        result.append({
            'text': sub,
            'heading': f"{heading} (часть {i+1})",
            'level': level,
            'line_range': f"{start_line}-{end_line}"
        })

    return result


def smart_split_chunk(text: str, max_size: int) -> list:
    """
    Умное разбиение чанка с сохранением контекста.

    Приоритеты разбиения:
    1. По двойным переводам строки (параграфы)
    2. По одиночным переводам строки
    3. По предложениям
    4. По словам

    Args:
        text: Текст для разбиения
        max_size: Максимальный размер части

    Returns:
        Список частей
    """
    # Попытка 1: разбить по параграфам
    paragraphs = text.split('\n\n')
    if all(len(p) <= max_size for p in paragraphs):
        return merge_small_chunks(paragraphs, max_size)

    # Попытка 2: разбить по строкам
    lines = text.split('\n')
    result = []
    current = []
    current_size = 0

    for line in lines:
        line_size = len(line) + 1  # +1 для \n

        # Если строка сама по себе больше max_size, разбить по словам
        if line_size > max_size:
            if current:
                result.append('\n'.join(current))
                current = []
                current_size = 0
            # Разбить длинную строку по словам
            result.extend(split_by_words(line, max_size))
            continue

        if current_size + line_size > max_size and current:
            result.append('\n'.join(current))
            current = [line]
            current_size = line_size
        else:
            current.append(line)
            current_size += line_size

    if current:
        result.append('\n'.join(current))

    return result


def split_by_words(text: str, max_size: int) -> list:
    """
    Разбить текст по словам.

    Args:
        text: Текст для разбиения
        max_size: Максимальный размер части

    Returns:
        Список частей
    """
    words = text.split()
    result = []
    current = []
    current_size = 0

    for word in words:
        word_size = len(word) + 1  # +1 для пробела
        if current_size + word_size > max_size and current:
            result.append(' '.join(current))
            current = [word]
            current_size = word_size
        else:
            current.append(word)
            current_size += word_size

    if current:
        result.append(' '.join(current))

    return result


def merge_small_chunks(chunks: list, max_size: int) -> list:
    """
    Объединить маленькие чанки для оптимизации.

    Args:
        chunks: Список чанков
        max_size: Максимальный размер

    Returns:
        Объединенные чанки
    """
    result = []
    current = []
    current_size = 0

    for chunk in chunks:
        chunk_size = len(chunk) + 2  # +2 для \n\n
        if current_size + chunk_size > max_size and current:
            result.append('\n\n'.join(current))
            current = [chunk]
            current_size = chunk_size
        else:
            current.append(chunk)
            current_size += chunk_size

    if current:
        result.append('\n\n'.join(current))

    return result


def create_database():
    """Создать таблицу для хранения embeddings CODE_STYLE.md."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Создать таблицу для CODE_STYLE embeddings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS code_style (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            heading TEXT NOT NULL,
            level INTEGER,
            line_range TEXT,
            chunk_text TEXT NOT NULL,
            embedding BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Создать индекс для ускорения поиска
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_code_style_heading
        ON code_style(heading)
    """)

    conn.commit()
    conn.close()
    logger.info("✅ Database table 'code_style' created")


def index_code_style():
    """
    Основная функция индексации CODE_STYLE.md.

    Процесс:
    1. Читает CODE_STYLE.md
    2. Разбивает на оптимальные чанки
    3. Генерирует embeddings через Ollama
    4. Сохраняет в БД
    """
    logger.info("Starting CODE_STYLE.md indexing...")

    # 1. Проверка наличия файла
    if not CODE_STYLE_PATH.exists():
        raise FileNotFoundError(f"CODE_STYLE.md not found at {CODE_STYLE_PATH}")

    # 2. Чтение файла
    logger.info(f"Reading {CODE_STYLE_PATH}")
    with open(CODE_STYLE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    logger.info(f"File size: {len(content)} chars, {len(content.splitlines())} lines")

    # 3. Chunking
    logger.info("Chunking document...")
    chunks = chunk_code_style_document(content)
    logger.info(f"Created {len(chunks)} chunks")

    # Статистика по размерам чанков
    sizes = [len(c['text']) for c in chunks]
    logger.info(f"Chunk sizes: min={min(sizes)}, max={max(sizes)}, avg={sum(sizes)//len(sizes)}")

    # 4. Создание БД
    create_database()

    # 5. Очистка старых данных
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM code_style")
    conn.commit()
    logger.info("Cleared existing code_style data")

    # 6. Генерация embeddings и сохранение
    logger.info("Generating embeddings...")
    for i, chunk in enumerate(chunks, 1):
        logger.info(f"Processing chunk {i}/{len(chunks)}: {chunk['heading'][:50]}...")

        try:
            # Генерировать embedding
            embedding = generate_embedding(chunk['text'])

            # Сохранить в БД
            cursor.execute("""
                INSERT INTO code_style (heading, level, line_range, chunk_text, embedding)
                VALUES (?, ?, ?, ?, ?)
            """, (
                chunk['heading'],
                chunk['level'],
                chunk['line_range'],
                chunk['text'],
                pickle.dumps(embedding)
            ))

            conn.commit()
        except Exception as e:
            logger.error(f"Failed to process chunk {i}: {e}")
            continue

    conn.close()

    logger.info(f"✅ Indexing complete! {len(chunks)} chunks indexed")
    logger.info(f"Database: {DB_PATH}")

    # Проверка
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM code_style")
    count = cursor.fetchone()[0]
    conn.close()

    logger.info(f"✅ Verification: {count} embeddings in database")


def print_chunks_preview(chunks: list, num_to_show: int = 5):
    """
    Показать preview первых чанков для проверки.

    Args:
        chunks: Список чанков
        num_to_show: Количество чанков для показа
    """
    logger.info(f"\n=== Preview первых {num_to_show} чанков ===\n")
    for i, chunk in enumerate(chunks[:num_to_show], 1):
        logger.info(f"Chunk {i}:")
        logger.info(f"  Heading: {chunk['heading']}")
        logger.info(f"  Level: {chunk['level']}")
        logger.info(f"  Line range: {chunk['line_range']}")
        logger.info(f"  Size: {len(chunk['text'])} chars")
        logger.info(f"  Preview: {chunk['text'][:100]}...")
        logger.info("")


if __name__ == "__main__":
    try:
        index_code_style()
    except Exception as e:
        logger.error(f"❌ Indexing failed: {e}", exc_info=True)
        exit(1)
