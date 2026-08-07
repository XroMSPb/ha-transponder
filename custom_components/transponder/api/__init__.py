"""Provider client factory for the Transponder integration."""

from __future__ import annotations

import aiohttp

try:  # Package import inside Home Assistant.
    from ..const import PROVIDER_AVTODOR, PROVIDER_ZSD
except ImportError:  # Standalone import (tools/test_login.py).
    from const import PROVIDER_AVTODOR, PROVIDER_ZSD  # type: ignore[no-redef]
from .avtodor import AvtodorClient
from .base import (
    Account,
    TransponderAuthError,
    TransponderClient,
    TransponderConnectionError,
    TransponderError,
)
from .zsd import ZsdClient

__all__ = [
    "Account",
    "TransponderAuthError",
    "TransponderClient",
    "TransponderConnectionError",
    "TransponderError",
    "get_client",
]


def get_client(
    provider: str,
    session: aiohttp.ClientSession,
    username: str,
    password: str,
) -> TransponderClient:
    """Return the client implementation for ``provider``."""
    if provider == PROVIDER_ZSD:
        return ZsdClient(session, username, password)
    if provider == PROVIDER_AVTODOR:
        return AvtodorClient(session, username, password)
    raise ValueError(f"Unknown provider: {provider}")
