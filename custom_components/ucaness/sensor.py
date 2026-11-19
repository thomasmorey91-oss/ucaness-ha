"""Capteurs UCANESS (lecture seule)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import parser
from .const import CONF_DEVICE_CODE, DOMAIN
from .coordinator import UcanessCoordinator

DEVICE_CLASSES = {
    "power": SensorDeviceClass.POWER,
    "energy": SensorDeviceClass.ENERGY,
    "voltage": SensorDeviceClass.VOLTAGE,
    "current": SensorDeviceClass.CURRENT,
    "frequency": SensorDeviceClass.FREQUENCY,
    "temperature": SensorDeviceClass.TEMPERATURE,
    "battery": SensorDeviceClass.BATTERY,
    "timestamp": SensorDeviceClass.TIMESTAMP,
}
STATE_CLASSES = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
}


def device_info(entry: ConfigEntry, coordinator: UcanessCoordinator) -> DeviceInfo:
    info = ((coordinator.data or {}).get("raw", {}).get("detail", {}) or {}).get("device_info") or {}
    return DeviceInfo(
        identifiers={(DOMAIN, entry.data[CONF_DEVICE_CODE])},
        name=info.get("device_name") or entry.title,
        manufacturer="UCanpower",
        model=f"UHome {info.get('pcs_model', '')}".strip(),
        sw_version=info.get("firmware"),
        serial_number=info.get("dev_sn"),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: UcanessCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(UcanessSensor(coordinator, entry, m) for m in parser.MEASURES)


class UcanessSensor(CoordinatorEntity[UcanessCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: UcanessCoordinator, entry: ConfigEntry, measure: parser.Measure) -> None:
        super().__init__(coordinator)
        self._measure = measure
        self._attr_unique_id = f"{entry.data[CONF_DEVICE_CODE]}_{measure.key}"
        self._attr_name = measure.name
        self._attr_native_unit_of_measurement = measure.unit
        self._attr_device_class = DEVICE_CLASSES.get(measure.device_class or "")
        self._attr_state_class = STATE_CLASSES.get(measure.state_class or "")
        if measure.precision is not None:
            self._attr_suggested_display_precision = measure.precision
        if measure.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = device_info(entry, coordinator)

    @property
    def native_value(self) -> Any:
        value = (self.coordinator.data or {}).get("values", {}).get(self._measure.key)
        if value is not None and self._measure.device_class == "timestamp":
            return dt_util.utc_from_timestamp(int(value))
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._measure.key == "event_count":
            last = (self.coordinator.data or {}).get("last_event")
            return {"dernier_evenement": last} if last else None
        return None
