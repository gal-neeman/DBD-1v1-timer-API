import unittest
from types import SimpleNamespace

from api.config import (
    FAST_POLL_CAP_SEC_RANGE,
    FAST_POLL_SEC_RANGE,
    SLOW_POLL_SEC_RANGE,
    ConfigError,
    Settings,
)

VALID_ENV = {
    "DBDL_GUILD_ID": "123456789012345678",
    "LEADERBOARD_ID": "lb-1",
    "SLUGBOT_BASE_URL": "https://slugbot.example/",
    "STATUS_ENABLED": "true",
    "FAST_POLL_SEC": "10",
    "SLOW_POLL_SEC": "60",
    "FAST_POLL_CAP_SEC": "600",
    "LATEST_VERSION": "1.2.0",
    "MIN_SUPPORTED_VERSION": "1.0.0",
    "STATUS_MESSAGE": "",
    "SLUGBOT_API_KEY": "secret",
}


def make_env(**overrides):
    return SimpleNamespace(**{**VALID_ENV, **overrides})


class SettingsTest(unittest.TestCase):
    def test_parses_types(self):
        settings = Settings.from_env(make_env())
        self.assertIs(settings.status_enabled, True)
        self.assertEqual(settings.fast_poll_sec, 10)
        self.assertEqual(settings.slugbot_base_url, "https://slugbot.example")
        self.assertEqual(settings.status_message, "")
        self.assertEqual(settings.log_level, "INFO")
        self.assertNotIn("secret", repr(settings))

    def test_accepts_native_values(self):
        settings = Settings.from_env(make_env(STATUS_ENABLED=False, SLOW_POLL_SEC=30))
        self.assertIs(settings.status_enabled, False)
        self.assertEqual(settings.slow_poll_sec, 30)

    def test_missing_variable(self):
        env = make_env()
        del env.SLUGBOT_API_KEY
        with self.assertRaisesRegex(ConfigError, "SLUGBOT_API_KEY"):
            Settings.from_env(env)

    def test_invalid_int_and_bool(self):
        with self.assertRaisesRegex(ConfigError, "FAST_POLL_SEC"):
            Settings.from_env(make_env(FAST_POLL_SEC="soon"))
        with self.assertRaisesRegex(ConfigError, "STATUS_ENABLED"):
            Settings.from_env(make_env(STATUS_ENABLED="maybe"))

    def test_clamps_poll_values(self):
        with self.assertLogs("dbd1v1timerapi", level="WARNING"):
            settings = Settings.from_env(
                make_env(FAST_POLL_SEC="1", SLOW_POLL_SEC="999999", FAST_POLL_CAP_SEC="-5")
            )
        self.assertEqual(settings.fast_poll_sec, FAST_POLL_SEC_RANGE[0])
        self.assertEqual(settings.slow_poll_sec, SLOW_POLL_SEC_RANGE[1])
        self.assertEqual(settings.fast_poll_cap_sec, FAST_POLL_CAP_SEC_RANGE[0])

    def test_warns_for_each_clamped_value(self):
        cases = [
            ("FAST_POLL_SEC", "1", FAST_POLL_SEC_RANGE[0]),
            ("FAST_POLL_SEC", "100000", FAST_POLL_SEC_RANGE[1]),
            ("SLOW_POLL_SEC", "1", SLOW_POLL_SEC_RANGE[0]),
            ("SLOW_POLL_SEC", "100000", SLOW_POLL_SEC_RANGE[1]),
            ("FAST_POLL_CAP_SEC", "-5", FAST_POLL_CAP_SEC_RANGE[0]),
            ("FAST_POLL_CAP_SEC", "100000", FAST_POLL_CAP_SEC_RANGE[1]),
        ]
        for variable, raw, expected in cases:
            with self.subTest(variable=variable, value=raw):
                with self.assertLogs("dbd1v1timerapi", level="WARNING") as logs:
                    Settings.from_env(make_env(**{variable: raw}))
                self.assertEqual(len(logs.records), 1)
                record = logs.records[0]
                self.assertEqual(record.levelname, "WARNING")
                self.assertEqual(record.variable, variable)
                self.assertEqual(record.value, int(raw))
                self.assertEqual(record.clamped, expected)

    def test_no_warning_for_in_range_values(self):
        with self.assertNoLogs("dbd1v1timerapi", level="WARNING"):
            Settings.from_env(make_env())

    def test_no_warning_at_bounds(self):
        for bound in (0, 1):
            with self.subTest(bound="min" if bound == 0 else "max"):
                env = make_env(
                    FAST_POLL_SEC=str(FAST_POLL_SEC_RANGE[bound]),
                    SLOW_POLL_SEC=str(SLOW_POLL_SEC_RANGE[bound]),
                    FAST_POLL_CAP_SEC=str(FAST_POLL_CAP_SEC_RANGE[bound]),
                )
                with self.assertNoLogs("dbd1v1timerapi", level="WARNING"):
                    Settings.from_env(env)


if __name__ == "__main__":
    unittest.main()
