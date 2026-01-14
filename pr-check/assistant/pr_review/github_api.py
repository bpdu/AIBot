"""
GitHub API Integration для PR Review

Интеграция с GitHub API для публикации code review в Pull Requests.

Функции:
- Получение информации о PR
- Публикация review комментариев
- Поддержка review events: APPROVE, REQUEST_CHANGES, COMMENT
"""

import requests
import logging
from typing import Dict, Optional

from .config import (
    GITHUB_API_BASE,
    GITHUB_TOKEN,
    GITHUB_REPOSITORY
)

logger = logging.getLogger(__name__)


class GitHubAPIClient:
    """
    GitHub API клиент для работы с Pull Requests.

    Использует GitHub REST API v3 для публикации ревью.
    """

    def __init__(
        self,
        token: str = GITHUB_TOKEN,
        repository: str = GITHUB_REPOSITORY,
        api_base: str = GITHUB_API_BASE
    ):
        """
        Инициализация клиента.

        Args:
            token: GitHub API token (GITHUB_TOKEN)
            repository: Repository в формате "owner/repo"
            api_base: Base URL для GitHub API

        Raises:
            ValueError: Если token или repository не заданы
        """
        if not token:
            raise ValueError("GITHUB_TOKEN is required")
        if not repository:
            raise ValueError("GITHUB_REPOSITORY is required (format: owner/repo)")

        self.token = token
        self.repository = repository
        self.api_base = api_base

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    def get_pr_details(self, pr_number: int) -> Optional[Dict]:
        """
        Получить детальную информацию о PR.

        Args:
            pr_number: Номер Pull Request

        Returns:
            Dict с информацией о PR или None при ошибке
            {
                "number": int,
                "title": str,
                "body": str,
                "state": str,
                "user": {...},
                "base": {"ref": str, ...},
                "head": {"ref": str, ...},
                ...
            }
        """
        url = f"{self.api_base}/repos/{self.repository}/pulls/{pr_number}"

        logger.info(f"Getting PR details: {url}")

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            pr_data = response.json()
            logger.info(f"PR #{pr_number}: {pr_data.get('title')}")

            return pr_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get PR details: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def get_pr_diff(self, pr_number: int) -> Optional[str]:
        """
        Получить diff для PR через GitHub API.

        Args:
            pr_number: Номер Pull Request

        Returns:
            Строка с diff или None при ошибке
        """
        url = f"{self.api_base}/repos/{self.repository}/pulls/{pr_number}"

        # Используем специальный Accept header для получения diff
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.v3.diff"

        logger.info(f"Getting PR diff from GitHub API: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()

            diff = response.text
            logger.info(f"✅ Diff received: {len(diff)} chars")

            return diff

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get PR diff: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def post_review(
        self,
        pr_number: int,
        body: str,
        event: str = "COMMENT"
    ) -> Optional[Dict]:
        """
        Опубликовать review в PR.

        Args:
            pr_number: Номер Pull Request
            body: Текст ревью в Markdown
            event: Тип review event:
                - "APPROVE": одобрить PR
                - "REQUEST_CHANGES": запросить изменения
                - "COMMENT": оставить комментарий

        Returns:
            Dict с информацией о созданном ревью или None при ошибке
        """
        url = f"{self.api_base}/repos/{self.repository}/pulls/{pr_number}/reviews"

        # Валидация event
        valid_events = ["APPROVE", "REQUEST_CHANGES", "COMMENT"]
        if event not in valid_events:
            logger.warning(f"Invalid event '{event}', using COMMENT")
            event = "COMMENT"

        payload = {
            "body": body,
            "event": event
        }

        logger.info(f"Posting {event} review to PR #{pr_number}")
        logger.debug(f"Review body length: {len(body)} chars")

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            review_data = response.json()
            logger.info(f"Review posted successfully: {review_data.get('id')}")

            return review_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to post review: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            return None

    def post_comment(
        self,
        pr_number: int,
        body: str
    ) -> Optional[Dict]:
        """
        Опубликовать простой комментарий (не review) в PR.

        Args:
            pr_number: Номер Pull Request
            body: Текст комментария в Markdown

        Returns:
            Dict с информацией о комментарии или None при ошибке
        """
        url = f"{self.api_base}/repos/{self.repository}/issues/{pr_number}/comments"

        payload = {"body": body}

        logger.info(f"Posting comment to PR #{pr_number}")

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            comment_data = response.json()
            logger.info(f"Comment posted successfully: {comment_data.get('id')}")

            return comment_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to post comment: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    def check_rate_limit(self) -> Optional[Dict]:
        """
        Проверить rate limit для API.

        Returns:
            Dict с информацией о rate limit:
            {
                "limit": int,
                "remaining": int,
                "reset": int (Unix timestamp)
            }
        """
        url = f"{self.api_base}/rate_limit"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            rate_data = response.json()
            core_limit = rate_data.get('resources', {}).get('core', {})

            logger.info(
                f"Rate limit: {core_limit.get('remaining')}/{core_limit.get('limit')}"
            )

            return core_limit

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to check rate limit: {e}")
            return None


def format_review_for_github(review_text: str, pr_info: Dict) -> str:
    """
    Форматировать review для публикации в GitHub.

    Добавляет заголовок и footer с дополнительной информацией.

    Args:
        review_text: Текст ревью от DeepSeek
        pr_info: Информация о PR

    Returns:
        Отформатированный текст для GitHub
    """
    header = f"""# 🤖 Automated Code Review

**PR:** `{pr_info.get('base', 'unknown')}` ← `{pr_info.get('head', 'unknown')}`
**Files changed:** {pr_info.get('files_count', 0)}

---

"""

    footer = """

---

<details>
<summary>ℹ️ Как работает этот review?</summary>

Этот автоматический review использует:
- **RAG (Retrieval-Augmented Generation)** для поиска релевантных правил из CODE_STYLE.md
- **Git MCP Server** для получения diff и информации о файлах
- **DeepSeek API** для генерации интеллектуального ревью

Правила стиля берутся из [CODE_STYLE.md](../CODE_STYLE.md) проекта.
</details>
"""

    return header + review_text + footer


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    try:
        # Создать клиент
        client = GitHubAPIClient()

        # Проверить rate limit
        print("\n=== Rate Limit ===")
        rate_limit = client.check_rate_limit()
        if rate_limit:
            print(f"Remaining: {rate_limit.get('remaining')}/{rate_limit.get('limit')}")

        # Получить информацию о PR (укажите реальный номер)
        pr_number = 1  # Замените на реальный номер PR
        print(f"\n=== PR #{pr_number} Details ===")
        pr_data = client.get_pr_details(pr_number)
        if pr_data:
            print(f"Title: {pr_data.get('title')}")
            print(f"State: {pr_data.get('state')}")
            print(f"Base: {pr_data.get('base', {}).get('ref')}")
            print(f"Head: {pr_data.get('head', {}).get('ref')}")
        else:
            print("Failed to get PR details")

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Set GITHUB_TOKEN and GITHUB_REPOSITORY environment variables")
