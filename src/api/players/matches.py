"""Pure match and streak logic from one player's point of view. No I/O."""

from __future__ import annotations

from typing import NamedTuple

from api.slugbot import SlugbotMatchDto, SlugbotMatchParticipantDto


class PlayerMatch(NamedTuple):
    match: SlugbotMatchDto
    me: SlugbotMatchParticipantDto
    opponent: SlugbotMatchParticipantDto

    @property
    def is_win(self) -> bool:
        return self.me.team_id == self.match.win_team


def player_matches(matches: list[SlugbotMatchDto], player_id: str) -> list[PlayerMatch]:
    """Newest first. Matches without the player, or without an opponent, are skipped."""
    found: list[PlayerMatch] = []
    for match in sorted(matches, key=lambda m: m.timestamp, reverse=True):
        me = next((p for p in match.participants if p.player_id == player_id), None)
        if me is None:
            continue
        opponent = next((p for p in match.participants if p.team_id != me.team_id), None)
        if opponent is not None:
            found.append(PlayerMatch(match, me, opponent))
    return found


def match_results(matches: list[SlugbotMatchDto], player_id: str) -> list[int]:
    """1 for a win, 0 for a loss, newest first."""
    return [int(pm.is_win) for pm in player_matches(matches, player_id)]


def score(match: SlugbotMatchDto, team_id: int) -> int | None:
    """Games the team won. Each participant declares it; the declarations agree on completed matches."""
    declared = match.declared_results.get(f"team{team_id}")
    return declared[0] if declared else None


def win_streak(results: list[int]) -> int:
    streak = 0
    for result in results:
        if result != 1:
            break
        streak += 1
    return streak


def winrate_percent(won: int, played: int) -> int:
    return round(won / played * 100) if played > 0 else 0
