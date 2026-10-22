import asyncio
import dataclasses
import json
import unittest

from api.config import Settings
from api.discord import (
    DiscordClient,
    DiscordError,
    DiscordNotFound,
    DiscordUnavailable,
    DiscordUserDto,
)
from api.discord.client import USER_AGENT
from api.transport import HttpResponse
from tests.discord.test_dtos import USER_JSON
from tests.slugbot.test_client import FakeSend
from tests.test_config import make_env


def make_client(send):
    return DiscordClient(Settings.from_env(make_env()), send)


class DiscordClientTest(unittest.TestCase):
    def test_get_user(self):
        send = FakeSend(body=json.dumps(USER_JSON))
        user = asyncio.run(make_client(send).get_user("80351110224678912"))
        self.assertIsInstance(user, DiscordUserDto)
        self.assertEqual(user.display_name, "Nelly")
        method, url, headers = send.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://discord.example/api/v10/users/80351110224678912")
        self.assertEqual(headers["Authorization"], "Bot discord-token")
        self.assertEqual(headers["User-Agent"], USER_AGENT)

    def test_user_id_is_quoted(self):
        send = FakeSend(body=json.dumps(USER_JSON))
        asyncio.run(make_client(send).get_user("../@me"))
        self.assertEqual(send.calls[0][1], "https://discord.example/api/v10/users/..%2F%40me")

    def test_timeout(self):
        async def slow_send(method, url, headers):
            await asyncio.sleep(1)
            return HttpResponse(200, json.dumps(USER_JSON))

        settings = dataclasses.replace(Settings.from_env(make_env()), discord_timeout_sec=0.01)
        client = DiscordClient(settings, slow_send)
        with self.assertLogs("dbd1v1timerapi", level="WARNING") as logs, self.assertRaisesRegex(
            DiscordUnavailable, "TimeoutError"
        ):
            asyncio.run(client.get_user("1"))
        self.assertEqual(logs.records[0].getMessage(), "Discord request failed")

    def test_not_found(self):
        with self.assertRaises(DiscordNotFound):
            asyncio.run(make_client(FakeSend(status=404)).get_user("1"))

    def test_error_status(self):
        for status in (401, 429, 500):
            with self.subTest(status=status):
                with self.assertLogs("dbd1v1timerapi", level="WARNING"), self.assertRaisesRegex(
                    DiscordError, f"HTTP {status}"
                ) as cm:
                    asyncio.run(make_client(FakeSend(status=status)).get_user("1"))
                self.assertNotIsInstance(cm.exception, DiscordNotFound)

    def test_network_failure(self):
        send = FakeSend(error=OSError("connection reset"))
        with self.assertLogs("dbd1v1timerapi", level="WARNING"), self.assertRaises(DiscordUnavailable):
            asyncio.run(make_client(send).get_user("1"))

    def test_schema_mismatch(self):
        body = json.dumps({k: v for k, v in USER_JSON.items() if k != "username"})
        with self.assertLogs("dbd1v1timerapi", level="WARNING"), self.assertRaisesRegex(
            DiscordError, "unexpected response shape"
        ):
            asyncio.run(make_client(FakeSend(body=body)).get_user("1"))

    def test_token_not_logged(self):
        with self.assertLogs("dbd1v1timerapi", level="DEBUG") as logs:
            asyncio.run(make_client(FakeSend(body=json.dumps(USER_JSON))).get_user("1"))
            with self.assertRaises(DiscordError):
                asyncio.run(make_client(FakeSend(status=500)).get_user("1"))
        for record in logs.records:
            self.assertNotIn("discord-token", json.dumps(vars(record), default=str))


if __name__ == "__main__":
    unittest.main()
