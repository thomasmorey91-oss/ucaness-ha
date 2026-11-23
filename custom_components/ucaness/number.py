"""Réglages numériques du pilotage (capacité, plancher, prix…). Voir reglages.py."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import reglages
from .coordinator import UcanessConfigEntry
from .entite_reglage import EntiteReglage, entites


async def async_setup_entry(hass: HomeAssistant, entry: UcanessConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(entites(entry.runtime_data, entry, reglages.NUMBER, ReglageNombre))


class ReglageNombre(EntiteReglage, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, entry, reglage) -> None:
        super().__init__(coordinator, entry, reglage)
        self._attr_native_min_value = reglage.mini
        self._attr_native_max_value = reglage.maxi
        self._attr_native_step = reglage.pas
        self._attr_native_unit_of_measurement = reglage.unite

    @property
    def native_value(self) -> float | None:
        return self.valeur

    async def async_set_native_value(self, value: float) -> None:
        await self.async_definir(value)
