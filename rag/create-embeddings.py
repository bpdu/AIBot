#!/usr/bin/env python3
"""
День 16: Индексация документов
Создание индекса Pond Mobile API Documentation с эмбеддингами через Ollama
"""

import json
import sqlite3
import pickle
import requests
import logging
from pathlib import Path
from typing import List, Dict, Any

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
OLLAMA_API_URL = "http://127.0.0.1:11434/api/embeddings"
OLLAMA_MODEL = "nomic-embed-text"
CHUNK_SIZE = 512  # токенов
CHUNK_OVERLAP = 50  # токенов
DB_PATH = Path(__file__).parent / "db.sqlite3"
SOURCE_JSON = Path(__file__).parent.parent / "resources" / "dist.json"


def load_api_spec() -> dict:
    """Загрузить OpenAPI спецификацию из dist.json."""
    logger.info(f"Loading API spec from {SOURCE_JSON}")
    with open(SOURCE_JSON, 'r', encoding='utf-8') as f:
        spec = json.load(f)
    logger.info(f"Loaded OpenAPI spec version {spec['info']['version']}")
    return spec


def format_endpoint_as_text(path: str, method: str, endpoint_data: dict) -> str:
    """
    Конвертировать endpoint в человеко-читаемый текстовый формат.

    Args:
        path: Путь endpoint (например, /core/countries)
        method: HTTP метод (GET, POST, etc.)
        endpoint_data: Данные endpoint из OpenAPI spec

    Returns:
        Форматированный текст описания endpoint
    """
    lines = []

    # Заголовок
    lines.append(f"Endpoint: {method.upper()} {path}")

    # Tags
    if 'tags' in endpoint_data:
        lines.append(f"Tag: {', '.join(endpoint_data['tags'])}")

    # Summary
    if 'summary' in endpoint_data:
        lines.append(f"Summary: {endpoint_data['summary']}")

    # Description
    if 'description' in endpoint_data:
        lines.append(f"Description: {endpoint_data['description']}")

    # Parameters
    if 'parameters' in endpoint_data and endpoint_data['parameters']:
        lines.append("\nParameters:")
        for param in endpoint_data['parameters']:
            param_name = param.get('name', 'unknown')
            param_in = param.get('in', 'unknown')
            param_type = param.get('schema', {}).get('type', 'unknown')
            param_desc = param.get('description', '')

            lines.append(f"- {param_name} ({param_in}, {param_type}): {param_desc}")

    # Request Body
    if 'requestBody' in endpoint_data:
        lines.append("\nRequest Body:")
        req_body = endpoint_data['requestBody']
        if 'description' in req_body:
            lines.append(f"Description: {req_body['description']}")

        if 'content' in req_body:
            for content_type, content_data in req_body['content'].items():
                lines.append(f"Content-Type: {content_type}")
                if 'schema' in content_data:
                    schema = content_data['schema']
                    if 'properties' in schema:
                        lines.append("Properties:")
                        for prop_name, prop_data in schema['properties'].items():
                            prop_type = prop_data.get('type', 'unknown')
                            prop_desc = prop_data.get('description', '')
                            lines.append(f"  - {prop_name} ({prop_type}): {prop_desc}")

    # Responses
    if 'responses' in endpoint_data:
        lines.append("\nResponses:")
        for status_code, response_data in endpoint_data['responses'].items():
            response_desc = response_data.get('description', '')
            lines.append(f"- {status_code}: {response_desc}")

            if 'content' in response_data:
                for content_type, content_data in response_data['content'].items():
                    if 'schema' in content_data:
                        schema = content_data['schema']
                        if 'properties' in schema:
                            lines.append(f"  Returns ({content_type}):")
                            for prop_name, prop_data in schema['properties'].items():
                                prop_type = prop_data.get('type', 'unknown')
                                prop_desc = prop_data.get('description', '')
                                lines.append(f"    - {prop_name} ({prop_type}): {prop_desc}")

    return '\n'.join(lines)


def simple_tokenize(text: str) -> List[str]:
    """
    Простая токенизация по словам.
    Для более точной токенизации нужно использовать tiktoken,
    но для простоты используем разбиение по пробелам.

    Args:
        text: Исходный текст

    Returns:
        Список "токенов" (слов)
    """
    # Разбиваем по пробелам и знакам препинания
    return text.split()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Разбить текст на чанки с перекрытием.

    Args:
        text: Исходный текст
        chunk_size: Размер чанка в токенах
        overlap: Размер перекрытия в токенах

    Returns:
        Список текстовых чанков
    """
    tokens = simple_tokenize(text)
    chunks = []

    i = 0
    while i < len(tokens):
        # Взять chunk_size токенов
        chunk_tokens = tokens[i:i + chunk_size]
        chunk_text = ' '.join(chunk_tokens)
        chunks.append(chunk_text)

        # Сдвинуть на (chunk_size - overlap) вперёд
        i += (chunk_size - overlap)

        # Если осталось слишком мало токенов для нового чанка - выходим
        if i + overlap >= len(tokens):
            break

    return chunks


def generate_embedding(text: str) -> List[float]:
    """
    Генерировать эмбеддинг через Ollama API.

    Args:
        text: Текст для генерации эмбеддинга

    Returns:
        Вектор эмбеддинга (список чисел)
    """
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                'model': OLLAMA_MODEL,
                'prompt': text
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        return result['embedding']
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise


def init_database() -> sqlite3.Connection:
    """
    Инициализировать SQLite базу данных.

    Returns:
        Соединение с БД
    """
    logger.info(f"Initializing database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Создать таблицу
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS embeddings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chunk_text TEXT NOT NULL,
        embedding BLOB NOT NULL,
        endpoint_path TEXT,
        method TEXT,
        tag TEXT,
        original_json TEXT
    )
    ''')

    # Очистить таблицу если есть старые данные
    cursor.execute('DELETE FROM embeddings')

    conn.commit()
    logger.info("Database initialized")
    return conn


def process_api_spec(spec: dict, conn: sqlite3.Connection):
    """
    Обработать OpenAPI спецификацию и создать индекс.

    Args:
        spec: OpenAPI спецификация
        conn: Соединение с БД
    """
    cursor = conn.cursor()
    total_chunks = 0
    total_endpoints = 0

    paths = spec.get('paths', {})
    logger.info(f"Processing {len(paths)} endpoints...")

    for path, path_data in paths.items():
        for method, endpoint_data in path_data.items():
            # Пропускаем не-методы (например, parameters)
            if method not in ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']:
                continue

            total_endpoints += 1

            # Извлечь метаданные
            tags = endpoint_data.get('tags', [])
            tag = tags[0] if tags else 'Uncategorized'

            # Форматировать endpoint в текст
            endpoint_text = format_endpoint_as_text(path, method, endpoint_data)

            # Сохранить оригинальный JSON
            original_json = json.dumps({
                'path': path,
                'method': method,
                'data': endpoint_data
            }, ensure_ascii=False)

            logger.info(f"Processing: {method.upper()} {path}")

            # Разбить на чанки
            chunks = chunk_text(endpoint_text)

            if not chunks:
                # Если текст короткий и не разбился на чанки
                chunks = [endpoint_text]

            logger.info(f"  Created {len(chunks)} chunk(s)")

            # Для каждого чанка: генерировать эмбеддинг и сохранить
            for chunk_idx, chunk_text in enumerate(chunks):
                logger.info(f"  Generating embedding for chunk {chunk_idx + 1}/{len(chunks)}...")

                try:
                    # Генерировать эмбеддинг
                    embedding = generate_embedding(chunk_text)
                    embedding_blob = pickle.dumps(embedding)

                    # Сохранить в БД
                    cursor.execute('''
                    INSERT INTO embeddings (chunk_text, embedding, endpoint_path, method, tag, original_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        chunk_text,
                        embedding_blob,
                        path,
                        method.upper(),
                        tag,
                        original_json
                    ))

                    total_chunks += 1

                except Exception as e:
                    logger.error(f"  Failed to process chunk {chunk_idx + 1}: {e}")
                    continue

            # Commit после каждого endpoint
            conn.commit()

    logger.info("=" * 60)
    logger.info(f"Processing complete!")
    logger.info(f"Total endpoints processed: {total_endpoints}")
    logger.info(f"Total chunks created: {total_chunks}")
    logger.info(f"Database saved to: {DB_PATH}")
    logger.info("=" * 60)


def main():
    """Главная функция."""
    logger.info("=" * 60)
    logger.info("День 16: Создание индекса документов")
    logger.info("Pond Mobile API Documentation → Embeddings")
    logger.info("=" * 60)
    logger.info(f"Ollama API: {OLLAMA_API_URL}")
    logger.info(f"Model: {OLLAMA_MODEL}")
    logger.info(f"Chunk size: {CHUNK_SIZE} tokens")
    logger.info(f"Chunk overlap: {CHUNK_OVERLAP} tokens")
    logger.info("=" * 60)

    # Проверить доступность Ollama
    try:
        logger.info("Testing Ollama API connection...")
        test_embedding = generate_embedding("test")
        logger.info(f"✓ Ollama API is available (embedding dim: {len(test_embedding)})")
    except Exception as e:
        logger.error(f"✗ Ollama API is not available: {e}")
        logger.error("Please ensure Ollama is running and nomic-embed-text model is installed")
        return

    # Загрузить API спецификацию
    spec = load_api_spec()

    # Инициализировать БД
    conn = init_database()

    try:
        # Обработать спецификацию
        process_api_spec(spec, conn)
    finally:
        conn.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    main()
