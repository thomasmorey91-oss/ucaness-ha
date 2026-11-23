"""Réglages oui / non du pilotage (week-end en heures creuses). Voir reglages.py."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import reglages
from .coordinator import UcanessConfigEntry
from .entite_reglage import EntiteReglage, entites


async def async_setup_entry(hass: HomeAssistant, entry: UcanessConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(entites(entry.runtime_data, entry, reglages.SWITCH, ReglageOuiNon))


class ReglageOuiNon(EntiteReglage, SwitchEntity):
    @property
    def is_on(self) -> bool | None:
        return self.valeur

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.async_definir(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.async_definir(False)
