"""Builds a player's details from Slugbot and Discord."""

from __future__ import annotations

import asyncio
import logging

from api.context import Context
from api.dtos import PlayerDetailsDto
from api.players.mapping import to_player_details
from api.players.matches import match_results, player_matches, win_streak
from api.players.names import opponent_names
from api.slugbot import SlugbotError, SlugbotMatchBatchDto

logger = logging.getLogger("dbd1v1timerapi")

LAST_MATCHES_LIMIT = 10


async def get_player_details(ctx: Context, player_id: str) -> PlayerDetailsDto:
    """Raises SlugbotError (or a subclass) if the player or their matches can't be fetched."""
    player, batch = await asyncio.gather(
        ctx.slugbot.get_player(player_id),
        ctx.slugbot.get_match_batch(player_id, LAST_MATCHES_LIMIT),
        return_exceptions=True,
    )
    # Player errors win, so a missing player is always a 404 whatever the batch did.
    for outcome in (player, batch):
        if isinstance(outcome, BaseException):
            raise outcome

    matches = player_matches(batch.data, player_id)
    results = [int(pm.is_win) for pm in matches]
    streak = win_streak(results)
    names_lookup = opponent_names(ctx, [pm.opponent.player_id for pm in matches])
    if results and streak == len(results):
        # Neither raises for upstream failures, so running them together only saves time.
        streak, names = await asyncio.gather(
            _extend_streak(ctx, player_id, batch, streak), names_lookup
        )
    else:
        names = await names_lookup
    return to_player_details(player, matches, names, streak)


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
