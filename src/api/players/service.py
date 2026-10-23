"""Builds a player's details from Slugbot and Discord."""

from __future__ import annotations

import asyncio
import logging
from typing import TypeVar

from api.context import Context
from api.dtos import PlayerDetailsDto
from api.players.mapping import NOT_IN_MATCH, to_current_match, to_player_details
from api.players.matches import current_opponent, match_results, player_matches, win_streak
from api.players.names import opponent_names
from api.players.ranks import opponent_rank
from api.slugbot import SlugbotError, SlugbotMatchBatchDto

logger = logging.getLogger("dbd1v1timerapi")

T = TypeVar("T")

LAST_MATCHES_LIMIT = 10
# The first page is unfiltered so it also shows the current match. The margin keeps
# unfinished matches from crowding out finished ones, and covers a match joined right after
# finishing another: it was created earlier, so it sorts below the finished one.
FIRST_PAGE_LIMIT = LAST_MATCHES_LIMIT + 5


async def get_player_details(ctx: Context, player_id: str) -> PlayerDetailsDto:
    """Raises SlugbotError (or a subclass) if the player or their matches can't be fetched."""
    player, batch = await asyncio.gather(
        ctx.slugbot.get_player(player_id),
        ctx.slugbot.get_match_batch(player_id, FIRST_PAGE_LIMIT, complete=False),
        return_exceptions=True,
    )
    # Player errors win, so a missing player is always a 404 whatever the batch did.
    for outcome in (player, batch):
        if isinstance(outcome, BaseException):
            raise outcome

    matches = player_matches(batch.data, player_id)
    results = [int(pm.is_win) for pm in matches]
    streak = win_streak(results)
    recent = matches[:LAST_MATCHES_LIMIT]
    opponent = current_opponent(batch.open_matches, player_id)
    opponent_ids = [pm.opponent.player_id for pm in recent]
    if opponent is not None:
        opponent_ids.append(opponent.player_id)
    # None of these raise for upstream failures, so running them together only saves time.
    names, streak, rank = await asyncio.gather(
        opponent_names(ctx, opponent_ids),
        _extend_streak(ctx, player_id, batch, streak)
        if results and streak == len(results)
        else _value(streak),
        opponent_rank(ctx, opponent.player_id) if opponent is not None else _value(None),
    )
    current = (
        NOT_IN_MATCH
        if opponent is None or rank is None
        else to_current_match(opponent.player_id, names, rank)
    )
    return to_player_details(player, recent, names, streak, current)


async def _value(value: T) -> T:
    return value


async def _extend_streak(
    ctx: Context, player_id: str, batch: SlugbotMatchBatchDto, streak: int
) -> int:
    """Keep counting wins on older pages until a loss or the last page.

    A failed page ends the count early: the streak so far is returned rather than an error.
    """
    while batch.paging.has_next_page and batch.paging.next_cursor is not None:
        cursor = batch.paging.next_cursor
        try:
            batch = await ctx.slugbot.get_match_batch(player_id, LAST_MATCHES_LIMIT, cursor)
        except SlugbotError:
            logger.warning(
                "Win streak truncated", extra={"player_id": player_id, "streak": streak}
            )
            return streak
        results = match_results(batch.data, player_id)
        page_streak = win_streak(results)
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
