"""Slugbot API client. URLs come from the SlugbotEndpoint registry; I/O goes through HttpSend."""

from __future__ import annotations

import logging

from api.config import Settings
from api.slugbot.dtos import SlugbotMatchBatchDto, SlugbotPlayerDto
from api.slugbot.endpoints import SlugbotEndpoint
from api.transport import HttpSend
from api.upstream import UpstreamClient, UpstreamError, UpstreamNotFound, UpstreamUnavailable

logger = logging.getLogger("dbd1v1timerapi")


class SlugbotError(UpstreamError):
    """Slugbot returned an error status, invalid JSON, or an unexpected shape."""


class SlugbotNotFound(SlugbotError, UpstreamNotFound):
    """Slugbot returned 404."""


class SlugbotUnavailable(SlugbotError, UpstreamUnavailable):
    """The request never got a response (network failure or timeout)."""


class SlugbotClient(UpstreamClient):
    _name = "Slugbot"
    _error = SlugbotError
    _not_found = SlugbotNotFound
    _unavailable = SlugbotUnavailable

    def __init__(self, settings: Settings, send: HttpSend) -> None:
        super().__init__(settings.slugbot_base_url, settings.slugbot_timeout_sec, send)
        self._guild_id = settings.dbdl_guild_id
        self._leaderboard_id = settings.leaderboard_id
        self._api_key = settings.slugbot_api_key

    def _headers(self) -> dict[str, str]:
        return {**super()._headers(), "Authorization": f"Bearer {self._api_key}"}

    def _path_params(self) -> dict[str, str]:
        return {"guild_id": self._guild_id, "leaderboard_id": self._leaderboard_id}

    async def get_player(self, user_id: str) -> SlugbotPlayerDto:
        data = await self._request(SlugbotEndpoint.PLAYER, user_id=user_id)
        return self._parse(SlugbotEndpoint.PLAYER, SlugbotPlayerDto, data)

    async def get_match_batch(
        self, user_id: str, limit: int, cursor: int | None = None, *, complete: bool = True
    ) -> SlugbotMatchBatchDto:
        """Newest matches first; pass a previous page's paging.next_cursor to get older ones.

        complete=False doesn't filter to unfinished matches: it returns finished and
        unfinished ones mixed, and the unfinished ones land in open_matches.
        """
        query = {"userId": user_id, "limit": str(limit), "complete": str(complete).lower()}
        if cursor is not None:
            query["nextCursor"] = str(cursor)
        data = await self._request(SlugbotEndpoint.MATCH_BATCH, query=query)
        batch = self._parse(SlugbotEndpoint.MATCH_BATCH, SlugbotMatchBatchDto, data)
        if not batch.success:
            logger.warning(
                "Slugbot batch unsuccessful",
                extra={"endpoint": SlugbotEndpoint.MATCH_BATCH.name, "cursor": cursor},
            )
            raise SlugbotError("MATCH_BATCH: success=false")
        return batch
