import unittest
from datetime import datetime, timezone

from api.dtos import CurrentMatchDto, MatchDto, PlayerDetailsDto


class DtoSerializationTest(unittest.TestCase):
    def test_player_details_camel_case(self):
        match = MatchDto(
            opponent_name="Nelly",
            points_gained=-2.25,
            match_date=datetime(2026, 1, 9, 19, 1, 31, tzinfo=timezone.utc),
            is_win=False,
            player_score=1,
            opponent_score=2,
            player_rank_before=7,
            opponent_rank_before=3,
        )
        dto = PlayerDetailsDto(
            player_name="TestPlayer",
            season_winrate=50,
            total_games=10,
            total_games_won=5,
            total_games_lost=5,
            current_streak=3,
            current_rank=7,
            current_points=1234.5,
            last_matches=[match],
            current_match=CurrentMatchDto(is_in_match=True, opponent_name="Nelly", opponent_rank=-1),
        )
        self.assertEqual(
            dto.to_dict(),
            {
                "playerName": "TestPlayer",
                "seasonWinrate": 50,
                "totalGames": 10,
                "totalGamesWon": 5,
                "totalGamesLost": 5,
                "currentStreak": 3,
                "currentRank": 7,
                "currentPoints": 1234.5,
                "lastMatches": [
                    {
                        "opponentName": "Nelly",
                        "pointsGained": -2.25,
                        "matchDate": "2026-01-09T19:01:31Z",
                        "isWin": False,
                        "playerScore": 1,
                        "opponentScore": 2,
                        "playerRankBefore": 7,
                        "opponentRankBefore": 3,
                    }
                ],
                "currentMatch": {"isInMatch": True, "opponentName": "Nelly", "opponentRank": -1},
            },
        )


if __name__ == "__main__":
    unittest.main()
