import asyncio
import dataclasses
import json
import unittest

from api.config import Settings
from api.slugbot import (
    SlugbotClient,
    SlugbotError,
    SlugbotMatchBatchDto,
    SlugbotNotFound,
    SlugbotPlayerDto,
    SlugbotUnavailable,
)
from api.transport import HttpResponse
from tests.slugbot.test_dtos import MATCH_BATCH_JSON, PLAYER_JSON
from tests.test_config import make_env

BASE = "https://slugbot.example/123456789012345678/lb%201"


class FakeSend:
    """Records requests and returns a canned response (or raises)."""

    def __init__(self, status=200, body="", error=None):
        self.response = HttpResponse(status, body)
        self.error = error
        self.calls = []

    async def __call__(self, method, url, headers):
        self.calls.append((method, url, headers))
        if self.error is not None:
            raise self.error
        return self.response


def make_client(send):
    settings = Settings.from_env(make_env(LEADERBOARD_ID="lb 1"))
    return SlugbotClient(settings, send)


class SlugbotClientTest(unittest.TestCase):
    def test_get_player(self):
        send = FakeSend(body=json.dumps(PLAYER_JSON))
        player = asyncio.run(make_client(send).get_player("381946270518364927"))
        self.assertIsInstance(player, SlugbotPlayerDto)
        self.assertEqual(player.display_name, "TestPlayer")
        method, url, headers = send.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, f"{BASE}/player/381946270518364927")
        self.assertEqual(headers["Authorization"], "Bearer secret")

    def test_get_match_batch(self):
        send = FakeSend(body=json.dumps(MATCH_BATCH_JSON))
        batch = asyncio.run(make_client(send).get_match_batch("273849165028374619", 10))
        self.assertIsInstance(batch, SlugbotMatchBatchDto)
        self.assertEqual(len(batch.data), 1)
        self.assertEqual(
            send.calls[0][1],
            f"{BASE}/match/batch?userId=273849165028374619&limit=10&complete=true",
        )

    def test_get_match_batch_with_cursor(self):
        send = FakeSend(body=json.dumps(MATCH_BATCH_JSON))
        asyncio.run(make_client(send).get_match_batch("273849165028374619", 10, 1792397295163))
        self.assertEqual(
            send.calls[0][1],
            f"{BASE}/match/batch?userId=273849165028374619&limit=10&complete=true&nextCursor=1792397295163",
        )

    def test_match_batch_unsuccessful(self):
        send = FakeSend(body=json.dumps({**MATCH_BATCH_JSON, "success": False}))
        with self.assertLogs("dbd1v1timerapi", level="WARNING"), self.assertRaisesRegex(
            SlugbotError, "success=false"
        ):
            asyncio.run(make_client(send).get_match_batch("1", 10))

    def test_timeout(self):
        async def slow_send(method, url, headers):
            await asyncio.sleep(1)
            return HttpResponse(200, json.dumps(PLAYER_JSON))

        settings = dataclasses.replace(
            Settings.from_env(make_env()), slugbot_timeout_sec=0.01
        )
        client = SlugbotClient(settings, slow_send)
        with self.assertLogs("dbd1v1timerapi", level="WARNING") as logs, self.assertRaisesRegex(
            SlugbotUnavailable, "TimeoutError"
        ):
            asyncio.run(client.get_player("1"))
        self.assertIn("TimeoutError", logs.records[0].reason)

    def test_not_found(self):
        with self.assertRaises(SlugbotNotFound):
            asyncio.run(make_client(FakeSend(status=404)).get_player("1"))

    def test_error_status(self):
        with self.assertLogs("dbd1v1timerapi", level="WARNING"), self.assertRaisesRegex(SlugbotError, "HTTP 500") as cm:
            asyncio.run(make_client(FakeSend(status=500)).get_player("1"))
        self.assertNotIsInstance(cm.exception, SlugbotNotFound)

    def test_network_failure(self):
        send = FakeSend(error=OSError("connection reset"))
        with self.assertLogs("dbd1v1timerapi", level="WARNING"), self.assertRaises(SlugbotUnavailable):
            asyncio.run(make_client(send).get_player("1"))

    def test_invalid_json(self):
        with self.assertLogs("dbd1v1timerapi", level="WARNING"), self.assertRaisesRegex(SlugbotError, "invalid JSON"):
            asyncio.run(make_client(FakeSend(body="<html>")).get_player("1"))

    def test_schema_mismatch(self):
        body = json.dumps({k: v for k, v in PLAYER_JSON.items() if k != "elo"})
        with self.assertLogs("dbd1v1timerapi", level="WARNING"), self.assertRaisesRegex(
            SlugbotError, "unexpected response shape"
        ):
            asyncio.run(make_client(FakeSend(body=body)).get_player("1"))

    def test_api_key_not_logged(self):
        with self.assertLogs("dbd1v1timerapi", level="DEBUG") as logs:
            asyncio.run(make_client(FakeSend(body=json.dumps(PLAYER_JSON))).get_player("1"))
            with self.assertRaises(SlugbotError):
                asyncio.run(make_client(FakeSend(status=500)).get_player("1"))
        for record in logs.records:
            self.assertNotIn("secret", json.dumps(vars(record), default=str))


if __name__ == "__main__":
    unittest.main()
