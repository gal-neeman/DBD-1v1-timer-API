"""Endpoint handlers. Each takes (context, path params) and returns an ApiResponse."""

from __future__ import annotations

import asyncio
import logging
import re

from api.context import Context
from api.discord import DiscordError
from api.dtos import MatchDto, PlayerDetailsDto, StatusDto
from api.responses import ApiResponse, json_error, json_ok
from api.slugbot import (
    SlugbotError,
    SlugbotMatchBatchDto,
    SlugbotMatchDto,
    SlugbotMatchParticipantDto,
    SlugbotNotFound,
    SlugbotPlayerDto,
    SlugbotUnavailable,
)

logger = logging.getLogger("dbd1v1timerapi")

# Discord user IDs are snowflakes: unsigned 64-bit ints, 17-20 decimal digits in practice.
_DISCORD_ID_RE = re.compile(r"[1-9][0-9]{16,19}")
_UINT64_MAX = 2**64 - 1

_LAST_MATCHES_LIMIT = 10
_UNKNOWN_NAME = "Unknown"

# (match, the player's participant entry, the opponent's participant entry)
_PlayerMatch = tuple[SlugbotMatchDto, SlugbotMatchParticipantDto, SlugbotMatchParticipantDto]


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

    matches = _player_matches(batch.data, player_id)
    results = [_result(match, me) for match, me, _ in matches]
    streak = _win_streak(results)
    names_lookup = _opponent_names(ctx, [opponent.player_id for _, _, opponent in matches])
    if results and streak == len(results):
        # Neither raises for upstream failures, so running them together only saves time.
        streak, names = await asyncio.gather(
            _extend_streak(ctx, player_id, batch, streak), names_lookup
        )
    else:
        names = await names_lookup
    return json_ok(_to_player_details(player, matches, names, streak))


async def _opponent_names(ctx: Context, opponent_ids: list[str]) -> dict[str, str]:
    """Discord display name per opponent, looked up once each and in parallel.

    A failed lookup (already logged by the client) maps to "Unknown" instead of failing
    the request; anything else is a bug and propagates.
    """
    unique_ids = list(dict.fromkeys(opponent_ids))
    users = await asyncio.gather(
        *(ctx.discord.get_user(user_id) for user_id in unique_ids), return_exceptions=True
    )
    names: dict[str, str] = {}
    for user_id, user in zip(unique_ids, users):
        if isinstance(user, DiscordError):
            names[user_id] = _UNKNOWN_NAME
        elif isinstance(user, BaseException):
            raise user
        else:
            names[user_id] = user.display_name
    return names


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


def _player_matches(matches: list[SlugbotMatchDto], player_id: str) -> list[_PlayerMatch]:
    """Newest first. Matches without the player, or without an opponent, are skipped."""
    found: list[_PlayerMatch] = []
    for match in sorted(matches, key=lambda m: m.timestamp, reverse=True):
        me = next((p for p in match.participants if p.player_id == player_id), None)
        if me is None:
            continue
        opponent = next((p for p in match.participants if p.team_id != me.team_id), None)
        if opponent is not None:
            found.append((match, me, opponent))
    return found


def _result(match: SlugbotMatchDto, me: SlugbotMatchParticipantDto) -> int:
    return 1 if me.team_id == match.win_team else 0


def _match_results(matches: list[SlugbotMatchDto], player_id: str) -> list[int]:
    """1 for a win, 0 for a loss, newest first."""
    return [_result(match, me) for match, me, _ in _player_matches(matches, player_id)]


def _score(match: SlugbotMatchDto, team_id: int) -> int | None:
    """Games the team won. Each participant declares it; the declarations agree on completed matches."""
    declared = match.declared_results.get(f"team{team_id}")
    return declared[0] if declared else None


def _win_streak(results: list[int]) -> int:
    streak = 0
    for result in results:
        if result != 1:
            break
        streak += 1
    return streak


def _winrate_percent(won: int, played: int) -> float:
    return round(won / played * 100, 2) if played > 0 else 0.0


def _to_match(match: _PlayerMatch, names: dict[str, str]) -> MatchDto:
    slugbot_match, me, opponent = match
    return MatchDto(
        opponent_name=names.get(opponent.player_id, _UNKNOWN_NAME),
        points_gained=me.points_received,
        match_date=slugbot_match.timestamp,
        is_win=me.team_id == slugbot_match.win_team,
        player_score=_score(slugbot_match, me.team_id),
        opponent_score=_score(slugbot_match, opponent.team_id),
        player_rank_before=me.initial_rank,
        opponent_rank_before=opponent.initial_rank,
    )


def _to_player_details(
    player: SlugbotPlayerDto, matches: list[_PlayerMatch], names: dict[str, str], streak: int
) -> PlayerDetailsDto:
    return PlayerDetailsDto(
        player_name=player.display_name,
        season_winrate=_winrate_percent(player.matches_won, player.matches_played),
        current_streak=streak,
        current_rank=player.rank,
        current_points=player.points,
        last_matches=[_to_match(match, names) for match in matches],
    )
