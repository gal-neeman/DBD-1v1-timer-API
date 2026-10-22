"""Registry of Slugbot API endpoints. Paths are templates relative to SLUGBOT_BASE_URL."""

from __future__ import annotations

from enum import Enum

from api.upstream import Endpoint


class SlugbotEndpoint(Enum):
    PLAYER = Endpoint("GET", "/{guild_id}/{leaderboard_id}/player/{user_id}")
    MATCH_BATCH = Endpoint(
        "GET",
        "/{guild_id}/{leaderboard_id}/match/batch",
        query_params=("complete", "limit", "nextCursor", "userId"),
    )
