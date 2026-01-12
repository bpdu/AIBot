#!/usr/bin/env python3
"""
День 20: Ассистент разработчика - Создание embeddings для документации проекта

Создает embeddings для:
- README.md
- ARCHITECTURE.md
- CODE_STYLE.md

Сохраняет в отдельную таблицу project_docs в db.sqlite3
"""

import sqlite3
import pickle
import requests
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Пути
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = Path(__file__).parent / "db.sqlite3"
OLLAMA_API_URL = "http://127.0.0.1:11434/api/embeddings"
OLLAMA_MODEL = "nomic-embed-text"

# Документы для индексации
DOCS_TO_INDEX = [
    "README.md",
    "ARCHITECTURE.md",
    "CODE_STYLE.md",
    "docs/OLLAMA_SETUP.md",
    "docs/EMBEDDINGS_GUIDE.md"
]


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


def chunk_markdown(content: str, chunk_size: int = 1000) -> list:
    """
    Разбить markdown документ на чанки по заголовкам и размеру.

    Args:
        content: Содержимое markdown файла
        chunk_size: Максимальный размер чанка в символах

    Returns:
        Список чанков с метаданными
    """
    chunks = []
    lines = content.split('\n')

    current_chunk = []
    current_heading = "Introduction"
    current_level = 0

    for line in lines:
        # Обнаружение заголовка
        if line.startswith('#'):
            # Сохранить предыдущий чанк
            if current_chunk:
                chunk_text = '\n'.join(current_chunk)
                if len(chunk_text) > chunk_size:
                    # Разбить большой чанк на части
                    sub_chunks = split_large_chunk(chunk_text, chunk_size)
                    for i, sub in enumerate(sub_chunks):
                        chunks.append({
                            'text': sub,
                            'heading': f"{current_heading} (часть {i+1})",
                            'level': current_level
                        })
                else:
                    chunks.append({
                        'text': chunk_text,
                        'heading': current_heading,
                        'level': current_level
                    })
                current_chunk = []

            # Новый заголовок
            level = len(line.split()[0])  # Количество #
            heading = line.lstrip('#').strip()
            current_heading = heading
            current_level = level

        current_chunk.append(line)

    # Последний чанк
    if current_chunk:
        chunk_text = '\n'.join(current_chunk)
        if len(chunk_text) > chunk_size:
            sub_chunks = split_large_chunk(chunk_text, chunk_size)
            for i, sub in enumerate(sub_chunks):
                chunks.append({
                    'text': sub,
                    'heading': f"{current_heading} (часть {i+1})",
                    'level': current_level
                })
        else:
            chunks.append({
                'text': chunk_text,
                'heading': current_heading,
                'level': current_level
            })

    return chunks


def split_large_chunk(text: str, chunk_size: int) -> list:
    """
    Разбить большой чанк на части по размеру.

    Args:
        text: Текст для разбиения
        chunk_size: Максимальный размер части

    Returns:
        Список частей
    """
    words = text.split()
    sub_chunks = []
    current_sub = []
    current_size = 0

    for word in words:
        word_size = len(word) + 1  # +1 для пробела
        if current_size + word_size > chunk_size and current_sub:
            sub_chunks.append(' '.join(current_sub))
            current_sub = [word]
            current_size = word_size
        else:
            current_sub.append(word)
            current_size += word_size

    if current_sub:
        sub_chunks.append(' '.join(current_sub))

    return sub_chunks


def create_database():
    """Создать таблицу для хранения embeddings документации проекта."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Создать таблицу для документации проекта
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_name TEXT NOT NULL,
            heading TEXT NOT NULL,
            level INTEGER,
            chunk_text TEXT NOT NULL,
            embedding BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Database table 'project_docs' created/verified")


def clear_existing_embeddings():
    """Очистить существующие embeddings."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM project_docs")
    conn.commit()
    conn.close()
    logger.info("Existing embeddings cleared")


def index_document(doc_path: Path):
    """
    Индексировать один документ.

    Args:
        doc_path: Путь к markdown файлу
    """
    logger.info(f"Processing {doc_path.name}...")

    # Прочитать документ
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Failed to read {doc_path}: {e}")
        return

    # Разбить на чанки
    chunks = chunk_markdown(content)
    logger.info(f"Created {len(chunks)} chunks from {doc_path.name}")

    # Создать embeddings и сохранить
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for i, chunk in enumerate(chunks, 1):
        try:
            logger.info(f"  Processing chunk {i}/{len(chunks)}: {chunk['heading'][:50]}...")

            # Генерировать embedding
            embedding = generate_embedding(chunk['text'])

            # Сохранить в БД
            cursor.execute("""
                INSERT INTO project_docs (doc_name, heading, level, chunk_text, embedding)
                VALUES (?, ?, ?, ?, ?)
            """, (
                doc_path.name,
                chunk['heading'],
                chunk['level'],
                chunk['text'],
                pickle.dumps(embedding)
            ))

            conn.commit()
            logger.info(f"  ✓ Chunk {i} saved")

        except Exception as e:
            logger.error(f"  ✗ Failed to process chunk {i}: {e}")
            continue

    conn.close()
    logger.info(f"✓ Completed {doc_path.name}")


def main():
    """Главная функция."""
    logger.info("=" * 60)
    logger.info("Creating embeddings for project documentation")
    logger.info("=" * 60)

    # Создать БД
    create_database()

    # Очистить старые embeddings
    clear_existing_embeddings()

    # Индексировать каждый документ
    total_docs = 0
    for doc_name in DOCS_TO_INDEX:
        doc_path = PROJECT_ROOT / doc_name
        if doc_path.exists():
            index_document(doc_path)
            total_docs += 1
        else:
            logger.warning(f"Document not found: {doc_path}")

    # Статистика
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM project_docs")
    total_chunks = cursor.fetchone()[0]
    conn.close()

    logger.info("=" * 60)
    logger.info(f"✓ Indexing complete!")
    logger.info(f"  Documents indexed: {total_docs}")
    logger.info(f"  Total chunks: {total_chunks}")
    logger.info(f"  Database: {DB_PATH}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
