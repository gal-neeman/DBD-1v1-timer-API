import asyncio
import copy
import json
import unittest
from urllib.parse import parse_qs, urlsplit

from api import handlers
from api.config import Settings
from api.context import Context
from api.discord import DiscordClient
from api.slugbot import SlugbotClient
from api.transport import HttpResponse
from tests.slugbot.test_dtos import MATCH_BATCH_JSON, PLAYER_JSON
from tests.test_config import make_env
from tests.test_routing import _no_network, make_context

PLAYER_ID = "273849165028374619"
OPPONENT_ID = "1048372615940283746"


def _match(timestamp, player_won):
    """A 1v1 match between PLAYER_ID (team 0) and OPPONENT_ID (team 1)."""
    match = copy.deepcopy(MATCH_BATCH_JSON["data"][0])
    match["timestamp"] = timestamp
    match["winTeam"] = 0 if player_won else 1
    return match


def _page(matches, next_cursor=None):
    """A match batch body; a next_cursor means more pages follow."""
    return {
        "success": True,
        "data": matches,
        "paging": {"nextCursor": next_cursor, "hasNextPage": next_cursor is not None},
    }


def _wins(count, newest):
    return [_match(newest - i, True) for i in range(count)]


class FakeSlugbot:
    """HttpSend serving the player and match batch pages (keyed by nextCursor) separately."""

    def __init__(self, player=(200, PLAYER_JSON), batches=None, error=None):
        self.player = player
        self.batches = batches if batches is not None else {None: (200, _page([_match(1000, True)]))}
        self.error = error
        self.urls = []

    async def __call__(self, method, url, headers):
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        if "/match/batch" in url:
            cursor = parse_qs(urlsplit(url).query).get("nextCursor", [None])[0]
            status, body = self.batches[None if cursor is None else int(cursor)]
        else:
            status, body = self.player
        return HttpResponse(status, json.dumps(body))

    def batch_urls(self):
        return [url for url in self.urls if "/match/batch" in url]


def make_slugbot_context(send):
    settings = Settings.from_env(make_env())
    return Context(settings, SlugbotClient(settings, send), DiscordClient(settings, _no_network))


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
        send = FakeSlugbot(batches={None: (200, _page(matches, next_cursor=900))})

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
        # Both calls run in parallel, so only membership is checked, not order.
        self.assertTrue(any(f"/player/{PLAYER_ID}" in url for url in send.urls))
        # The streak ended on the first page, so no older page is fetched.
        self.assertEqual(len(send.batch_urls()), 1)
        self.assertIn(f"userId={PLAYER_ID}&limit=10", send.batch_urls()[0])

    def test_skips_matches_without_player(self):
        other = _match(9000, True)
        for participant in other["participants"]:
            participant["playerId"] = "999999999999999999"
        batches = {None: (200, _page([other, _match(1000, False)]))}
        body = json.loads(self._call(FakeSlugbot(batches=batches)).render())
        self.assertEqual(body["lastMatchesResults"], [0])
        self.assertEqual(body["currentStreak"], 0)

    def test_no_matches_played(self):
        player = {**PLAYER_JSON, "matchesPlayed": 0, "matchesWon": 0}
        send = FakeSlugbot(player=(200, player), batches={None: (200, _page([]))})
        body = json.loads(self._call(send).render())
        self.assertEqual(body["seasonWinrate"], 0.0)
        self.assertEqual(body["currentStreak"], 0)
        self.assertEqual(body["lastMatchesResults"], [])

    def test_fewer_than_ten_matches(self):
        matches = [_match(3000, True), _match(2000, False), _match(1000, True)]
        body = json.loads(self._call(FakeSlugbot(batches={None: (200, _page(matches))})).render())
        self.assertEqual(body["lastMatchesResults"], [1, 0, 1])
        self.assertEqual(body["currentStreak"], 1)


class PlayerDetailsStreakTest(unittest.TestCase):
    def _call(self, send):
        ctx = make_slugbot_context(send)
        return asyncio.run(handlers.get_player_details(ctx, {"player_id": PLAYER_ID}))

    def test_streak_continues_across_pages(self):
        older = _wins(3, newest=90) + [_match(80, False)]
        send = FakeSlugbot(
            batches={
                None: (200, _page(_wins(10, newest=100), next_cursor=91)),
                91: (200, _page(older, next_cursor=79)),
            }
        )
        body = json.loads(self._call(send).render())
        self.assertEqual(body["currentStreak"], 13)
        self.assertEqual(body["lastMatchesResults"], [1] * 10)
        # Stopped at the loss without fetching the page after it.
        self.assertEqual(len(send.batch_urls()), 2)
        self.assertIn("nextCursor=91", send.batch_urls()[1])

    def test_streak_stops_on_last_page(self):
        send = FakeSlugbot(
            batches={
                None: (200, _page(_wins(10, newest=100), next_cursor=91)),
                91: (200, _page(_wins(2, newest=90))),
            }
        )
        body = json.loads(self._call(send).render())
        self.assertEqual(body["currentStreak"], 12)
        self.assertEqual(len(send.batch_urls()), 2)

    def test_failed_page_returns_streak_so_far(self):
        send = FakeSlugbot(
            batches={
                None: (200, _page(_wins(10, newest=100), next_cursor=91)),
                91: (500, {}),
            }
        )
        with self.assertLogs("dbd1v1timerapi", level="WARNING") as logs:
            response = self._call(send)
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.render())["currentStreak"], 10)
        self.assertIn("Win streak truncated", [r.getMessage() for r in logs.records])

    def test_stops_when_cursor_does_not_advance(self):
        send = FakeSlugbot(
            batches={
                None: (200, _page(_wins(10, newest=100), next_cursor=91)),
                91: (200, _page(_wins(10, newest=90), next_cursor=91)),
            }
        )
        with self.assertLogs("dbd1v1timerapi", level="WARNING"):
            body = json.loads(self._call(send).render())
        self.assertEqual(body["currentStreak"], 20)
        self.assertEqual(len(send.batch_urls()), 2)


class PlayerDetailsErrorTest(unittest.TestCase):
    def _call(self, send):
        ctx = make_slugbot_context(send)
        return asyncio.run(handlers.get_player_details(ctx, {"player_id": PLAYER_ID}))

    def test_player_not_found(self):
        response = self._call(FakeSlugbot(player=(404, {})))
        self.assertEqual(response.status, 404)
        self.assertEqual(response.body["error"]["code"], "player_not_found")

    def test_player_not_found_wins_over_batch_error(self):
        send = FakeSlugbot(player=(404, {}), batches={None: (500, {})})
        with self.assertLogs("dbd1v1timerapi", level="WARNING"):
            response = self._call(send)
        self.assertEqual(response.status, 404)
        self.assertEqual(response.body["error"]["code"], "player_not_found")

    def test_upstream_error_status(self):
        with self.assertLogs("dbd1v1timerapi", level="WARNING"):
            response = self._call(FakeSlugbot(batches={None: (500, {})}))
        self.assertEqual(response.status, 502)
        self.assertEqual(response.body["error"]["code"], "upstream_error")

    def test_upstream_unreachable(self):
        with self.assertLogs("dbd1v1timerapi", level="WARNING"):
            response = self._call(FakeSlugbot(error=OSError("connection reset")))
        self.assertEqual(response.status, 503)
        self.assertEqual(response.body["error"]["code"], "upstream_unavailable")

    def test_batch_unsuccessful(self):
        batch = {**_page([_match(1000, True)]), "success": False}
        with self.assertLogs("dbd1v1timerapi", level="WARNING") as logs:
            response = self._call(FakeSlugbot(batches={None: (200, batch)}))
        self.assertEqual(response.status, 502)
        self.assertEqual(response.body["error"]["code"], "upstream_error")
        self.assertIn("Slugbot batch unsuccessful", [r.getMessage() for r in logs.records])


if __name__ == "__main__":
    unittest.main()
