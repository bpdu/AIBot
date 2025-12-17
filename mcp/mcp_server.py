"""
MCP Server с Yandex Tracker API
День 13: Планировщик + MCP

HTTP/SSE сервер для получения задач из Yandex Tracker.
"""

import asyncio
import json
import logging
import os
import requests
from datetime import datetime
from typing import Any
from dotenv import load_dotenv

from mcp.server import Server
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response
from sse_starlette import EventSourceResponse
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


# Хранилище активных сессий
sessions: dict[str, tuple[Any, asyncio.Queue, asyncio.Queue]] = {}


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


async def handle_sse(request: Request):
    """Обработчик SSE endpoint."""
    session_id = request.headers.get("mcp-session-id", "default")

    logger.info(f"Новое SSE подключение, session_id={session_id}")

    # Создаём очереди для входящих и исходящих сообщений
    read_queue: asyncio.Queue = asyncio.Queue()
    write_queue: asyncio.Queue = asyncio.Queue()

    # Создаём потоки для MCP сервера с правильными context managers
    class MCPReadStream:
        async def __aenter__(self):
            logger.info("MCPReadStream.__aenter__")
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            logger.info("MCPReadStream.__aexit__")
            pass

        def __aiter__(self):
            logger.info("MCPReadStream.__aiter__")
            return self

        async def __anext__(self):
            logger.info("MCPReadStream.__anext__: waiting for message from read_queue")
            message = await read_queue.get()
            logger.info(f"MCPReadStream.__anext__: received message type={type(message)}")
            if message is None:
                logger.info("MCPReadStream.__anext__: message is None, raising StopAsyncIteration")
                raise StopAsyncIteration
            return message

    class MCPWriteStream:
        async def __aenter__(self):
            logger.info("MCPWriteStream.__aenter__")
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            logger.info("MCPWriteStream.__aexit__")
            pass

        async def send(self, message):
            logger.info(f"MCPWriteStream.send: message type={type(message)}, putting to write_queue")
            await write_queue.put(message)
            logger.info("MCPWriteStream.send: message put to write_queue")

    read_stream = MCPReadStream()
    write_stream = MCPWriteStream()

    # Запускаем MCP сервер с этими потоками
    async def run_server():
        """Запуск MCP сервера."""
        try:
            logger.info("run_server: starting mcp_server.run()")
            # Запускаем сервер с нашими read/write потоками
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options()
            )
            logger.info("run_server: mcp_server.run() completed")
        except Exception as e:
            logger.error(f"Error in server: {e}", exc_info=True)

    # Сохраняем сессию
    sessions[session_id] = (None, read_queue, write_queue)

    async def event_generator():
        """Генератор SSE событий."""
        try:
            # Запускаем обработку сервера в фоне
            logger.info("event_generator: creating run_server task")
            session_task = asyncio.create_task(run_server())
            logger.info("event_generator: run_server task created")

            # Отправляем сообщения из очереди
            while True:
                try:
                    logger.info("event_generator: waiting for message from write_queue (timeout=30s)")
                    message = await asyncio.wait_for(write_queue.get(), timeout=30.0)
                    logger.info(f"event_generator: got message from write_queue, type={type(message)}")
                    yield {
                        "event": "message",
                        "data": json.dumps(message)
                    }
                    logger.info("event_generator: message sent to client")
                except asyncio.TimeoutError:
                    # Отправляем keepalive
                    logger.info("event_generator: timeout, sending keepalive ping")
                    yield {
                        "event": "ping",
                        "data": ""
                    }

        except asyncio.CancelledError:
            logger.info("event_generator: SSE подключение закрыто")
            session_task.cancel()
            if session_id in sessions:
                del sessions[session_id]
        except Exception as e:
            logger.error(f"event_generator: Ошибка в SSE: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())


async def handle_message(request: Request):
    """Обработчик POST запросов с сообщениями."""
    session_id = request.headers.get("mcp-session-id", "default")
    logger.info(f"handle_message: received POST request, session_id={session_id}")

    if session_id not in sessions:
        logger.error(f"handle_message: session {session_id} not found")
        return Response(
            content=json.dumps({"error": "Invalid session"}),
            status_code=400,
            media_type="application/json"
        )

    _, read_queue, _ = sessions[session_id]

    body = await request.body()
    logger.info(f"handle_message: body length={len(body)}")
    message = json.loads(body.decode())
    logger.info(f"handle_message: parsed message type={type(message)}, keys={message.keys() if isinstance(message, dict) else 'N/A'}")

    await read_queue.put(message)
    logger.info("handle_message: message put to read_queue")

    return Response(status_code=202)


# Создаём приложение
app = Starlette(
    routes=[
        Route("/", root),
        Route("/mcp", handle_sse),
        Route("/mcp/message", handle_message, methods=["POST"]),
    ]
)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Yandex Tracker MCP Server запущен (HTTP/SSE)")
    logger.info("=" * 60)
    logger.info(f"Tracker Token: {'✓ configured' if TRACKER_TOKEN else '✗ missing'}")
    logger.info(f"Tracker Org ID: {TRACKER_ORG_ID if TRACKER_ORG_ID else '✗ missing'}")
    logger.info("Доступные инструменты: 1")
    logger.info("  - get-tracker-tasks: Получить список задач из Yandex Tracker")
    logger.info("=" * 60)
    logger.info("Listening on http://localhost:8080")
    logger.info("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8080)
