"""Minimal regex route table with 404/405 handling."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from api import handlers
from api.config import Settings
from api.responses import ApiResponse, json_error

Handler = Callable[[Settings, dict[str, str]], Awaitable[ApiResponse]]


@dataclass(frozen=True, slots=True)
class Route:
    method: str
    pattern: re.Pattern[str]
    handler: Handler


ROUTES: tuple[Route, ...] = (
    Route("GET", re.compile(r"/api/v1/status"), handlers.get_status),
    Route(
        "GET",
        re.compile(r"/api/v1/players/(?P<player_id>[^/]+)"),
        handlers.get_player_details,
    ),
)


def resolve(method: str, path: str) -> tuple[Handler, dict[str, str]] | ApiResponse:
    """Return (handler, params) for a match, or an error ApiResponse (404/405)."""
    if len(path) > 1:
        path = path.rstrip("/")
    allowed: list[str] = []
    for route in ROUTES:
        match = route.pattern.fullmatch(path)
        if match is None:
            continue
        if route.method == method.upper():
            return route.handler, match.groupdict()
        allowed.append(route.method)
    if allowed:
        return json_error(
            405,
            "method_not_allowed",
            f"Method {method} not allowed for {path}",
            {"Allow": ", ".join(sorted(set(allowed)))},
        )
    return json_error(404, "not_found", f"No route for {path}")
