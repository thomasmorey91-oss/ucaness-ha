"""Capteurs binaires de surveillance (premières détections de défauts)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BATTERY_CHARGE_TEMP_MAX, BATTERY_CHARGE_TEMP_MIN, CONF_DEVICE_CODE, OBJECT_IDS, STALE_AFTER_S
from .coordinator import UcanessConfigEntry, UcanessCoordinator
from .sensor import device_info


def _cloud_ok(data: dict[str, Any]) -> bool | None:
    """Connecté si le portail voit l'appareil en ligne ET si la dernière mesure date de moins de 15 min."""
    values = data.get("values", {})
    age = values.get("data_age")
    online = data.get("online")
    if online is None and age is None:
        return None
    return bool(online) and age is not None and age < STALE_AFTER_S


def _battery_fault(data: dict[str, Any]) -> bool | None:
    values = data.get("values", {})
    codes = [values.get("battery_fault_code"), values.get("battery_alarm_code")]
    if all(c is None for c in codes):
        return None
    return any(c not in (None, 0) for c in codes)


def _charge_temp_out_of_range(data: dict[str, Any]) -> bool | None:
    values = data.get("values", {})
    tmin, tmax = values.get("cell_temp_min"), values.get("cell_temp_max")
    if tmin is None and tmax is None:
        return None
    return (tmin is not None and tmin < BATTERY_CHARGE_TEMP_MIN) or (tmax is not None and tmax > BATTERY_CHARGE_TEMP_MAX)


@dataclass(frozen=True)
class Check:
    key: str
    name: str
    device_class: BinarySensorDeviceClass
    fn: Callable[[dict[str, Any]], bool | None]


CHECKS = (
    Check("cloud_connection", "Connexion au cloud UCANESS", BinarySensorDeviceClass.CONNECTIVITY, _cloud_ok),
    Check("battery_fault", "Défaut ou alarme batterie", BinarySensorDeviceClass.PROBLEM, _battery_fault),
    Check(
        "battery_temp_out_of_charge_range",
        "Température batterie hors plage de charge (0–50 °C)",
        BinarySensorDeviceClass.PROBLEM,
        _charge_temp_out_of_range,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: UcanessConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(UcanessCheck(coordinator, entry, c) for c in CHECKS)


class UcanessCheck(CoordinatorEntity[UcanessCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: UcanessCoordinator, entry: UcanessConfigEntry, check: Check) -> None:
        super().__init__(coordinator)
        self._check = check
        self._attr_unique_id = f"{entry.data[CONF_DEVICE_CODE]}_{check.key}"
        self._attr_name = check.name
        self._attr_device_class = check.device_class
        self._attr_device_info = device_info(entry, coordinator)
        if check.key in OBJECT_IDS:
            self.entity_id = f"binary_sensor.{OBJECT_IDS[check.key]}"

    @property
    def is_on(self) -> bool | None:
        return self._check.fn(self.coordinator.data or {})
