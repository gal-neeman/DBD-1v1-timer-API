import unittest

from api.slugbot.endpoints import SlugbotEndpoint


class SlugbotEndpointTest(unittest.TestCase):
    def test_player_path(self):
        path = SlugbotEndpoint.PLAYER.value.build_path(
            guild_id="459532023690821643",
            leaderboard_id="1v1 - ranked dbd",
            user_id="80351110224678912",
        )
        self.assertEqual(path, "/459532023690821643/1v1%20-%20ranked%20dbd/player/80351110224678912")

    def test_missing_param_raises(self):
        with self.assertRaises(KeyError):
            SlugbotEndpoint.PLAYER.value.build_path(guild_id="1", leaderboard_id="lb")

    def test_unknown_query_param_raises(self):
        with self.assertRaisesRegex(ValueError, "cursor"):
            SlugbotEndpoint.MATCH_BATCH.value.build_query({"cursor": "1"})


if __name__ == "__main__":
    unittest.main()
