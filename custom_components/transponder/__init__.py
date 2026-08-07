"""The Transponder (ЗСД / Автодор) integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_PROVIDER, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .coordinator import TransponderConfigEntry, TransponderCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: TransponderConfigEntry
) -> bool:
    """Set up a Transponder account from a config entry."""
    scan_minutes = entry.options.get(CONF_SCAN_INTERVAL)
    scan_interval = (
        timedelta(minutes=scan_minutes) if scan_minutes else DEFAULT_SCAN_INTERVAL
    )

    coordinator = TransponderCoordinator(
        hass,
        entry,
        provider=entry.data[CONF_PROVIDER],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        scan_interval=scan_interval,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TransponderConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: TransponderConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
