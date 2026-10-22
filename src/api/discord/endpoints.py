"""Registry of Discord API endpoints. Paths are templates relative to DISCORD_BASE_URL."""

from __future__ import annotations

from enum import Enum

from api.upstream import Endpoint


class DiscordEndpoint(Enum):
    USER = Endpoint("GET", "/users/{user_id}")
