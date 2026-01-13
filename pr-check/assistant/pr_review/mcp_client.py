"""
MCP WebSocket Client для Git операций

WebSocket клиент для подключения к Git MCP Server и получения информации
о PR (diff, files, content) для автоматического ревью.

Паттерн из bot.py (строки 841-933)
"""

import asyncio
import logging
import json
from typing import Optional, Dict, List

from mcp import ClientSession
from mcp.client.websocket import websocket_client

from .config import (
    MCP_GIT_SERVER_URL,
    MCP_CONNECTION_TIMEOUT,
    MCP_MAX_RETRIES
)

logger = logging.getLogger(__name__)


class GitMCPClient:
    """
    WebSocket клиент для Git MCP Server.

    Предоставляет async методы для получения Git информации через MCP протокол.
    """

    def __init__(self, server_url: str = MCP_GIT_SERVER_URL):
        """
        Инициализация клиента.

        Args:
            server_url: WebSocket URL Git MCP Server
        """
        self.server_url = server_url
        self.timeout = MCP_CONNECTION_TIMEOUT
        self.max_retries = MCP_MAX_RETRIES

    async def _call_tool(
        self,
        tool_name: str,
        arguments: Dict = None,
        timeout: float = None
    ) -> Optional[str]:
        """
        Вызвать MCP tool через WebSocket.

        Args:
            tool_name: Имя инструмента
            arguments: Аргументы инструмента
            timeout: Timeout в секундах (по умолчанию из config)

        Returns:
            Текст результата или None при ошибке
        """
        if timeout is None:
            timeout = float(self.timeout)

        try:
            logger.info(f"Connecting to MCP server at {self.server_url}")
            async with websocket_client(self.server_url) as (read, write):
                logger.debug("WebSocket connection established")
                async with ClientSession(read, write) as session:
                    logger.debug("MCP session created")

                    # Инициализация с timeout
                    await asyncio.wait_for(session.initialize(), timeout=10.0)
                    logger.debug("Session initialized")

                    # Вызов tool
                    logger.info(f"Calling tool: {tool_name}")
                    result = await asyncio.wait_for(
                        session.call_tool(tool_name, arguments or {}),
                        timeout=timeout
                    )
                    logger.info(f"Tool call completed: {tool_name}")

                    # Извлечь текст из результата
                    if result.content and len(result.content) > 0:
                        return result.content[0].text
                    else:
                        logger.warning(f"No content in result from {tool_name}")
                    return None

        except asyncio.TimeoutError:
            logger.error(f"Timeout calling MCP tool: {tool_name}")
            return None
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}", exc_info=True)
            return None

    async def _call_tool_with_retry(
        self,
        tool_name: str,
        arguments: Dict = None,
        timeout: float = None
    ) -> Optional[str]:
        """
        Вызвать MCP tool с retry logic.

        Args:
            tool_name: Имя инструмента
            arguments: Аргументы инструмента
            timeout: Timeout в секундах

        Returns:
            Текст результата или None при ошибке
        """
        for attempt in range(1, self.max_retries + 1):
            logger.info(f"Attempt {attempt}/{self.max_retries} for {tool_name}")

            result = await self._call_tool(tool_name, arguments, timeout)

            if result is not None:
                return result

            if attempt < self.max_retries:
                # Exponential backoff
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

        logger.error(f"All {self.max_retries} attempts failed for {tool_name}")
        return None

    async def get_pr_diff(self, base_branch: str, head_branch: str) -> Optional[Dict]:
        """
        Получить diff между двумя ветками для PR.

        Args:
            base_branch: Базовая ветка (например, 'main')
            head_branch: Ветка с изменениями (например, 'feature/new-feature')

        Returns:
            Dict с diff информацией или None при ошибке
            {
                "success": bool,
                "base": str,
                "head": str,
                "diff": str,
                "stats": {
                    "lines": int,
                    "chars": int,
                    "truncated": bool
                }
            }
        """
        logger.info(f"Getting PR diff: {base_branch}...{head_branch}")

        arguments = {
            "base_branch": base_branch,
            "head_branch": head_branch
        }

        # Увеличенный timeout для больших PR
        result_text = await self._call_tool_with_retry(
            "get-pr-diff",
            arguments,
            timeout=60.0
        )

        if result_text:
            try:
                return json.loads(result_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from get-pr-diff: {e}")
                return None

        return None

    async def get_changed_files(self) -> Optional[List[str]]:
        """
        Получить список всех измененных файлов.

        Returns:
            Список путей к файлам или None при ошибке
        """
        logger.info("Getting changed files")

        result_text = await self._call_tool("get-changed-files")

        if result_text:
            try:
                data = json.loads(result_text)
                if data.get("success"):
                    # Парсим вывод git status
                    # Формат: " M file.py", "?? new_file.py", и т.д.
                    files = []
                    for line in data.get("output", "").split('\n'):
                        if line.strip():
                            # Извлечь путь к файлу
                            parts = line.strip().split(maxsplit=1)
                            if len(parts) == 2:
                                files.append(parts[1])
                    return files
                return None
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from get-changed-files: {e}")
                return None

        return None

    async def get_file_content(self, file_path: str) -> Optional[str]:
        """
        Получить содержимое файла из репозитория.

        Args:
            file_path: Относительный путь к файлу

        Returns:
            Содержимое файла или None при ошибке
        """
        logger.info(f"Getting file content: {file_path}")

        arguments = {"file_path": file_path}

        result_text = await self._call_tool("get-file-content", arguments)

        if result_text:
            try:
                data = json.loads(result_text)
                if data.get("success"):
                    return data.get("content", "")
                else:
                    logger.error(f"Failed to get file content: {data.get('error')}")
                return None
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from get-file-content: {e}")
                return None

        return None

    async def get_current_branch(self) -> Optional[str]:
        """
        Получить текущую git ветку.

        Returns:
            Имя ветки или None при ошибке
        """
        logger.info("Getting current branch")

        result_text = await self._call_tool("get-current-branch")

        if result_text:
            try:
                data = json.loads(result_text)
                if data.get("success"):
                    return data.get("branch", "")
                return None
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from get-current-branch: {e}")
                return None

        return None

    async def get_git_status(self) -> Optional[Dict]:
        """
        Получить статус git репозитория.

        Returns:
            Dict со статусом или None при ошибке
        """
        logger.info("Getting git status")

        result_text = await self._call_tool("get-git-status")

        if result_text:
            try:
                return json.loads(result_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from get-git-status: {e}")
                return None

        return None


# Синхронная обертка для удобства
class GitMCPClientSync:
    """
    Синхронная обертка для GitMCPClient.

    Позволяет использовать async методы в синхронном коде.
    """

    def __init__(self, server_url: str = MCP_GIT_SERVER_URL):
        """
        Инициализация синхронного клиента.

        Args:
            server_url: WebSocket URL Git MCP Server
        """
        self.client = GitMCPClient(server_url)

    def _run_async(self, coro):
        """Запустить async coroutine синхронно."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def get_pr_diff(self, base_branch: str, head_branch: str) -> Optional[Dict]:
        """Синхронная версия get_pr_diff."""
        return self._run_async(self.client.get_pr_diff(base_branch, head_branch))

    def get_changed_files(self) -> Optional[List[str]]:
        """Синхронная версия get_changed_files."""
        return self._run_async(self.client.get_changed_files())

    def get_file_content(self, file_path: str) -> Optional[str]:
        """Синхронная версия get_file_content."""
        return self._run_async(self.client.get_file_content(file_path))

    def get_current_branch(self) -> Optional[str]:
        """Синхронная версия get_current_branch."""
        return self._run_async(self.client.get_current_branch())

    def get_git_status(self) -> Optional[Dict]:
        """Синхронная версия get_git_status."""
        return self._run_async(self.client.get_git_status())


# Тестирование
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test_client():
        """Тестирование MCP клиента."""
        client = GitMCPClient()

        # Тест 1: Текущая ветка
        print("\n=== Test 1: Current branch ===")
        branch = await client.get_current_branch()
        print(f"Current branch: {branch}")

        # Тест 2: Git status
        print("\n=== Test 2: Git status ===")
        status = await client.get_git_status()
        print(f"Status: {status}")

        # Тест 3: Changed files
        print("\n=== Test 3: Changed files ===")
        files = await client.get_changed_files()
        print(f"Changed files: {files}")

        # Тест 4: PR diff (main...current)
        if branch:
            print(f"\n=== Test 4: PR diff (main...{branch}) ===")
            diff_data = await client.get_pr_diff("main", branch)
            if diff_data:
                print(f"Diff stats: {diff_data.get('stats')}")
                print(f"Diff preview: {diff_data.get('diff', '')[:200]}...")

    # Запуск тестов
    asyncio.run(test_client())
