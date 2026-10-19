"""Typed application settings loaded from Worker environment bindings."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("dbd1v1timerapi")

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}
# Names logging.setLevel accepts, including its WARN/FATAL aliases.
_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "WARN", "ERROR", "CRITICAL", "FATAL")

# Hard bounds for client poll settings, so a typo in the env can't make every
# client hammer the API (or stop polling entirely). Out-of-range values are clamped.
FAST_POLL_SEC_RANGE = (10, 300)
SLOW_POLL_SEC_RANGE = (30, 3600)
FAST_POLL_CAP_SEC_RANGE = (0, 600)
# Slugbot calls past this are abandoned with a 503; a request can make several in a row.
SLUGBOT_TIMEOUT_SEC_RANGE = (1, 30)


class ConfigError(Exception):
    """Raised when a required environment variable is missing or invalid."""


def _require(env: Any, name: str) -> Any:
    value = getattr(env, name, None)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ConfigError(f"Missing environment variable: {name}")
    return value


def _parse_str(env: Any, name: str) -> str:
    return str(_require(env, name)).strip()


def _parse_int(env: Any, name: str) -> int:
    value = _require(env, name)
    if isinstance(value, bool):
        raise ConfigError(f"{name} must be an integer, got bool")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be an integer, got {value!r}") from exc


def _parse_bounded_int(env: Any, name: str, bounds: tuple[int, int]) -> int:
    value = _parse_int(env, name)
    low, high = bounds
    clamped = min(max(value, low), high)
    if clamped != value:
        logger.warning(
            "Config value out of range, clamped",
            extra={"variable": name, "value": value, "clamped": clamped, "min": low, "max": high},
        )
    return clamped


def _parse_bool(env: Any, name: str) -> bool:
    value = _require(env, name)
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    raise ConfigError(f"{name} must be a boolean, got {value!r}")


def _parse_log_level(env: Any, name: str) -> str:
    # Optional; an unknown name would make logging.setLevel raise on every request,
    # so it falls back to INFO instead of failing.
    level = str(getattr(env, name, None) or "INFO").strip().upper()
    if level not in _LOG_LEVELS:
        logger.warning(
            "Unknown log level, falling back to INFO",
            extra={"variable": name, "value": level, "allowed": list(_LOG_LEVELS)},
        )
        return "INFO"
    return level


@dataclass(frozen=True, slots=True)
class Settings:
    dbdl_guild_id: str
    leaderboard_id: str
    slugbot_base_url: str
    slugbot_timeout_sec: float
    status_enabled: bool
    fast_poll_sec: int
    slow_poll_sec: int
    fast_poll_cap_sec: int
    latest_version: str
    min_supported_version: str
    status_message: str
    log_level: str
    slugbot_api_key: str = field(repr=False)

    @classmethod
    def from_env(cls, env: Any) -> Settings:
        # STATUS_MESSAGE may legitimately be empty, so it is read without _require.
        status_message = getattr(env, "STATUS_MESSAGE", None)
        return cls(
            dbdl_guild_id=_parse_str(env, "DBDL_GUILD_ID"),
            leaderboard_id=_parse_str(env, "LEADERBOARD_ID"),
            slugbot_base_url=_parse_str(env, "SLUGBOT_BASE_URL").rstrip("/"),
            slugbot_timeout_sec=_parse_bounded_int(
                env, "SLUGBOT_TIMEOUT_SEC", SLUGBOT_TIMEOUT_SEC_RANGE
            ),
            status_enabled=_parse_bool(env, "STATUS_ENABLED"),
            fast_poll_sec=_parse_bounded_int(env, "FAST_POLL_SEC", FAST_POLL_SEC_RANGE),
            slow_poll_sec=_parse_bounded_int(env, "SLOW_POLL_SEC", SLOW_POLL_SEC_RANGE),
            fast_poll_cap_sec=_parse_bounded_int(
                env, "FAST_POLL_CAP_SEC", FAST_POLL_CAP_SEC_RANGE
            ),
            latest_version=_parse_str(env, "LATEST_VERSION"),
            min_supported_version=_parse_str(env, "MIN_SUPPORTED_VERSION"),
            status_message="" if status_message is None else str(status_message),
            log_level=_parse_log_level(env, "LOG_LEVEL"),
            slugbot_api_key=_parse_str(env, "SLUGBOT_API_KEY"),
        )


_cached_settings: Settings | None = None


def get_settings(env: Any) -> Settings:
    """Parse settings once per isolate and reuse them for later requests.

    The env can't change within an isolate (changing a var or secret deploys a new
    version, which starts new isolates), so re-parsing only repeats config warnings.
    A failed parse raises before anything is cached, so the next request retries.
    """
    global _cached_settings
    if _cached_settings is None:
        _cached_settings = Settings.from_env(env)
    return _cached_settings
