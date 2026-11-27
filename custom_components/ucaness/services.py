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
from datetime import timedelta
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
from . import catalogue, optimiseur, reglages, tarifs

_LOGGER = logging.getLogger(__name__)

SERVICE_TEST = "tester_api"
SERVICE_WINDOWS = "definir_plages_charge"
SERVICE_MODE = "definir_mode"
SERVICE_OPTIMISER = "optimiser_charge"
SERVICE_PLAN = "plages_depuis_plan"
SERVICE_OFFRES = "evaluer_offres"
SERVICE_SIMULER = "simuler"

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
        # Abonnement annuel TTC par puissance souscrite : {"6": 150.0, "9": 190.0} (ou {"3.45": 70.0}).
        vol.Required("abonnement_eur_an"): vol.Schema({vol.Coerce(float): vol.All(vol.Coerce(float), vol.Range(min=0))}),
        vol.Required("prix_kwh"): vol.Schema({cv.string: PRIX}),
        vol.Optional("plages_hc", default=list): vol.All(cv.ensure_list, [WINDOW]),
        vol.Optional("weekend_hc", default=False): cv.boolean,
        vol.Optional("source", default=""): cv.string,
        vol.Optional("date_prix"): vol.Any(None, cv.date),
        # Tempo : jours de chaque couleur dans l'année (300 bleus, 43 blancs, 22 rouges par défaut).
        vol.Optional("jours_tempo"): vol.Any(None, vol.Schema({vol.In(tarifs.COULEURS): vol.All(vol.Coerce(int), vol.Range(min=0, max=366))})),
        # Formule « plages » (autres pays) : grille horaire du catalogue, prix par niveau (prix_kwh).
        vol.Optional("structure"): vol.In(list(catalogue.STRUCTURES)),
        vol.Optional("taxes_comprises", default=True): cv.boolean,
    }
)
OFFRES_SCHEMA = vol.Schema(
    {
        vol.Required("offres"): vol.All(cv.ensure_list, [OFFRE]),
        vol.Optional("contrat_actuel"): vol.Any(None, OFFRE),
        vol.Required("soutirage"): vol.All(cv.ensure_list, [dict]),
        vol.Required("puissance_kva"): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=50)),
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


SIMULER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY): cv.string,
        vol.Required("question"): vol.In(["contrat", "puissance"]),
        vol.Optional("jours", default=30): vol.All(vol.Coerce(int), vol.Range(min=1, max=400)),
        vol.Optional("puissance_actuelle_kva"): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=0.5, max=50))),
        vol.Optional("abonnement_actuel_eur_an"): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=0))),
        vol.Optional("offres"): vol.All(cv.ensure_list, [dict]),
        vol.Optional("soutirage", default="sensor.uhome_soutirage_reseau_total"): cv.entity_id,
        vol.Optional("puissance_reseau", default="sensor.uhome_puissance_reseau"): cv.entity_id,
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
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="appareil_introuvable")
    return entries[0]


def _coordinator(hass: HomeAssistant, entry: UcanessConfigEntry) -> UcanessCoordinator:
    return entry.runtime_data


def _require_write(entry: UcanessConfigEntry) -> None:
    if not entry.options.get(CONF_WRITE_ENABLED, False):
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="ecriture_desactivee")


async def _write_and_verify(
    hass: HomeAssistant, entry: UcanessConfigEntry, items: dict[int, int], sujet: str, valeur: str
) -> dict[str, Any]:
    """Envoie, relit et confirme. `sujet` : « plages » ou « mode » (choisit les messages d'erreur traduits)."""
    label = f"{'plages de charge' if sujet == 'plages' else 'mode'} {valeur}"     # journal (en français)
    ph = {"plages" if sujet == "plages" else "mode": valeur}
    suffixe = {"plages": ("plages_non_envoyees", "plages_non_confirmees", "plages_relecture_impossible"),
               "mode": ("mode_non_envoye", "mode_non_confirme", "mode_relecture_impossible")}[sujet]
    coordinator = _coordinator(hass, entry)
    code = entry.data[CONF_DEVICE_CODE]
    mode_before = _telemetry_mode(coordinator)
    try:
        sent = await coordinator.client.update_settings(code, items)
    except UcanessWriteRefused as err:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="consigne_refusee", translation_placeholders={"detail": str(err)}) from err
    except UcanessError as err:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key=suffixe[0], translation_placeholders={**ph, "detail": str(err)}) from err

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
        if mismatch:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key=suffixe[1], translation_placeholders={**ph, "ecarts": str(mismatch)})
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key=suffixe[2], translation_placeholders=ph)
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
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="donnees_refusees", translation_placeholders={"detail": str(err)}) from err
        except UcanessError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="api_tierce", translation_placeholders={"detail": str(err)}) from err
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
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="donnees_refusees", translation_placeholders={"detail": str(err)}) from err
        return await _write_and_verify(hass, entry, items, "plages", str(windows))

    async def definir_mode(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass, call)
        _require_write(entry)
        mode = call.data["mode"]
        return await _write_and_verify(hass, entry, {SET_WORK_MODE: WORK_MODES[mode]}, "mode", str(mode))

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

        if d["formule"] == tarifs.PLAGES:
            if not d.get("structure"):
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="donnees_refusees",
                                             translation_placeholders={"detail": f"{d['nom']} : formule plages sans structure"})
            return catalogue.offre_plages(
                d["nom"], d["structure"], dict(d["abonnement_eur_an"]), dict(d["prix_kwh"]),
                fournisseur=d["fournisseur"], source=d["source"], date_prix=d.get("date_prix"),
                taxes_comprises=d["taxes_comprises"],
            )
        return tarifs.Offre(
            nom=d["nom"], fournisseur=d["fournisseur"], formule=d["formule"],
            abonnement_eur_an=dict(d["abonnement_eur_an"]), prix_kwh=dict(d["prix_kwh"]),
            plages_hc=tuple((hhmm(p["debut"]), hhmm(p["fin"])) for p in d["plages_hc"]),
            weekend_hc=d["weekend_hc"], source=d["source"], date_prix=d.get("date_prix"),
            jours_tempo=dict(d["jours_tempo"]) if d.get("jours_tempo") else None,
            taxes_comprises=d["taxes_comprises"],
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

    async def _statistiques(entite: str, jours: int, type_: str) -> list[tuple[Any, float | None]]:
        """Statistiques horaires de l'enregistreur (« change » ou « max ») des derniers jours."""
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import statistics_during_period

        fin = dt_util.now().replace(minute=0, second=0, microsecond=0)
        debut = fin - timedelta(days=jours)
        lignes = await get_instance(hass).async_add_executor_job(
            statistics_during_period, hass, debut, fin, {entite}, "hour", None, {type_}
        )
        fuseau = dt_util.get_default_time_zone()
        out = []
        for r in lignes.get(entite, []):
            debut_h = r.get("start")
            if isinstance(debut_h, (int, float)):
                debut_h = dt_util.utc_from_timestamp(debut_h)
            out.append((debut_h.astimezone(fuseau), r.get(type_)))
        return out

    async def simuler(call: ServiceCall) -> ServiceResponse:
        """Simulateur « et si » : calcul seul sur les mesures de la maison, rien n'est appliqué.

        contrat : coût annuel estimé du contrat actuel (réglages du tarif) et des offres de référence
        (catalogue.py) ou passées, sur le soutirage horaire des derniers jours ;
        puissance : la puissance souscrite convient-elle, d'après la puissance maximale prise au
        réseau chaque jour (relevée par l'onduleur, donc estimée)."""
        d = call.data
        entry = _entry(hass, call)
        pays = (hass.config.country or "FR").upper()
        kva = d.get("puissance_actuelle_kva")
        if d["question"] == "puissance":
            if not kva:
                raise ServiceValidationError(translation_domain=DOMAIN, translation_key="puissance_actuelle_manquante")
            maxi = await _statistiques(d["puissance_reseau"], d["jours"], "max")
            par_jour: dict[Any, float] = {}
            for debut_h, w in maxi:
                if isinstance(w, (int, float)):
                    par_jour[debut_h.date()] = max(par_jour.get(debut_h.date(), 0.0), w / 1000)
            r = tarifs.analyser_puissance(list(par_jour.values()), kva, paliers=catalogue.paliers(pays))
            return {"question": "puissance", "pays": pays, **r}
        valeur = lambda cle: reglages.valeur(hass, entry, cle)  # noqa: E731
        hc_d, hc_f = valeur("hc_debut"), valeur("hc_fin")
        actuel = None
        if kva and d.get("abonnement_actuel_eur_an") is not None and valeur("prix_hp"):
            base = valeur("type_tarif") == reglages.TARIF_BASE
            actuel = tarifs.Offre(
                "Contrat actuel", tarifs.BASE if base else tarifs.HPHC, {kva: d["abonnement_actuel_eur_an"]},
                {"base": valeur("prix_hp")} if base else {"hp": valeur("prix_hp"), "hc": valeur("prix_hc") or 0},
                plages_hc=() if base or not (hc_d and hc_f) else ((str(hc_d)[:5], str(hc_f)[:5]),),
                weekend_hc=bool(valeur("hc_jours_non_ouvres")) and not base,
                source="Réglages du tarif dans Home Assistant", date_prix=dt_util.now().date(),
            )
        offres = [_offre(OFFRE(o)) for o in d["offres"]] if d.get("offres") else list(catalogue.offres_reference(pays))
        cible = kva or catalogue.puissance_defaut(pays)
        ramenees = [tarifs.a_la_puissance(o, cible)[0] for o in offres]
        mesures = [(h, k) for h, k in await _statistiques(d["soutirage"], d["jours"], "change") if k is not None]
        if not mesures:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="aucune_mesure_horaire", translation_placeholders={"entite": str(d["soutirage"]), "jours": str(d["jours"])})
        simulation = hass.states.get("input_boolean.jarvis_mode_simulation")
        resultat = await hass.async_add_executor_job(
            lambda: tarifs.classer(
                ramenees, mesures, cible, contrat_actuel=actuel,
                aujourdhui=dt_util.now().date(),
                recharge_deja_active=simulation is None or simulation.state == "off",
            )
        )
        resultat["question"] = "contrat"
        resultat["pays"] = pays
        resultat["puissance_kva"] = cible
        if not offres:
            resultat["limites"].insert(0, catalogue.POURQUOI_SANS_OFFRE.get(
                pays, f"Pas d'offre de référence pour ce pays ({pays}) : passez vos offres (champ « offres »)."))
        resultat["jours_demandes"] = d["jours"]
        if actuel is None:
            resultat["limites"].append("Contrat actuel non comparé : indiquez la puissance souscrite et l'abonnement annuel.")
        return resultat

    hass.services.async_register(
        DOMAIN, SERVICE_SIMULER, simuler, schema=SIMULER_SCHEMA, supports_response=SupportsResponse.ONLY
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
