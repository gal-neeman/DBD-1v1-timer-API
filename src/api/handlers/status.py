"""GET /api/v1/status."""

from __future__ import annotations

from api.context import Context
from api.dtos import StatusDto
from api.responses import ApiResponse, json_ok


async def get_status(ctx: Context, params: dict[str, str]) -> ApiResponse:
    settings = ctx.settings
    dto = StatusDto(
        status_enabled=settings.status_enabled,
        fast_poll_sec=settings.fast_poll_sec,
        slow_poll_sec=settings.slow_poll_sec,
        fast_poll_cap_sec=settings.fast_poll_cap_sec,
        latest_version=settings.latest_version,
        min_supported_version=settings.min_supported_version,
        status_message=settings.status_message,
    )
    return json_ok(dto, {"Cache-Control": "no-store"})
