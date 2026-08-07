"""Data update coordinator for the ЗСД Transponder integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ContractBalance,
    ZsdApiClient,
    ZsdAuthError,
    ZsdConnectionError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type ZsdConfigEntry = ConfigEntry[ZsdDataUpdateCoordinator]


class ZsdDataUpdateCoordinator(DataUpdateCoordinator[dict[str, ContractBalance]]):
    """Coordinator that keeps every contract's balance up to date."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        username: str,
        password: str,
        scan_interval: timedelta = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=scan_interval,
            config_entry=entry,
        )
        # A dedicated session gives us an isolated cookie jar for the login.
        session = async_create_clientsession(hass)
        self.client = ZsdApiClient(session, username, password)

    async def _async_update_data(self) -> dict[str, ContractBalance]:
        try:
            contracts = await self.client.async_get_balances()
        except ZsdAuthError as err:
            # Surfaces as a re-auth flow / persistent auth error in HA.
            from homeassistant.exceptions import ConfigEntryAuthFailed

            raise ConfigEntryAuthFailed(str(err)) from err
        except ZsdConnectionError as err:
            raise UpdateFailed(str(err)) from err

        return {contract.contract: contract for contract in contracts}
