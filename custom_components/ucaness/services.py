"""Actions (services) de pilotage de l'onduleur UHome.

- ucaness.tester_api : lecture seule par l'API tierce signée (vérifie clé, appareil, réglages).
- ucaness.definir_plages_charge : programme jusqu'à 3 plages de charge du mode arbitrage
  horaire ; les autres plages de charge et toutes les plages de décharge sont vidées.
- ucaness.definir_mode : autoconsommation ou arbitrage horaire (Backup refusé).

Les deux actions d'écriture exigent l'option « Écriture autorisée » de l'intégration.
Chaque envoi est journalisé puis relu : si l'onduleur ne reflète pas la consigne, l'action
échoue (le script appelant s'arrête, par exemple avant de changer de mode).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import (
    SET_WORK_MODE,
    WORK_MODES,
    UcanessError,
    UcanessWriteRefused,
    model_write_confirmed,
    pcs_settings,
    read_back_value,
    windows_to_settings,
)
from .const import (
    CONF_DEVICE_CODE,
    CONF_WRITE_ENABLED,
    DOMAIN,
    MODE_READBACK_ATTEMPTS,
    READBACK_ATTEMPTS,
    READBACK_DELAY_S,
)
from .coordinator import UcanessCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_TEST = "tester_api"
SERVICE_WINDOWS = "definir_plages_charge"
SERVICE_MODE = "definir_mode"

ATTR_ENTRY = "config_entry_id"
HHMM = vol.All(cv.string, vol.Match(r"^([01]\d|2[0-3]):?[0-5]\d$"))
WINDOW = vol.Schema({vol.Required("debut"): HHMM, vol.Required("fin"): HHMM})

TEST_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTRY): cv.string})
WINDOWS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY): cv.string,
        vol.Required("plages"): vol.All(cv.ensure_list, [WINDOW], vol.Length(max=3)),
    }
)
MODE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY): cv.string,
        vol.Required("mode"): vol.In(list(WORK_MODES)),
    }
)


def _entry(hass: HomeAssistant, call: ServiceCall) -> ConfigEntry:
    entry_id = call.data.get(ATTR_ENTRY)
    entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.state is ConfigEntryState.LOADED and (entry_id is None or e.entry_id == entry_id)
    ]
    if len(entries) != 1:
        raise ServiceValidationError("Appareil UCANESS introuvable ou ambigu (préciser config_entry_id)")
    return entries[0]


def _coordinator(hass: HomeAssistant, entry: ConfigEntry) -> UcanessCoordinator:
    return hass.data[DOMAIN][entry.entry_id]


def _require_write(entry: ConfigEntry) -> None:
    if not entry.options.get(CONF_WRITE_ENABLED, False):
        raise ServiceValidationError(
            "Écriture vers l'onduleur désactivée (option « Écriture autorisée » de l'intégration UCANESS)"
        )


async def _write_and_verify(
    hass: HomeAssistant, entry: ConfigEntry, items: dict[int, int], label: str
) -> dict[str, Any]:
    coordinator = _coordinator(hass, entry)
    code = entry.data[CONF_DEVICE_CODE]
    mode_before = _telemetry_mode(coordinator)
    try:
        sent = await coordinator.client.update_settings(code, items)
    except UcanessWriteRefused as err:
        raise ServiceValidationError(f"Consigne refusée par le garde-fou : {err}") from err
    except UcanessError as err:
        raise HomeAssistantError(f"Consigne non envoyée ({label}) : {err}") from err

    mismatch: dict[int, Any] = {}
    settings: dict[str, Any] = {}
    attempts = MODE_READBACK_ATTEMPTS if SET_WORK_MODE in items else READBACK_ATTEMPTS
    for attempt in range(attempts):
        await asyncio.sleep(READBACK_DELAY_S)
        try:
            settings = pcs_settings(await coordinator.client.get_config_v1(code))
        except UcanessError as err:
            _LOGGER.debug("Relecture impossible (essai %s) : %s", attempt + 1, err)
            continue
        mismatch = {
            set_id: read_back_value(settings, set_id)
            for set_id, value in items.items()
            if read_back_value(settings, set_id) != int(value)
        }
        if set(mismatch) == {SET_WORK_MODE}:
            # Le cloud ne garde pas toujours le mode dans la configuration : on regarde aussi
            # le mode affiché par l'onduleur.
            await coordinator.async_refresh()
            if _telemetry_mode_matches(_telemetry_mode(coordinator), int(items[SET_WORK_MODE]), mode_before):
                mismatch = {}
        if not mismatch:
            break
    coordinator.invalidate_config()
    await coordinator.async_request_refresh()
    if mismatch or not settings:
        _LOGGER.warning("UCANESS : %s envoyé mais non confirmé par l'onduleur : %s", label, mismatch or "relecture impossible")
        raise HomeAssistantError(f"{label} : consigne envoyée mais non confirmée par l'onduleur ({mismatch or 'relecture impossible'})")
    _LOGGER.info("UCANESS : %s confirmé par l'onduleur", label)
    return {"envoye": sent, "confirme": True}


def _telemetry_mode(coordinator: UcanessCoordinator) -> str | None:
    raw = (coordinator.data or {}).get("raw") or {}
    status = ((raw.get("detail") or {}).get("status")) or {}
    value = status.get("work_mode_str")
    return value if isinstance(value, str) else None


def _telemetry_mode_matches(shown: str | None, value: int, before: str | None) -> bool:
    if not shown:
        return False
    low = shown.lower()
    if value == 0:
        return "match load" in low or "self" in low
    if value == 1:
        return "peak" in low or (before is not None and shown != before and "match load" not in low)
    return False


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def async_setup_services(hass: HomeAssistant) -> None:
    async def tester_api(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass, call)
        client = _coordinator(hass, entry).client
        code = entry.data[CONF_DEVICE_CODE]
        try:
            device_id, model = await client.resolve_device_v1(code)
            settings = pcs_settings(await client.get_config_v1(code), model)
        except UcanessWriteRefused as err:
            raise ServiceValidationError(str(err)) from err
        except UcanessError as err:
            raise HomeAssistantError(f"API tierce UCANESS : {err}") from err
        windows = {
            key: settings.get(key)
            for key in sorted(settings)
            if key.startswith(("charge_time", "discharge_time"))
        }
        return {
            "device_id": device_id,
            "inverter_model": model,
            "work_mode": read_back_value(settings, SET_WORK_MODE),
            "mode_affiche": _telemetry_mode(_coordinator(hass, entry)),
            "plages": windows,
            "ecriture_autorisee": bool(entry.options.get(CONF_WRITE_ENABLED, False)),
            "modele_confirme_pour_ecriture": model_write_confirmed(model),
            "reglages_bruts": dict(sorted(settings.items())),
        }

    async def definir_plages_charge(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass, call)
        _require_write(entry)
        windows = [(w["debut"], w["fin"]) for w in call.data["plages"]]
        try:
            items = windows_to_settings(windows)
        except UcanessWriteRefused as err:
            raise ServiceValidationError(str(err)) from err
        return await _write_and_verify(hass, entry, items, f"plages de charge {windows}")

    async def definir_mode(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass, call)
        _require_write(entry)
        mode = call.data["mode"]
        return await _write_and_verify(hass, entry, {SET_WORK_MODE: WORK_MODES[mode]}, f"mode {mode}")

    hass.services.async_register(
        DOMAIN, SERVICE_TEST, tester_api, schema=TEST_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, SERVICE_WINDOWS, definir_plages_charge, schema=WINDOWS_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MODE, definir_mode, schema=MODE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
