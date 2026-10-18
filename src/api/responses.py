"""Runtime-agnostic HTTP response model, converted to a Workers Response in entry.py."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from api.dtos import Dto

JSON_CONTENT_TYPE = "application/json; charset=utf-8"


@dataclass(frozen=True, slots=True)
class ApiResponse:
    status: int
    body: Any
    headers: dict[str, str] = field(default_factory=dict)

    def render(self) -> str:
        payload = self.body.to_dict() if isinstance(self.body, Dto) else self.body
        return json.dumps(payload, separators=(",", ":"))

    def all_headers(self) -> dict[str, str]:
        return {"Content-Type": JSON_CONTENT_TYPE, **self.headers}


def json_ok(body: Any, headers: dict[str, str] | None = None) -> ApiResponse:
    return ApiResponse(200, body, headers or {})


def json_error(
    status: int, code: str, message: str, headers: dict[str, str] | None = None
) -> ApiResponse:
    return ApiResponse(status, {"error": {"code": code, "message": message}}, headers or {})
