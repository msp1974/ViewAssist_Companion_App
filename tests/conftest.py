"""Local pytest overrides for lightweight unit tests."""

from __future__ import annotations

import asyncio
import pytest


@pytest.fixture(autouse=True)
def enable_event_loop_debug():
    """Override HA plugin fixture to guarantee a loop exists."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.set_debug(True)
    yield
