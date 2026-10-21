"""Discord response DTOs. Only the fields this API uses are parsed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DiscordUserDto:
    """Response of GET /users/<id>."""

    id: str
    username: str
    global_name: str | None

    @property
    def display_name(self) -> str:
        """The user's display name, or their username if they haven't set one."""
        return self.global_name or self.username

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiscordUserDto:
        global_name = data.get("global_name")
        if global_name is not None and not isinstance(global_name, str):
            raise TypeError(f"expected str or null global_name, got {type(global_name).__name__}")
        return cls(
            id=str(data["id"]),
            username=str(data["username"]),
            global_name=global_name,
        )
