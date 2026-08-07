"""Balance sensors for the ЗСД Transponder integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ContractBalance
from .const import (
    ATTR_CONTRACT,
    ATTR_STATUS,
    ATTR_UPDATED_AT,
    CURRENCY_RUB,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import ZsdConfigEntry, ZsdDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZsdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ЗСД balance sensors from a config entry."""
    coordinator = entry.runtime_data

    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = [
            ZsdBalanceSensor(coordinator, contract)
            for contract in coordinator.data
            if contract not in known
        ]
        if new:
            known.update(s.contract_id for s in new)
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class ZsdBalanceSensor(CoordinatorEntity[ZsdDataUpdateCoordinator], SensorEntity):
    """Balance sensor for a single ЗСД contract."""

    _attr_has_entity_name = True
    _attr_translation_key = "balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = CURRENCY_RUB
    _attr_suggested_display_precision = 2

    def __init__(
        self, coordinator: ZsdDataUpdateCoordinator, contract_id: str
    ) -> None:
        super().__init__(coordinator)
        self.contract_id = contract_id
        self._attr_unique_id = f"{DOMAIN}_{contract_id}_balance"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, contract_id)},
            name=f"ЗСД {contract_id}",
            manufacturer=MANUFACTURER,
            model="Транспондер",
        )

    @property
    def _contract(self) -> ContractBalance | None:
        return self.coordinator.data.get(self.contract_id)

    @property
    def available(self) -> bool:
        return super().available and self._contract is not None

    @property
    def native_value(self) -> float | None:
        contract = self._contract
        return contract.balance if contract else None

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        contract = self._contract
        if contract is None:
            return {}
        return {
            ATTR_CONTRACT: contract.contract,
            ATTR_STATUS: contract.status,
            ATTR_UPDATED_AT: contract.updated_at,
        }
