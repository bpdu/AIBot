"""
RAG система для поиска релевантных правил из CODE_STYLE.md

Использует embeddings созданные index_code_style.py для поиска
релевантных правил стиля во время ревью PR.

Стратегия retrieval:
- Top-K = 5 (больше чем обычно для покрытия разных аспектов)
- Min similarity = 0.3
- Hybrid filtering (strict 0.50 + adaptive 85%)
"""

import sqlite3
import pickle
import requests
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "rag" / "db.sqlite3"
OLLAMA_API_URL = "http://127.0.0.1:11434/api/embeddings"
OLLAMA_MODEL = "nomic-embed-text"

# Retrieval parameters
TOP_K = 5
MIN_SIMILARITY = 0.3
MIN_SIMILARITY_STRICT = 0.50
ADAPTIVE_THRESHOLD_PERCENTILE = 0.85


def generate_query_embedding(query: str) -> List[float]:
    """
    Генерировать embedding для запроса.

    Args:
        query: Запрос пользователя

    Returns:
        Вектор embedding

    Raises:
        ConnectionError: Если Ollama недоступна
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
        raise ConnectionError(f"Failed to generate embedding: {e}")


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Вычислить косинусное сходство между векторами.

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


def search_code_style_rules(
    query: str,
    top_k: int = TOP_K,
    min_similarity: float = MIN_SIMILARITY,
    enable_filtering: bool = True
) -> Tuple[List[Dict], Dict]:
    """
    Поиск релевантных правил стиля для кода.

    Args:
        query: Описание кода или проблемы
        top_k: Количество результатов
        min_similarity: Минимальное сходство
        enable_filtering: Применить двухэтапную фильтрацию

    Returns:
        Tuple[rules, stats]:
            - rules: Список релевантных правил с метаданными
            - stats: Статистика фильтрации

    Raises:
        ConnectionError: Если Ollama недоступна
    """
    logger.info(f"Searching CODE_STYLE rules for: '{query[:100]}...'")

    # 1. Генерировать embedding для запроса
    try:
        query_embedding = generate_query_embedding(query)
    except ConnectionError as e:
        logger.error(f"Failed to generate query embedding: {e}")
        raise

    # 2. Загрузить все embeddings из БД
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, heading, level, line_range, chunk_text, embedding
        FROM code_style
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        logger.warning("No code_style embeddings found in database")
        return [], {"total": 0, "filtered": 0, "mode": "none"}

    logger.info(f"Loaded {len(rows)} embeddings from database")

    # 3. Вычислить косинусное сходство для каждого правила
    similarities = []

    for row in rows:
        rule_id, heading, level, line_range, chunk_text, embedding_blob = row

        try:
            chunk_embedding = pickle.loads(embedding_blob)
            similarity = cosine_similarity(query_embedding, chunk_embedding)

            if similarity >= min_similarity:
                similarities.append({
                    'id': rule_id,
                    'heading': heading,
                    'level': level,
                    'line_range': line_range,
                    'chunk_text': chunk_text,
                    'similarity': similarity
                })
        except Exception as e:
            logger.warning(f"Failed to process rule {rule_id}: {e}")
            continue

    # 4. Сортировать по убыванию релевантности
    similarities.sort(key=lambda x: x['similarity'], reverse=True)

    initial_count = len(similarities)
    logger.info(f"Found {initial_count} rules above similarity {min_similarity}")

    # 5. Применить hybrid filtering
    if enable_filtering and similarities:
        similarities = apply_hybrid_filtering(similarities, top_k)

    # 6. Вернуть топ-K результатов
    top_results = similarities[:top_k]

    logger.info(f"Returning {len(top_results)} rules after filtering")

    for i, result in enumerate(top_results, 1):
        logger.info(
            f"  {i}. {result['heading'][:50]} "
            f"(similarity: {result['similarity']:.3f}, lines: {result['line_range']})"
        )

    stats = {
        "total": initial_count,
        "filtered": len(similarities),
        "returned": len(top_results),
        "mode": "hybrid" if enable_filtering else "simple"
    }

    return top_results, stats


def apply_hybrid_filtering(similarities: List[Dict], top_k: int) -> List[Dict]:
    """
    Применить гибридную фильтрацию (strict + adaptive).

    Стратегия:
    1. Strict threshold: 0.50 (удалить явно нерелевантные)
    2. Adaptive threshold: 85% от top score (сохранить связанные правила)

    Args:
        similarities: Список результатов с similarity scores
        top_k: Целевое количество результатов

    Returns:
        Отфильтрованный список
    """
    if not similarities:
        return []

    # Этап 1: Strict filtering
    strict_filtered = [
        s for s in similarities
        if s['similarity'] >= MIN_SIMILARITY_STRICT
    ]

    if not strict_filtered:
        logger.warning(f"No results above strict threshold {MIN_SIMILARITY_STRICT}")
        # Fallback: вернуть хотя бы top результаты
        return similarities[:top_k]

    # Этап 2: Adaptive filtering
    top_score = strict_filtered[0]['similarity']
    adaptive_threshold = top_score * ADAPTIVE_THRESHOLD_PERCENTILE

    adaptive_filtered = [
        s for s in strict_filtered
        if s['similarity'] >= adaptive_threshold
    ]

    logger.info(
        f"Hybrid filtering: {len(similarities)} → "
        f"{len(strict_filtered)} (strict) → "
        f"{len(adaptive_filtered)} (adaptive)"
    )

    return adaptive_filtered


def build_style_query_from_diff(diff_content: str, file_path: str = "") -> str:
    """
    Построить запрос для RAG из diff содержимого.

    Анализирует diff и определяет типы изменений для поиска релевантных правил.

    Args:
        diff_content: Содержимое diff
        file_path: Путь к файлу (опционально)

    Returns:
        Оптимизированный запрос для RAG
    """
    # Определить типы изменений в diff
    patterns = {
        'import': r'^\+import |^\+from .* import',
        'function': r'^\+def ',
        'class': r'^\+class ',
        'docstring': r'^\+\s+"""',
        'comment': r'^\+\s*#',
        'type_hint': r': \w+|-> \w+',
        'error_handling': r'^\+\s*(try:|except|raise)',
        'logging': r'logger\.|logging\.',
    }

    detected_patterns = []
    for pattern_name, pattern_regex in patterns.items():
        import re
        if re.search(pattern_regex, diff_content, re.MULTILINE):
            detected_patterns.append(pattern_name)

    # Построить запрос на основе обнаруженных паттернов
    if detected_patterns:
        query_parts = [
            f"Python code review for {file_path if file_path else 'file'}:",
            f"Code patterns: {', '.join(detected_patterns)}",
            "Need rules about: " + ", ".join([
                "naming" if any(p in detected_patterns for p in ['function', 'class']) else "",
                "documentation" if 'docstring' in detected_patterns else "",
                "error handling" if 'error_handling' in detected_patterns else "",
                "imports" if 'import' in detected_patterns else "",
                "type hints" if 'type_hint' in detected_patterns else "",
            ]).replace(", , ", ", ").strip(", ")
        ]
        query = " ".join(query_parts)
    else:
        # Fallback: общий запрос
        query = f"Python style guide rules for code review of {file_path if file_path else 'Python file'}"

    logger.debug(f"Built query: {query}")
    return query


def format_rules_for_llm(rules: List[Dict]) -> str:
    """
    Форматировать релевантные правила для промпта LLM.

    Args:
        rules: Список релевантных правил

    Returns:
        Отформатированный контекст для DeepSeek
    """
    if not rules:
        return "No specific CODE_STYLE rules found for this code."

    context_parts = [
        "=== РЕЛЕВАНТНЫЕ ПРАВИЛА ИЗ CODE_STYLE.md ===\n",
        f"Найдено {len(rules)} релевантных правил:\n"
    ]

    for i, rule in enumerate(rules, 1):
        context_parts.append(
            f"\n## Правило {i} (релевантность: {rule['similarity']:.2%})"
        )
        context_parts.append(f"**Раздел:** {rule['heading']}")
        context_parts.append(f"**Строки:** {rule['line_range']}")
        context_parts.append(f"\n{rule['chunk_text']}")
        context_parts.append("\n" + "=" * 60)

    return "\n".join(context_parts)


def get_rules_for_pr_review(
    diff_content: str,
    file_path: str = "",
    top_k: int = TOP_K
) -> Tuple[str, List[Dict], Dict]:
    """
    Получить релевантные правила для ревью PR.

    Полный workflow:
    1. Построить запрос из diff
    2. Поиск релевантных правил через RAG
    3. Форматировать контекст для LLM

    Args:
        diff_content: Содержимое diff
        file_path: Путь к файлу
        top_k: Количество правил

    Returns:
        Tuple[context, rules, stats]:
            - context: Форматированный контекст для LLM
            - rules: Список правил с метаданными
            - stats: Статистика поиска
    """
    # 1. Построить запрос
    query = build_style_query_from_diff(diff_content, file_path)

    # 2. Поиск правил
    try:
        rules, stats = search_code_style_rules(query, top_k=top_k)
    except ConnectionError as e:
        logger.error(f"RAG search failed: {e}")
        return "CODE_STYLE rules unavailable (Ollama connection error)", [], {}

    # 3. Форматировать контекст
    context = format_rules_for_llm(rules)

    return context, rules, stats


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Примеры запросов
    test_queries = [
        "function without docstring",
        "import statements ordering",
        "error handling with try except",
        "type hints for function parameters",
        "naming convention for variables and functions"
    ]

    for query in test_queries:
        print("\n" + "=" * 80)
        print(f"Query: {query}")
        print("=" * 80)

        try:
            rules, stats = search_code_style_rules(query, top_k=3)

            print(f"\nFound {len(rules)} rules:")
            for i, rule in enumerate(rules, 1):
                print(f"\n{i}. {rule['heading']}")
                print(f"   Similarity: {rule['similarity']:.3f}")
                print(f"   Lines: {rule['line_range']}")
                print(f"   Preview: {rule['chunk_text'][:150]}...")

            print(f"\nStats: {stats}")
        except Exception as e:
            print(f"Error: {e}")
