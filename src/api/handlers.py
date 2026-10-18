"""Endpoint handlers. Each takes (settings, path params) and returns an ApiResponse."""

from __future__ import annotations

from datetime import datetime, timezone

from api.config import Settings
from api.dtos import MatchDataDto, PlayerDetailsDto, StatusDto
from api.responses import ApiResponse, json_ok


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
    # TODO: fetch from Slugbot (settings.slugbot_base_url / settings.slugbot_api_key)
    # using params["player_id"]. Static placeholder until then.
    dto = PlayerDetailsDto(
        season_winrate=0.0,
        current_streak=0,
        last10_results=[],
        current_rank=0,
        current_points=0.0,
        last10_matches_data=[
            MatchDataDto(
                played_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
                players=[],
                is_win=False,
                points_received=0.0,
            )
        ],
    )
    return json_ok(dto)
