"""Endpoint handlers. Each takes (context, path params) and returns an ApiResponse."""

from __future__ import annotations

import asyncio
import logging
import re

from api.context import Context
from api.dtos import PlayerDetailsDto, StatusDto
from api.responses import ApiResponse, json_error, json_ok
from api.slugbot import (
    SlugbotError,
    SlugbotMatchBatchDto,
    SlugbotMatchDto,
    SlugbotNotFound,
    SlugbotPlayerDto,
    SlugbotUnavailable,
)

logger = logging.getLogger("dbd1v1timerapi")

# Discord user IDs are snowflakes: unsigned 64-bit ints, 17-20 decimal digits in practice.
_DISCORD_ID_RE = re.compile(r"[1-9][0-9]{16,19}")
_UINT64_MAX = 2**64 - 1

_LAST_MATCHES_LIMIT = 10


def is_discord_id(value: str) -> bool:
    return _DISCORD_ID_RE.fullmatch(value) is not None and int(value) <= _UINT64_MAX


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


async def get_player_details(ctx: Context, params: dict[str, str]) -> ApiResponse:
    player_id = params["player_id"]
    if not is_discord_id(player_id):
        return json_error(400, "invalid_player_id", "player_id must be a Discord user ID")

    # The client logs every failure, so errors are only mapped to responses here.
    # SlugbotNotFound and SlugbotUnavailable subclass SlugbotError, so they come first.
    try:
        player, batch = await asyncio.gather(
            ctx.slugbot.get_player(player_id),
            ctx.slugbot.get_match_batch(player_id, _LAST_MATCHES_LIMIT),
            return_exceptions=True,
        )
        # Player errors win, so a missing player is always a 404 whatever the batch did.
        for outcome in (player, batch):
            if isinstance(outcome, BaseException):
                raise outcome
    except SlugbotNotFound:
        return json_error(404, "player_not_found", "No ranked data for this player")
    except SlugbotUnavailable:
        return json_error(503, "upstream_unavailable", "Leaderboard service is unreachable")
    except SlugbotError:
        return json_error(
            502, "upstream_error", "Leaderboard service returned an invalid response"
        )

    results = _match_results(batch.data, player_id)
    streak = _win_streak(results)
    if results and streak == len(results):
        streak = await _extend_streak(ctx, player_id, batch, streak)
    return json_ok(_to_player_details(player, results, streak))


async def _extend_streak(
    ctx: Context, player_id: str, batch: SlugbotMatchBatchDto, streak: int
) -> int:
    """Keep counting wins on older pages until a loss or the last page.

    A failed page ends the count early: the streak so far is returned rather than an error.
    """
    while batch.paging.has_next_page and batch.paging.next_cursor is not None:
        cursor = batch.paging.next_cursor
        try:
            batch = await ctx.slugbot.get_match_batch(player_id, _LAST_MATCHES_LIMIT, cursor)
        except SlugbotError:
            logger.warning(
                "Win streak truncated", extra={"player_id": player_id, "streak": streak}
            )
            return streak
        results = _match_results(batch.data, player_id)
        page_streak = _win_streak(results)
        streak += page_streak
        if page_streak < len(results):
            break
        # Without this a misbehaving upstream could keep us paging forever.
        if batch.paging.next_cursor == cursor:
            logger.warning(
                "Slugbot paging cursor did not advance",
                extra={"player_id": player_id, "cursor": cursor, "streak": streak},
            )
            break
    return streak


def _match_results(matches: list[SlugbotMatchDto], player_id: str) -> list[int]:
    """1 for a win, 0 for a loss, newest first. Matches the player isn't in are skipped."""
    results: list[int] = []
    for match in sorted(matches, key=lambda m: m.timestamp, reverse=True):
        participant = next((p for p in match.participants if p.player_id == player_id), None)
        if participant is not None:
            results.append(1 if participant.team_id == match.win_team else 0)
    return results


def _win_streak(results: list[int]) -> int:
    streak = 0
    for result in results:
        if result != 1:
            break
        streak += 1
    return streak


def _winrate_percent(won: int, played: int) -> float:
    return round(won / played * 100, 2) if played > 0 else 0.0


def _to_player_details(
    player: SlugbotPlayerDto, results: list[int], streak: int
) -> PlayerDetailsDto:
    return PlayerDetailsDto(
        player_name=player.display_name,
        season_winrate=_winrate_percent(player.matches_won, player.matches_played),
        current_streak=streak,
        current_rank=player.rank,
        current_points=player.points,
        last_matches_results=results,
    )
