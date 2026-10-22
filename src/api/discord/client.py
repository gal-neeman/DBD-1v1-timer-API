"""Discord API client. URLs come from the DiscordEndpoint registry; I/O goes through HttpSend."""

from __future__ import annotations

from api.config import Settings
from api.discord.dtos import DiscordUserDto
from api.discord.endpoints import DiscordEndpoint
from api.transport import HttpSend
from api.upstream import UpstreamClient, UpstreamError, UpstreamNotFound, UpstreamUnavailable

# Discord rejects bot requests without a User-Agent in this format.
USER_AGENT = "DiscordBot (https://dbd1v1-api.truuehsoft.com, 1.0)"


class DiscordError(UpstreamError):
    """Discord returned an error status, invalid JSON, or an unexpected shape."""


class DiscordNotFound(DiscordError, UpstreamNotFound):
    """Discord returned 404 (e.g. unknown user)."""


class DiscordUnavailable(DiscordError, UpstreamUnavailable):
    """The request never got a response (network failure or timeout)."""


class DiscordClient(UpstreamClient):
    _name = "Discord"
    _error = DiscordError
    _not_found = DiscordNotFound
    _unavailable = DiscordUnavailable

    def __init__(self, settings: Settings, send: HttpSend) -> None:
        super().__init__(settings.discord_base_url, settings.discord_timeout_sec, send)
        self._bot_token = settings.discord_bot_token

    def _headers(self) -> dict[str, str]:
        return {
            **super()._headers(),
            "Authorization": f"Bot {self._bot_token}",
            "User-Agent": USER_AGENT,
        }

    async def get_user(self, user_id: str, *, log: bool = True) -> DiscordUserDto:
        data = await self._request(DiscordEndpoint.USER, log=log, user_id=user_id)
        return self._parse(DiscordEndpoint.USER, DiscordUserDto, data, log=log)
