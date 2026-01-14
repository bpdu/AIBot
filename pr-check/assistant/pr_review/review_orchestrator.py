#!/usr/bin/env python3
"""
PR Review Orchestrator - главный координатор автоматического ревью

Объединяет все компоненты системы:
- GitHub API для получения diff
- RAG для поиска релевантных правил
- DeepSeek для генерации ревью
- GitHub API для публикации

Entry point для GitHub Actions workflow.
"""

import logging
import sys
import os
from pathlib import Path
from typing import Optional, Dict

# Добавить parent директории в path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from assistant.pr_review.rag_code_style import get_rules_for_pr_review
from assistant.pr_review.deepseek_reviewer import DeepSeekReviewer
from assistant.pr_review.github_api import GitHubAPIClient, format_review_for_github
from assistant.pr_review.config import (
    validate_config,
    MAX_FILES_TO_REVIEW,
    MAX_DIFF_SIZE_CHARS,
    SUPPORTED_FILE_EXTENSIONS
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def review_pull_request(
    pr_number: int,
    repository: str,
    base_branch: str,
    head_branch: str
) -> bool:
    """
    Основная функция для ревью Pull Request.

    Args:
        pr_number: Номер PR
        repository: Repository в формате "owner/repo"
        base_branch: Базовая ветка (например, 'main')
        head_branch: Ветка с изменениями

    Returns:
        True если ревью успешно опубликовано, False иначе
    """
    logger.info(f"=" * 80)
    logger.info(f"Starting PR review: #{pr_number}")
    logger.info(f"Repository: {repository}")
    logger.info(f"Branches: {base_branch}...{head_branch}")
    logger.info(f"=" * 80)

    try:
        # 1. Валидация конфигурации
        logger.info("\n=== Phase 1: Configuration Validation ===")
        try:
            validate_config()
            logger.info("✅ Configuration valid")
        except ValueError as e:
            logger.error(f"❌ Configuration error: {e}")
            return False

        # 2. Получение PR информации через GitHub API
        logger.info("\n=== Phase 2: Fetching PR Details ===")
        github_client = GitHubAPIClient(repository=repository)
        pr_details = github_client.get_pr_details(pr_number)

        if not pr_details:
            logger.error("❌ Failed to get PR details")
            return False

        logger.info(f"✅ PR details: {pr_details.get('title')}")
        logger.info(f"   Files changed: {pr_details.get('changed_files', 0)}")

        # 3. Получение diff через GitHub API (упрощённый подход)
        logger.info("\n=== Phase 3: Fetching PR Diff via GitHub API ===")

        diff = github_client.get_pr_diff(pr_number)

        if not diff:
            logger.error("❌ Failed to get PR diff from GitHub API")
            return False

        logger.info(f"✅ Diff received: {len(diff)} chars")

        # Проверка размера diff
        truncated = False
        if len(diff) > MAX_DIFF_SIZE_CHARS:
            logger.warning(f"⚠️ Diff too large ({len(diff)} > {MAX_DIFF_SIZE_CHARS})")
            diff = diff[:MAX_DIFF_SIZE_CHARS]
            truncated = True

        # 4. Фильтрация файлов (только Python)
        logger.info("\n=== Phase 4: Filtering Files ===")
        changed_files = extract_changed_files_from_diff(diff)
        python_files = [
            f for f in changed_files
            if any(f.endswith(ext) for ext in SUPPORTED_FILE_EXTENSIONS)
        ]

        logger.info(f"Total files changed: {len(changed_files)}")
        logger.info(f"Python files: {len(python_files)}")

        if not python_files:
            logger.info("ℹ️ No Python files to review")
            comment = """## 🤖 Automated Code Review

ℹ️ Нет Python файлов для ревью в этом PR.

Автоматический ревью проверяет только `.py` файлы на соответствие CODE_STYLE.md.
"""
            github_client.post_comment(pr_number, comment)
            return True

        # 5. RAG поиск релевантных правил из CODE_STYLE.md
        logger.info("\n=== Phase 5: RAG Search for Style Rules ===")
        try:
            rules_context, rules, rag_stats = get_rules_for_pr_review(
                diff_content=diff,
                file_path=", ".join(python_files[:3]),  # Первые 3 файла
                top_k=5
            )

            logger.info(f"✅ Found {len(rules)} relevant rules")
            logger.info(f"   RAG stats: {rag_stats}")

            for i, rule in enumerate(rules[:3], 1):
                logger.info(
                    f"   {i}. {rule['heading'][:40]}... "
                    f"(similarity: {rule['similarity']:.3f})"
                )

        except Exception as e:
            logger.error(f"⚠️ RAG search failed: {e}")
            rules_context = "CODE_STYLE rules unavailable (RAG error)"
            rules = []

        # 6. Генерация ревью через DeepSeek
        logger.info("\n=== Phase 6: Generating Review with DeepSeek ===")
        reviewer = DeepSeekReviewer()

        pr_info = {
            "base": base_branch,
            "head": head_branch,
            "files_count": len(python_files),
            "title": pr_details.get("title", ""),
            "truncated": truncated
        }

        review_text, token_usage = reviewer.generate_review(
            diff=diff,
            rules_context=rules_context,
            pr_info=pr_info
        )

        logger.info(f"✅ Review generated: {len(review_text)} chars")
        logger.info(f"   Tokens: {token_usage.get('total_tokens', 0)}")

        # 7. Определение решения (APPROVE/CHANGES_REQUESTED/COMMENT)
        logger.info("\n=== Phase 7: Parsing Review Decision ===")
        decision = reviewer.parse_review_decision(review_text)
        logger.info(f"✅ Decision: {decision}")

        # 8. Форматирование и публикация в GitHub
        logger.info("\n=== Phase 8: Publishing Review to GitHub ===")
        formatted_review = format_review_for_github(review_text, pr_info)

        result = github_client.post_review(
            pr_number=pr_number,
            body=formatted_review,
            event=decision
        )

        if result:
            logger.info(f"✅ Review published successfully (ID: {result.get('id')})")
            logger.info(f"   Event: {decision}")
            logger.info(f"   URL: {result.get('html_url', 'N/A')}")
            return True
        else:
            logger.error("❌ Failed to publish review")
            return False

    except Exception as e:
        logger.error(f"❌ Unexpected error during review: {e}", exc_info=True)
        return False


def extract_changed_files_from_diff(diff: str) -> list:
    """
    Извлечь список измененных файлов из diff.

    Args:
        diff: Git diff содержимое

    Returns:
        Список путей к файлам
    """
    import re

    files = set()

    # Паттерны для поиска файлов в diff
    # diff --git a/file.py b/file.py
    # +++ b/file.py
    patterns = [
        r'diff --git a/(.*?) b/',
        r'\+\+\+ b/(.*?)$'
    ]

    for pattern in patterns:
        matches = re.findall(pattern, diff, re.MULTILINE)
        files.update(matches)

    return sorted(list(files))


def main():
    """
    Main entry point для CLI.

    Использует environment variables:
    - PR_NUMBER: Номер PR (обязательно)
    - GITHUB_REPOSITORY: Repository (owner/repo) (обязательно)
    - PR_BASE: Базовая ветка (опционально, не используется при GitHub API)
    - PR_HEAD: Ветка с изменениями (опционально, по умолчанию "feature")
    """
    # Получить параметры из environment
    pr_number = os.getenv("PR_NUMBER")
    repository = os.getenv("GITHUB_REPOSITORY")
    base_branch = os.getenv("PR_BASE", "main")
    head_branch = os.getenv("PR_HEAD", "feature")

    # Валидация параметров
    if not pr_number:
        logger.error("PR_NUMBER environment variable is required")
        sys.exit(1)

    if not repository:
        logger.error("GITHUB_REPOSITORY environment variable is required")
        sys.exit(1)

    try:
        pr_number = int(pr_number)
    except ValueError:
        logger.error(f"Invalid PR_NUMBER: {pr_number}")
        sys.exit(1)

    # Запуск ревью
    logger.info(f"Starting review for PR #{pr_number}")

    success = review_pull_request(
        pr_number=pr_number,
        repository=repository,
        base_branch=base_branch,
        head_branch=head_branch
    )

    if success:
        logger.info("✅ Review completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Review failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
