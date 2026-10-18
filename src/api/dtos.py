"""Response DTOs. Fields are snake_case in Python and serialized as camelCase JSON."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from typing import Any


def _to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def _serialize(value: Any) -> Any:
    if isinstance(value, Dto):
        return value.to_dict()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


class Dto:
    """Base for dataclass DTOs; provides camelCase JSON-ready serialization."""

    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        assert is_dataclass(self)
        return {_to_camel(f.name): _serialize(getattr(self, f.name)) for f in fields(self)}


@dataclass(frozen=True, slots=True)
class StatusDto(Dto):
    status_enabled: bool
    fast_poll_sec: int
    slow_poll_sec: int
    fast_poll_cap_sec: int
    latest_version: str
    min_supported_version: str
    status_message: str


@dataclass(frozen=True, slots=True)
class MatchDataDto(Dto):
    played_at: datetime
    players: list[str]
    is_win: bool
    points_received: float


@dataclass(frozen=True, slots=True)
class PlayerDetailsDto(Dto):
    season_winrate: float
    current_streak: int
    last10_results: list[int]
    current_rank: int
    current_points: float
    last10_matches_data: list[MatchDataDto]
