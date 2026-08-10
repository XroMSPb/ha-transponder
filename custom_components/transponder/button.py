"""Button platform for the Transponder integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PROVIDERS
from .coordinator import TransponderConfigEntry, TransponderCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransponderConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a refresh button for every account."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = [
            TransponderRefreshButton(coordinator, key)
            for key in coordinator.data
            if key not in known
        ]
        if new:
            known.update(button.key for button in new)
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class TransponderRefreshButton(
    CoordinatorEntity[TransponderCoordinator], ButtonEntity
):
    """Force an immediate balance refresh for an account."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: TransponderCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = f"{key}_refresh"
        account = coordinator.data.get(key)
        provider_name = PROVIDERS.get(coordinator.provider, coordinator.provider)
        device_label = (
            (account.contract or account.account_id) if account else key
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, key)},
            name=f"{provider_name} · {device_label}",
            manufacturer=provider_name,
            model="Транспондер",
        )

    async def async_press(self) -> None:
        """Trigger a coordinator refresh."""
        await self.coordinator.async_request_refresh()
