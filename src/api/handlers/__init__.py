"""Endpoint handlers. Each takes (context, path params) and returns an ApiResponse."""

from api.handlers.players import get_player_details
from api.handlers.status import get_status

__all__ = ["get_player_details", "get_status"]
