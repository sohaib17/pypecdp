"""Pytest configuration and shared fixtures."""

import asyncio
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest


@pytest.fixture
def mock_process() -> Mock:
    """Create a mock subprocess."""
    proc = Mock()
    proc.pid = 12345
    proc.returncode = None
    proc.wait = AsyncMock(return_value=0)
    proc.terminate = Mock()
    proc.kill = Mock()
    return proc


@pytest.fixture
def mock_reader() -> AsyncMock:
    """Create a mock StreamReader."""
    reader = AsyncMock()
    reader.readuntil = AsyncMock()
    return reader


@pytest.fixture
def mock_writer() -> Mock:
    """Create a mock writer."""
    writer = Mock()
    writer.write = Mock()
    writer.drain = AsyncMock()
    writer.close = Mock()
    return writer


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_browser_context() -> AsyncGenerator[dict[str, Any], None]:
    """Create a mock browser with basic setup."""
    from unittest.mock import AsyncMock, Mock, patch

    proc = Mock()
    proc.pid = 12345
    proc.returncode = None
    proc.wait = AsyncMock()

    reader = AsyncMock()
    writer = Mock()
    writer.write = Mock()
    writer.drain = AsyncMock()
    writer.close = Mock()

    context = {
        "proc": proc,
        "reader": reader,
        "writer": writer,
    }

    yield context
