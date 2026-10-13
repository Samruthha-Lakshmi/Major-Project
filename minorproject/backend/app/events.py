"""In-process pub/sub that carries pipeline events from worker threads to WebSocket clients.

Each run has its own channel (with a replay buffer so late subscribers see every
event), and a global "feed" channel announces run lifecycle changes to all clients.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any


class Channel:
    def __init__(self, keep_history: bool) -> None:
        self.history: list[dict] = []
        self.keep_history = keep_history
        self.subscribers: set[asyncio.Queue] = set()
        self.closed = False


class EventBus:
    def __init__(self) -> None:
        self._channels: dict[str, Channel] = defaultdict(lambda: Channel(keep_history=True))
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    # -- publishing (safe to call from any thread) ---------------------------------
    def publish(self, channel: str, event: dict[str, Any]) -> None:
        event = {"ts": time.time(), **event}
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._deliver, channel, event)

    def close(self, channel: str) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._close, channel)

    def _deliver(self, channel: str, event: dict) -> None:
        ch = self._channels[channel]
        if channel == "feed":
            ch.keep_history = False
        if ch.keep_history:
            ch.history.append(event)
        for q in list(ch.subscribers):
            q.put_nowait(event)

    def _close(self, channel: str) -> None:
        ch = self._channels.get(channel)
        if not ch:
            return
        ch.closed = True
        for q in list(ch.subscribers):
            q.put_nowait(None)

    def history(self, channel: str) -> list[dict]:
        ch = self._channels.get(channel)
        return list(ch.history) if ch else []

    def forget(self, channel: str) -> None:
        self._channels.pop(channel, None)

    # -- subscribing (event-loop side) --------------------------------------------
    def subscribe(self, channel: str) -> tuple[asyncio.Queue, list[dict], bool]:
        ch = self._channels[channel]
        q: asyncio.Queue = asyncio.Queue()
        ch.subscribers.add(q)
        return q, list(ch.history), ch.closed

    def unsubscribe(self, channel: str, q: asyncio.Queue) -> None:
        ch = self._channels.get(channel)
        if ch:
            ch.subscribers.discard(q)

    def known(self, channel: str) -> bool:
        return channel in self._channels


bus = EventBus()
