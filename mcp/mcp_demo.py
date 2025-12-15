"""
MCP Demo - День 11: Подключение MCP
Простая демонстрация подключения к MCP серверу

Запускает локальный MCP-сервер и подключается к нему.
"""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run_demo():
    """Запуск демонстрации MCP."""
    print()
    print("=" * 60)
    print("  MCP Client - День 11")
    print("  Подключение к MCP серверу")
    print("=" * 60)
    print()

    # Параметры для запуска локального MCP-сервера
    server_params = StdioServerParameters(
        command="python3",
        args=["mcp_server.py"],
        env=None
    )

    print("Запуск локального MCP сервера...")
    print()

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Инициализация
                print("Инициализация сессии...")
                await session.initialize()

                print("✓ Успешное подключение к MCP серверу!")
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

                print(f"📊 Итого получено {len(tools.tools)} инструментов от MCP сервера")
                print()

                print("✅ День 11 выполнен успешно!")
                print("   - Создан MCP-сервер с 3 инструментами")
                print("   - Выполнено подключение к серверу")
                print("   - Получен список инструментов")
                print()

    except FileNotFoundError:
        print()
        print("❌ Ошибка: Файл mcp_server_stdio.py не найден!")
        print()
        print("Убедитесь, что файл mcp_server_stdio.py находится")
        print("в той же директории, что и этот скрипт.")
        print()
    except Exception as e:
        print()
        print("❌ Ошибка при подключении!")
        print("=" * 60)
        print(f"Тип ошибки: {type(e).__name__}")
        print(f"Сообщение: {str(e)}")
        print()
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        exit(1)
