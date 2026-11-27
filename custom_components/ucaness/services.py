"""Actions (services) de pilotage de l'onduleur UHome.

- ucaness.tester_api : lecture seule par l'API tierce signée (vérifie clé, appareil, réglages).
- ucaness.definir_plages_charge : programme jusqu'à 3 plages de charge du mode arbitrage
  horaire ; les autres plages de charge et toutes les plages de décharge sont vidées.
- ucaness.definir_mode : autoconsommation ou arbitrage horaire (Backup refusé).
- ucaness.optimiser_charge : calcul seul (rien n'est envoyé) des plages de charge sous tarif
  dynamique, par le moteur intégré (optimiseur.py).
- ucaness.plages_depuis_plan : calcul seul ; traduit le plan d'un moteur externe (EMHASS)
  en 3 plages de charge au plus.

Les deux actions d'écriture exigent l'option « Écriture autorisée » de l'intégration.
Chaque envoi est journalisé puis relu : si l'onduleur ne reflète pas la consigne, l'action
échoue (le script appelant s'arrête, par exemple avant de changer de mode).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

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
from .coordinator import UcanessConfigEntry, UcanessCoordinator
from . import optimiseur, tarifs

_LOGGER = logging.getLogger(__name__)

SERVICE_TEST = "tester_api"
SERVICE_WINDOWS = "definir_plages_charge"
SERVICE_MODE = "definir_mode"
SERVICE_OPTIMISER = "optimiser_charge"
SERVICE_PLAN = "plages_depuis_plan"
SERVICE_OFFRES = "evaluer_offres"

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
POURCENT = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))
OPTIMISER_SCHEMA = vol.Schema(
    {
        vol.Required("prix"): vol.All(cv.ensure_list, [dict]),
        vol.Required("conso"): list,
        vol.Required("solaire"): vol.All(cv.ensure_list, [dict]),
        vol.Required("capacite_kwh"): vol.All(vol.Coerce(float), vol.Range(min=0, max=200)),
        vol.Required("plancher_pct"): POURCENT,
        vol.Required("soc_pct"): POURCENT,
        vol.Optional("rendement_pct", default=95): vol.All(vol.Coerce(float), vol.Range(min=50, max=100)),
        vol.Required("puissance_charge_kw"): vol.All(vol.Coerce(float), vol.Range(min=0, max=50)),
        vol.Optional("prix_revente", default=0): vol.Coerce(float),
        vol.Optional("marge_pct", default=0): POURCENT,
        vol.Optional("charge_interdite", default=False): cv.boolean,
        vol.Optional("reserve"): vol.Any(
            None,
            vol.Schema({vol.Required("debut"): cv.string, vol.Required("fin"): cv.string, vol.Required("soc_pct"): POURCENT}),
        ),
        vol.Optional("seuil_gain_eur", default=0.02): vol.Coerce(float),
        vol.Optional("valeur_stock_eur_kwh"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("max_plages", default=3): vol.All(vol.Coerce(int), vol.Range(min=1, max=3)),
    }
)
PLAN_SCHEMA = vol.Schema(
    {
        vol.Required("plan"): vol.All(cv.ensure_list, [dict]),
        vol.Optional("seuil_kw", default=0.2): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("max_plages", default=3): vol.All(vol.Coerce(int), vol.Range(min=1, max=3)),
    }
)
PRIX = vol.All(vol.Coerce(float), vol.Range(min=0, max=5))
OFFRE = vol.Schema(
    {
        vol.Required("nom"): cv.string,
        vol.Optional("fournisseur", default=""): cv.string,
        vol.Required("formule"): cv.string,
        # Abonnement annuel TTC par puissance souscrite : {"6": 150.0, "9": 190.0}.
        vol.Required("abonnement_eur_an"): vol.Schema({vol.Coerce(int): vol.All(vol.Coerce(float), vol.Range(min=0))}),
        vol.Required("prix_kwh"): vol.Schema({cv.string: PRIX}),
        vol.Optional("plages_hc", default=list): vol.All(cv.ensure_list, [WINDOW]),
        vol.Optional("weekend_hc", default=False): cv.boolean,
        vol.Optional("source", default=""): cv.string,
        vol.Optional("date_prix"): vol.Any(None, cv.date),
        # Tempo : jours de chaque couleur dans l'année (300 bleus, 43 blancs, 22 rouges par défaut).
        vol.Optional("jours_tempo"): vol.Any(None, vol.Schema({vol.In(tarifs.COULEURS): vol.All(vol.Coerce(int), vol.Range(min=0, max=366))})),
    }
)
OFFRES_SCHEMA = vol.Schema(
    {
        vol.Required("offres"): vol.All(cv.ensure_list, [OFFRE]),
        vol.Optional("contrat_actuel"): vol.Any(None, OFFRE),
        vol.Required("soutirage"): vol.All(cv.ensure_list, [dict]),
        vol.Required("puissance_kva"): vol.All(vol.Coerce(int), vol.Range(min=1, max=36)),
        vol.Optional("jours_non_ouvres", default=list): vol.All(cv.ensure_list, [cv.date]),
        vol.Optional("puissances_max_kva", default=list): vol.All(cv.ensure_list, [vol.Any(None, vol.Coerce(float))]),
        vol.Optional("mesure_fine", default=False): cv.boolean,
        # Batterie : pour estimer la recharge de nuit avec une offre à heures creuses.
        vol.Optional("capacite_utile_kwh"): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=0, max=200))),
        vol.Optional("rendement_pct", default=95): vol.All(vol.Coerce(float), vol.Range(min=50, max=100)),
        vol.Optional("recharge_deja_active", default=False): cv.boolean,
        # Tempo : couleur de chaque jour mesuré (jour de 6h à 6h) : {"2026-11-24": "blanc", …}.
        vol.Optional("couleurs_tempo", default=dict): vol.Schema({cv.date: vol.All(cv.string, vol.Lower, vol.In(tarifs.COULEURS))}),
    }
)
MODE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY): cv.string,
        vol.Required("mode"): vol.In(list(WORK_MODES)),
    }
)


def _entry(hass: HomeAssistant, call: ServiceCall) -> UcanessConfigEntry:
    entry_id = call.data.get(ATTR_ENTRY)
    entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.state is ConfigEntryState.LOADED and (entry_id is None or e.entry_id == entry_id)
    ]
    if len(entries) != 1:
        raise ServiceValidationError("Appareil UCANESS introuvable ou ambigu (préciser config_entry_id)")
    return entries[0]


def _coordinator(hass: HomeAssistant, entry: UcanessConfigEntry) -> UcanessCoordinator:
    return entry.runtime_data


def _require_write(entry: UcanessConfigEntry) -> None:
    if not entry.options.get(CONF_WRITE_ENABLED, False):
        raise ServiceValidationError(
            "Écriture vers l'onduleur désactivée (option « Écriture autorisée » de l'intégration UCANESS)"
        )


async def _write_and_verify(
    hass: HomeAssistant, entry: UcanessConfigEntry, items: dict[int, int], label: str
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

    async def optimiser_charge(call: ServiceCall) -> ServiceResponse:
        """Calcul seul : rien n'est envoyé à l'onduleur. Repli sûr si une donnée manque."""
        d = call.data
        fuseau = dt_util.get_default_time_zone()
        maintenant = dt_util.now()
        cap_brute = d["capacite_kwh"]
        plancher = d["plancher_pct"]
        cap = cap_brute * (1 - plancher / 100)
        stock = max(0.0, (d["soc_pct"] - plancher) / 100 * cap_brute)
        reserves = []
        r = d.get("reserve")
        try:
            if r:
                debut = dt_util.parse_datetime(r["debut"])
                fin = dt_util.parse_datetime(r["fin"])
                if debut and fin and fin > maintenant:
                    niveau = max(0.0, (r["soc_pct"] - plancher) / 100 * cap_brute)
                    reserves.append(optimiseur.Reserve(debut, fin, min(niveau, cap)))
            creneaux = optimiseur.construire_creneaux(
                d["prix"], d["conso"], d["solaire"], maintenant=maintenant, fuseau=fuseau,
                prix_vente=d["prix_revente"], marge=d["marge_pct"] / 100,
            )
            batterie = optimiseur.Batterie(cap, stock, d["rendement_pct"] / 100, d["puissance_charge_kw"])
            plan = await hass.async_add_executor_job(
                lambda: optimiseur.optimiser(
                    creneaux, batterie, fuseau=fuseau, max_plages=d["max_plages"],
                    charge_interdite=d["charge_interdite"], reserves=reserves,
                    valeur_stock_eur_kwh=d.get("valeur_stock_eur_kwh"), seuil_gain_eur=d["seuil_gain_eur"],
                )
            )
        except (optimiseur.DonneesManquantes, ValueError, TypeError) as err:
            return {"valide": False, "plages": [], "nombre_plages": 0, "charge_en_cours": False,
                    "justification": f"{err} : pas de charge réseau (repli sûr)."}
        return {"valide": True, "calcule_le": maintenant.isoformat(), **plan.resume(maintenant)}

    async def plages_depuis_plan(call: ServiceCall) -> ServiceResponse:
        """Calcul seul : plan externe (EMHASS) -> 3 plages de charge au plus."""
        try:
            r = optimiseur.plages_depuis_plan(
                call.data["plan"], maintenant=dt_util.now(), fuseau=dt_util.get_default_time_zone(),
                seuil_kw=call.data["seuil_kw"], max_plages=call.data["max_plages"],
            )
        except (ValueError, TypeError) as err:
            return {"valide": False, "plages": [], "justification": f"Plan illisible ({err}) : pas de charge réseau."}
        return {"valide": True, **r}

    def _offre(d: dict[str, Any]) -> tarifs.Offre:
        def hhmm(v: str) -> str:
            v = v.replace(":", "")
            return f"{v[:2]}:{v[2:]}"

        return tarifs.Offre(
            nom=d["nom"], fournisseur=d["fournisseur"], formule=d["formule"],
            abonnement_eur_an=dict(d["abonnement_eur_an"]), prix_kwh=dict(d["prix_kwh"]),
            plages_hc=tuple((hhmm(p["debut"]), hhmm(p["fin"])) for p in d["plages_hc"]),
            weekend_hc=d["weekend_hc"], source=d["source"], date_prix=d.get("date_prix"),
            jours_tempo=dict(d["jours_tempo"]) if d.get("jours_tempo") else None,
        )

    async def evaluer_offres(call: ServiceCall) -> ServiceResponse:
        """Calcul seul : coût annuel estimé de chaque offre sur le soutirage mesuré, classement par
        coût, avis sur la puissance souscrite. Rien n'est souscrit, rien n'est envoyé."""
        d = call.data
        fuseau = dt_util.get_default_time_zone()
        mesures = []
        for m in d["soutirage"]:
            debut = dt_util.parse_datetime(str(m.get("debut")))
            if debut is None:
                continue
            if debut.tzinfo is None:
                debut = debut.replace(tzinfo=fuseau)
            try:
                kwh = float(m.get("kwh"))
            except (TypeError, ValueError):
                kwh = None
            mesures.append((debut.astimezone(fuseau), kwh))
        actuel = d.get("contrat_actuel")
        resultat = await hass.async_add_executor_job(
            lambda: tarifs.classer(
                [_offre(o) for o in d["offres"]], mesures, d["puissance_kva"],
                contrat_actuel=_offre(actuel) if actuel else None,
                jours_non_ouvres=d["jours_non_ouvres"], aujourdhui=dt_util.now().date(),
                batterie=tarifs.Batterie(d["capacite_utile_kwh"], d["rendement_pct"] / 100) if d.get("capacite_utile_kwh") else None,
                recharge_deja_active=d["recharge_deja_active"],
                couleurs_tempo=dict(d["couleurs_tempo"]),
            )
        )
        resultat["puissance"] = tarifs.analyser_puissance(
            d["puissances_max_kva"], d["puissance_kva"], mesure_fine=d["mesure_fine"]
        )
        return resultat

    hass.services.async_register(
        DOMAIN, SERVICE_OFFRES, evaluer_offres, schema=OFFRES_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, SERVICE_OPTIMISER, optimiser_charge, schema=OPTIMISER_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, SERVICE_PLAN, plages_depuis_plan, schema=PLAN_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TEST, tester_api, schema=TEST_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, SERVICE_WINDOWS, definir_plages_charge, schema=WINDOWS_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MODE, definir_mode, schema=MODE_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
