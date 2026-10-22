"""Runtime-agnostic key/value cache interface, implemented over the Workers Cache API in entry.py."""

from __future__ import annotations

from typing import Protocol


class Cache(Protocol):
    """String values with a TTL. Both methods raise on backend failure; callers treat that as a miss."""

    async def get(self, key: str) -> str | None:
        """The cached value, or None on a miss or after expiry."""
        ...

    async def put(self, key: str, value: str, ttl_sec: int) -> None: ...
