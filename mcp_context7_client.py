"""
Context7 MCP Client
Подключение к Context7 MCP-серверу через HTTP и получение списка инструментов.

День 11: Подключение MCP
Для выполнения на Linux сервере
"""

import asyncio
import json
import os
from typing import Optional
from mcp import ClientSession
from mcp.client.sse import sse_client


async def connect_to_context7(api_key: Optional[str] = None):
    """
    Подключается к Context7 MCP серверу и получает список инструментов.

    Args:
        api_key: API ключ для Context7 (опционально)
    """
    url = "https://mcp.context7.com/mcp"

    print("=" * 60)
    print("Подключение к Context7 MCP Server")
    print("=" * 60)
    print(f"URL: {url}")
    print()

    try:
        # Подготовка заголовков
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            print("✓ Использую API ключ для подключения")
        else:
            print("! Подключение без API ключа (базовые лимиты)")
        print()

        # Подключение через SSE (Server-Sent Events)
        print("Установка соединения...")
        async with sse_client(url, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                # Инициализация сессии
                print("Инициализация сессии...")
                await session.initialize()

                print("✓ Успешное подключение к Context7 MCP!")
                print()

                # Получение списка инструментов
                print("Запрос списка доступных инструментов...")
                print()

                tools = await session.list_tools()

                print(f"✓ Найдено инструментов: {len(tools.tools)}")
                print("=" * 60)
                print()

                # Вывод информации о каждом инструменте
                for i, tool in enumerate(tools.tools, 1):
                    print(f"[{i}] {tool.name}")
                    print(f"    📝 Описание: {tool.description}")

                    if hasattr(tool, 'inputSchema') and tool.inputSchema:
                        schema = tool.inputSchema
                        if isinstance(schema, dict):
                            properties = schema.get('properties', {})
                            required = schema.get('required', [])

                            if properties:
                                print(f"    ⚙️  Параметры:")
                                for param_name, param_info in properties.items():
                                    param_type = param_info.get('type', 'unknown')
                                    param_desc = param_info.get('description', '')
                                    is_required = "✓ обязательный" if param_name in required else "○ опциональный"

                                    print(f"      • {param_name}")
                                    print(f"        Тип: {param_type} ({is_required})")
                                    if param_desc:
                                        print(f"        {param_desc}")

                    print()

                print("=" * 60)
                print("✓ Подключение завершено успешно!")
                print()

                return tools.tools

    except Exception as e:
        print()
        print("❌ Ошибка при подключении!")
        print("=" * 60)
        print(f"Тип ошибки: {type(e).__name__}")
        print(f"Сообщение: {str(e)}")
        print()
        print("Проверьте:")
        print("  1. Установлен ли MCP SDK: pip install mcp")
        print("  2. Доступен ли сервер Context7")
        print("  3. Корректен ли API ключ (если используется)")
        print("  4. Есть ли подключение к интернету")
        print()
        raise


async def main():
    """Главная функция."""
    print()
    print("=" * 60)
    print("  Context7 MCP Client - День 11")
    print("  Подключение к MCP серверу")
    print("=" * 60)
    print()

    # Попытка загрузить API ключ из переменной окружения
    api_key = os.getenv('CONTEXT7_API_KEY')

    if api_key:
        print("✓ API ключ найден в переменной окружения CONTEXT7_API_KEY")
    else:
        print("! API ключ не найден. Работа с базовыми лимитами.")
        print("  Для использования API ключа установите переменную окружения:")
        print("  export CONTEXT7_API_KEY='your-api-key'")

    print()

    # Подключение к Context7
    tools = await connect_to_context7(api_key)

    print()
    print(f"📊 Итого получено {len(tools)} инструментов от Context7 MCP")
    print()


if __name__ == "__main__":
    # Запуск асинхронной функции
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        exit(1)
