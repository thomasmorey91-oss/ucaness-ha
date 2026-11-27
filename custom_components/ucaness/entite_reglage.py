"""Base commune des entités de réglage (number, select, time, switch). Voir reglages.py."""
from __future__ import annotations

from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.core import Event, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import reglages
from .const import CONF_DEVICE_CODE
from .coordinator import UcanessConfigEntry, UcanessCoordinator
from .sensor import device_info


class EntiteReglage(CoordinatorEntity[UcanessCoordinator]):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: UcanessCoordinator, entry: UcanessConfigEntry, reglage: reglages.Reglage) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._reglage = reglage
        self._attr_unique_id = f"{entry.data[CONF_DEVICE_CODE]}_reglage_{reglage.cle}"
        self._attr_translation_key = reglage.cle
        self._attr_icon = reglage.icone
        self._attr_device_info = device_info(entry, coordinator)
        self.entity_id = f"{reglage.type}.ucaness_{reglage.cle}"

    @property
    def available(self) -> bool:
        # Un réglage reste modifiable même si l'onduleur ne répond pas.
        return True

    @property
    def valeur(self) -> Any:
        return reglages.valeur(self.hass, self._entry, self._reglage.cle)

    async def async_definir(self, valeur: Any) -> None:
        await reglages.async_definir(self.hass, self._entry, {self._reglage.cle: valeur})
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _entree_modifiee(event: Event) -> None:
            self.async_write_ha_state()

        # L'entrée du package est la référence tant qu'elle existe : on suit ses changements.
        if self._reglage.entree:
            self.async_on_remove(async_track_state_change_event(self.hass, [self._reglage.entree], _entree_modifiee))


def entites(coordinator: UcanessCoordinator, entry: UcanessConfigEntry, type_: str, classe: type) -> list:
    return [classe(coordinator, entry, r) for r in reglages.REGLAGES if r.type == type_]
