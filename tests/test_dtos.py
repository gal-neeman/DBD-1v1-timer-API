import unittest
from datetime import datetime, timedelta, timezone

from api.dtos import MatchDataDto, PlayerDetailsDto


class DtoSerializationTest(unittest.TestCase):
    def test_player_details_camel_case(self):
        dto = PlayerDetailsDto(
            player_name="TestPlayer",
            season_winrate=0.5,
            current_streak=3,
            current_rank=7,
            current_points=1234.5,
            last_matches_results=[0, 1, 1],
        )
        self.assertEqual(
            dto.to_dict(),
            {
                "playerName": "TestPlayer",
                "seasonWinrate": 0.5,
                "currentStreak": 3,
                "currentRank": 7,
                "currentPoints": 1234.5,
                "lastMatchesResults": [0, 1, 1],
            },
        )

    def test_match_data_camel_case_and_iso_dates(self):
        match = MatchDataDto(
            played_at=datetime(2026, 1, 2, 5, 4, 5, tzinfo=timezone(timedelta(hours=2))),
            players=["a", "b"],
            is_win=True,
            points_received=12.5,
        )
        self.assertEqual(
            match.to_dict(),
            {
                "playedAt": "2026-01-02T03:04:05Z",
                "players": ["a", "b"],
                "isWin": True,
                "pointsReceived": 12.5,
            },
        )


if __name__ == "__main__":
    unittest.main()
