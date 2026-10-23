"""Everything about talking to the Slugbot API."""

from api.slugbot.client import SlugbotClient, SlugbotError, SlugbotNotFound, SlugbotUnavailable
from api.slugbot.dtos import (
    SlugbotMatchBatchDto,
    SlugbotMatchDto,
    SlugbotMatchParticipantDto,
    SlugbotMatchSeatDto,
    SlugbotOpenMatchDto,
    SlugbotPagingDto,
    SlugbotPlayerDto,
)
from api.slugbot.endpoints import SlugbotEndpoint

__all__ = [
    "SlugbotClient",
    "SlugbotEndpoint",
    "SlugbotError",
    "SlugbotMatchBatchDto",
    "SlugbotMatchDto",
    "SlugbotMatchParticipantDto",
    "SlugbotMatchSeatDto",
    "SlugbotNotFound",
    "SlugbotOpenMatchDto",
    "SlugbotPagingDto",
    "SlugbotPlayerDto",
    "SlugbotUnavailable",
]
