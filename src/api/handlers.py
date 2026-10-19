"""Endpoint handlers. Each takes (settings, path params) and returns an ApiResponse."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from api.config import Settings
from api.dtos import MatchDataDto, PlayerDetailsDto, StatusDto
from api.responses import ApiResponse, json_error, json_ok

# Discord user IDs are snowflakes: unsigned 64-bit ints, 17-20 decimal digits in practice.
_DISCORD_ID_RE = re.compile(r"[1-9][0-9]{16,19}")
_UINT64_MAX = 2**64 - 1


def is_discord_id(value: str) -> bool:
    return _DISCORD_ID_RE.fullmatch(value) is not None and int(value) <= _UINT64_MAX


async def get_status(settings: Settings, params: dict[str, str]) -> ApiResponse:
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


async def get_player_details(settings: Settings, params: dict[str, str]) -> ApiResponse:
    if not is_discord_id(params["player_id"]):
        return json_error(400, "invalid_player_id", "player_id must be a Discord user ID")
    # TODO: fetch from Slugbot (settings.slugbot_base_url / settings.slugbot_api_key)
    # using params["player_id"]. Static placeholder until then.
    dto = PlayerDetailsDto(
        season_winrate=0.0,
        current_streak=0,
        last10_results=[],
        current_rank=0,
        current_points=0.0,
        last_matches_results=[0,0,1,1,1],
    )
    return json_ok(dto)
