"""
PR Review Automation Package
День 21: Автоматизация ревью кода

Автоматическая проверка Pull Requests с использованием:
- Git MCP Server для получения diff и файлов
- RAG для поиска релевантных правил из CODE_STYLE.md
- DeepSeek API для генерации ревью
- GitHub API для публикации комментариев

Modules:
    review_orchestrator: Главный координатор процесса ревью
    mcp_client: WebSocket клиент для Git MCP Server
    rag_code_style: RAG система для CODE_STYLE.md
    deepseek_reviewer: DeepSeek API интеграция
    github_api: GitHub API клиент
    config: Конфигурация и константы
"""

__version__ = "1.0.0"
__author__ = "AIBot Team"

from .config import (
    MCP_GIT_SERVER_URL,
    DEEPSEEK_API_URL,
    GITHUB_API_BASE
)

__all__ = [
    'MCP_GIT_SERVER_URL',
    'DEEPSEEK_API_URL',
    'GITHUB_API_BASE',
]
