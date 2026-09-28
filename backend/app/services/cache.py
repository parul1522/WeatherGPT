"""Small in-memory TTL cache.

The methods are async so a Redis-backed class with the same interface can replace this one
without changing any caller. Values are kept as Python objects; a Redis version would
serialise them (the cached objects are Pydantic models or dataclasses of them).
"""

import time
from typing import Any


class InMemoryTTLCache:
    def __init__(self, max_items: int = 2048) -> None:
        self._max_items = max_items
        self._store: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= time.monotonic():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            return
        if len(self._store) >= self._max_items and key not in self._store:
            self._evict()
        self._store[key] = (time.monotonic() + ttl_seconds, value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def clear(self) -> None:
        self._store.clear()

    def _evict(self) -> None:
        now = time.monotonic()
        for key in [k for k, (expires_at, _) in self._store.items() if expires_at <= now]:
            del self._store[key]
        # Still full: drop the oldest insertions (dicts keep insertion order).
        while len(self._store) >= self._max_items:
            del self._store[next(iter(self._store))]
