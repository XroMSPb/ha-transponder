"""Data update coordinator for the Transponder integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    Account,
    TransponderAuthError,
    TransponderConnectionError,
    get_client,
)
from .const import (
    DEFAULT_HEADERS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_FAST_RETRIES,
    RETRY_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type TransponderConfigEntry = ConfigEntry[TransponderCoordinator]


class TransponderCoordinator(DataUpdateCoordinator[dict[str, Account]]):
    """Keeps every account's balance up to date for one provider login."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        provider: str,
        username: str,
        password: str,
        scan_interval: timedelta = DEFAULT_SCAN_INTERVAL,
        retry_interval: timedelta = RETRY_SCAN_INTERVAL,
        max_retries: int = MAX_FAST_RETRIES,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{provider}",
            update_interval=scan_interval,
            config_entry=entry,
        )
        # Dedicated session → isolated cookie jar for the login.
        session = async_create_clientsession(hass, headers=DEFAULT_HEADERS)
        self.provider = provider
        self.client = get_client(provider, session, username, password)
        # The interval requested by the user; we temporarily poll faster after
        # a failure, then fall back to this once the data recovers.
        self._normal_interval = scan_interval
        self._retry_interval = retry_interval
        self._max_retries = max_retries
        self._failure_count = 0

    async def _async_update_data(self) -> dict[str, Account]:
        try:
            accounts = await self.client.async_get_accounts()
        except TransponderAuthError as err:
            # Bad credentials won't be fixed by retrying; hand off to reauth.
            self._reset_backoff()
            raise ConfigEntryAuthFailed(str(err)) from err
        except TransponderConnectionError as err:
            self._apply_backoff()
            raise UpdateFailed(str(err)) from err
        except Exception:
            # Any other error is also transient from our point of view – keep
            # the balance's last value and retry soon instead of waiting for
            # the full interval. The coordinator marks the update as failed.
            self._apply_backoff()
            raise
        self._reset_backoff()
        return {account.unique_key: account for account in accounts}

    def _apply_backoff(self) -> None:
        """Poll faster for the first few failures, then back off to normal."""
        self._failure_count += 1
        if self._failure_count <= self._max_retries:
            # Never poll slower than the user asked for.
            self.update_interval = min(self._retry_interval, self._normal_interval)
        else:
            self.update_interval = self._normal_interval

    def _reset_backoff(self) -> None:
        """Restore the configured interval after a successful update."""
        self._failure_count = 0
        self.update_interval = self._normal_interval
