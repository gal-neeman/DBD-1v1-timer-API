"""Slugbot response DTOs. Parsed from Slugbot's camelCase JSON into snake_case fields."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# Slugbot omits "rank" for unranked players.
UNRANKED = -1
# Slugbot's "winTeam" for a match that hasn't finished.
NO_WINNER = -1


def _from_epoch_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _optional_int(value: Any) -> int | None:
    """None or a real int. Strict because cursors are sent back to Slugbot as-is."""
    if value is None or (isinstance(value, int) and not isinstance(value, bool)):
        return value
    raise TypeError(f"expected int or null, got {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class SlugbotPlayerDto:
    """Response of GET /player/<id>."""

    user_id: str
    guild_id: str
    leader_board_id: str
    display_name: str
    members: list[str]
    rank: int
    matches_played: int
    matches_won: int
    points: float
    decayed_points: float
    elo: float
    last_match_played_at: datetime

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlugbotPlayerDto:
        return cls(
            user_id=data["userId"],
            guild_id=data["guildId"],
            leader_board_id=data["leaderBoardId"],
            display_name=data["displayName"],
            members=list(data["members"]),
            rank=int(data.get("rank", UNRANKED)),
            matches_played=int(data["matchesPlayed"]),
            matches_won=int(data["matchesWon"]),
            points=float(data["points"]),
            decayed_points=float(data["decayedPoints"]),
            elo=float(data["elo"]),
            last_match_played_at=_from_epoch_ms(data["lastMatchPlayedAt"]),
        )


@dataclass(frozen=True, slots=True)
class SlugbotMatchParticipantDto:
    team_id: int
    player_id: str
    initial_points: float
    initial_elo: float
    initial_rank: int
    points_received: float
    elo_received: float
    point_decay_regened: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlugbotMatchParticipantDto:
        return cls(
            team_id=int(data["teamId"]),
            player_id=data["playerId"],
            initial_points=float(data["initialPoints"]),
            initial_elo=float(data["initialElo"]),
            initial_rank=int(data["initialRank"]),
            points_received=float(data["pointsReceived"]),
            elo_received=float(data["eloReceived"]),
            point_decay_regened=float(data["pointDecayRegened"]),
        )


@dataclass(frozen=True, slots=True)
class SlugbotMatchDto:
    match_id: str
    guild_id: str
    leader_board_id: str
    timestamp: datetime
    rank_range_limit: int
    platform_limit: list[str]
    region_limit: list[str]
    declared_results: dict[str, list[int]]
    win_team: int
    participants: list[SlugbotMatchParticipantDto]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlugbotMatchDto:
        return cls(
            match_id=data["matchId"],
            guild_id=data["guildId"],
            leader_board_id=data["leaderBoardId"],
            timestamp=_from_epoch_ms(data["timestamp"]),
            rank_range_limit=int(data["rankRangeLimit"]),
            platform_limit=list(data["platformLimit"]),
            region_limit=list(data["regionLimit"]),
            declared_results={team: list(scores) for team, scores in data["declaredResults"].items()},
            win_team=int(data["winTeam"]),
            participants=[SlugbotMatchParticipantDto.from_dict(p) for p in data["participants"]],
        )


@dataclass(frozen=True, slots=True)
class SlugbotMatchSeatDto:
    team_id: int
    player_id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlugbotMatchSeatDto:
        return cls(team_id=int(data["teamId"]), player_id=data["playerId"])


@dataclass(frozen=True, slots=True)
class SlugbotOpenMatchDto:
    """An unfinished match: only who is in it, since its ranks, points and scores are null.
    With a single participant, that player is still waiting for an opponent."""

    match_id: str
    # When it was created. A finished match's timestamp is when it finished instead.
    timestamp: datetime
    participants: list[SlugbotMatchSeatDto]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlugbotOpenMatchDto:
        return cls(
            match_id=data["matchId"],
            timestamp=_from_epoch_ms(data["timestamp"]),
            participants=[SlugbotMatchSeatDto.from_dict(p) for p in data["participants"]],
        )


@dataclass(frozen=True, slots=True)
class SlugbotPagingDto:
    next_cursor: int | None
    has_next_page: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlugbotPagingDto:
        return cls(
            next_cursor=_optional_int(data.get("nextCursor")),
            has_next_page=bool(data["hasNextPage"]),
        )


@dataclass(frozen=True, slots=True)
class SlugbotMatchBatchDto:
    """Response of /match/batch. Finished matches go to data, unfinished ones (only on a
    complete=false page) to open_matches."""

    success: bool
    data: list[SlugbotMatchDto]
    open_matches: list[SlugbotOpenMatchDto]
    paging: SlugbotPagingDto

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlugbotMatchBatchDto:
        matches = data["data"]
        return cls(
            success=bool(data["success"]),
            data=[SlugbotMatchDto.from_dict(m) for m in matches if m["winTeam"] != NO_WINNER],
            open_matches=[
                SlugbotOpenMatchDto.from_dict(m) for m in matches if m["winTeam"] == NO_WINNER
            ],
            paging=SlugbotPagingDto.from_dict(data["paging"]),
        )
