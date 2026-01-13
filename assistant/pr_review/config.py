"""
Configuration module for PR Review automation
Константы и настройки для системы автоматического ревью
"""

import os
from pathlib import Path

# Пути
PROJECT_ROOT = Path(__file__).parent.parent.parent
CODE_STYLE_PATH = PROJECT_ROOT / "CODE_STYLE.md"
RAG_DB_PATH = PROJECT_ROOT / "rag" / "db.sqlite3"

# MCP Server
MCP_GIT_SERVER_URL = os.getenv("MCP_GIT_SERVER_URL", "ws://localhost:8082/mcp")
MCP_CONNECTION_TIMEOUT = int(os.getenv("MCP_CONNECTION_TIMEOUT", "30"))
MCP_MAX_RETRIES = int(os.getenv("MCP_MAX_RETRIES", "3"))

# RAG System
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_MIN_SIMILARITY = float(os.getenv("RAG_MIN_SIMILARITY", "0.3"))
RAG_FILTERING_MODE = os.getenv("RAG_FILTERING_MODE", "hybrid")
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "800"))

# Ollama
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://127.0.0.1:11434/api/embeddings")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "nomic-embed-text")

# DeepSeek API
DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL",
    "https://api.deepseek.com/v1/chat/completions"
)
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
REVIEW_TEMPERATURE = float(os.getenv("REVIEW_TEMPERATURE", "0.3"))
REVIEW_MAX_TOKENS = int(os.getenv("REVIEW_MAX_TOKENS", "3000"))

# GitHub API
GITHUB_API_BASE = os.getenv("GITHUB_API_BASE", "https://api.github.com")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")  # format: owner/repo

# PR Review Constraints
MAX_FILES_TO_REVIEW = int(os.getenv("MAX_FILES_TO_REVIEW", "20"))
MAX_DIFF_SIZE_CHARS = int(os.getenv("MAX_DIFF_SIZE_CHARS", "50000"))
SUPPORTED_FILE_EXTENSIONS = [".py"]

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Validation
def validate_config():
    """Проверить обязательные переменные окружения."""
    errors = []

    if not DEEPSEEK_API_KEY:
        errors.append("DEEPSEEK_API_KEY is required")

    if not CODE_STYLE_PATH.exists():
        errors.append(f"CODE_STYLE.md not found at {CODE_STYLE_PATH}")

    # GitHub token опционален для локального тестирования
    # но обязателен для CI

    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")

if __name__ == "__main__":
    # Проверка конфигурации
    try:
        validate_config()
        print("✅ Configuration valid")
        print(f"MCP Server: {MCP_GIT_SERVER_URL}")
        print(f"CODE_STYLE: {CODE_STYLE_PATH}")
        print(f"RAG DB: {RAG_DB_PATH}")
        print(f"DeepSeek API Key: {'***' if DEEPSEEK_API_KEY else 'NOT SET'}")
    except ValueError as e:
        print(f"❌ {e}")
