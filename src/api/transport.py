"""Runtime-agnostic outbound HTTP interface, implemented over workers.fetch in entry.py."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: str


# (method, url, headers) -> response. Raises on network failure.
HttpSend = Callable[[str, str, dict[str, str]], Awaitable[HttpResponse]]
