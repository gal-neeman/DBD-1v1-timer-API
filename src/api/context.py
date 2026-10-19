"""Per-request dependencies passed to every handler."""

from __future__ import annotations

from dataclasses import dataclass

from api.config import Settings
from api.slugbot import SlugbotClient


@dataclass(frozen=True, slots=True)
class Context:
    settings: Settings
    slugbot: SlugbotClient
