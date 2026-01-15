"""
MCP Server с Yandex Tracker API + Host Monitoring
День 13: Планировщик + MCP
День 15: Environment - Мониторинг хоста

WebSocket сервер для получения задач из Yandex Tracker и сбора метрик хоста.
"""

import asyncio
import json
import logging
import os
import requests
import socket
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


def get_tracker_tasks(priority: str = None):
    """
    Получить задачи из Yandex Tracker API.

    Args:
        priority: Фильтр по приоритету ('blocker', 'critical', 'high', 'normal', 'low')
                  Если None - возвращает все задачи
    """
    if not TRACKER_TOKEN or not TRACKER_ORG_ID:
        logger.error("Tracker credentials not configured!")
        logger.error(f"Token present: {bool(TRACKER_TOKEN)}")
        logger.error(f"Org ID present: {bool(TRACKER_ORG_ID)}")
        return json.dumps({"error": "Tracker credentials not configured"})

    headers = {
        'Authorization': f'OAuth {TRACKER_TOKEN}',
        'X-Cloud-Org-Id': TRACKER_ORG_ID,
        'Content-Type': 'application/json'
    }

    try:
        logger.info(f"Requesting tasks from Yandex Tracker (priority filter: {priority})...")

        response = requests.get(TRACKER_API_URL, headers=headers, timeout=10)

        logger.info(f"Response status code: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"Response body: {response.text[:500]}")

        response.raise_for_status()

        tasks = response.json()
        logger.info(f"Retrieved {len(tasks)} tasks from Tracker")

        # Форматируем задачи для лучшей читаемости
        formatted_tasks = []
        for task in tasks:
            task_priority = task.get('priority', {}).get('key', 'normal')

            # Фильтруем по приоритету если указан
            if priority and task_priority != priority:
                continue

            formatted_task = {
                'key': task.get('key'),
                'summary': task.get('summary'),
                'description': task.get('description', ''),
                'status': task.get('status', {}).get('display', 'Unknown'),
                'priority': task.get('priority', {}).get('display', 'Normal'),
                'priority_key': task_priority,
                'assignee': task.get('assignee', {}).get('display', 'Unassigned'),
                'created': task.get('createdAt', ''),
                'updated': task.get('updatedAt', '')
            }
            formatted_tasks.append(formatted_task)

        logger.info(f"Returning {len(formatted_tasks)} tasks after filtering")
        return json.dumps(formatted_tasks, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching tasks from Tracker: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Error response body: {e.response.text[:500]}")
        return json.dumps({"error": str(e)})


def create_tracker_task(summary: str, description: str = "", priority: str = "normal", queue: str = "RK"):
    """
    Создать новую задачу в Yandex Tracker.

    Args:
        summary: Название задачи (обязательно)
        description: Описание задачи
        priority: Приоритет ('blocker', 'critical', 'high', 'normal', 'low')
        queue: Очередь для задачи (по умолчанию 'RK')

    Returns:
        JSON с информацией о созданной задаче или ошибкой
    """
    if not TRACKER_TOKEN or not TRACKER_ORG_ID:
        logger.error("Tracker credentials not configured!")
        return json.dumps({"error": "Tracker credentials not configured"})

    if not summary:
        return json.dumps({"error": "Summary is required"})

    headers = {
        'Authorization': f'OAuth {TRACKER_TOKEN}',
        'X-Cloud-Org-Id': TRACKER_ORG_ID,
        'Content-Type': 'application/json'
    }

    # Маппинг приоритетов на ключи Yandex Tracker
    priority_map = {
        'blocker': 'blocker',
        'critical': 'critical',
        'high': 'high',
        'normal': 'normal',
        'low': 'low'
    }

    priority_key = priority_map.get(priority.lower(), 'normal')

    task_data = {
        "queue": queue,
        "summary": summary,
        "description": description,
        "priority": priority_key
    }

    try:
        logger.info(f"Creating task in Yandex Tracker: {summary}")
        logger.info(f"Task data: {json.dumps(task_data, ensure_ascii=False)}")

        response = requests.post(TRACKER_API_URL, headers=headers, json=task_data, timeout=10)

        logger.info(f"Response status code: {response.status_code}")

        if response.status_code not in [200, 201]:
            logger.error(f"Response body: {response.text[:500]}")
            return json.dumps({"error": f"Failed to create task: {response.text[:200]}"})

        created_task = response.json()
        logger.info(f"Task created: {created_task.get('key')}")

        result = {
            "success": True,
            "task": {
                "key": created_task.get('key'),
                "summary": created_task.get('summary'),
                "status": created_task.get('status', {}).get('display', 'Unknown'),
                "priority": created_task.get('priority', {}).get('display', 'Normal'),
                "url": f"https://tracker.yandex.ru/{created_task.get('key')}"
            }
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating task in Tracker: {e}")
        return json.dumps({"error": str(e)})


def get_host_metrics():
    """
    Собрать метрики хоста (CPU, RAM, Disk, Uptime, Temperature).

    Returns:
        JSON строка с метриками хоста
    """
    try:
        logger.info("Collecting host metrics...")

        # Импортируем psutil локально
        try:
            import psutil
            import platform
        except ImportError:
            return json.dumps({
                "error": "psutil not installed. Install with: pip install psutil"
            })

        # CPU метрики
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        cpu_freq_current = int(cpu_freq.current) if cpu_freq else 0

        # Memory метрики
        mem = psutil.virtual_memory()
        mem_total_gb = round(mem.total / (1024**3), 2)
        mem_used_gb = round(mem.used / (1024**3), 2)
        mem_percent = mem.percent

        # Disk метрики
        disk = psutil.disk_usage('/')
        disk_total_gb = round(disk.total / (1024**3), 2)
        disk_used_gb = round(disk.used / (1024**3), 2)
        disk_percent = disk.percent

        # Uptime
        from datetime import datetime, timedelta
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime_seconds = (datetime.now() - boot_time).total_seconds()

        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)

        if days > 0:
            uptime_str = f"{days}д {hours}ч {minutes}м"
        else:
            uptime_str = f"{hours}ч {minutes}м"

        # System info
        hostname = socket.gethostname()
        platform_info = f"{platform.system()} {platform.release()}"
        architecture = platform.machine()

        # Temperature (если доступно)
        temperature = "N/A"
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if 'coretemp' in name.lower() or 'cpu' in name.lower():
                        if entries:
                            temperature = f"{entries[0].current:.1f}°C"
                            break
        except:
            pass

        # IP адрес
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except:
            ip_address = "N/A"

        # Формирование результата
        metrics = {
            "success": True,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cpu": {
                "percent": cpu_percent,
                "cores": cpu_count,
                "frequency_mhz": cpu_freq_current
            },
            "memory": {
                "percent": mem_percent,
                "used_gb": mem_used_gb,
                "total_gb": mem_total_gb
            },
            "disk": {
                "percent": disk_percent,
                "used_gb": disk_used_gb,
                "total_gb": disk_total_gb
            },
            "uptime": {
                "formatted": uptime_str,
                "boot_time": boot_time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "system": {
                "hostname": hostname,
                "platform": platform_info,
                "architecture": architecture,
                "ip_address": ip_address,
                "temperature": temperature
            }
        }

        logger.info("Metrics collected successfully")
        return json.dumps(metrics, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Error collecting metrics: {e}", exc_info=True)
        return json.dumps({
            "error": f"Failed to collect metrics: {str(e)}"
        })


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """Возвращает список доступных инструментов."""
    tools = [
        Tool(
            name="get-tracker-tasks",
            description="Получить список задач из Yandex Tracker",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get-host-metrics",
            description="Получить метрики хоста (CPU, RAM, Disk, Uptime, Temperature, System info)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]
    return tools


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Вызов инструмента."""
    if name == "get-tracker-tasks":
        tasks_json = get_tracker_tasks()
        return [TextContent(
            type="text",
            text=tasks_json
        )]
    elif name == "get-host-metrics":
        result_json = get_host_metrics()
        return [TextContent(
            type="text",
            text=result_json
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
                                    "description": "Получить список задач из Yandex Tracker с возможностью фильтрации по приоритету",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "priority": {
                                                "type": "string",
                                                "description": "Фильтр по приоритету: blocker, critical, high, normal, low",
                                                "enum": ["blocker", "critical", "high", "normal", "low"]
                                            }
                                        },
                                        "required": []
                                    }
                                },
                                {
                                    "name": "create-tracker-task",
                                    "description": "Создать новую задачу в Yandex Tracker",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "summary": {
                                                "type": "string",
                                                "description": "Название задачи (обязательно)"
                                            },
                                            "description": {
                                                "type": "string",
                                                "description": "Описание задачи"
                                            },
                                            "priority": {
                                                "type": "string",
                                                "description": "Приоритет: blocker, critical, high, normal, low",
                                                "enum": ["blocker", "critical", "high", "normal", "low"],
                                                "default": "normal"
                                            }
                                        },
                                        "required": ["summary"]
                                    }
                                },
                                {
                                    "name": "get-host-metrics",
                                    "description": "Получить метрики хоста (CPU, RAM, Disk, Uptime, Temperature, System info)",
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
                    tool_args = params.get("arguments", {})
                    logger.info(f"Calling tool: {tool_name} with args: {tool_args}")

                    if tool_name == "get-tracker-tasks":
                        # Получаем задачи из Yandex Tracker с опциональным фильтром по приоритету
                        priority_filter = tool_args.get("priority")
                        tasks_json = get_tracker_tasks(priority=priority_filter)

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

                    elif tool_name == "create-tracker-task":
                        # Создаём новую задачу в Yandex Tracker
                        summary = tool_args.get("summary", "")
                        description = tool_args.get("description", "")
                        priority = tool_args.get("priority", "normal")

                        result_json = create_tracker_task(
                            summary=summary,
                            description=description,
                            priority=priority
                        )

                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": result_json
                                    }
                                ]
                            }
                        }
                        await websocket.send_text(json.dumps(response))
                        logger.info(f"Sent create task response: {len(result_json)} chars")

                    elif tool_name == "get-host-metrics":
                        # Получение метрик хоста
                        monitoring_result = get_host_metrics()

                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": monitoring_result
                                    }
                                ]
                            }
                        }
                        await websocket.send_text(json.dumps(response))
                        logger.info(f"Sent host metrics response: {len(monitoring_result)} chars")

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
    logger.info("MCP Server запущен (WebSocket)")
    logger.info("День 13: Планировщик + MCP | День 15: Environment - Мониторинг")
    logger.info("=" * 60)
    logger.info(f"Tracker Token: {'✓ configured' if TRACKER_TOKEN else '✗ missing'}")
    logger.info(f"Tracker Org ID: {TRACKER_ORG_ID if TRACKER_ORG_ID else '✗ missing'}")
    logger.info("Доступные инструменты: 2")
    logger.info("  1. get-tracker-tasks: Получить список задач из Yandex Tracker")
    logger.info("  2. get-host-metrics: Получить метрики хоста (CPU, RAM, Disk, Uptime)")
    logger.info("=" * 60)
    logger.info("WebSocket endpoint: ws://localhost:8080/mcp")
    logger.info("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8080)
