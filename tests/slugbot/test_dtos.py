import unittest
from datetime import datetime, timezone

from api.slugbot.dtos import SlugbotMatchBatchDto, SlugbotPlayerDto

PLAYER_JSON = {
    "userId": "381946270518364927",
    "guildId": "902817364519283746",
    "leaderBoardId": "test lb",
    "displayName": "TestPlayer",
    "members": ["381946270518364927"],
    "rank": 1,
    "matchesPlayed": 8,
    "matchesWon": 7,
    "points": 30.10524021259957,
    "decayedPoints": 0,
    "elo": 1029.0332436228407,
    "lastMatchPlayedAt": 1767985291309,
}

MATCH_BATCH_JSON = {
    "success": True,
    "data": [
        {
            "matchId": "3f9a1c7e5b2d8a4f6c0e1b93",
            "guildId": "746281937465019283",
            "leaderBoardId": "1v1 - ranked dbd",
            "timestamp": 1792398138435,
            "rankRangeLimit": -1,
            "platformLimit": [],
            "regionLimit": ["518293746102938475", "629384751029384756"],
            "declaredResults": {"team0": [2, 2], "team1": [0, 0]},
            "winTeam": 0,
            "participants": [
                {
                    "teamId": 0,
                    "playerId": "273849165028374619",
                    "initialPoints": 416.04817535797224,
                    "initialElo": 1019.4488054302791,
                    "initialRank": 667,
                    "pointsReceived": 7.360593541613343,
                    "eloReceived": 10.967722259634805,
                    "pointDecayRegened": 0,
                },
                {
                    "teamId": 1,
                    "playerId": "1048372615940283746",
                    "initialPoints": 360.36809552529496,
                    "initialElo": 906.3408597945108,
                    "initialRank": 3972,
                    "pointsReceived": -7.360593541613343,
                    "eloReceived": -10.967722259634805,
                    "pointDecayRegened": 0,
                },
            ],
        }
    ],
    "paging": {"nextCursor": 1792397295163, "hasNextPage": True},
}

_OPEN_SEAT = {
    "initialPoints": None,
    "initialElo": None,
    "initialRank": None,
    "pointsReceived": None,
    "eloReceived": None,
    "pointDecayRegened": None,
}

# An unfinished match as Slugbot returns it with complete=false: no winner, everything null.
OPEN_MATCH_JSON = {
    "matchId": "6adba7903fb28de224afd879",
    "guildId": "746281937465019283",
    "leaderBoardId": "1v1 - ranked dbd",
    "timestamp": 1792780176203,
    "rankRangeLimit": -1,
    "platformLimit": [],
    "regionLimit": [],
    "isResolvePending": False,
    "declaredResults": {"team0": [None, None], "team1": [None, None]},
    "winTeam": -1,
    "participants": [
        {"teamId": 0, "playerId": "273849165028374619", **_OPEN_SEAT},
        {"teamId": 1, "playerId": "1048372615940283746", **_OPEN_SEAT},
    ],
}


class SlugbotDtoParsingTest(unittest.TestCase):
    def test_player_from_dict(self):
        player = SlugbotPlayerDto.from_dict(PLAYER_JSON)
        self.assertEqual(player.user_id, "381946270518364927")
        self.assertEqual(player.leader_board_id, "test lb")
        self.assertEqual(player.display_name, "TestPlayer")
        self.assertEqual(player.members, ["381946270518364927"])
        self.assertEqual(player.rank, 1)
        self.assertEqual(player.matches_played, 8)
        self.assertEqual(player.matches_won, 7)
        self.assertAlmostEqual(player.points, 30.10524021259957)
        self.assertIsInstance(player.decayed_points, float)
        self.assertEqual(
            player.last_match_played_at,
            datetime(2026, 1, 9, 19, 1, 31, 309000, tzinfo=timezone.utc),
        )

    def test_player_from_dict_unranked(self):
        data = {k: v for k, v in PLAYER_JSON.items() if k != "rank"}
        self.assertEqual(SlugbotPlayerDto.from_dict(data).rank, -1)

    def test_match_batch_from_dict(self):
        batch = SlugbotMatchBatchDto.from_dict(MATCH_BATCH_JSON)
        self.assertTrue(batch.success)
        self.assertEqual(len(batch.data), 1)

        match = batch.data[0]
        self.assertEqual(match.match_id, "3f9a1c7e5b2d8a4f6c0e1b93")
        self.assertEqual(match.timestamp, datetime.fromtimestamp(1792398138.435, tz=timezone.utc))
        self.assertEqual(match.rank_range_limit, -1)
        self.assertEqual(match.platform_limit, [])
        self.assertEqual(match.region_limit, ["518293746102938475", "629384751029384756"])
        self.assertEqual(match.declared_results, {"team0": [2, 2], "team1": [0, 0]})
        self.assertEqual(match.win_team, 0)

        winner, loser = match.participants
        self.assertEqual(winner.team_id, 0)
        self.assertEqual(winner.player_id, "273849165028374619")
        self.assertEqual(winner.initial_rank, 667)
        self.assertAlmostEqual(winner.points_received, 7.360593541613343)
        self.assertIsInstance(winner.point_decay_regened, float)
        self.assertAlmostEqual(loser.elo_received, -10.967722259634805)

        self.assertEqual(batch.paging.next_cursor, 1792397295163)
        self.assertTrue(batch.paging.has_next_page)

    def test_paging_without_cursor(self):
        batch = SlugbotMatchBatchDto.from_dict(
            {"success": True, "data": [], "paging": {"hasNextPage": False}}
        )
        self.assertIsNone(batch.paging.next_cursor)
        self.assertFalse(batch.paging.has_next_page)

    def test_paging_rejects_non_int_cursor(self):
        for cursor in ("1792397295163", True, 1.5):
            with self.subTest(cursor=cursor), self.assertRaises(TypeError):
                SlugbotMatchBatchDto.from_dict(
                    {"success": True, "data": [], "paging": {"nextCursor": cursor, "hasNextPage": True}}
                )

    def test_complete_batch_has_no_open_matches(self):
        self.assertEqual(SlugbotMatchBatchDto.from_dict(MATCH_BATCH_JSON).open_matches, [])

    def test_mixed_batch_splits_finished_and_open_matches(self):
        searching = {**OPEN_MATCH_JSON, "participants": OPEN_MATCH_JSON["participants"][:1]}
        batch = SlugbotMatchBatchDto.from_dict(
            {**MATCH_BATCH_JSON, "data": [OPEN_MATCH_JSON, MATCH_BATCH_JSON["data"][0], searching]}
        )
        (finished,) = batch.data
        self.assertEqual(finished.win_team, 0)
        self.assertEqual(finished.participants[0].initial_rank, 667)

        open_match, solo = batch.open_matches
        self.assertEqual(open_match.match_id, "6adba7903fb28de224afd879")
        self.assertEqual(
            open_match.timestamp, datetime.fromtimestamp(1792780176.203, tz=timezone.utc)
        )
        self.assertEqual(
            [(p.team_id, p.player_id) for p in open_match.participants],
            [(0, "273849165028374619"), (1, "1048372615940283746")],
        )
        self.assertEqual(len(solo.participants), 1)
        self.assertEqual(batch.paging.next_cursor, 1792397295163)


if __name__ == "__main__":
    unittest.main()
