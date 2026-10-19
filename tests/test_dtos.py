import unittest

from api.dtos import PlayerDetailsDto


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


if __name__ == "__main__":
    unittest.main()
