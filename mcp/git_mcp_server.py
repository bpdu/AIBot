"""
MCP Server для работы с Git репозиторием
День 20: Ассистент разработчика

WebSocket сервер для получения информации о git репозитории:
- Текущая ветка
- Статус репозитория
- Последние коммиты
- Измененные файлы
- Содержимое файлов
"""

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute
from starlette.requests import Request
from starlette.responses import Response
from starlette.websockets import WebSocket
import uvicorn

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Путь к репозиторию (родительская директория от mcp/)
REPO_PATH = Path(__file__).parent.parent

# Создаём MCP сервер
mcp_server = Server("git-mcp-server")


def run_git_command(command: list, cwd=None):
    """
    Выполнить git команду и вернуть результат.

    Args:
        command: Список аргументов команды (например, ['git', 'status'])
        cwd: Рабочая директория (по умолчанию REPO_PATH)

    Returns:
        Словарь с результатом: {"success": bool, "output": str, "error": str}
    """
    if cwd is None:
        cwd = REPO_PATH

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            return {
                "success": True,
                "output": result.stdout.strip(),
                "error": None
            }
        else:
            return {
                "success": False,
                "output": None,
                "error": result.stderr.strip()
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": None,
            "error": "Command timeout"
        }
    except Exception as e:
        return {
            "success": False,
            "output": None,
            "error": str(e)
        }


def get_current_branch():
    """Получить текущую git ветку."""
    logger.info("Getting current branch...")

    result = run_git_command(['git', 'branch', '--show-current'])

    if result["success"]:
        branch = result["output"]
        return json.dumps({
            "success": True,
            "branch": branch,
            "repo_path": str(REPO_PATH)
        }, ensure_ascii=False, indent=2)
    else:
        return json.dumps({
            "success": False,
            "error": result["error"]
        })


def get_git_status():
    """Получить статус git репозитория."""
    logger.info("Getting git status...")

    # Получить статус
    result = run_git_command(['git', 'status', '--porcelain'])

    if not result["success"]:
        return json.dumps({
            "success": False,
            "error": result["error"]
        })

    # Парсинг статуса
    lines = result["output"].split('\n') if result["output"] else []

    status = {
        "success": True,
        "clean": len(lines) == 0,
        "modified": [],
        "added": [],
        "deleted": [],
        "untracked": []
    }

    for line in lines:
        if not line:
            continue

        status_code = line[:2]
        file_path = line[3:]

        if status_code == '??':
            status["untracked"].append(file_path)
        elif 'M' in status_code:
            status["modified"].append(file_path)
        elif 'A' in status_code:
            status["added"].append(file_path)
        elif 'D' in status_code:
            status["deleted"].append(file_path)

    return json.dumps(status, ensure_ascii=False, indent=2)


def get_recent_commits(count=10):
    """
    Получить последние коммиты.

    Args:
        count: Количество коммитов (по умолчанию 10)
    """
    logger.info(f"Getting {count} recent commits...")

    # Формат: hash|author|date|message
    result = run_git_command([
        'git', 'log',
        f'-{count}',
        '--pretty=format:%h|%an|%ar|%s'
    ])

    if not result["success"]:
        return json.dumps({
            "success": False,
            "error": result["error"]
        })

    # Парсинг коммитов
    lines = result["output"].split('\n') if result["output"] else []
    commits = []

    for line in lines:
        if not line:
            continue

        parts = line.split('|', 3)
        if len(parts) == 4:
            commits.append({
                "hash": parts[0],
                "author": parts[1],
                "date": parts[2],
                "message": parts[3]
            })

    return json.dumps({
        "success": True,
        "count": len(commits),
        "commits": commits
    }, ensure_ascii=False, indent=2)


def get_changed_files():
    """Получить список измененных файлов (unstaged + staged)."""
    logger.info("Getting changed files...")

    # Получить все измененные файлы
    result = run_git_command(['git', 'diff', '--name-only', 'HEAD'])

    if not result["success"]:
        return json.dumps({
            "success": False,
            "error": result["error"]
        })

    files = result["output"].split('\n') if result["output"] else []
    files = [f for f in files if f]  # Убрать пустые строки

    return json.dumps({
        "success": True,
        "count": len(files),
        "files": files
    }, ensure_ascii=False, indent=2)


def get_file_content(file_path: str):
    """
    Получить содержимое файла из репозитория.

    Args:
        file_path: Относительный путь к файлу от корня репозитория
    """
    logger.info(f"Getting content of file: {file_path}")

    full_path = REPO_PATH / file_path

    # Проверить, что файл существует
    if not full_path.exists():
        return json.dumps({
            "success": False,
            "error": f"File not found: {file_path}"
        })

    # Проверить, что это файл (не директория)
    if not full_path.is_file():
        return json.dumps({
            "success": False,
            "error": f"Not a file: {file_path}"
        })

    # Прочитать файл
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Ограничить размер (максимум 10000 символов)
        if len(content) > 10000:
            content = content[:10000] + "\n\n... (truncated)"

        return json.dumps({
            "success": True,
            "file_path": file_path,
            "content": content,
            "size": len(content)
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to read file: {str(e)}"
        })


def get_git_diff(file_path: str = None):
    """
    Получить git diff (изменения).

    Args:
        file_path: Путь к файлу (опционально, если None - показать все изменения)
    """
    logger.info(f"Getting git diff for: {file_path if file_path else 'all files'}")

    command = ['git', 'diff', 'HEAD']
    if file_path:
        command.append(file_path)

    result = run_git_command(command)

    if not result["success"]:
        return json.dumps({
            "success": False,
            "error": result["error"]
        })

    diff = result["output"]

    # Ограничить размер
    if len(diff) > 5000:
        diff = diff[:5000] + "\n\n... (truncated)"

    return json.dumps({
        "success": True,
        "file_path": file_path,
        "diff": diff
    }, ensure_ascii=False, indent=2)


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """Возвращает список доступных инструментов."""
    tools = [
        Tool(
            name="get-current-branch",
            description="Получить текущую git ветку",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get-git-status",
            description="Получить статус git репозитория (измененные, добавленные, удаленные файлы)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get-recent-commits",
            description="Получить последние коммиты из git истории",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Количество коммитов (по умолчанию 10)",
                        "default": 10
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get-changed-files",
            description="Получить список всех измененных файлов",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get-file-content",
            description="Получить содержимое файла из репозитория",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Относительный путь к файлу от корня репозитория"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="get-git-diff",
            description="Получить git diff (изменения в файлах)",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к файлу (опционально, если не указан - показать все изменения)"
                    }
                },
                "required": []
            }
        )
    ]
    return tools


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Вызов инструмента."""
    if name == "get-current-branch":
        result = get_current_branch()
    elif name == "get-git-status":
        result = get_git_status()
    elif name == "get-recent-commits":
        count = arguments.get("count", 10)
        result = get_recent_commits(count)
    elif name == "get-changed-files":
        result = get_changed_files()
    elif name == "get-file-content":
        file_path = arguments.get("file_path")
        if not file_path:
            result = json.dumps({"success": False, "error": "file_path is required"})
        else:
            result = get_file_content(file_path)
    elif name == "get-git-diff":
        file_path = arguments.get("file_path")
        result = get_git_diff(file_path)
    else:
        result = json.dumps({
            "success": False,
            "error": f"Tool not found: {name}"
        })

    return [TextContent(type="text", text=result)]


async def root(request: Request):
    """Корневой endpoint."""
    return Response(
        content=json.dumps({
            "name": "Git MCP Server",
            "version": "1.0.0",
            "protocol": "MCP",
            "endpoint": "/mcp",
            "tools": 6,
            "repo_path": str(REPO_PATH)
        }),
        media_type="application/json"
    )


async def handle_websocket(websocket: WebSocket):
    """Обработчик WebSocket endpoint для MCP протокола."""
    subprotocol = None
    if "mcp" in websocket.headers.get("sec-websocket-protocol", "").split(", "):
        subprotocol = "mcp"

    await websocket.accept(subprotocol=subprotocol)
    logger.info(f"Новое WebSocket подключение от {websocket.client}")

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message: {data[:200]}")

            try:
                request = json.loads(data)
                method = request.get("method")
                request_id = request.get("id")
                params = request.get("params", {})

                logger.info(f"JSON-RPC request: method={method}, id={request_id}")

                # Обработка initialize
                if method == "initialize":
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {}},
                            "serverInfo": {
                                "name": "git-mcp-server",
                                "version": "1.0.0"
                            }
                        }
                    }
                    await websocket.send_text(json.dumps(response))

                # Обработка tools/list
                elif method == "tools/list":
                    tools_list = await list_tools()
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "tools": [
                                {
                                    "name": tool.name,
                                    "description": tool.description,
                                    "inputSchema": tool.inputSchema
                                }
                                for tool in tools_list
                            ]
                        }
                    }
                    await websocket.send_text(json.dumps(response))

                # Обработка tools/call
                elif method == "tools/call":
                    tool_name = params.get("name")
                    tool_arguments = params.get("arguments", {})
                    logger.info(f"Calling tool: {tool_name} with args: {tool_arguments}")

                    result_content = await call_tool(tool_name, tool_arguments)

                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [
                                {
                                    "type": content.type,
                                    "text": content.text
                                }
                                for content in result_content
                            ]
                        }
                    }
                    await websocket.send_text(json.dumps(response))

                # Обработка notifications/initialized
                elif method == "notifications/initialized":
                    logger.info("Received initialized notification")

                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}"
                        }
                    }
                    await websocket.send_text(json.dumps(response))

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"}
                }
                await websocket.send_text(json.dumps(error_response))
            except Exception as e:
                logger.error(f"Error processing request: {e}", exc_info=True)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id") if 'request' in locals() else None,
                    "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
                }
                await websocket.send_text(json.dumps(error_response))

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        logger.info("WebSocket connection closed")


# Создаём приложение
app = Starlette(
    routes=[
        Route("/", root),
        WebSocketRoute("/mcp", handle_websocket),
    ]
)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Git MCP Server запущен")
    logger.info("День 20: Ассистент разработчика")
    logger.info("=" * 60)
    logger.info(f"Repo path: {REPO_PATH}")
    logger.info("Доступные инструменты: 6")
    logger.info("  1. get-current-branch: Получить текущую ветку")
    logger.info("  2. get-git-status: Получить статус репозитория")
    logger.info("  3. get-recent-commits: Получить последние коммиты")
    logger.info("  4. get-changed-files: Получить измененные файлы")
    logger.info("  5. get-file-content: Получить содержимое файла")
    logger.info("  6. get-git-diff: Получить git diff")
    logger.info("=" * 60)
    logger.info("WebSocket endpoint: ws://localhost:8082/mcp")
    logger.info("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8082)
