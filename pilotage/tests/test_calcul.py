"""Calcul de la recharge de nuit joué avec le moteur de modèles de Home Assistant.

Données INVENTÉES (maison type, batterie de 10,24 kWh, prix d'exemple) : aucune mesure réelle.
Usage : python pilotage/tests/test_calcul.py [chemin/jarvis_batterie.yaml]
Dépendances : homeassistant, freezegun, pyyaml.
"""
import asyncio
import datetime as dt
import pathlib
import sys
import tempfile
import zoneinfo

import yaml
from freezegun import freeze_time
from homeassistant.core import HomeAssistant
from homeassistant.helpers import template as tpl
from homeassistant.helpers.script_variables import ScriptVariables

PAQUET = pathlib.Path(__file__).resolve().parent.parent / "packages" / "jarvis_batterie.yaml"
TZ = zoneinfo.ZoneInfo("Europe/Paris")
JOUR = dt.date(2030, 1, 15)  # un mardi

# Production solaire d'exemple (kWh par heure) et consommation moyenne d'exemple (W par heure).
SOLAIRE = {8: 0.5, 9: 1.5, 10: 2.5, 11: 3.2, 12: 3.4, 13: 3.2, 14: 2.6, 15: 1.7, 16: 0.8}
CONSO_W = [300, 280, 260, 250, 250, 300, 1400, 1300, 1000, 700, 600, 600,
           750, 650, 550, 500, 600, 900, 1500, 1600, 1300, 1000, 600, 400]


def statistiques(jours=3, heures=range(24)):
    lignes = []
    for j in range(1, jours + 1):
        d = JOUR - dt.timedelta(days=7 * j)  # mêmes jours de semaine
        for h in heures:
            lignes.append({"start": dt.datetime.combine(d, dt.time(h), TZ).isoformat(), "mean": CONSO_W[h]})
    return {"statistics": {"sensor.uhome_puissance_maison": lignes}}


async def calcul(quand, soc="15", solaire=1.0, mesures=True, heures=range(24), conso_defaut="0",
                 capacite="10.24", hp="0.25", hc="0.18", t_batt="20", ouvre=True):
    with tempfile.TemporaryDirectory() as d:
        hass = HomeAssistant(d)
        await hass.config.async_set_time_zone("Europe/Paris")
        pkg = yaml.safe_load(open(CHEMIN, encoding="utf-8"))
        actions = pkg["template"][0]["actions"]
        v1 = actions[0]["variables"]
        v2 = next(a["variables"] for a in actions[1:] if "variables" in a)
        etats = {
            "input_number.jarvis_batterie_capacite": capacite, "input_number.jarvis_batterie_plancher": "15",
            "input_number.jarvis_batterie_rendement": "95", "input_number.jarvis_batterie_puissance_charge": "3",
            "input_number.jarvis_batterie_marge": "10", "input_number.jarvis_conso_journaliere": conso_defaut,
            "input_number.jarvis_prix_hp": hp, "input_number.jarvis_prix_hc": hc,
            "input_datetime.jarvis_hc_debut": "23:00:00", "input_datetime.jarvis_hc_fin": "06:00:00",
            "sensor.uhome_soc": soc, "sensor.uhome_temperature_batterie": t_batt,
        }
        for k, v in etats.items():
            hass.states.async_set(k, v)
        prevision = [{"period_start": dt.datetime.combine(JOUR, dt.time(h), TZ).isoformat(), "pv_estimate": v * solaire}
                     for h, v in SOLAIRE.items()]
        for capteur in ("sensor.solcast_pv_forecast_prevision_demain", "sensor.solcast_pv_forecast_prevision_aujourdhui"):
            hass.states.async_set(capteur, "0", {"detailedHourly": prevision})
        with freeze_time(quand):
            r1 = ScriptVariables({k: tpl.Template(v, hass) for k, v in v1.items()}).async_render(hass, {})
            run = {**r1, "jour": {"binary_sensor.workday_sensor": {"workday": ouvre}}}
            if mesures:
                run["mesures"] = statistiques(heures=heures)
            c = ScriptVariables({k: tpl.Template(v, hass) if isinstance(v, str) else v for k, v in v2.items()}).async_render(hass, run)["calcul"]
        await hass.async_stop(force=True)
        return c


SOIR = "2030-01-14 22:00:00"   # 23h à Paris, la veille du jour préparé
NUIT = "2030-01-15 02:30:00"   # 3h30 à Paris


def verifier():
    c = asyncio.run(calcul(SOIR))
    assert c["heures_mesurees"] == 24 and c["recharge_kwh"] > 0
    assert c["plages"][-1]["fin"] == "0545" and c["reevaluation"]
    assert 9 <= c["relais_h"] <= 12                               # le solaire reprend le relais en matinée
    print("Matin couvert jusqu'au solaire :", c["justification"])

    c2 = asyncio.run(calcul(SOIR, solaire=0.2))
    assert c2["relais_h"] == 23 and c2["recharge_kwh"] > c["recharge_kwh"]
    print("Journée grise :", c2["justification"])

    assert asyncio.run(calcul(SOIR, soc="90"))["recharge_kwh"] == 0   # stock suffisant
    assert asyncio.run(calcul(SOIR, t_batt="-2"))["recharge_kwh"] == 0  # sous 0 °C
    assert asyncio.run(calcul(SOIR, ouvre=False))["recharge_kwh"] == 0  # jour non ouvré
    assert asyncio.run(calcul(SOIR, hp="0", hc="0"))["recharge_kwh"] == 0  # prix non renseignés
    assert asyncio.run(calcul(SOIR, capacite="0"))["recharge_kwh"] == 0    # capacité non renseignée

    sans = asyncio.run(calcul(SOIR, mesures=False))
    assert sans["recharge_kwh"] == 0 and sans["calcul_valide"] is False   # ni mesure ni défaut : repli sûr
    defaut = asyncio.run(calcul(SOIR, mesures=False, conso_defaut="15"))
    assert defaut["recharge_kwh"] > 0 and defaut["heures_mesurees"] == 0  # profil type × 15 kWh/jour

    nuit = asyncio.run(calcul(NUIT, soc="15"))
    assert nuit["conso_nuit_kwh"] < c["conso_nuit_kwh"]                    # il reste moins de nuit à couvrir
    print("Réévaluation de 3h30 :", nuit["justification"])
    print("Tous les contrôles sont passés.")


if __name__ == "__main__":
    CHEMIN = sys.argv[1] if len(sys.argv) > 1 else str(PAQUET)
    verifier()
