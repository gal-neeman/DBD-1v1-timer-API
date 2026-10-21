"""Shared plumbing for clients of upstream HTTP APIs (Slugbot, Discord)."""

from api.upstream.client import UpstreamClient, UpstreamError, UpstreamNotFound, UpstreamUnavailable
from api.upstream.endpoint import Endpoint

__all__ = [
    "Endpoint",
    "UpstreamClient",
    "UpstreamError",
    "UpstreamNotFound",
    "UpstreamUnavailable",
]
