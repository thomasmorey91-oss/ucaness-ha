"""Véhicule électrique, côté Home Assistant : réglage enregistré dans les options, plan de recharge,
image du véhicule.

Calcul seul : rien n'est envoyé à la borne ni à l'onduleur (vehicules.py).
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from . import reglages, vehicules
from .const import DOMAIN

CONF_VEHICULE = "vehicule"
SERVICE_PLAN = "planifier_recharge_vehicule"
SERVICE_IMAGE = "definir_image_vehicule"
ATTR_ENTRY = "config_entry_id"

DEFAUTS = {"soc_cible": 80.0, "puissance_borne_kw": 7.4, "couleur": "#4A90D9"}
DEPART_PAR_DEFAUT = time(7, 30)
HORIZON_MAX = timedelta(days=7)        # au-delà, ni prix ni prévision solaire ne sont connus
PREVISIONS = ("sensor.solcast_pv_forecast_prevision_aujourdhui", "sensor.solcast_pv_forecast_prevision_demain")
JOURS_OUVRES = "binary_sensor.workday_sensor"
INCONNU = (None, "", "unknown", "unavailable")
# Images acceptées : celles servies par Home Assistant lui-même (téléversement ou dossier www).
PREFIXES_IMAGE = ("/api/image/serve/", "/local/")

PLAN_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY): cv.string,
        vol.Optional("soc_actuel"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        vol.Optional("soc_cible"): vol.All(vol.Coerce(float), vol.Range(min=1, max=100)),
        vol.Optional("depart"): cv.datetime,
        vol.Optional("puissance_borne_kw"): vol.All(vol.Coerce(float), vol.Range(min=1, max=22)),
    }
)
IMAGE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTRY): cv.string, vol.Required("image"): cv.string})


def config(entry) -> dict[str, Any] | None:
    return entry.options.get(CONF_VEHICULE) or None


def couleur_hex(rgb: Any) -> str:
    """[r, g, b] (sélecteur de couleur) ou « #rrggbb » -> « #rrggbb »."""
    if isinstance(rgb, str) and len(rgb) == 7 and rgb.startswith("#"):
        return rgb.lower()
    try:
        r, g, b = (max(0, min(255, int(x))) for x in rgb)
    except (TypeError, ValueError):
        return DEFAUTS["couleur"]
    return f"#{r:02x}{g:02x}{b:02x}"


def couleur_rgb(hexa: str) -> list[int]:
    h = couleur_hex(hexa).lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def image_valide(image: str) -> bool:
    return isinstance(image, str) and image.startswith(PREFIXES_IMAGE) and ".." not in image and "://" not in image


def soc_mesure(hass: HomeAssistant, cfg: dict[str, Any]) -> float | None:
    entite = cfg.get("entite_soc")
    etat = hass.states.get(entite) if entite else None
    if etat is None or etat.state in INCONNU:
        return None
    try:
        return max(0.0, min(100.0, float(etat.state)))
    except ValueError:
        return None


def _surplus(hass: HomeAssistant, entry) -> Any:
    """kW de surplus solaire prévu pour une heure : prévision Solcast − consommation moyenne de la maison."""
    par_heure: dict[datetime, float] = {}
    for entite in PREVISIONS:
        etat = hass.states.get(entite)
        for p in (etat.attributes.get("detailedHourly") or []) if etat else []:
            debut = p.get("period_start")
            debut = dt_util.parse_datetime(debut) if isinstance(debut, str) else debut
            if isinstance(debut, datetime):
                par_heure[dt_util.as_local(debut).replace(minute=0, second=0, microsecond=0)] = float(p.get("pv_estimate") or 0)
    conso = reglages.valeur(hass, entry, "conso_journaliere")
    conso_kw = float(conso) / 24 if conso else 0.5

    def surplus(moment: datetime) -> float:
        cle = dt_util.as_local(moment).replace(minute=0, second=0, microsecond=0)
        return par_heure.get(cle, 0.0) - conso_kw

    return surplus, bool(par_heure)


def _prix(hass: HomeAssistant, entry) -> Any:
    v = {cle: reglages.valeur(hass, entry, cle) for cle in ("prix_hp", "prix_hc", "hc_debut", "hc_fin", "hc_jours_non_ouvres", "type_tarif")}
    base = v["type_tarif"] == reglages.TARIF_BASE
    if v["prix_hp"] is None or (not base and (v["prix_hc"] is None or v["hc_debut"] is None or v["hc_fin"] is None)):
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="vehicule_tarif_inconnu")
    debut, fin = (time.fromisoformat(v[c]) for c in ("hc_debut", "hc_fin")) if not base else (time(0), time(0))
    aujourdhui_non_ouvre = (hass.states.get(JOURS_OUVRES) is not None and hass.states.get(JOURS_OUVRES).state == "off")
    jours_hc = bool(v["hc_jours_non_ouvres"])

    def prix(moment: datetime) -> tuple[float, bool]:
        p, creuse = vehicules.prix_heure(moment, prix_hp=v["prix_hp"], prix_hc=v["prix_hc"] or v["prix_hp"],
                                         hc_debut=debut, hc_fin=fin, jours_non_ouvres_hc=jours_hc, type_tarif_base=base)
        if not base and jours_hc and aujourdhui_non_ouvre and moment.date() == dt_util.now().date():
            return v["prix_hc"], True
        return p, creuse

    return prix


def _entree(hass: HomeAssistant, call: ServiceCall):
    entry_id = call.data.get(ATTR_ENTRY)
    entries = [e for e in hass.config_entries.async_entries(DOMAIN)
               if e.state is ConfigEntryState.LOADED and (entry_id is None or e.entry_id == entry_id)]
    if len(entries) != 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="appareil_introuvable")
    return entries[0]


def prochain_depart(maintenant: datetime, heure: time = DEPART_PAR_DEFAUT) -> datetime:
    depart = maintenant.replace(hour=heure.hour, minute=heure.minute, second=0, microsecond=0)
    return depart if depart > maintenant else depart + timedelta(days=1)


async def async_setup_services(hass: HomeAssistant) -> None:
    async def planifier(call: ServiceCall) -> ServiceResponse:
        """Calcul seul : quand recharger la voiture avant le départ, au moindre coût."""
        entry = _entree(hass, call)
        cfg = config(entry)
        if not cfg:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="vehicule_absent")
        d = call.data
        soc = d.get("soc_actuel")
        source_soc = "saisi"
        if soc is None:
            soc, source_soc = soc_mesure(hass, cfg), "vehicule"
        if soc is None:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="vehicule_soc_inconnu")
        cible = float(d.get("soc_cible") or cfg.get("soc_cible") or DEFAUTS["soc_cible"])
        maintenant = dt_util.now()
        depart = d.get("depart")
        depart = dt_util.as_local(depart if depart.tzinfo else depart.replace(tzinfo=dt_util.get_default_time_zone())) if depart else prochain_depart(maintenant)
        if not maintenant < depart <= maintenant + HORIZON_MAX:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="vehicule_depart_invalide")
        borne = float(d.get("puissance_borne_kw") or cfg.get("puissance_borne_kw") or DEFAUTS["puissance_borne_kw"])
        puissance = vehicules.puissance_recharge_kw(float(cfg["ac_kw"]), borne)
        energie = vehicules.energie_a_prendre_kwh(float(cfg["capacite_kwh"]), float(soc), cible)
        prix = _prix(hass, entry)
        surplus, prevision = _surplus(hass, entry)
        prix_solaire = reglages.valeur(hass, entry, "prix_injection") or 0.0
        creneaux = vehicules.creneaux_horaires(maintenant, depart, prix, surplus)
        plan = vehicules.plan_recharge(energie, puissance, creneaux, depart, prix_solaire=float(prix_solaire))
        return {
            "vehicule": cfg.get("nom"),
            "soc_actuel": round(float(soc), 1),
            "source_soc": source_soc,
            "soc_cible": cible,
            "depart": depart.isoformat(),
            "prevision_solaire": prevision,
            "a_blanc": True,
            **plan.en_dict(),
        }

    async def definir_image(call: ServiceCall) -> None:
        entry = _entree(hass, call)
        cfg = config(entry)
        if not cfg:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="vehicule_absent")
        image = call.data["image"].strip()
        if image and not image_valide(image):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="vehicule_image_invalide")
        hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_VEHICULE: {**cfg, "image": image}})

    hass.services.async_register(DOMAIN, SERVICE_PLAN, planifier, schema=PLAN_SCHEMA, supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, SERVICE_IMAGE, definir_image, schema=IMAGE_SCHEMA)
