"""Tiny in-process pub/sub so open clients learn about new articles and count changes (SSE)."""

from __future__ import annotations

import asyncio
import json
from typing import Any


class Broadcaster:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[str]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        self._queues.discard(q)

    def _deliver(self, message: str) -> None:
        for q in list(self._queues):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                pass

    def publish(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Safe to call from the event loop or from worker threads."""
        message = json.dumps({"type": event, **(data or {})})
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            self._deliver(message)
        else:
            loop.call_soon_threadsafe(self._deliver, message)


broadcaster = Broadcaster()
