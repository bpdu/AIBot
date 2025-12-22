#!/usr/bin/env python3
"""
Скрипт для проверки эмбеддингов в базе данных
"""

import sqlite3
import pickle
from pathlib import Path

DB_PATH = Path(__file__).parent / "db.sqlite3"

def test_embeddings():
    """Проверить что эмбеддинги корректно сохранены."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получить общую статистику
    cursor.execute("SELECT COUNT(*) FROM embeddings")
    total_count = cursor.fetchone()[0]
    print(f"Всего записей в БД: {total_count}")

    # Получить первую запись
    cursor.execute("""
        SELECT id, endpoint_path, method, tag, embedding,
               substr(chunk_text, 1, 100) as preview
        FROM embeddings
        LIMIT 1
    """)

    row = cursor.fetchone()
    if row:
        id, path, method, tag, embedding_blob, preview = row

        print("\n" + "=" * 60)
        print("Пример записи:")
        print("=" * 60)
        print(f"ID: {id}")
        print(f"Endpoint: {method} {path}")
        print(f"Tag: {tag}")
        print(f"Preview: {preview}...")
        print(f"\nEmbedding BLOB size: {len(embedding_blob)} bytes")

        # Распаковать эмбеддинг
        try:
            embedding = pickle.loads(embedding_blob)
            print(f"✓ Embedding успешно распакован")
            print(f"✓ Тип: {type(embedding)}")
            print(f"✓ Размерность: {len(embedding)}")
            print(f"✓ Первые 5 значений: {embedding[:5]}")
            print(f"✓ Последние 5 значений: {embedding[-5:]}")

            # Проверить что все элементы - числа
            if all(isinstance(x, (int, float)) for x in embedding):
                print(f"✓ Все элементы - числа")
            else:
                print(f"✗ Не все элементы - числа!")

        except Exception as e:
            print(f"✗ Ошибка при распаковке embedding: {e}")

    # Проверить все записи
    print("\n" + "=" * 60)
    print("Проверка всех записей:")
    print("=" * 60)

    cursor.execute("SELECT id, embedding FROM embeddings")
    rows = cursor.fetchall()

    valid_count = 0
    invalid_count = 0
    dimensions = set()

    for row in rows:
        id, embedding_blob = row
        try:
            embedding = pickle.loads(embedding_blob)
            if isinstance(embedding, list) and all(isinstance(x, (int, float)) for x in embedding):
                valid_count += 1
                dimensions.add(len(embedding))
            else:
                invalid_count += 1
                print(f"✗ ID {id}: invalid embedding type or content")
        except Exception as e:
            invalid_count += 1
            print(f"✗ ID {id}: failed to unpickle: {e}")

    print(f"\n✓ Корректных эмбеддингов: {valid_count}")
    print(f"✗ Некорректных эмбеддингов: {invalid_count}")
    print(f"📊 Уникальные размерности: {dimensions}")

    if len(dimensions) == 1:
        print(f"✓ Все эмбеддинги имеют одинаковую размерность: {list(dimensions)[0]}")

    # Показать распределение по тегам
    print("\n" + "=" * 60)
    print("Распределение по категориям (tags):")
    print("=" * 60)

    cursor.execute("""
        SELECT tag, COUNT(*) as count
        FROM embeddings
        GROUP BY tag
        ORDER BY count DESC
    """)

    for row in cursor.fetchall():
        tag, count = row
        print(f"  {tag}: {count} чанков")

    conn.close()

    print("\n" + "=" * 60)
    print("Проверка завершена!")
    print("=" * 60)


if __name__ == "__main__":
    test_embeddings()
