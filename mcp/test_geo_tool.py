"""
Тестирование инструмента GeoIP в MCP сервере
День 12: Первый инструмент MCP

Тестирует новый инструмент getGeoByIP с различными IP-адресами.
"""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_geo_tool():
    """Тестирование инструмента геолокации по IP."""
    print()
    print("=" * 70)
    print("  Тестирование GeoIP инструмента MCP сервера")
    print("=" * 70)
    print()

    # Параметры для запуска локального MCP-сервера
    # Используем sys.executable чтобы запустить тот же Python, что и текущий скрипт
    import sys
    server_params = StdioServerParameters(
        command=sys.executable,  # Автоматически использует активный Python (venv или system)
        args=["mcp_server.py"],
        env=None
    )

    # Тестовые IP-адреса
    test_ips = [
        ("8.8.8.8", "Google DNS - USA"),
        ("1.1.1.1", "Cloudflare - Australia"),
        ("77.88.8.8", "Yandex - Russia"),
        ("256.1.1.1", "Некорректный IP (тест валидации)"),
        ("invalid", "Неверный формат (тест валидации)")
    ]

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

                # Проверка наличия инструмента getGeoByIP
                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]

                if "getGeoByIP" not in tool_names:
                    print("❌ Ошибка: Инструмент getGeoByIP не найден!")
                    print(f"   Доступные инструменты: {', '.join(tool_names)}")
                    return

                print(f"✓ Инструмент getGeoByIP найден в списке ({len(tools.tools)} всего)")
                print()
                print("=" * 70)
                print()

                # Тестирование каждого IP-адреса
                for i, (ip, description) in enumerate(test_ips, 1):
                    print(f"[Тест {i}/{len(test_ips)}] {description}")
                    print(f"   IP: {ip}")
                    print()

                    try:
                        # Вызов инструмента через MCP
                        result = await session.call_tool(
                            "getGeoByIP",
                            arguments={"ip_address": ip}
                        )

                        # Обработка результата
                        if result and result.content:
                            for content in result.content:
                                if hasattr(content, 'text'):
                                    # Форматирование вывода
                                    lines = content.text.split('\n')
                                    for line in lines:
                                        print(f"   {line}")
                            print("   ✓ Успешно")
                        else:
                            print("   ⚠ Пустой результат")

                    except Exception as e:
                        print(f"   ❌ Ошибка: {type(e).__name__}")
                        print(f"   {str(e)}")

                    print()
                    print("-" * 70)
                    print()

                    # Небольшая задержка между запросами
                    if i < len(test_ips):
                        await asyncio.sleep(0.5)

                print("=" * 70)
                print()
                print("✅ Тестирование завершено!")
                print(f"   Протестировано IP-адресов: {len(test_ips)}")
                print()

    except FileNotFoundError:
        print()
        print("❌ Ошибка: Файл mcp_server.py не найден!")
        print()
        print("Убедитесь, что файл mcp_server.py находится")
        print("в той же директории, что и этот скрипт.")
        print()
    except Exception as e:
        print()
        print("❌ Ошибка при тестировании!")
        print("=" * 70)
        print(f"Тип ошибки: {type(e).__name__}")
        print(f"Сообщение: {str(e)}")
        print()
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(test_geo_tool())
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        exit(1)
