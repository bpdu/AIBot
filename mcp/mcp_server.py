"""
Простой MCP Server через stdio
День 11: Подключение MCP

Локальный MCP-сервер для демонстрации работы протокола.
"""

import asyncio
import json
import sys
from datetime import datetime
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import httpx


# Создаём MCP сервер
app = Server("demo-mcp-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Возвращает список доступных инструментов."""
    return [
        Tool(
            name="get-current-time",
            description="Получить текущее время сервера",
            inputSchema={
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Временная зона (опционально)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="calculate",
            description="Выполнить простое математическое вычисление",
            inputSchema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "Операция: add, subtract, multiply, divide",
                        "enum": ["add", "subtract", "multiply", "divide"]
                    },
                    "a": {
                        "type": "number",
                        "description": "Первое число"
                    },
                    "b": {
                        "type": "number",
                        "description": "Второе число"
                    }
                },
                "required": ["operation", "a", "b"]
            }
        ),
        Tool(
            name="echo",
            description="Вернуть переданное сообщение (эхо)",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Сообщение для эха"
                    }
                },
                "required": ["message"]
            }
        ),
        Tool(
            name="getGeoByIP",
            description="Получить геолокацию по IP-адресу",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip_address": {
                        "type": "string",
                        "description": "IP-адрес для определения геолокации (например, 8.8.8.8)"
                    }
                },
                "required": ["ip_address"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Вызов инструмента."""
    if name == "get-current-time":
        current_time = datetime.now().isoformat()
        return [TextContent(
            type="text",
            text=f"Текущее время: {current_time}"
        )]

    elif name == "calculate":
        operation = arguments.get("operation")
        a = arguments.get("a")
        b = arguments.get("b")

        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                return [TextContent(
                    type="text",
                    text="Ошибка: деление на ноль"
                )]
            result = a / b
        else:
            return [TextContent(
                type="text",
                text=f"Неизвестная операция: {operation}"
            )]

        return [TextContent(
            type="text",
            text=f"Результат: {a} {operation} {b} = {result}"
        )]

    elif name == "echo":
        message = arguments.get("message", "")
        return [TextContent(
            type="text",
            text=f"Эхо: {message}"
        )]

    elif name == "getGeoByIP":
        ip_address = arguments.get("ip_address", "").strip()

        # Валидация IP адреса
        if not ip_address:
            return [TextContent(type="text", text="Ошибка: IP-адрес не указан")]

        # Проверка формата IP (4 октета)
        parts = ip_address.split(".")
        if len(parts) != 4:
            return [TextContent(
                type="text",
                text=f"Ошибка: Некорректный формат IP-адреса: {ip_address}"
            )]

        # Проверка диапазона (0-255)
        try:
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    raise ValueError()
        except (ValueError, AttributeError):
            return [TextContent(
                type="text",
                text=f"Ошибка: Некорректный IP-адрес: {ip_address}"
            )]

        # Запрос к API
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"http://ip-api.com/json/{ip_address}",
                    params={"lang": "ru"}
                )
                response.raise_for_status()
                data = response.json()

                # Проверка статуса ответа
                if data.get("status") == "fail":
                    error_msg = data.get("message", "Неизвестная ошибка")
                    return [TextContent(type="text", text=f"Ошибка API: {error_msg}")]

                # Формирование результата
                country = data.get("country", "Неизвестно")
                city = data.get("city", "Неизвестно")
                result_text = f"IP: {ip_address}\nСтрана: {country}\nГород: {city}"

                return [TextContent(type="text", text=result_text)]

        except httpx.TimeoutException:
            return [TextContent(
                type="text",
                text=f"Ошибка: Превышено время ожидания при запросе геолокации для {ip_address}"
            )]
        except httpx.HTTPStatusError as e:
            return [TextContent(
                type="text",
                text=f"Ошибка HTTP: {e.response.status_code} при запросе геолокации"
            )]
        except httpx.RequestError:
            return [TextContent(
                type="text",
                text="Ошибка сети: Не удалось подключиться к API геолокации"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Неожиданная ошибка: {type(e).__name__}: {str(e)}"
            )]

    else:
        return [TextContent(
            type="text",
            text=f"Инструмент не найден: {name}"
        )]


async def main():
    """Запуск сервера через stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
