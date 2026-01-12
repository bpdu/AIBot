#!/usr/bin/env python3
"""
День 20: Ассистент разработчика - Поиск по документации проекта

Поиск релевантных фрагментов из README, ARCHITECTURE, CODE_STYLE
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
TOP_K = 5
MIN_SIMILARITY = 0.4


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
    v1 = np.array(vec1)
    v2 = np.array(vec2)

    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


def search_project_docs(
    query: str,
    top_k: int = TOP_K,
    min_similarity: float = MIN_SIMILARITY
) -> List[Dict]:
    """
    Поиск релевантных фрагментов документации проекта.

    Args:
        query: Вопрос пользователя
        top_k: Количество результатов
        min_similarity: Минимальное сходство

    Returns:
        Список релевантных фрагментов с метаданными
    """
    logger.info(f"Searching project docs for: '{query}'")

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
        SELECT id, doc_name, heading, level, chunk_text, embedding
        FROM project_docs
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        logger.warning("No project docs embeddings found in database")
        return []

    logger.info(f"Loaded {len(rows)} embeddings from database")

    # 3. Вычислить косинусное сходство для каждого чанка
    similarities = []

    for row in rows:
        id, doc_name, heading, level, chunk_text, embedding_blob = row

        try:
            chunk_embedding = pickle.loads(embedding_blob)
            similarity = cosine_similarity(query_embedding, chunk_embedding)

            if similarity >= min_similarity:
                similarities.append({
                    'id': id,
                    'doc_name': doc_name,
                    'heading': heading,
                    'level': level,
                    'chunk_text': chunk_text,
                    'similarity': similarity
                })
        except Exception as e:
            logger.warning(f"Failed to process chunk {id}: {e}")
            continue

    # 4. Сортировать по убыванию релевантности
    similarities.sort(key=lambda x: x['similarity'], reverse=True)

    # 5. Вернуть топ-K результатов
    top_results = similarities[:top_k]

    logger.info(f"Found {len(top_results)} relevant chunks")

    for i, result in enumerate(top_results, 1):
        logger.info(
            f"  {i}. {result['doc_name']} - {result['heading']} "
            f"(similarity: {result['similarity']:.3f})"
        )

    return top_results


def format_project_docs_context(chunks: List[Dict]) -> str:
    """
    Форматировать релевантные фрагменты в контекст для LLM.

    Args:
        chunks: Список релевантных фрагментов

    Returns:
        Отформатированный контекст
    """
    if not chunks:
        return ""

    context_parts = [
        "# Релевантная документация проекта AIBot\n",
        "Ниже представлены фрагменты документации проекта:\n"
    ]

    for i, chunk in enumerate(chunks, 1):
        context_parts.append(f"\n## Фрагмент {i} (релевантность: {chunk['similarity']:.2%})")
        context_parts.append(f"Документ: {chunk['doc_name']}")
        context_parts.append(f"Раздел: {chunk['heading']}")
        context_parts.append(f"\n{chunk['chunk_text']}")
        context_parts.append("\n" + "=" * 60)

    return "\n".join(context_parts)


def query_project_docs(
    question: str,
    top_k: int = TOP_K
) -> Tuple[str, List[Dict]]:
    """
    Выполнить запрос к документации проекта.

    Args:
        question: Вопрос пользователя
        top_k: Количество результатов

    Returns:
        Tuple[context, chunks] - контекст для LLM и список фрагментов
    """
    # Поиск релевантных чанков
    relevant_chunks = search_project_docs(question, top_k=top_k)

    if not relevant_chunks:
        logger.warning("No relevant chunks found")
        return "", []

    # Форматирование контекста
    context = format_project_docs_context(relevant_chunks)

    return context, relevant_chunks


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Примеры запросов
    test_queries = [
        "Как устроена архитектура бота?",
        "Какие есть MCP серверы?",
        "Как добавить новый MCP сервер?",
        "Правила форматирования кода",
        "Как работает RAG система?",
    ]

    for query in test_queries:
        print("\n" + "=" * 80)
        print(f"Query: {query}")
        print("=" * 80)

        context, chunks = query_project_docs(query, top_k=3)

        if chunks:
            print(f"\nНайдено {len(chunks)} релевантных фрагментов:")
            for i, chunk in enumerate(chunks, 1):
                print(f"\n{i}. {chunk['doc_name']} - {chunk['heading']}")
                print(f"   Similarity: {chunk['similarity']:.3f}")
                print(f"   Preview: {chunk['chunk_text'][:200]}...")
        else:
            print("\nNo relevant chunks found")
