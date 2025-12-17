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
        return json.dumps({"error": "Tracker credentials not configured"})

    headers = {
        'Authorization': f'OAuth {TRACKER_TOKEN}',
        'X-Org-ID': TRACKER_ORG_ID,
        'Content-Type': 'application/json'
    }

    try:
        logger.info(f"Requesting tasks from Yandex Tracker...")
        response = requests.get(TRACKER_API_URL, headers=headers, timeout=10)
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
    """Обработчик WebSocket endpoint."""
    # Принимаем WebSocket с subprotocol "mcp"
    subprotocol = None
    if "mcp" in websocket.headers.get("sec-websocket-protocol", "").split(", "):
        subprotocol = "mcp"

    await websocket.accept(subprotocol=subprotocol)
    logger.info(f"Новое WebSocket подключение от {websocket.client}, subprotocol={subprotocol}")

    # Создаём anyio memory streams для MCP SDK
    import anyio

    # Создаём пары потоков для двунаправленной коммуникации
    read_stream_send, read_stream_receive = anyio.create_memory_object_stream(0)
    write_stream_send, write_stream_receive = anyio.create_memory_object_stream(0)

    logger.info("Created anyio memory streams for MCP communication")

    # Запускаем MCP сервер с этими потоками
    async def run_server():
        """Запуск MCP сервера."""
        try:
            logger.info("run_server: starting mcp_server.run()")
            await mcp_server.run(
                read_stream_receive,
                write_stream_send,
                mcp_server.create_initialization_options()
            )
            logger.info("run_server: mcp_server.run() completed")
        except Exception as e:
            logger.error(f"Error in server: {e}", exc_info=True)

    # Задачи для чтения из WebSocket и записи в WebSocket
    async def read_from_websocket():
        """Читаем сообщения из WebSocket и отправляем в MCP read stream."""
        try:
            while True:
                logger.info("read_from_websocket: waiting for message from client")
                data = await websocket.receive_text()
                logger.info(f"read_from_websocket: received {len(data)} bytes")
                # Парсим JSON и отправляем объект в MCP stream
                try:
                    json_obj = json.loads(data)
                    logger.info(f"read_from_websocket: parsed JSON, sending to read_stream_send")
                    await read_stream_send.send(json_obj)
                    logger.info("read_from_websocket: sent to MCP")
                except json.JSONDecodeError as e:
                    logger.error(f"read_from_websocket: failed to parse JSON: {e}")
        except Exception as e:
            logger.error(f"read_from_websocket: error {e}", exc_info=True)
        finally:
            await read_stream_send.aclose()

    async def write_to_websocket():
        """Читаем из MCP write stream и отправляем в WebSocket."""
        try:
            while True:
                logger.info("write_to_websocket: waiting for message from MCP")
                message = await write_stream_receive.receive()
                logger.info(f"write_to_websocket: got message type={type(message)}")
                # Сериализуем в JSON строку и отправляем в WebSocket
                if isinstance(message, str):
                    json_str = message
                else:
                    json_str = json.dumps(message)
                logger.info(f"write_to_websocket: sending {len(json_str)} bytes to WebSocket")
                await websocket.send_text(json_str)
                logger.info("write_to_websocket: sent to client")
        except Exception as e:
            logger.error(f"write_to_websocket: error {e}", exc_info=True)
        finally:
            await write_stream_receive.aclose()

    # Запускаем все задачи параллельно
    try:
        logger.info("handle_websocket: starting all tasks")
        await asyncio.gather(
            run_server(),
            read_from_websocket(),
            write_to_websocket(),
            return_exceptions=True
        )
    except Exception as e:
        logger.error(f"handle_websocket: error in gather {e}", exc_info=True)
    finally:
        logger.info("handle_websocket: cleaning up")
        # Закрыть потоки
        await read_stream_send.aclose()
        await write_stream_receive.aclose()
        # Закрыть WebSocket если еще не закрыт
        if websocket.client_state.name != "DISCONNECTED":
            try:
                await websocket.close()
            except Exception as e:
                logger.error(f"Error closing websocket: {e}")


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
