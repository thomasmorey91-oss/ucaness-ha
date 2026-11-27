"""Assistant d'installation, côté Home Assistant.

Construit l'instantané de l'installation, le fait évaluer par installation.py et signale l'étape
suivante dans Paramètres > Système > Réparations (une seule à la fois).

Lecture seule : aucun réglage n'est modifié, rien n'est envoyé à l'onduleur, aucune autre
intégration n'est installée ni configurée. L'utilisateur clique et saisit lui-même.
"""
from __future__ import annotations

from typing import Any

from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from . import installation, reglages
from .const import (
    CONF_WRITE_ENABLED,
    DOMAIN,
    ENTITES_PILOTAGE,
)
from .cle_application import cle_effective
from .coordinator import UcanessConfigEntry

# Entrées des packages de pilotage (pilotage/packages/*.yaml).
E_SIMULATION = "input_boolean.jarvis_mode_simulation"
# Étapes qui se règlent par un court dialogue dans la réparation elle-même (repairs.py).
ETAPES_A_QUESTIONS = ("batterie", "solaire", "contrat")
E_NOTIFICATION = "input_text.jarvis_service_notification"
E_JOURS_OUVRES = "binary_sensor.workday_sensor"
E_PREVISIONS = (
    "sensor.solcast_pv_forecast_prevision_aujourdhui",
    "sensor.solcast_pv_forecast_prevision_demain",
)
INCONNU = (None, "", "unknown", "unavailable")


def _etat(hass: HomeAssistant, entite: str) -> str | None:
    """État de l'entité, ou None si elle est absente, inconnue ou indisponible."""
    etat = hass.states.get(entite)
    return None if etat is None or etat.state in INCONNU else etat.state


def construire_contexte(hass: HomeAssistant, entry: UcanessConfigEntry) -> dict[str, Any]:
    """Instantané de l'installation, lu dans Home Assistant (aucune écriture)."""
    coordinator = entry.runtime_data
    simulation = _etat(hass, E_SIMULATION)
    notification = _etat(hass, E_NOTIFICATION)
    options = entry.options
    # Panneaux solaires : la réponse de l'utilisateur fait foi ; à défaut, une production déjà
    # mesurée par l'onduleur suffit à le savoir. Sinon la question est posée.
    solaire = reglages.valeur(hass, entry, "solaire")
    if solaire is None:
        produit = ((coordinator.data or {}).get("values") or {}).get("energy_solar_total")
        solaire = True if (produit or 0) > 0 else None
    return {
        "solaire": solaire,
        "connexion": bool(coordinator.last_update_success and coordinator.data),
        "packages": hass.states.get(E_SIMULATION) is not None,
        "entites_manquantes": [e for e in ENTITES_PILOTAGE if hass.states.get(e) is None],
        "capacite_kwh": reglages.valeur(hass, entry, "capacite"),
        "type_tarif": reglages.valeur(hass, entry, "type_tarif"),
        "prix_hp": reglages.valeur(hass, entry, "prix_hp"),
        "prix_hc": reglages.valeur(hass, entry, "prix_hc"),
        "jours_ouvres": hass.states.get(E_JOURS_OUVRES) is not None,
        # Une prévision compte si elle porte des valeurs heure par heure (attribut detailedHourly).
        "prevision_solaire": any(
            (hass.states.get(e) is not None and hass.states.get(e).attributes.get("detailedHourly"))
            for e in E_PREVISIONS
        ),
        "notification": bool(notification) and hass.services.has_service("notify", notification),
        # True = simulation, False = mode réel, None = inconnu (jamais pris pour le mode réel).
        "simulation": None if simulation is None else simulation == "on",
        "ecriture": bool(
            options.get(CONF_WRITE_ENABLED) and cle_effective(options)[2]
        ),
    }


def bilan(hass: HomeAssistant, entry: UcanessConfigEntry) -> installation.Bilan:
    return installation.evaluer(construire_contexte(hass, entry))


def _issue_id(entry: UcanessConfigEntry, cle: str) -> str:
    return f"etape_{cle}_{entry.entry_id}"


@callback
def signaler_etape_suivante(hass: HomeAssistant, entry: UcanessConfigEntry) -> installation.Bilan:
    """Une réparation pour l'étape suivante, aucune pour les autres.

    Tant que Home Assistant démarre, les autres intégrations ne sont pas toutes chargées : on ne
    signale rien (une étape paraîtrait manquer à tort).
    """
    b = bilan(hass, entry)
    if hass.state is not CoreState.running:
        return b
    suivante = b.suivante
    for cle in installation.CLES:
        if suivante is None or cle != suivante.cle:
            ir.async_delete_issue(hass, DOMAIN, _issue_id(entry, cle))
    if suivante is not None:
        ir.async_create_issue(
            hass, DOMAIN, _issue_id(entry, suivante.cle),
            is_fixable=suivante.cle in ETAPES_A_QUESTIONS,
            is_persistent=False,
            data={"cle": suivante.cle, "entry_id": entry.entry_id},
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"etape_{suivante.cle}",
            translation_placeholders={
                "appareil": entry.title,
                "lien": suivante.lien or "",
                "entites": ", ".join(b.entites_manquantes) or "-",
            },
        )
    return b


@callback
def retirer_les_signalements(hass: HomeAssistant, entry: UcanessConfigEntry) -> None:
    for cle in installation.CLES:
        ir.async_delete_issue(hass, DOMAIN, _issue_id(entry, cle))
