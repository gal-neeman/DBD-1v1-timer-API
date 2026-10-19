"""Slugbot API client. URLs come from the SlugbotEndpoint registry; I/O goes through HttpSend."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Protocol, TypeVar

from api.config import Settings
from api.slugbot.dtos import SlugbotMatchBatchDto, SlugbotPlayerDto
from api.slugbot.endpoints import SlugbotEndpoint
from api.transport import HttpSend

logger = logging.getLogger("dbd1v1timerapi")


class SlugbotError(Exception):
    """Slugbot returned an error status, invalid JSON, or an unexpected shape."""


class SlugbotNotFound(SlugbotError):
    """Slugbot returned 404."""


class SlugbotUnavailable(SlugbotError):
    """The request never got a response (network failure)."""


class _FromDict(Protocol):
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Any: ...


T = TypeVar("T", bound=_FromDict)


class SlugbotClient:
    def __init__(self, settings: Settings, send: HttpSend) -> None:
        self._base_url = settings.slugbot_base_url
        self._guild_id = settings.dbdl_guild_id
        self._leaderboard_id = settings.leaderboard_id
        self._api_key = settings.slugbot_api_key
        self._send = send

    async def get_player(self, user_id: str) -> SlugbotPlayerDto:
        data = await self._request(SlugbotEndpoint.PLAYER, user_id=user_id)
        return self._parse(SlugbotEndpoint.PLAYER, SlugbotPlayerDto, data)

    async def get_match_batch(self, user_id: str, limit: int) -> SlugbotMatchBatchDto:
        data = await self._request(
            SlugbotEndpoint.MATCH_BATCH, query={"userId": user_id, "limit": str(limit)}
        )
        return self._parse(SlugbotEndpoint.MATCH_BATCH, SlugbotMatchBatchDto, data)

    async def _request(
        self,
        endpoint: SlugbotEndpoint,
        *,
        query: dict[str, str] | None = None,
        **path_params: str,
    ) -> Any:
        spec = endpoint.value
        path = spec.build_path(
            guild_id=self._guild_id, leaderboard_id=self._leaderboard_id, **path_params
        )
        url = self._base_url + path + spec.build_query(query)
        headers = {"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"}
        log_extra: dict[str, object] = {"endpoint": endpoint.name, "upstream_path": path}

        started = time.perf_counter()
        try:
            response = await self._send(spec.method, url, headers)
        except Exception as exc:
            logger.warning(
                "Slugbot request failed",
                extra={**log_extra, "reason": f"{type(exc).__name__}: {exc}"},
            )
            raise SlugbotUnavailable(f"{endpoint.name}: {type(exc).__name__}") from exc

        log_extra["upstream_status"] = response.status
        log_extra["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        if response.status == 404:
            logger.info("Slugbot not found", extra=log_extra)
            raise SlugbotNotFound(f"{endpoint.name}: 404")
        if not 200 <= response.status < 300:
            logger.warning("Slugbot error status", extra=log_extra)
            raise SlugbotError(f"{endpoint.name}: HTTP {response.status}")
        logger.debug("Slugbot request ok", extra=log_extra)

        try:
            return json.loads(response.body)
        except ValueError as exc:
            logger.warning("Slugbot returned invalid JSON", extra=log_extra)
            raise SlugbotError(f"{endpoint.name}: invalid JSON") from exc

    @staticmethod
    def _parse(endpoint: SlugbotEndpoint, dto_cls: type[T], data: Any) -> T:
        try:
            return dto_cls.from_dict(data)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            reason = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Slugbot response did not match schema",
                extra={"endpoint": endpoint.name, "reason": reason},
            )
            raise SlugbotError(f"{endpoint.name}: unexpected response shape ({reason})") from exc
