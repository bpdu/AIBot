#!/usr/bin/env python3
"""
День 20: Ассистент разработчика - Демонстрация

Демонстрирует работу всех компонентов ассистента разработчика:
1. Git MCP сервер
2. RAG поиск по документации проекта
3. Интеграция с командой /help
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавить пути для импортов
sys.path.append(str(Path(__file__).parent / 'rag'))
sys.path.append(str(Path(__file__).parent / 'mcp'))

from mcp import ClientSession
from mcp.client.websocket import websocket_client
from project_docs_retrieval import query_project_docs


# Цвета для терминала
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """Печать заголовка."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}")
    print(f"{text}")
    print(f"{'='*70}{Colors.ENDC}\n")


def print_section(text):
    """Печать секции."""
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}--- {text} ---{Colors.ENDC}\n")


def print_success(text):
    """Печать успеха."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text):
    """Печать ошибки."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text):
    """Печать предупреждения."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


async def test_git_mcp_server(server_url="ws://localhost:8082/mcp"):
    """
    Тест Git MCP сервера.

    Args:
        server_url: URL WebSocket сервера
    """
    print_section("Git MCP Server Tests")

    try:
        async with websocket_client(server_url) as (read, write):
            async with ClientSession(read, write) as session:
                # Инициализация
                await session.initialize()
                print_success("Connected to Git MCP server")

                # 1. Получить текущую ветку
                print("\n1. Get Current Branch:")
                result = await session.call_tool("get-current-branch", {})
                data = json.loads(result.content[0].text)
                if data.get("success"):
                    print(f"   Branch: {Colors.OKBLUE}{data['branch']}{Colors.ENDC}")
                    print(f"   Repo: {data['repo_path']}")
                else:
                    print_error(f"   Error: {data.get('error')}")

                # 2. Получить статус
                print("\n2. Get Git Status:")
                result = await session.call_tool("get-git-status", {})
                data = json.loads(result.content[0].text)
                if data.get("success"):
                    if data.get("clean"):
                        print_success("   Repository is clean")
                    else:
                        print(f"   Modified: {len(data.get('modified', []))}")
                        print(f"   Added: {len(data.get('added', []))}")
                        print(f"   Untracked: {len(data.get('untracked', []))}")

                # 3. Получить последние коммиты
                print("\n3. Get Recent Commits (last 5):")
                result = await session.call_tool("get-recent-commits", {"count": 5})
                data = json.loads(result.content[0].text)
                if data.get("success"):
                    commits = data.get("commits", [])
                    for i, commit in enumerate(commits, 1):
                        print(f"   {i}. {Colors.OKGREEN}{commit['hash']}{Colors.ENDC} - {commit['message']}")
                        print(f"      by {commit['author']}, {commit['date']}")

                # 4. Получить измененные файлы
                print("\n4. Get Changed Files:")
                result = await session.call_tool("get-changed-files", {})
                data = json.loads(result.content[0].text)
                if data.get("success"):
                    files = data.get("files", [])
                    if files:
                        print(f"   Found {len(files)} changed files:")
                        for f in files[:5]:  # Показать максимум 5
                            print(f"   - {f}")
                    else:
                        print_success("   No changed files")

                # 5. Получить содержимое README
                print("\n5. Get File Content (README.md):")
                result = await session.call_tool("get-file-content", {"file_path": "README.md"})
                data = json.loads(result.content[0].text)
                if data.get("success"):
                    content = data.get("content", "")
                    lines = content.split('\n')
                    print(f"   File size: {data['size']} bytes")
                    print(f"   Preview (first 5 lines):")
                    for line in lines[:5]:
                        print(f"   {line}")
                else:
                    print_error(f"   Error: {data.get('error')}")

                print_success("\n✓ All Git MCP tests passed!")

    except Exception as e:
        print_error(f"Git MCP server error: {e}")
        print_warning("Make sure Git MCP server is running: python mcp/git_mcp_server.py")


def test_rag_project_docs():
    """Тест RAG поиска по документации проекта."""
    print_section("Project Documentation RAG Tests")

    test_queries = [
        "Как устроена архитектура бота?",
        "Какие есть MCP серверы?",
        "Как добавить новый MCP сервер?",
        "Правила форматирования кода",
        "Как работает RAG система?"
    ]

    try:
        for i, query in enumerate(test_queries, 1):
            print(f"\n{i}. Query: {Colors.OKBLUE}{query}{Colors.ENDC}")

            context, chunks = query_project_docs(query, top_k=3)

            if chunks:
                print(f"   Found {Colors.OKGREEN}{len(chunks)}{Colors.ENDC} relevant chunks:")
                for j, chunk in enumerate(chunks, 1):
                    print(f"   {j}. {chunk['doc_name']} - {chunk['heading']}")
                    print(f"      Similarity: {chunk['similarity']:.3f}")
            else:
                print_warning("   No relevant chunks found")

        print_success("\n✓ All RAG tests passed!")

    except Exception as e:
        print_error(f"RAG error: {e}")
        print_warning("Make sure to run: python rag/create-project-docs-embeddings.py")


def display_help_examples():
    """Показать примеры использования /help команды."""
    print_section("Help Command Examples")

    examples = [
        "/help",
        "/help как добавить новый MCP сервер",
        "/help правила стиля кода",
        "/help архитектура RAG системы",
        "/help как работает команда /compress",
        "/help как настроить Ollama"
    ]

    print("Примеры использования команды /help в Telegram боте:\n")
    for example in examples:
        print(f"   {Colors.OKCYAN}{example}{Colors.ENDC}")

    print("\n" + "="*70)
    print("Команда /help интегрирует:")
    print("  1. RAG поиск по документации проекта")
    print("  2. Git MCP сервер (текущая ветка, коммиты)")
    print("  3. DeepSeek API для генерации ответа")
    print("="*70)


def check_prerequisites():
    """Проверить наличие всех необходимых компонентов."""
    print_section("Prerequisites Check")

    # 1. Проверить документацию
    docs_exist = {
        "README.md": Path("README.md").exists(),
        "ARCHITECTURE.md": Path("ARCHITECTURE.md").exists(),
        "CODE_STYLE.md": Path("CODE_STYLE.md").exists()
    }

    print("📄 Documentation files:")
    for doc, exists in docs_exist.items():
        if exists:
            print_success(f"   {doc}")
        else:
            print_error(f"   {doc} - missing")

    # 2. Проверить RAG БД
    db_path = Path("rag/db.sqlite3")
    if db_path.exists():
        print_success(f"\n💾 Database: {db_path}")
    else:
        print_error(f"\n💾 Database: {db_path} - missing")
        print_warning("   Run: python rag/create-project-docs-embeddings.py")

    # 3. Проверить MCP серверы
    print("\n🔌 MCP Servers (should be running):")
    print("   1. Git MCP Server - ws://localhost:8082/mcp")
    print("      Start: python mcp/git_mcp_server.py")
    print("   2. Yandex Tracker MCP - ws://localhost:8080/mcp")
    print("      Start: python mcp/mcp_server.py")
    print("   3. Translation MCP - ws://localhost:8081/mcp")
    print("      Start: python mcp/mcp_server2.py")

    print("\n🤖 Telegram Bot:")
    print("   Start: python bot.py")


async def main():
    """Главная функция."""
    print_header("🤖 AIBot - Developer Assistant Demo")
    print("День 20: Ассистент разработчика")

    # Проверка необходимых компонентов
    check_prerequisites()

    # Тесты
    input(f"\n{Colors.BOLD}Press Enter to start Git MCP tests...{Colors.ENDC}")
    await test_git_mcp_server()

    input(f"\n{Colors.BOLD}Press Enter to start RAG tests...{Colors.ENDC}")
    test_rag_project_docs()

    # Примеры использования
    input(f"\n{Colors.BOLD}Press Enter to see Help command examples...{Colors.ENDC}")
    display_help_examples()

    # Завершение
    print_header("✓ Demo Complete!")
    print("Ассистент разработчика готов к работе!\n")
    print("Запустите бота: python bot.py")
    print("И используйте команду: /help <ваш вопрос>\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Demo interrupted by user{Colors.ENDC}")
    except Exception as e:
        print_error(f"Demo error: {e}")
