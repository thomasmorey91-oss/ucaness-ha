"""Réglages horaires du pilotage (début et fin des heures creuses). Voir reglages.py."""
from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import reglages
from .coordinator import UcanessConfigEntry
from .entite_reglage import EntiteReglage, entites


async def async_setup_entry(hass: HomeAssistant, entry: UcanessConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(entites(entry.runtime_data, entry, reglages.TIME, ReglageHeure))


class ReglageHeure(EntiteReglage, TimeEntity):
    @property
    def native_value(self) -> time | None:
        v = self.valeur
        return None if v is None else time.fromisoformat(v)

    async def async_set_value(self, value: time) -> None:
        await self.async_definir(value.isoformat())
