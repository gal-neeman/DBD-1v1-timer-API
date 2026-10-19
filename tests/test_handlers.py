import asyncio
import copy
import json
import unittest

from api import handlers
from api.config import Settings
from api.context import Context
from api.slugbot import SlugbotClient
from api.transport import HttpResponse
from tests.slugbot.test_dtos import MATCH_BATCH_JSON, PLAYER_JSON
from tests.test_config import make_env
from tests.test_routing import make_context

PLAYER_ID = "273849165028374619"
OPPONENT_ID = "1048372615940283746"


def _match(timestamp, player_won):
    """A 1v1 match between PLAYER_ID (team 0) and OPPONENT_ID (team 1)."""
    match = copy.deepcopy(MATCH_BATCH_JSON["data"][0])
    match["timestamp"] = timestamp
    match["winTeam"] = 0 if player_won else 1
    return match


class FakeSlugbot:
    """HttpSend that answers player and match batch requests with separate canned responses."""

    def __init__(self, player=(200, PLAYER_JSON), batch=(200, MATCH_BATCH_JSON), error=None):
        self.player = player
        self.batch = batch
        self.error = error
        self.urls = []

    async def __call__(self, method, url, headers):
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        status, body = self.batch if "/match/batch" in url else self.player
        return HttpResponse(status, json.dumps(body))


def make_slugbot_context(send):
    settings = Settings.from_env(make_env())
    return Context(settings, SlugbotClient(settings, send))


class PlayerDetailsValidationTest(unittest.TestCase):
    def test_valid_discord_ids(self):
        for player_id in ("80351110224678912", "1234567890123456789", "18446744073709551615"):
            with self.subTest(player_id=player_id):
                ctx = make_slugbot_context(FakeSlugbot())
                response = asyncio.run(handlers.get_player_details(ctx, {"player_id": player_id}))
                self.assertEqual(response.status, 200)

    def test_invalid_player_ids(self):
        # make_context's client fails on any network call, so this also proves none is made.
        for player_id in (
            "abc-123",
            "1234567890123456",  # 16 digits, too short
            "123456789012345678901",  # 21 digits, too long
            "18446744073709551616",  # exceeds uint64
            "01234567890123456",  # leading zero
            "١٢٣٤٥٦٧٨٩٠١٢٣٤٥٦٧",  # non-ASCII digits
            "80351110224678912 ",
        ):
            with self.subTest(player_id=player_id):
                response = asyncio.run(
                    handlers.get_player_details(make_context(), {"player_id": player_id})
                )
                self.assertEqual(response.status, 400)
                self.assertEqual(response.body["error"]["code"], "invalid_player_id")


class PlayerDetailsMappingTest(unittest.TestCase):
    def _call(self, send):
        ctx = make_slugbot_context(send)
        return asyncio.run(handlers.get_player_details(ctx, {"player_id": PLAYER_ID}))

    def test_maps_player_and_matches(self):
        # Deliberately out of order: newest first is W, W, L, W.
        matches = [_match(3000, False), _match(4000, True), _match(1000, True), _match(5000, True)]
        batch = {**MATCH_BATCH_JSON, "data": matches}
        send = FakeSlugbot(batch=(200, batch))

        response = self._call(send)

        self.assertEqual(response.status, 200)
        self.assertEqual(
            json.loads(response.render()),
            {
                "playerName": "TestPlayer",
                "seasonWinrate": 87.5,
                "currentStreak": 2,
                "currentRank": 1,
                "currentPoints": 30.10524021259957,
                "lastMatchesResults": [1, 1, 0, 1],
            },
        )
        self.assertIn(f"/player/{PLAYER_ID}", send.urls[0])
        self.assertIn(f"userId={PLAYER_ID}&limit=10", send.urls[1])

    def test_skips_matches_without_player(self):
        other = _match(9000, True)
        for participant in other["participants"]:
            participant["playerId"] = "999999999999999999"
        batch = {**MATCH_BATCH_JSON, "data": [other, _match(1000, False)]}
        body = json.loads(self._call(FakeSlugbot(batch=(200, batch))).render())
        self.assertEqual(body["lastMatchesResults"], [0])
        self.assertEqual(body["currentStreak"], 0)

    def test_no_matches_played(self):
        player = {**PLAYER_JSON, "matchesPlayed": 0, "matchesWon": 0}
        batch = {**MATCH_BATCH_JSON, "data": []}
        body = json.loads(self._call(FakeSlugbot(player=(200, player), batch=(200, batch))).render())
        self.assertEqual(body["seasonWinrate"], 0.0)
        self.assertEqual(body["currentStreak"], 0)
        self.assertEqual(body["lastMatchesResults"], [])


class PlayerDetailsErrorTest(unittest.TestCase):
    def _call(self, send):
        ctx = make_slugbot_context(send)
        return asyncio.run(handlers.get_player_details(ctx, {"player_id": PLAYER_ID}))

    def test_player_not_found_skips_batch(self):
        send = FakeSlugbot(player=(404, {}))
        response = self._call(send)
        self.assertEqual(response.status, 404)
        self.assertEqual(response.body["error"]["code"], "player_not_found")
        self.assertEqual(len(send.urls), 1)

    def test_upstream_error_status(self):
        with self.assertLogs("dbd1v1timerapi", level="WARNING"):
            response = self._call(FakeSlugbot(batch=(500, {})))
        self.assertEqual(response.status, 502)
        self.assertEqual(response.body["error"]["code"], "upstream_error")

    def test_upstream_unreachable(self):
        with self.assertLogs("dbd1v1timerapi", level="WARNING"):
            response = self._call(FakeSlugbot(error=OSError("connection reset")))
        self.assertEqual(response.status, 503)
        self.assertEqual(response.body["error"]["code"], "upstream_unavailable")

    def test_batch_unsuccessful(self):
        batch = {**MATCH_BATCH_JSON, "success": False}
        response = self._call(FakeSlugbot(batch=(200, batch)))
        self.assertEqual(response.status, 502)
        self.assertEqual(response.body["error"]["code"], "upstream_error")


if __name__ == "__main__":
    unittest.main()
