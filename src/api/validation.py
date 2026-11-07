"""Validation of client-supplied values."""

from __future__ import annotations

import re

# Discord user IDs are snowflakes: unsigned 64-bit ints, 17-20 decimal digits in practice.
_DISCORD_ID_RE = re.compile(r"[0-9]{17,20}")
_UINT64_MAX = 2**64 - 1


def is_discord_id(value: str) -> bool:
    return _DISCORD_ID_RE.fullmatch(value) is not None and int(value) <= _UINT64_MAX
