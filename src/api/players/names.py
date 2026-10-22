"""Opponent display names: from the cache when we have them, from Discord otherwise."""

from __future__ import annotations

import asyncio
import logging

from api.context import Context
from api.discord import DiscordError
from api.players.mapping import UNKNOWN_NAME

logger = logging.getLogger("dbd1v1timerapi")


def _cache_key(user_id: str) -> str:
    return f"discord-name/{user_id}"


async def opponent_names(ctx: Context, opponent_ids: list[str]) -> dict[str, str]:
    """Discord display name per opponent, looked up once each and in parallel.

    Cached names skip Discord entirely; fetched names are cached for next time. A cache
    failure counts as a miss. A failed Discord lookup (already logged by the client) maps
    to "Unknown" and isn't cached, so an outage doesn't stick. Anything else is a bug and
    propagates.
    """
    unique_ids = list(dict.fromkeys(opponent_ids))
    cached = await asyncio.gather(
        *(ctx.cache.get(_cache_key(user_id)) for user_id in unique_ids), return_exceptions=True
    )
    names: dict[str, str] = {}
    misses: list[str] = []
    for user_id, value in zip(unique_ids, cached):
        if isinstance(value, str):
            names[user_id] = value
            continue
        if isinstance(value, Exception):
            _log_cache_failure("get", user_id, value)
        elif isinstance(value, BaseException):
            raise value
        misses.append(user_id)
    logger.debug("Opponent name cache", extra={"hits": len(names), "misses": len(misses)})

    users = await asyncio.gather(
        *(ctx.discord.get_user(user_id) for user_id in misses), return_exceptions=True
    )
    fetched: dict[str, str] = {}
    for user_id, user in zip(misses, users):
        if isinstance(user, DiscordError):
            names[user_id] = UNKNOWN_NAME
        elif isinstance(user, BaseException):
            raise user
        else:
            names[user_id] = fetched[user_id] = user.display_name

    ttl = ctx.settings.discord_name_cache_ttl_sec
    stored = await asyncio.gather(
        *(ctx.cache.put(_cache_key(user_id), name, ttl) for user_id, name in fetched.items()),
        return_exceptions=True,
    )
    for user_id, outcome in zip(fetched, stored):
        if isinstance(outcome, Exception):
            _log_cache_failure("put", user_id, outcome)
        elif isinstance(outcome, BaseException):
            raise outcome
    return names


def _log_cache_failure(operation: str, user_id: str, exc: Exception) -> None:
    logger.warning(
        f"Cache {operation} failed",
        extra={"user_id": user_id, "reason": f"{type(exc).__name__}: {exc}"},
    )
