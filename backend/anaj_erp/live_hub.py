"""WebSocket fan-out for LAN live events (locks, auction board, mandi bhav)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class LiveEventHub:
    """Thread-safe bridge between sync RPC handlers and async WebSocket clients."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._clients: set[Any] = set()
        self._lock = asyncio.Lock()

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def register(self, websocket: Any) -> None:
        async with self._lock:
            self._clients.add(websocket)

    async def unregister(self, websocket: Any) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def _broadcast_async(self, event: str, payload: dict[str, Any]) -> None:
        message = json.dumps({"event": event, "payload": payload}, default=str)
        async with self._lock:
            dead: list[Any] = []
            for client in self._clients:
                try:
                    await client.send_text(message)
                except Exception:
                    dead.append(client)
            for client in dead:
                self._clients.discard(client)

    def broadcast(self, event: str, payload: dict[str, Any]) -> None:
        if self._loop is None or not self._loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(
            self._broadcast_async(event, payload),
            self._loop,
        )
