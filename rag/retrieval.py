#!/usr/bin/env python3
"""
День 17: RAG Retrieval
Поиск релевантных чанков документации по запросу пользователя
"""

import sqlite3
import pickle
import requests
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# Конфигурация
DB_PATH = Path(__file__).parent / "db.sqlite3"
OLLAMA_API_URL = "http://127.0.0.1:11434/api/embeddings"
OLLAMA_MODEL = "nomic-embed-text"
TOP_K = 3  # Количество релевантных чанков для возврата


def generate_query_embedding(query: str) -> List[float]:
    """
    Генерировать эмбеддинг для запроса пользователя.

    Args:
        query: Вопрос пользователя

    Returns:
        Вектор эмбеддинга
    """
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                'model': OLLAMA_MODEL,
                'prompt': query
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        return result['embedding']
    except Exception as e:
        logger.error(f"Error generating query embedding: {e}")
        raise


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Вычислить косинусное сходство между двумя векторами.

    Args:
        vec1: Первый вектор
        vec2: Второй вектор

    Returns:
        Косинусное сходство (от -1 до 1)
    """
    # Конвертировать в numpy arrays
    v1 = np.array(vec1)
    v2 = np.array(vec2)

    # Косинусное сходство = dot product / (norm1 * norm2)
    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


def search_relevant_chunks(
    query: str,
    top_k: int = TOP_K,
    min_similarity: float = 0.3
) -> List[Dict]:
    """
    Поиск релевантных чанков документации по запросу.

    Args:
        query: Вопрос пользователя
        top_k: Количество результатов для возврата
        min_similarity: Минимальное косинусное сходство

    Returns:
        Список релевантных чанков с метаданными и оценкой релевантности
    """
    logger.info(f"Searching for relevant chunks: '{query}'")

    # 1. Генерировать эмбеддинг для запроса
    try:
        query_embedding = generate_query_embedding(query)
    except Exception as e:
        logger.error(f"Failed to generate query embedding: {e}")
        return []

    # 2. Загрузить все эмбеддинги из БД
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, chunk_text, embedding, endpoint_path, method, tag, original_json
        FROM embeddings
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        logger.warning("No embeddings found in database")
        return []

    logger.info(f"Loaded {len(rows)} embeddings from database")

    # 3. Вычислить косинусное сходство для каждого чанка
    similarities = []

    for row in rows:
        id, chunk_text, embedding_blob, endpoint_path, method, tag, original_json = row

        try:
            # Распаковать эмбеддинг
            chunk_embedding = pickle.loads(embedding_blob)

            # Вычислить сходство
            similarity = cosine_similarity(query_embedding, chunk_embedding)

            # Сохранить только если выше минимального порога
            if similarity >= min_similarity:
                similarities.append({
                    'id': id,
                    'chunk_text': chunk_text,
                    'endpoint_path': endpoint_path,
                    'method': method,
                    'tag': tag,
                    'original_json': original_json,
                    'similarity': similarity
                })
        except Exception as e:
            logger.warning(f"Failed to process chunk {id}: {e}")
            continue

    # 4. Сортировать по убыванию релевантности
    similarities.sort(key=lambda x: x['similarity'], reverse=True)

    # 5. Вернуть топ-K результатов
    top_results = similarities[:top_k]

    logger.info(f"Found {len(similarities)} chunks above threshold, returning top {len(top_results)}")

    for i, result in enumerate(top_results, 1):
        logger.info(
            f"  {i}. {result['method']} {result['endpoint_path']} "
            f"(similarity: {result['similarity']:.3f})"
        )

    return top_results


def format_context_for_llm(chunks: List[Dict]) -> str:
    """
    Форматировать релевантные чанки в контекст для LLM.

    Args:
        chunks: Список релевантных чанков

    Returns:
        Отформатированный контекст
    """
    if not chunks:
        return ""

    context_parts = [
        "# Релевантная документация Pond Mobile API\n",
        "Ниже представлены фрагменты документации, которые могут помочь ответить на вопрос:\n"
    ]

    for i, chunk in enumerate(chunks, 1):
        context_parts.append(f"\n## Фрагмент {i} (релевантность: {chunk['similarity']:.2%})")
        context_parts.append(f"Endpoint: {chunk['method']} {chunk['endpoint_path']}")
        context_parts.append(f"Категория: {chunk['tag']}")
        context_parts.append(f"\n{chunk['chunk_text']}")
        context_parts.append("\n" + "=" * 60)

    return "\n".join(context_parts)


def rag_query(question: str, top_k: int = TOP_K) -> Tuple[str, List[Dict]]:
    """
    Выполнить RAG-запрос: найти релевантные чанки и сформировать контекст.

    Args:
        question: Вопрос пользователя
        top_k: Количество релевантных чанков

    Returns:
        Tuple[context, chunks] - контекст для LLM и список чанков
    """
    # Поиск релевантных чанков
    relevant_chunks = search_relevant_chunks(question, top_k=top_k)

    if not relevant_chunks:
        logger.warning("No relevant chunks found")
        return "", []

    # Форматирование контекста
    context = format_context_for_llm(relevant_chunks)

    return context, relevant_chunks


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Примеры запросов
    test_queries = [
        "How do I get a list of SIM cards?",
        "How to transfer SIMs between inventories?",
        "What endpoints are available for managing countries?",
        "How do I create a new eSIM?",
    ]

    for query in test_queries:
        print("\n" + "=" * 80)
        print(f"Query: {query}")
        print("=" * 80)

        context, chunks = rag_query(query, top_k=3)

        if chunks:
            print(f"\nFound {len(chunks)} relevant chunks:")
            for i, chunk in enumerate(chunks, 1):
                print(f"\n{i}. {chunk['method']} {chunk['endpoint_path']}")
                print(f"   Similarity: {chunk['similarity']:.3f}")
                print(f"   Preview: {chunk['chunk_text'][:200]}...")
        else:
            print("\nNo relevant chunks found")
