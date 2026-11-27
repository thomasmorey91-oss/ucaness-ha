"""Réglages du pilotage portés par l'intégration (option « réglages dans l'intégration », pas b1).

Chaque réglage est une entité de l'intégration (number, select, time, switch), enregistrée dans
les options de l'entrée de configuration. Tant que les packages de pilotage lisent leurs propres
entrées (`input_*.jarvis_*`), l'entrée du package reste la référence :
- lecture : valeur de l'entrée du package si elle existe, sinon valeur enregistrée ici ;
- écriture : valeur enregistrée ici ET recopiée dans l'entrée du package si elle existe.
Il n'y a donc qu'une seule valeur par réglage, où qu'on la modifie. Le calcul du pilotage n'est
pas touché : il lit les mêmes entrées qu'avant.

Rien ici n'écrit sur l'onduleur.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import translation

from .const import DOMAIN
from .coordinator import UcanessConfigEntry

CONF_REGLAGES = "reglages"

NUMBER, SELECT, TIME, SWITCH = "number", "select", "time", "switch"
TARIF_HPHC = "Heures pleines / heures creuses"
TARIF_BASE = "Base"
INCONNU = (None, "", "unknown", "unavailable")


@dataclass(frozen=True)
class Reglage:
    cle: str                        # aussi clé de traduction (translations/*.json, entity.<type>)
    type: str                       # number, select, time, switch
    entree: str                     # entrée du package de pilotage (référence tant qu'elle existe)
    unite: str | None = None
    mini: float | None = None
    maxi: float | None = None
    pas: float | None = None
    options: tuple[str, ...] = ()      # valeurs des entrées du package (textes en français)
    cles_options: tuple[str, ...] = ()  # clés de traduction des options, dans le même ordre (états de l'entité)
    icone: str | None = None
    # Réglage oui / non dont l'entrée du package est une liste de choix : (choix « oui », choix « non »).
    # Tout autre choix de la liste (détection automatique) laisse la valeur enregistrée ici.
    choix_oui_non: tuple[str, str] | None = None


REGLAGES: tuple[Reglage, ...] = (
    # Batterie (bornes de pilotage/packages/jarvis_batterie.yaml)
    Reglage("capacite", NUMBER, "input_number.jarvis_batterie_capacite", "kWh", 0, 40, 0.01, icone="mdi:battery"),
    Reglage("plancher", NUMBER, "input_number.jarvis_batterie_plancher", "%", 0, 60, 1, icone="mdi:battery-low"),
    Reglage("rendement", NUMBER, "input_number.jarvis_batterie_rendement", "%", 0, 100, 0.5, icone="mdi:percent"),
    Reglage("puissance_charge", NUMBER, "input_number.jarvis_batterie_puissance_charge", "kW", 0.5, 10, 0.1, icone="mdi:flash"),
    Reglage("marge", NUMBER, "input_number.jarvis_batterie_marge", "%", 0, 50, 1, icone="mdi:shield-half-full"),
    Reglage("conso_journaliere", NUMBER, "input_number.jarvis_conso_journaliere", "kWh", 0, 200, 0.1, icone="mdi:home-lightning-bolt"),
    # Installation (pilotage/packages/jarvis_batterie.yaml : « Batterie : panneaux solaires »)
    Reglage("solaire", SWITCH, "input_select.jarvis_solaire",
            icone="mdi:solar-power", choix_oui_non=("Avec panneaux", "Sans panneaux")),
    # Contrat (pilotage/packages/jarvis_tarif.yaml)
    Reglage("type_tarif", SELECT, "input_select.jarvis_type_tarif", options=(TARIF_HPHC, TARIF_BASE), cles_options=("hphc", "base"), icone="mdi:cash-clock"),
    Reglage("prix_hp", NUMBER, "input_number.jarvis_prix_hp", "EUR/kWh", 0, 1, 0.00001, icone="mdi:currency-eur"),
    Reglage("prix_hc", NUMBER, "input_number.jarvis_prix_hc", "EUR/kWh", 0, 1, 0.00001, icone="mdi:currency-eur"),
    Reglage("prix_injection", NUMBER, "input_number.jarvis_prix_injection", "EUR/kWh", 0, 1, 0.00001, icone="mdi:currency-eur"),
    Reglage("hc_debut", TIME, "input_datetime.jarvis_hc_debut", icone="mdi:clock-start"),
    Reglage("hc_fin", TIME, "input_datetime.jarvis_hc_fin", icone="mdi:clock-end"),
    Reglage("hc_jours_non_ouvres", SWITCH, "input_boolean.jarvis_hc_jours_non_ouvres", icone="mdi:calendar-weekend"),
)
PAR_CLE = {r.cle: r for r in REGLAGES}


def _heure(valeur: Any) -> str:
    """« HH:MM » ou « HH:MM:SS » -> « HH:MM:SS »."""
    morceaux = str(valeur).split(":")
    if len(morceaux) not in (2, 3):
        raise ValueError(valeur)
    h, m, s = (int(x) for x in (morceaux + ["0"])[:3])
    if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60):
        raise ValueError(valeur)
    return f"{h:02d}:{m:02d}:{s:02d}"


class ReglageInvalide(ValueError):
    """Valeur refusée pour un réglage. `raison` est la clé de traduction du message (exceptions.*)."""

    def __init__(self, reglage: Reglage, raison: str, valeur: Any) -> None:
        super().__init__(f"{reglage.cle} : {valeur} ({raison})")
        self.reglage, self.raison, self.valeur = reglage, raison, valeur

    def placeholders(self, nom: str) -> dict[str, str]:
        return {"reglage": nom, "valeur": str(self.valeur), "mini": f"{self.reglage.mini:g}" if self.reglage.mini is not None else "",
                "maxi": f"{self.reglage.maxi:g}" if self.reglage.maxi is not None else ""}


def normaliser(reglage: Reglage, valeur: Any) -> Any:
    """Valeur vérifiée et mise au format enregistré. ReglageInvalide (ValueError) si elle n'est pas acceptable."""
    if reglage.type == NUMBER:
        try:
            v = float(valeur)
        except (TypeError, ValueError):
            raise ReglageInvalide(reglage, "reglage_hors_bornes", valeur) from None
        if v != v or not (reglage.mini <= v <= reglage.maxi):
            raise ReglageInvalide(reglage, "reglage_hors_bornes", valeur)
        return v
    if reglage.type == SELECT:
        if valeur not in reglage.options:
            raise ReglageInvalide(reglage, "reglage_choix_impossible", valeur)
        return valeur
    if reglage.type == TIME:
        try:
            return _heure(valeur)
        except (TypeError, ValueError):
            raise ReglageInvalide(reglage, "reglage_heure_invalide", valeur) from None
    if isinstance(valeur, bool):
        return valeur
    if valeur in ("on", "off"):
        return valeur == "on"
    raise ReglageInvalide(reglage, "reglage_ni_vrai_ni_faux", valeur)


def nom(hass: HomeAssistant, reglage: Reglage) -> str:
    """Nom du réglage dans la langue de Home Assistant (traductions déjà chargées), sinon sa clé."""
    cle = f"component.{DOMAIN}.entity.{reglage.type}.{reglage.cle}.name"
    for langue in (hass.config.language, "en"):
        texte = translation.async_get_cached_translations(hass, langue, "entity", DOMAIN).get(cle)
        if texte:
            return texte
    return reglage.cle


def valeur(hass: HomeAssistant, entry: UcanessConfigEntry, cle: str) -> Any:
    """Valeur du réglage : entrée du package si elle existe et se lit, sinon valeur enregistrée.

    None si le réglage n'a jamais été renseigné (une donnée absente reste absente)."""
    reglage = PAR_CLE[cle]
    etat = hass.states.get(reglage.entree) if reglage.entree else None
    if etat is not None and reglage.choix_oui_non:
        if etat.state in reglage.choix_oui_non:
            return etat.state == reglage.choix_oui_non[0]
    elif etat is not None and etat.state not in INCONNU:
        try:
            return normaliser(reglage, etat.state)
        except ValueError:
            pass
    return (entry.options.get(CONF_REGLAGES) or {}).get(cle)


async def async_definir(hass: HomeAssistant, entry: UcanessConfigEntry, valeurs: dict[str, Any]) -> None:
    """Enregistre un ou plusieurs réglages et les recopie dans les entrées du package présentes."""
    inconnus = [cle for cle in valeurs if cle not in PAR_CLE]
    if inconnus:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="reglage_inconnu", translation_placeholders={"reglage": ", ".join(inconnus)}
        )
    try:
        propres = {cle: normaliser(PAR_CLE[cle], v) for cle, v in valeurs.items()}
    except ReglageInvalide as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key=err.raison, translation_placeholders=err.placeholders(nom(hass, err.reglage))
        ) from err
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_REGLAGES: {**(entry.options.get(CONF_REGLAGES) or {}), **propres}}
    )
    for cle, v in propres.items():
        reglage = PAR_CLE[cle]
        if not reglage.entree or hass.states.get(reglage.entree) is None:
            continue
        cible = {"entity_id": reglage.entree}
        if reglage.choix_oui_non:
            choix = reglage.choix_oui_non[0 if v else 1]
            await hass.services.async_call("input_select", "select_option", {**cible, "option": choix}, blocking=True)
        elif reglage.type == NUMBER:
            await hass.services.async_call("input_number", "set_value", {**cible, "value": v}, blocking=True)
        elif reglage.type == SELECT:
            await hass.services.async_call("input_select", "select_option", {**cible, "option": v}, blocking=True)
        elif reglage.type == TIME:
            await hass.services.async_call("input_datetime", "set_datetime", {**cible, "time": v}, blocking=True)
        else:
            await hass.services.async_call("input_boolean", "turn_on" if v else "turn_off", cible, blocking=True)


def gain_cyclage_eur_kwh(prix_hp: float, prix_hc: float, rendement_pct: float) -> float:
    """Gain d'un kWh rechargé en heures creuses et rendu en heures pleines : rendement² × HP − HC."""
    r = rendement_pct / 100
    return r * r * prix_hp - prix_hc


__all__ = ["CONF_REGLAGES", "DOMAIN", "PAR_CLE", "REGLAGES", "Reglage", "ReglageInvalide", "async_definir", "gain_cyclage_eur_kwh", "nom", "normaliser", "valeur"]
