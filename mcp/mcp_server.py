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
