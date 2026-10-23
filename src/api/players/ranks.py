"""Current opponent's rank: from the cache when we have it, from Slugbot otherwise."""

from __future__ import annotations

import logging

from api.context import Context
from api.slugbot import SlugbotError
from api.slugbot.dtos import UNRANKED

logger = logging.getLogger("dbd1v1timerapi")


def _cache_key(player_id: str) -> str:
    return f"slugbot-rank/{player_id}"


async def opponent_rank(ctx: Context, opponent_id: str) -> int:
    """The opponent's leaderboard rank, or UNRANKED.

    A cached rank skips Slugbot; a fetched rank is cached for next time, including UNRANKED
    when Slugbot says so. A cache failure, or a cached value that isn't a number, counts as
    a miss. A failed lookup maps to UNRANKED and isn't cached, so an outage doesn't stick;
    the client has already logged why. Anything else is a bug and propagates.
    """
    key = _cache_key(opponent_id)
    try:
        cached = await ctx.cache.get(key)
    except Exception as exc:
        _log_cache_failure("get", opponent_id, exc)
        cached = None
    if cached is not None:
        try:
            rank = int(cached)
        except ValueError:
            pass
        else:
            logger.debug("Opponent rank cache", extra={"hit": True})
            return rank
    logger.debug("Opponent rank cache", extra={"hit": False})

    try:
        opponent = await ctx.slugbot.get_player(opponent_id)
    except SlugbotError:
        return UNRANKED

    try:
        await ctx.cache.put(key, str(opponent.rank), ctx.settings.slugbot_rank_cache_ttl_sec)
    except Exception as exc:
        _log_cache_failure("put", opponent_id, exc)
    return opponent.rank


def _log_cache_failure(operation: str, player_id: str, exc: Exception) -> None:
    logger.warning(
        f"Cache {operation} failed",
        extra={"player_id": player_id, "reason": f"{type(exc).__name__}: {exc}"},
    )
