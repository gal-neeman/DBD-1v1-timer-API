"""GET /api/v1/players/{player_id}."""

from __future__ import annotations

from api import players
from api.context import Context
from api.responses import ApiResponse, json_error, json_ok
from api.slugbot import SlugbotError, SlugbotNotFound, SlugbotUnavailable
from api.validation import is_discord_id


async def get_player_details(ctx: Context, params: dict[str, str]) -> ApiResponse:
    player_id = params["player_id"]
    if not is_discord_id(player_id):
        return json_error(400, "invalid_player_id", "player_id must be a Discord user ID")

    # The client logs every failure, so errors are only mapped to responses here.
    # SlugbotNotFound and SlugbotUnavailable subclass SlugbotError, so they come first.
    try:
        details = await players.get_player_details(ctx, player_id)
    except SlugbotNotFound:
        return json_error(404, "player_not_found", "No ranked data for this player")
    except SlugbotUnavailable:
        return json_error(503, "upstream_unavailable", "Leaderboard service is unreachable")
    except SlugbotError:
        return json_error(
            502, "upstream_error", "Leaderboard service returned an invalid response"
        )
    return json_ok(details)
