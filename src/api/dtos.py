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
class MatchDto(Dto):
    """One match from the player's point of view."""

    opponent_name: str
    points_gained: float  # signed: negative on a loss
    match_date: datetime
    is_win: bool
    # Games won in the set (best of 3); None if Slugbot didn't report a score.
    player_score: int | None
    opponent_score: int | None
    player_rank_before: int
    opponent_rank_before: int


@dataclass(frozen=True, slots=True)
class PlayerDetailsDto(Dto):
    player_name: str
    season_winrate: float
    current_streak: int
    current_rank: int
    current_points: float
    last_matches: list[MatchDto]
