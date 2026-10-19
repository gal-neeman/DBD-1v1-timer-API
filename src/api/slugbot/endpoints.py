"""Registry of Slugbot API endpoints. Paths are templates relative to SLUGBOT_BASE_URL."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import quote, urlencode


@dataclass(frozen=True, slots=True)
class Endpoint:
    method: str
    path: str
    query_params: tuple[str, ...] = ()

    def build_path(self, **params: str) -> str:
        """Fill the path template, URL-encoding each value. Raises KeyError for a missing param."""
        encoded = {name: quote(str(value), safe="") for name, value in params.items()}
        return self.path.format(**encoded)

    def build_query(self, query: dict[str, str] | None) -> str:
        """Encode query params as '?a=b', or '' if none. Raises ValueError for unknown keys."""
        if not query:
            return ""
        unknown = set(query) - set(self.query_params)
        if unknown:
            raise ValueError(f"Unknown query params for {self.path}: {sorted(unknown)}")
        return "?" + urlencode(query)


class SlugbotEndpoint(Enum):
    PLAYER = Endpoint("GET", "/{guild_id}/{leaderboard_id}/player/{user_id}")
    MATCH_BATCH = Endpoint(
        "GET",
        "/{guild_id}/{leaderboard_id}/match/batch",
        query_params=("limit", "nextCursor", "userId"),
    )
