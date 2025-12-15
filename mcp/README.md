# День 11: Подключение к MCP

Демонстрация подключения к MCP-серверу через stdio.

## Файлы

- `mcp_server.py` - MCP-сервер с 3 инструментами
- `mcp_client.py` - MCP-клиент для подключения к серверу
- `requirements.txt` - Зависимости Python

## Инструменты сервера

1. **get-current-time** - получить текущее время сервера
2. **calculate** - математические вычисления (add, subtract, multiply, divide)
3. **echo** - вернуть эхо сообщения

## Запуск

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить демо
python3 mcp_client.py
```

Клиент автоматически запустит сервер и подключится к нему.
