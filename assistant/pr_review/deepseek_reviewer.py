"""
DeepSeek Review Generator

Генерирует code review используя DeepSeek API с учетом правил из CODE_STYLE.md.

Стратегия:
- Structured prompt (system + user messages)
- Temperature 0.3 для consistency
- Max tokens 3000 для детального ревью
- Parsing итога: APPROVED/CHANGES_REQUESTED/COMMENT
"""

import requests
import json
import logging
import re
from typing import Dict, List, Tuple, Optional

from .config import (
    DEEPSEEK_API_URL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    REVIEW_TEMPERATURE,
    REVIEW_MAX_TOKENS
)

logger = logging.getLogger(__name__)


# System prompt для ревьюера
SYSTEM_PROMPT = """Ты — эксперт по code review для проекта AIBot.

ТВОЯ ЗАДАЧА:
1. Проверить код на соответствие CODE_STYLE.md
2. Найти потенциальные ошибки и проблемы
3. Дать конструктивные рекомендации

ФОРМАТ ОТВЕТА:
## ✅ Положительные моменты
- Что сделано хорошо (минимум 1-2 пункта)

## ⚠️ Замечания

### Критические
- [file.py:123] Описание проблемы
  **Правило:** [цитата из CODE_STYLE.md или описание правила]
  **Рекомендация:** конкретное исправление

### Рекомендации
- [file.py:456] Предложение по улучшению
  **Пояснение:** почему это улучшит код

## 📊 Итого
Общая оценка: [APPROVED/CHANGES_REQUESTED/COMMENT]

**Краткое резюме:** 1-2 предложения о качестве кода

ПРИНЦИПЫ РЕВЬЮ:
- Будь конкретным (указывай файл и строку)
- Цитируй CODE_STYLE.md для обоснования
- Объясняй "почему", не только "что"
- Предлагай решения, не только критикуй
- Находи и хорошее: что сделано правильно
- Если правила из CODE_STYLE не нарушены, пиши APPROVED

КРИТЕРИИ ОЦЕНКИ:
- APPROVED: Код соответствует стандартам, нет критических замечаний
- CHANGES_REQUESTED: Есть критические проблемы, требующие исправления
- COMMENT: Есть рекомендации, но код можно принять
"""


class DeepSeekReviewer:
    """
    DeepSeek API клиент для генерации code review.

    Использует structured prompting для получения качественных ревью.
    """

    def __init__(
        self,
        api_key: str = DEEPSEEK_API_KEY,
        api_url: str = DEEPSEEK_API_URL,
        model: str = DEEPSEEK_MODEL
    ):
        """
        Инициализация ревьюера.

        Args:
            api_key: DeepSeek API key
            api_url: DeepSeek API URL
            model: Имя модели
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model = model

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is required")

    def generate_review(
        self,
        diff: str,
        rules_context: str,
        pr_info: Dict
    ) -> Tuple[str, Dict]:
        """
        Генерировать code review для PR.

        Args:
            diff: Diff содержимое PR
            rules_context: Релевантные правила из CODE_STYLE.md
            pr_info: Информация о PR (base, head, files, etc.)

        Returns:
            Tuple[review_text, token_usage]:
                - review_text: Текст ревью в Markdown
                - token_usage: Статистика токенов
        """
        logger.info(f"Generating review for PR: {pr_info.get('base')}...{pr_info.get('head')}")

        # 1. Построить промпт
        messages = self._build_messages(diff, rules_context, pr_info)

        # 2. Вызвать DeepSeek API
        review_text, token_usage = self._call_deepseek_api(messages)

        # 3. Валидировать и улучшить ответ если нужно
        review_text = self._post_process_review(review_text)

        logger.info(f"Review generated: {len(review_text)} chars")
        logger.info(f"Token usage: {token_usage}")

        return review_text, token_usage

    def _build_messages(
        self,
        diff: str,
        rules_context: str,
        pr_info: Dict
    ) -> List[Dict]:
        """
        Построить messages для DeepSeek API.

        Args:
            diff: Diff содержимое
            rules_context: Правила из CODE_STYLE.md
            pr_info: Информация о PR

        Returns:
            Список messages в формате DeepSeek API
        """
        # System message
        system_message = {
            "role": "system",
            "content": SYSTEM_PROMPT
        }

        # User message с контекстом
        user_content = f"""
=== ИНФОРМАЦИЯ О PR ===
Branch: {pr_info.get('head', 'unknown')} → {pr_info.get('base', 'unknown')}
Измененных файлов: {pr_info.get('files_count', 0)}
Размер diff: {len(diff)} символов

{rules_context}

=== ИЗМЕНЕННЫЙ КОД ===
```diff
{diff}
```

Проведи code review, используя правила из CODE_STYLE.md выше.
Обрати внимание на:
1. Соответствие правилам стиля
2. Качество кода
3. Потенциальные проблемы
4. Что сделано хорошо

Следуй формату ответа из system prompt.
""".strip()

        user_message = {
            "role": "user",
            "content": user_content
        }

        return [system_message, user_message]

    def _call_deepseek_api(self, messages: List[Dict]) -> Tuple[str, Dict]:
        """
        Вызвать DeepSeek API.

        Args:
            messages: Список messages

        Returns:
            Tuple[response_text, token_usage]
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": REVIEW_TEMPERATURE,
            "max_tokens": REVIEW_MAX_TOKENS
        }

        try:
            logger.info(f"Calling DeepSeek API with {len(messages)} messages")
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=60  # 60 секунд timeout
            )
            response.raise_for_status()
            result = response.json()

            # Извлечь текст ответа
            response_text = result['choices'][0]['message']['content']

            # Извлечь статистику токенов
            usage = result.get('usage', {})
            token_usage = {
                'total_tokens': usage.get('total_tokens', 0),
                'prompt_tokens': usage.get('prompt_tokens', 0),
                'completion_tokens': usage.get('completion_tokens', 0)
            }

            logger.info(
                f"API call successful: "
                f"{token_usage['total_tokens']} tokens "
                f"({token_usage['prompt_tokens']} prompt + "
                f"{token_usage['completion_tokens']} completion)"
            )

            return response_text, token_usage

        except requests.exceptions.Timeout:
            logger.error("DeepSeek API timeout")
            return (
                "⚠️ Review timeout: DeepSeek API не ответил вовремя. Попробуйте позже.",
                {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"DeepSeek API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            return (
                f"⚠️ Review error: {str(e)}",
                {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return (
                f"⚠️ Unexpected error during review: {str(e)}",
                {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
            )

    def _post_process_review(self, review_text: str) -> str:
        """
        Post-processing ревью для улучшения качества.

        Args:
            review_text: Сырой текст ревью от DeepSeek

        Returns:
            Обработанный текст ревью
        """
        # Убрать лишние пустые строки
        review_text = re.sub(r'\n{3,}', '\n\n', review_text)

        # Убрать trailing whitespace
        lines = [line.rstrip() for line in review_text.split('\n')]
        review_text = '\n'.join(lines)

        # Добавить footer если его нет
        if "🤖" not in review_text and "Generated" not in review_text:
            review_text += "\n\n---\n🤖 Generated with AI Code Review (DeepSeek API + RAG)"

        return review_text.strip()

    def parse_review_decision(self, review_text: str) -> str:
        """
        Извлечь решение ревью из текста.

        Args:
            review_text: Текст ревью

        Returns:
            "APPROVE", "REQUEST_CHANGES", или "COMMENT"
        """
        # Поиск секции "Итого"
        match = re.search(
            r'##?\s*📊?\s*Итого.*?:\s*(APPROVED|CHANGES_REQUESTED|COMMENT)',
            review_text,
            re.IGNORECASE | re.DOTALL
        )

        if match:
            decision = match.group(1).upper()
            logger.info(f"Parsed decision: {decision}")

            # Преобразовать в GitHub event type
            if decision == "APPROVED":
                return "APPROVE"
            elif decision == "CHANGES_REQUESTED":
                return "REQUEST_CHANGES"
            else:
                return "COMMENT"

        # Fallback: искать критические замечания
        if re.search(r'###\s*Критические', review_text, re.IGNORECASE):
            logger.info("Found critical issues, requesting changes")
            return "REQUEST_CHANGES"

        # Fallback: если нет критических, это COMMENT
        logger.info("No explicit decision found, defaulting to COMMENT")
        return "COMMENT"


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Тестовые данные
    test_diff = """
+def calculate_sum(a, b):
+    return a + b
    """.strip()

    test_rules = """
## Релевантные правила из CODE_STYLE.md

### Документация
Docstring обязательны для всех публичных функций.

### Type Hints
Обязательны для параметров функций и возвращаемых значений.
    """.strip()

    test_pr_info = {
        "base": "main",
        "head": "feature/test",
        "files_count": 1
    }

    # Создать ревьюер
    try:
        reviewer = DeepSeekReviewer()

        # Генерировать ревью
        review, usage = reviewer.generate_review(test_diff, test_rules, test_pr_info)

        print("\n=== GENERATED REVIEW ===")
        print(review)
        print(f"\n=== TOKEN USAGE ===")
        print(f"Total: {usage['total_tokens']}")
        print(f"Prompt: {usage['prompt_tokens']}")
        print(f"Completion: {usage['completion_tokens']}")

        print(f"\n=== DECISION ===")
        decision = reviewer.parse_review_decision(review)
        print(f"Decision: {decision}")

    except ValueError as e:
        print(f"Error: {e}")
        print("Set DEEPSEEK_API_KEY environment variable to test")
