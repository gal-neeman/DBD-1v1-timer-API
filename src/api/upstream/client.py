"""Base client for upstream JSON APIs. URLs come from an Endpoint enum; I/O goes through HttpSend."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from enum import Enum
from typing import Any, ClassVar, Protocol, TypeVar

from api.transport import HttpSend
from api.upstream.endpoint import Endpoint

logger = logging.getLogger("dbd1v1timerapi")


class UpstreamError(Exception):
    """The upstream returned an error status, invalid JSON, or an unexpected shape."""


class UpstreamNotFound(UpstreamError):
    """The upstream returned 404."""


class UpstreamUnavailable(UpstreamError):
    """The request never got a response (network failure or timeout)."""


class _FromDict(Protocol):
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Any: ...


T = TypeVar("T", bound=_FromDict)


class UpstreamClient:
    """Subclasses set the class attributes below and override _headers/_path_params as needed."""

    # Prefix for log messages, e.g. "Slugbot request failed".
    _name: ClassVar[str]
    _error: ClassVar[type[UpstreamError]]
    _not_found: ClassVar[type[UpstreamError]]
    _unavailable: ClassVar[type[UpstreamError]]

    def __init__(self, base_url: str, timeout: float, send: HttpSend) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._send = send

    def _headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _path_params(self) -> dict[str, str]:
        """Params filled into every path template (e.g. a fixed guild id)."""
        return {}

    async def _request(
        self,
        endpoint: Enum,
        *,
        query: dict[str, str] | None = None,
        log: bool = True,
        **path_params: str,
    ) -> Any:
        """log=False is for callers that log the outcome themselves."""
        spec: Endpoint = endpoint.value
        path = spec.build_path(**self._path_params(), **path_params)
        url = self._base_url + path + spec.build_query(query)
        headers = self._headers()
        log_extra: dict[str, object] = {"endpoint": endpoint.name, "upstream_path": path}

        started = time.perf_counter()
        try:
            # Stops waiting on timeout (raises TimeoutError); the fetch itself isn't aborted.
            response = await asyncio.wait_for(
                self._send(spec.method, url, headers), timeout=self._timeout
            )
        except Exception as exc:
            if log:
                logger.warning(
                    f"{self._name} request failed",
                    extra={**log_extra, "reason": f"{type(exc).__name__}: {exc}"},
                )
            raise self._unavailable(f"{endpoint.name}: {type(exc).__name__}") from exc

        log_extra["upstream_status"] = response.status
        log_extra["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        if response.status == 404:
            if log:
                logger.info(f"{self._name} not found", extra=log_extra)
            raise self._not_found(f"{endpoint.name}: 404")
        if not 200 <= response.status < 300:
            if log:
                logger.warning(f"{self._name} error status", extra=log_extra)
            raise self._error(f"{endpoint.name}: HTTP {response.status}")
        if log:
            logger.debug(f"{self._name} request ok", extra=log_extra)

        try:
            return json.loads(response.body)
        except ValueError as exc:
            if log:
                logger.warning(f"{self._name} returned invalid JSON", extra=log_extra)
            raise self._error(f"{endpoint.name}: invalid JSON") from exc

    def _parse(self, endpoint: Enum, dto_cls: type[T], data: Any, *, log: bool = True) -> T:
        try:
            return dto_cls.from_dict(data)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            reason = f"{type(exc).__name__}: {exc}"
            if log:
                logger.warning(
                    f"{self._name} response did not match schema",
                    extra={"endpoint": endpoint.name, "reason": reason},
                )
            raise self._error(f"{endpoint.name}: unexpected response shape ({reason})") from exc
