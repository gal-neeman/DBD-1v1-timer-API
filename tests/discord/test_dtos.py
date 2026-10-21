import unittest

from api.discord.dtos import DiscordUserDto

# Trimmed GET /users/<id> response; extra fields are ignored.
USER_JSON = {
    "id": "80351110224678912",
    "username": "nelly",
    "global_name": "Nelly",
    "discriminator": "0",
    "avatar": "8342729096ea3675442027381ff50dfe",
    "public_flags": 64,
}


class DiscordDtoParsingTest(unittest.TestCase):
    def test_user_from_dict(self):
        user = DiscordUserDto.from_dict(USER_JSON)
        self.assertEqual(user.id, "80351110224678912")
        self.assertEqual(user.username, "nelly")
        self.assertEqual(user.global_name, "Nelly")
        self.assertEqual(user.display_name, "Nelly")

    def test_display_name_falls_back_to_username(self):
        for body in ({**USER_JSON, "global_name": None}, {k: v for k, v in USER_JSON.items() if k != "global_name"}):
            with self.subTest(global_name=body.get("global_name", "<missing>")):
                user = DiscordUserDto.from_dict(body)
                self.assertIsNone(user.global_name)
                self.assertEqual(user.display_name, "nelly")

    def test_rejects_non_string_global_name(self):
        with self.assertRaises(TypeError):
            DiscordUserDto.from_dict({**USER_JSON, "global_name": 5})


if __name__ == "__main__":
    unittest.main()
