"""Écrans de questions de l'assistant d'installation (Paramètres > Système > Réparations).

Deux étapes se règlent ici, par un court dialogue : « Votre batterie » et « Votre contrat ».
Les réponses sont enregistrées comme réglages de l'intégration (reglages.py) et recopiées dans
les entrées du package de pilotage présentes. Rien n'est envoyé à l'onduleur.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from . import assistant, reglages
from .const import DOMAIN

# Gamme résidentielle UHome (monophasée 3 à 8 kW, triphasée UHome-KT 8 à 20 kW) : modules de
# 5,12 kWh, 2 à 8 modules (fiches techniques du constructeur). Simple proposition : l'utilisateur
# confirme ou corrige.
CAPACITE_MODULE_KWH = 5.12
DEFAUTS = {"plancher": 20.0, "puissance_charge": 3.0, "rendement": 95.0, "marge": 10.0,
           "type_tarif": reglages.TARIF_HPHC, "hc_debut": "22:30:00", "hc_fin": "06:30:00",
           "hc_jours_non_ouvres": False, "prix_injection": 0.0}


def _nombre(cle: str) -> selector.NumberSelector:
    r = reglages.PAR_CLE[cle]
    return selector.NumberSelector(selector.NumberSelectorConfig(
        min=r.mini, max=r.maxi, step=r.pas if r.pas >= 0.001 else "any",   # le sélecteur refuse un pas sous 0,001
        unit_of_measurement=r.unite, mode=selector.NumberSelectorMode.BOX))


class _Etape(RepairsFlow):
    """Base : accès à l'entrée de configuration et aux valeurs déjà connues."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id

    @property
    def _entry(self):
        return self.hass.config_entries.async_get_entry(self._entry_id)

    def _connu(self, cle: str) -> Any:
        v = reglages.valeur(self.hass, self._entry, cle)
        return DEFAUTS.get(cle) if v is None else v

    def _champ(self, cle: str, obligatoire: bool = True, propose: Any = None) -> vol.Marker:
        valeur = self._connu(cle) if propose is None else propose
        cls = vol.Required if obligatoire else vol.Optional
        return cls(cle, description={"suggested_value": valeur}) if valeur is not None else cls(cle)

    async def _enregistrer(self, valeurs: dict[str, Any]) -> None:
        await reglages.async_definir(self.hass, self._entry, valeurs)
        assistant.signaler_etape_suivante(self.hass, self._entry)


class EtapeBatterie(_Etape):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> data_entry_flow.FlowResult:
        if self._entry is None:
            return self.async_abort(reason="entree_absente")
        errors: dict[str, str] = {}
        if user_input is not None:
            if float(user_input["capacite"]) <= 0:
                errors["capacite"] = "capacite_nulle"
            else:
                await self._enregistrer(user_input)
                return self.async_create_entry(data={})
        modules = ((self._entry.runtime_data.data or {}).get("values") or {}).get("battery_modules")
        capacite = reglages.valeur(self.hass, self._entry, "capacite")
        propose = capacite if capacite else (round(float(modules) * CAPACITE_MODULE_KWH, 2) if modules else None)
        schema = vol.Schema({
            self._champ("capacite", propose=propose): _nombre("capacite"),
            self._champ("plancher"): _nombre("plancher"),
            self._champ("puissance_charge"): _nombre("puissance_charge"),
        })
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors,
            description_placeholders={"modules": str(int(modules)) if modules else "?",
                                      "proposition": f"{propose:g}" if propose else "?"},
        )


class EtapeContrat(_Etape):
    def __init__(self, entry_id: str) -> None:
        super().__init__(entry_id)
        self._reponses: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> data_entry_flow.FlowResult:
        if self._entry is None:
            return self.async_abort(reason="entree_absente")
        errors: dict[str, str] = {}
        if user_input is not None:
            base = user_input["type_tarif"] == reglages.TARIF_BASE
            if float(user_input["prix_hp"]) <= 0:
                errors["prix_hp"] = "prix_nul"
            elif not base and float(user_input.get("prix_hc") or 0) <= 0:
                errors["prix_hc"] = "prix_nul"
            else:
                self._reponses = {k: v for k, v in user_input.items() if v is not None}
                return await self.async_step_bilan()
        r = reglages.PAR_CLE["type_tarif"]
        schema = vol.Schema({
            self._champ("type_tarif"): selector.SelectSelector(selector.SelectSelectorConfig(options=list(r.options))),
            self._champ("prix_hp"): _nombre("prix_hp"),
            self._champ("prix_hc", obligatoire=False): _nombre("prix_hc"),
            self._champ("hc_debut", obligatoire=False): selector.TimeSelector(),
            self._champ("hc_fin", obligatoire=False): selector.TimeSelector(),
            self._champ("hc_jours_non_ouvres", obligatoire=False): selector.BooleanSelector(),
            self._champ("prix_injection", obligatoire=False): _nombre("prix_injection"),
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    async def async_step_bilan(self, user_input: dict[str, Any] | None = None) -> data_entry_flow.FlowResult:
        """Ce que le contrat change pour la recharge de nuit, avant d'enregistrer."""
        if user_input is not None:
            await self._enregistrer(self._reponses)
            return self.async_create_entry(data={})
        rendement = float(self._connu("rendement") or 0)
        if rendement <= 0:      # entrée du package pas encore initialisée : valeur de départ du pilotage
            rendement = DEFAUTS["rendement"]
        if self._reponses["type_tarif"] == reglages.TARIF_BASE:
            verdict, gain = "base", 0.0
        else:
            gain = reglages.gain_cyclage_eur_kwh(float(self._reponses["prix_hp"]), float(self._reponses["prix_hc"]), rendement)
            verdict = "rentable" if gain > 0 else "non_rentable"
        return self.async_show_form(
            step_id=f"bilan_{verdict}" if verdict != "rentable" else "bilan", data_schema=vol.Schema({}),
            description_placeholders={"gain": f"{abs(gain) * 100:.1f}".replace(".", ","), "rendement": f"{rendement:g}"},
        )

    async_step_bilan_non_rentable = async_step_bilan
    async_step_bilan_base = async_step_bilan


FLUX = {"batterie": EtapeBatterie, "contrat": EtapeContrat}


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None) -> RepairsFlow:
    data = data or {}
    return FLUX[data["cle"]](data["entry_id"])


__all__ = ["DOMAIN", "FLUX", "async_create_fix_flow"]
