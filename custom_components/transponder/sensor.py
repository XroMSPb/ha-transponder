"""Sensors for the Transponder (ЗСД / Автодор) integration."""

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

from .api import Account
from .const import (
    ATTR_ACCOUNT,
    ATTR_CONTRACT,
    ATTR_PROVIDER,
    ATTR_STATUS,
    ATTR_TRANSPONDERS,
    ATTR_UPDATED_AT,
    DOMAIN,
    PROVIDERS,
)
from .coordinator import TransponderConfigEntry, TransponderCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransponderConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up balance (and bonus) sensors for every account."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new: list[SensorEntity] = []
        for key, account in coordinator.data.items():
            if key in known:
                continue
            known.add(key)
            new.append(TransponderBalanceSensor(coordinator, key))
            if account.bonus_points is not None:
                new.append(TransponderBonusSensor(coordinator, key))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class _BaseAccountSensor(
    CoordinatorEntity[TransponderCoordinator], SensorEntity
):
    """Shared device/account plumbing."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TransponderCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        account = self._account
        provider_name = PROVIDERS.get(coordinator.provider, coordinator.provider)
        device_label = account.contract or account.account_id if account else key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, key)},
            name=f"{provider_name} · {device_label}",
            manufacturer=provider_name,
            model="Транспондер",
        )

    @property
    def _account(self) -> Account | None:
        return self.coordinator.data.get(self._key)

    @property
    def available(self) -> bool:
        return super().available and self._account is not None


class TransponderBalanceSensor(_BaseAccountSensor):
    """Account balance."""

    _attr_translation_key = "balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: TransponderCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._attr_unique_id = f"{key}_balance"
        account = self._account
        self._attr_native_unit_of_measurement = (
            account.currency if account else "RUB"
        )

    @property
    def native_value(self) -> float | None:
        account = self._account
        return account.balance if account else None

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None]:
        account = self._account
        if account is None:
            return {}
        return {
            ATTR_PROVIDER: account.provider,
            ATTR_CONTRACT: account.contract,
            ATTR_ACCOUNT: account.extra.get("account") or account.account_id,
            ATTR_STATUS: account.status,
            ATTR_TRANSPONDERS: account.transponders_count,
            ATTR_UPDATED_AT: account.updated_at,
        }


class TransponderBonusSensor(_BaseAccountSensor):
    """Loyalty bonus points (Автодор)."""

    _attr_translation_key = "bonus"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "баллы"
    _attr_icon = "mdi:star-circle"

    def __init__(self, coordinator: TransponderCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._attr_unique_id = f"{key}_bonus"

    @property
    def native_value(self) -> float | None:
        account = self._account
        return account.bonus_points if account else None
