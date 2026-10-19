import asyncio
import json
import unittest

from api import handlers
from api.config import Settings
from api.context import Context
from api.responses import ApiResponse
from api.routing import resolve
from api.slugbot import SlugbotClient
from tests.test_config import make_env


async def _no_network(method, url, headers):
    raise AssertionError(f"unexpected Slugbot call: {method} {url}")


def make_context():
    settings = Settings.from_env(make_env())
    return Context(settings, SlugbotClient(settings, _no_network))


class RoutingTest(unittest.TestCase):
    def test_status_route(self):
        handler, params = resolve("GET", "/api/v1/status/")
        self.assertIs(handler, handlers.get_status)
        self.assertEqual(params, {})

    def test_player_route_captures_id(self):
        handler, params = resolve("GET", "/api/v1/players/abc-123")
        self.assertIs(handler, handlers.get_player_details)
        self.assertEqual(params, {"player_id": "abc-123"})

    def test_not_found(self):
        response = resolve("GET", "/nope")
        self.assertIsInstance(response, ApiResponse)
        self.assertEqual(response.status, 404)

    def test_method_not_allowed(self):
        response = resolve("POST", "/api/v1/status")
        self.assertEqual(response.status, 405)
        self.assertEqual(response.headers["Allow"], "GET")


class StatusHandlerTest(unittest.TestCase):
    def test_status_body_excludes_secret(self):
        response = asyncio.run(handlers.get_status(make_context(), {}))
        body = json.loads(response.render())
        self.assertEqual(response.status, 200)
        self.assertEqual(body["latestVersion"], "1.2.0")
        self.assertEqual(len(body), 7)
        self.assertNotIn("dbdlGuildId", body)
        self.assertNotIn("secret", response.render())


class PlayerDetailsHandlerTest(unittest.TestCase):
    def _call(self, player_id):
        return asyncio.run(handlers.get_player_details(make_context(), {"player_id": player_id}))

    def test_valid_discord_ids(self):
        for player_id in ("80351110224678912", "1234567890123456789", "18446744073709551615"):
            with self.subTest(player_id=player_id):
                self.assertEqual(self._call(player_id).status, 200)

    def test_invalid_player_ids(self):
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
                response = self._call(player_id)
                self.assertEqual(response.status, 400)
                self.assertEqual(response.body["error"]["code"], "invalid_player_id")


if __name__ == "__main__":
    unittest.main()
