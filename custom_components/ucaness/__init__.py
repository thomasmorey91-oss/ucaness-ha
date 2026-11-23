"""Intégration Home Assistant UCANESS (UCanpower UHome), non officielle.

Lecture des mesures par le portail ; pilotage limité (mode autoconsommation ou arbitrage
horaire, plages de charge) par l'API tierce signée d'UCanpower, seulement si l'option
« Écriture autorisée » est activée. Voir services.py et api.py pour les garde-fous.
"""
from __future__ import annotations

from collections import deque

from homeassistant.const import CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from . import assistant
from .reglages import CONF_REGLAGES
from .api import UcanessClient
from .const import (
    CONF_APP_KEY,
    CONF_APP_SECRET,
    CONF_DEVICE_CODE,
    CONF_PASSWORD_MD5,
    CONF_SCAN_INTERVAL,
    DATA_WRITE_LOG,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import UcanessConfigEntry, UcanessCoordinator
from .services import async_setup_services

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SELECT, Platform.TIME, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: UcanessConfigEntry) -> bool:
    # Plafond d'écritures par onduleur, conservé d'un rechargement à l'autre de l'entrée.
    write_log = hass.data.setdefault(DATA_WRITE_LOG, {}).setdefault(entry.data[CONF_DEVICE_CODE], deque())
    client = UcanessClient(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD_MD5],
        app_key=entry.options.get(CONF_APP_KEY),
        app_secret=entry.options.get(CONF_APP_SECRET),
        write_log=write_log,
    )
    scan = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = UcanessCoordinator(hass, client, entry.data[CONF_DEVICE_CODE], scan)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    coordinator.options_chargees = _hors_reglages(entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    # Assistant d'installation : à chaque lecture de l'onduleur, l'étape suivante est signalée dans
    # Paramètres > Système > Réparations (lecture seule, rien n'est modifié).
    @callback
    def _suivre_l_installation(_hass: HomeAssistant | None = None) -> None:
        assistant.signaler_etape_suivante(hass, entry)

    entry.async_on_unload(coordinator.async_add_listener(_suivre_l_installation))
    entry.async_on_unload(async_at_started(hass, _suivre_l_installation))
    # Toutes les plateformes sont chargées : le bilan de l'installation voit maintenant chaque entité.
    coordinator.async_update_listeners()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: UcanessConfigEntry) -> bool:
    assistant.retirer_les_signalements(hass, entry)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _hors_reglages(entry: UcanessConfigEntry) -> dict:
    return {k: v for k, v in entry.options.items() if k != CONF_REGLAGES}


async def _async_reload(hass: HomeAssistant, entry: UcanessConfigEntry) -> None:
    # Un réglage du pilotage modifié ne change rien à la liaison avec l'onduleur : pas de
    # rechargement, les entités sont simplement rafraîchies.
    if _hors_reglages(entry) == getattr(entry.runtime_data, "options_chargees", None):
        entry.runtime_data.async_update_listeners()
        return
    await hass.config_entries.async_reload(entry.entry_id)
