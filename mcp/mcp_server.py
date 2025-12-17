"""
MCP Server с Yandex Tracker API
День 13: Планировщик + MCP

WebSocket сервер для получения задач из Yandex Tracker.
"""

import asyncio
import json
import logging
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

from mcp.server import Server
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute
from starlette.requests import Request
from starlette.responses import Response
from starlette.websockets import WebSocket
import uvicorn

# Загрузка переменных окружения
# Получаем путь к директории проекта (на уровень выше mcp/)
import pathlib
project_dir = pathlib.Path(__file__).parent.parent
load_dotenv(dotenv_path=project_dir / '.secrets' / 'yandex-tracker-token.env')
load_dotenv(dotenv_path=project_dir / '.secrets' / 'yandex-tracker-org-id.env')

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Yandex Tracker credentials
TRACKER_TOKEN = os.getenv('YANDEX_TRACKER_TOKEN')
TRACKER_ORG_ID = os.getenv('YANDEX_TRACKER_ORG_ID')
TRACKER_API_URL = 'https://api.tracker.yandex.net/v2/issues'

# Создаём MCP сервер
mcp_server = Server("yandex-tracker-mcp-server")


def get_tracker_tasks():
    """Получить задачи из Yandex Tracker API."""
    if not TRACKER_TOKEN or not TRACKER_ORG_ID:
        logger.error("Tracker credentials not configured!")
        logger.error(f"Token present: {bool(TRACKER_TOKEN)}")
        logger.error(f"Org ID present: {bool(TRACKER_ORG_ID)}")
        return json.dumps({"error": "Tracker credentials not configured"})

    headers = {
        'Authorization': f'OAuth {TRACKER_TOKEN}',
        'X-Org-ID': TRACKER_ORG_ID,
        'Content-Type': 'application/json'
    }

    try:
        logger.info(f"Requesting tasks from Yandex Tracker...")
        logger.info(f"API URL: {TRACKER_API_URL}")
        logger.info(f"Token (first 10 chars): {TRACKER_TOKEN[:10]}...")
        logger.info(f"Org ID: {TRACKER_ORG_ID}")
        logger.info(f"Headers: Authorization=OAuth {TRACKER_TOKEN[:10]}..., X-Org-ID={TRACKER_ORG_ID}")

        response = requests.get(TRACKER_API_URL, headers=headers, timeout=10)

        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")

        if response.status_code != 200:
            logger.error(f"Response body: {response.text[:500]}")

        response.raise_for_status()

        tasks = response.json()
        logger.info(f"Retrieved {len(tasks)} tasks from Tracker")

        # Форматируем задачи для лучшей читаемости
        formatted_tasks = []
        for task in tasks:
            formatted_task = {
                'key': task.get('key'),
                'summary': task.get('summary'),
                'status': task.get('status', {}).get('display', 'Unknown'),
                'assignee': task.get('assignee', {}).get('display', 'Unassigned'),
                'created': task.get('createdAt', ''),
                'updated': task.get('updatedAt', '')
            }
            formatted_tasks.append(formatted_task)

        return json.dumps(formatted_tasks, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching tasks from Tracker: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Error response body: {e.response.text[:500]}")
        return json.dumps({"error": str(e)})


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """Возвращает список доступных инструментов."""
    return [
        Tool(
            name="get-tracker-tasks",
            description="Получить список задач из Yandex Tracker",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Вызов инструмента."""
    if name == "get-tracker-tasks":
        tasks_json = get_tracker_tasks()
        return [TextContent(
            type="text",
            text=tasks_json
        )]
    else:
        return [TextContent(
            type="text",
            text=f"Инструмент не найден: {name}"
        )]


async def root(request: Request):
    """Корневой endpoint."""
    return Response(
        content=json.dumps({
            "name": "Yandex Tracker MCP Server",
            "version": "1.0.0",
            "protocol": "MCP",
            "endpoint": "/mcp",
            "tools": 1
        }),
        media_type="application/json"
    )


async def handle_websocket(websocket: WebSocket):
    """Обработчик WebSocket endpoint для MCP протокола."""
    # Принимаем WebSocket с subprotocol "mcp"
    subprotocol = None
    if "mcp" in websocket.headers.get("sec-websocket-protocol", "").split(", "):
        subprotocol = "mcp"

    await websocket.accept(subprotocol=subprotocol)
    logger.info(f"Новое WebSocket подключение от {websocket.client}, subprotocol={subprotocol}")

    try:
        while True:
            # Получаем сообщение от клиента
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
                            "capabilities": {
                                "tools": {}
                            },
                            "serverInfo": {
                                "name": "yandex-tracker-mcp-server",
                                "version": "1.0.0"
                            }
                        }
                    }
                    await websocket.send_text(json.dumps(response))
                    logger.info("Sent initialize response")

                # Обработка tools/list
                elif method == "tools/list":
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "tools": [
                                {
                                    "name": "get-tracker-tasks",
                                    "description": "Получить список задач из Yandex Tracker",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {},
                                        "required": []
                                    }
                                }
                            ]
                        }
                    }
                    await websocket.send_text(json.dumps(response))
                    logger.info("Sent tools/list response")

                # Обработка tools/call
                elif method == "tools/call":
                    tool_name = params.get("name")
                    logger.info(f"Calling tool: {tool_name}")

                    if tool_name == "get-tracker-tasks":
                        # Получаем задачи из Yandex Tracker
                        tasks_json = get_tracker_tasks()

                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": tasks_json
                                    }
                                ]
                            }
                        }
                        await websocket.send_text(json.dumps(response))
                        logger.info(f"Sent tool response: {len(tasks_json)} chars")
                    else:
                        # Неизвестный tool
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32601,
                                "message": f"Tool not found: {tool_name}"
                            }
                        }
                        await websocket.send_text(json.dumps(response))

                # Обработка notifications/initialized
                elif method == "notifications/initialized":
                    # Это notification, не требует ответа
                    logger.info("Received initialized notification")

                else:
                    # Неизвестный метод
                    logger.warning(f"Unknown method: {method}")
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
                    "error": {
                        "code": -32700,
                        "message": "Parse error"
                    }
                }
                await websocket.send_text(json.dumps(error_response))
            except Exception as e:
                logger.error(f"Error processing request: {e}", exc_info=True)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id") if 'request' in locals() else None,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
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
    logger.info("Yandex Tracker MCP Server запущен (WebSocket)")
    logger.info("=" * 60)
    logger.info(f"Tracker Token: {'✓ configured' if TRACKER_TOKEN else '✗ missing'}")
    logger.info(f"Tracker Org ID: {TRACKER_ORG_ID if TRACKER_ORG_ID else '✗ missing'}")
    logger.info("Доступные инструменты: 1")
    logger.info("  - get-tracker-tasks: Получить список задач из Yandex Tracker")
    logger.info("=" * 60)
    logger.info("WebSocket endpoint: ws://localhost:8080/mcp")
    logger.info("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8080)
