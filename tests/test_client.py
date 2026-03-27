"""Tests for the custom Wyoming TCP client."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock


class _FakeAsyncTcpClient:
    """Lightweight stand-in for wyoming.client.AsyncTcpClient."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._writer = None

    async def write_event(self, event) -> None:
        return None

    async def read_event(self):
        return None


def _load_module_with_wyoming_stubs():
    """Load client module with stubbed wyoming dependencies."""
    wyoming_pkg = types.ModuleType("wyoming")
    wyoming_client = types.ModuleType("wyoming.client")
    wyoming_event = types.ModuleType("wyoming.event")

    wyoming_client.AsyncTcpClient = _FakeAsyncTcpClient
    wyoming_event.Event = object

    sys.modules["wyoming"] = wyoming_pkg
    sys.modules["wyoming.client"] = wyoming_client
    sys.modules["wyoming.event"] = wyoming_event

    module_path = Path(__file__).resolve().parents[1] / "custom_components" / "vaca" / "client.py"
    spec = importlib.util.spec_from_file_location("va_client_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_write_event_short_circuits_when_not_writable():
    module = _load_module_with_wyoming_stubs()

    before_callback = AsyncMock()
    after_callback = AsyncMock()
    client = module.VAAsyncTcpClient(
        "127.0.0.1",
        10700,
        before_send_callback=before_callback,
        after_send_callback=after_callback,
    )
    client.can_write_event = lambda: False

    event = {"type": "ping"}
    asyncio.run(client.write_event(event))

    before_callback.assert_awaited_once_with(event)
    after_callback.assert_not_awaited()


def test_write_event_calls_super_and_after_callback():
    module = _load_module_with_wyoming_stubs()
    module.AsyncTcpClient.write_event = AsyncMock()

    before_callback = AsyncMock()
    after_callback = AsyncMock()
    client = module.VAAsyncTcpClient(
        "127.0.0.1",
        10700,
        before_send_callback=before_callback,
        after_send_callback=after_callback,
    )
    client.can_write_event = lambda: True

    event = {"type": "run-pipeline"}
    asyncio.run(client.write_event(event))

    before_callback.assert_awaited_once_with(event)
    module.AsyncTcpClient.write_event.assert_awaited_once_with(event)
    after_callback.assert_awaited_once_with(event)


def test_read_event_returns_none_on_timeout():
    module = _load_module_with_wyoming_stubs()
    module.AsyncTcpClient.read_event = AsyncMock(side_effect=asyncio.TimeoutError())

    client = module.VAAsyncTcpClient("127.0.0.1", 10700)
    result = asyncio.run(client.read_event())

    assert result is None


def test_read_event_filters_until_forwarded():
    module = _load_module_with_wyoming_stubs()
    module.AsyncTcpClient.read_event = AsyncMock(side_effect=["first", "second"])

    callback_results = iter([(False, None), (True, "modified-second")])

    def on_receive(_event):
        return next(callback_results)

    client = module.VAAsyncTcpClient(
        "127.0.0.1",
        10700,
        on_receive_callback=on_receive,
    )

    result = asyncio.run(client.read_event())

    assert result == "modified-second"


def test_can_write_event_respects_writer_state():
    module = _load_module_with_wyoming_stubs()
    client = module.VAAsyncTcpClient("127.0.0.1", 10700)

    assert client.can_write_event() is False

    class _Writer:
        def __init__(self, closing: bool) -> None:
            self._closing = closing

        def is_closing(self) -> bool:
            return self._closing

    client._writer = _Writer(closing=True)
    assert client.can_write_event() is False

    client._writer = _Writer(closing=False)
    assert client.can_write_event() is True
