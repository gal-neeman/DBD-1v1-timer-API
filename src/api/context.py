"""Per-request dependencies passed to every handler."""

from __future__ import annotations

from dataclasses import dataclass

from api.cache import Cache
from api.config import Settings
from api.discord import DiscordClient
from api.slugbot import SlugbotClient


@dataclass(frozen=True, slots=True)
class Context:
    settings: Settings
    slugbot: SlugbotClient
    discord: DiscordClient
    cache: Cache
