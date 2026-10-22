"""Slugbot models to response DTOs."""

from __future__ import annotations

from api.dtos import MatchDto, PlayerDetailsDto
from api.players.matches import PlayerMatch, score, winrate_percent
from api.slugbot import SlugbotPlayerDto

UNKNOWN_NAME = "Unknown"


def to_match(pm: PlayerMatch, names: dict[str, str]) -> MatchDto:
    return MatchDto(
        opponent_name=names.get(pm.opponent.player_id, UNKNOWN_NAME),
        points_gained=pm.me.points_received,
        match_date=pm.match.timestamp,
        is_win=pm.is_win,
        player_score=score(pm.match, pm.me.team_id),
        opponent_score=score(pm.match, pm.opponent.team_id),
        player_rank_before=pm.me.initial_rank,
        opponent_rank_before=pm.opponent.initial_rank,
    )


def to_player_details(
    player: SlugbotPlayerDto, matches: list[PlayerMatch], names: dict[str, str], streak: int
) -> PlayerDetailsDto:
    return PlayerDetailsDto(
        player_name=player.display_name,
        season_winrate=winrate_percent(player.matches_won, player.matches_played),
        current_streak=streak,
        current_rank=player.rank,
        current_points=player.points,
        last_matches=[to_match(pm, names) for pm in matches],
    )
