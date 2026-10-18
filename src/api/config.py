"""Typed application settings loaded from Worker environment bindings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


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


@dataclass(frozen=True, slots=True)
class Settings:
    dbdl_guild_id: str
    leaderboard_id: str
    slugbot_base_url: str
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
            status_enabled=_parse_bool(env, "STATUS_ENABLED"),
            fast_poll_sec=_parse_int(env, "FAST_POLL_SEC"),
            slow_poll_sec=_parse_int(env, "SLOW_POLL_SEC"),
            fast_poll_cap_sec=_parse_int(env, "FAST_POLL_CAP_SEC"),
            latest_version=_parse_str(env, "LATEST_VERSION"),
            min_supported_version=_parse_str(env, "MIN_SUPPORTED_VERSION"),
            status_message="" if status_message is None else str(status_message),
            log_level=str(getattr(env, "LOG_LEVEL", None) or "INFO").upper(),
            slugbot_api_key=_parse_str(env, "SLUGBOT_API_KEY"),
        )
