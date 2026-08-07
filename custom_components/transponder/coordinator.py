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
from .const import DEFAULT_HEADERS, DEFAULT_SCAN_INTERVAL, DOMAIN

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

    async def _async_update_data(self) -> dict[str, Account]:
        try:
            accounts = await self.client.async_get_accounts()
        except TransponderAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TransponderConnectionError as err:
            raise UpdateFailed(str(err)) from err
        return {account.unique_key: account for account in accounts}
