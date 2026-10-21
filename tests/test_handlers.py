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
from tests.discord.test_dtos import USER_JSON
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


class FakeDiscord:
    """HttpSend serving /users/<id>. Unlisted ids get USER_JSON with that id; a listed
    (status, body) pair overrides it, and a listed exception is raised."""

    def __init__(self, users=None):
        self.users = users or {}
        self.urls = []

    async def __call__(self, method, url, headers):
        self.urls.append(url)
        user_id = url.rsplit("/", 1)[1]
        outcome = self.users.get(user_id, (200, {**USER_JSON, "id": user_id}))
        if isinstance(outcome, BaseException):
            raise outcome
        status, body = outcome
        return HttpResponse(status, json.dumps(body))


def make_slugbot_context(send, discord_send=None):
    settings = Settings.from_env(make_env())
    return Context(
        settings,
        SlugbotClient(settings, send),
        DiscordClient(settings, discord_send or FakeDiscord()),
    )


def _is_wins(body):
    return [match["isWin"] for match in body["lastMatches"]]


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
    def _call(self, send, discord_send=None):
        ctx = make_slugbot_context(send, discord_send)
        return asyncio.run(handlers.get_player_details(ctx, {"player_id": PLAYER_ID}))

    def test_maps_player_and_matches(self):
        # Deliberately out of order: newest first is W, W, L, W.
        matches = [_match(3000, False), _match(4000, True), _match(1000, True), _match(5000, True)]
        send = FakeSlugbot(batches={None: (200, _page(matches, next_cursor=900))})

        response = self._call(send)

        self.assertEqual(response.status, 200)
        body = json.loads(response.render())
        self.assertEqual(
            {k: v for k, v in body.items() if k != "lastMatches"},
            {
                "playerName": "TestPlayer",
                "seasonWinrate": 87.5,
                "currentStreak": 2,
                "currentRank": 1,
                "currentPoints": 30.10524021259957,
            },
        )
        self.assertEqual(_is_wins(body), [True, True, False, True])
        # Both calls run in parallel, so only membership is checked, not order.
        self.assertTrue(any(f"/player/{PLAYER_ID}" in url for url in send.urls))
        # The streak ended on the first page, so no older page is fetched.
        self.assertEqual(len(send.batch_urls()), 1)
        self.assertIn(f"userId={PLAYER_ID}&limit=10", send.batch_urls()[0])

    def test_match_fields(self):
        loss = _match(1792398138435, False)
        loss["declaredResults"] = {"team0": [1, 1], "team1": [2, 2]}
        loss["participants"][0]["pointsReceived"] = -3.5
        body = json.loads(self._call(FakeSlugbot(batches={None: (200, _page([loss]))})).render())
        self.assertEqual(
            body["lastMatches"],
            [
                {
                    "opponentName": "Nelly",
                    "pointsGained": -3.5,
                    "matchDate": "2026-10-19T08:22:18.435000Z",
                    "isWin": False,
                    "playerScore": 1,
                    "opponentScore": 2,
                    "playerRankBefore": 667,
                    "opponentRankBefore": 3972,
                }
            ],
        )

    def test_player_on_second_team(self):
        match = _match(1000, True)
        first, second = match["participants"]
        first["playerId"], second["playerId"] = OPPONENT_ID, PLAYER_ID
        match["winTeam"] = 1
        body = json.loads(self._call(FakeSlugbot(batches={None: (200, _page([match]))})).render())
        played = body["lastMatches"][0]
        self.assertTrue(played["isWin"])
        self.assertEqual((played["playerScore"], played["opponentScore"]), (0, 2))
        self.assertEqual((played["playerRankBefore"], played["opponentRankBefore"]), (3972, 667))
        self.assertEqual(played["pointsGained"], -7.360593541613343)

    def test_opponent_name_falls_back_to_username(self):
        discord = FakeDiscord({OPPONENT_ID: (200, {**USER_JSON, "global_name": None})})
        body = json.loads(self._call(FakeSlugbot(), discord).render())
        self.assertEqual(body["lastMatches"][0]["opponentName"], "nelly")

    def test_failed_name_lookup_is_unknown(self):
        for outcome in ((404, {}), (429, {}), OSError("connection reset")):
            with self.subTest(outcome=outcome):
                discord = FakeDiscord({OPPONENT_ID: outcome})
                with self.assertLogs("dbd1v1timerapi", level="INFO"):
                    response = self._call(FakeSlugbot(), discord)
                self.assertEqual(response.status, 200)
                body = json.loads(response.render())
                self.assertEqual(body["lastMatches"][0]["opponentName"], "Unknown")

    def test_each_opponent_looked_up_once(self):
        other = _match(500, True)
        other["participants"][1]["playerId"] = "555555555555555555"
        matches = [_match(3000, True), _match(2000, False), other]
        discord = FakeDiscord()
        self._call(FakeSlugbot(batches={None: (200, _page(matches))}), discord)
        self.assertEqual(
            sorted(url.rsplit("/", 1)[1] for url in discord.urls),
            sorted(["555555555555555555", OPPONENT_ID]),
        )

    def test_missing_score_is_null(self):
        match = _match(1000, True)
        match["declaredResults"] = {}
        body = json.loads(self._call(FakeSlugbot(batches={None: (200, _page([match]))})).render())
        self.assertIsNone(body["lastMatches"][0]["playerScore"])
        self.assertIsNone(body["lastMatches"][0]["opponentScore"])

    def test_skips_matches_without_player(self):
        other = _match(9000, True)
        for participant in other["participants"]:
            participant["playerId"] = "999999999999999999"
        batches = {None: (200, _page([other, _match(1000, False)]))}
        body = json.loads(self._call(FakeSlugbot(batches=batches)).render())
        self.assertEqual(_is_wins(body), [False])
        self.assertEqual(body["currentStreak"], 0)

    def test_skips_matches_without_opponent(self):
        solo = _match(9000, True)
        solo["participants"] = solo["participants"][:1]
        batches = {None: (200, _page([solo, _match(1000, False)]))}
        body = json.loads(self._call(FakeSlugbot(batches=batches)).render())
        self.assertEqual(_is_wins(body), [False])

    def test_no_matches_played(self):
        player = {**PLAYER_JSON, "matchesPlayed": 0, "matchesWon": 0}
        send = FakeSlugbot(player=(200, player), batches={None: (200, _page([]))})
        discord = FakeDiscord()
        body = json.loads(self._call(send, discord).render())
        self.assertEqual(body["seasonWinrate"], 0.0)
        self.assertEqual(body["currentStreak"], 0)
        self.assertEqual(body["lastMatches"], [])
        self.assertEqual(discord.urls, [])

    def test_fewer_than_ten_matches(self):
        matches = [_match(3000, True), _match(2000, False), _match(1000, True)]
        body = json.loads(self._call(FakeSlugbot(batches={None: (200, _page(matches))})).render())
        self.assertEqual(_is_wins(body), [True, False, True])
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
        self.assertEqual(_is_wins(body), [True] * 10)
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
