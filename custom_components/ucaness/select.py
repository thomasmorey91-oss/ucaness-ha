"""Réglages à choix du pilotage (type de contrat). Voir reglages.py."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import reglages
from .coordinator import UcanessConfigEntry
from .entite_reglage import EntiteReglage, entites


async def async_setup_entry(hass: HomeAssistant, entry: UcanessConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities(entites(entry.runtime_data, entry, reglages.SELECT, ReglageChoix))


class ReglageChoix(EntiteReglage, SelectEntity):
    def __init__(self, coordinator, entry, reglage) -> None:
        super().__init__(coordinator, entry, reglage)
        self._attr_options = list(reglage.options)

    @property
    def current_option(self) -> str | None:
        return self.valeur

    async def async_select_option(self, option: str) -> None:
        await self.async_definir(option)
