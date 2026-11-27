"""Mises à jour Solcast pilotées : quota compté par journée UTC et journal fidèle.

Cas traité : la mise à jour de nuit lancée avant minuit UTC est refusée par Solcast
(« API allowed polling limit has been exceeded »), le quota du jour UTC étant déjà épuisé par les
trois mises à jour de jour et les valeurs réelles de minuit ; le journal ne doit pas l'annoncer
réussie. Ces tests font tourner l'automatisation du package dans un vrai Home Assistant, avec un
faux service Solcast, à l'heure de Paris (hiver : minuit UTC = 01h00).
Usage : python -m pytest -q test_solcast.py
"""
import asyncio
import datetime as dt
import pathlib

import pytest
from homeassistant.core import ServiceCall, callback
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml
from pytest_homeassistant_custom_component.common import async_fire_time_changed

PKG = pathlib.Path(__file__).resolve().parent.parent / "packages"
MAJ = "sensor.solcast_pv_forecast_derniere_interrogation_de_l_api"
UTILISES = "sensor.solcast_pv_forecast_api_utilisee"
PARIS = dt.timezone(dt.timedelta(hours=1))   # janvier : heure d'hiver


async def _preparer(hass, reevaluation, utilises="6", repond=True):
    await hass.config.async_set_time_zone("Europe/Paris")
    # Paris (coordonnées génériques) : lever vers 8h, coucher vers 17h, loin des heures testées.
    hass.config.latitude, hass.config.longitude = 48.86, 2.35
    bat = load_yaml(str(PKG / "jarvis_batterie.yaml"))
    auto = next(a for a in bat["automation"] if a.get("id") == "jarvis_solcast_mises_a_jour")
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": {
        "jarvis_solcast_pilote": {"initial": True}, "jarvis_batterie_plan_actif": {"initial": True}}})
    assert await async_setup_component(hass, "input_datetime", {"input_datetime": {
        "jarvis_batterie_reevaluation": {"has_date": False, "has_time": True, "initial": reevaluation}}})
    hass.states.async_set(MAJ, "2030-01-14T15:26:00+00:00")
    hass.states.async_set(UTILISES, utilises)
    hass.states.async_set("sensor.solcast_pv_forecast_limite_api", "10")
    appels, journal = [], []

    @callback
    def mise_a_jour(call: ServiceCall):
        appels.append(dt_util.utcnow())
        if repond:
            hass.states.async_set(MAJ, dt_util.utcnow().isoformat())
            hass.states.async_set(UTILISES, str(int(hass.states.get(UTILISES).state) + 2))

    @callback
    def log(call: ServiceCall):
        journal.append(" ".join(call.data["message"].split()))

    hass.services.async_register("solcast_solar", "update_forecasts", mise_a_jour)
    hass.services.async_register("logbook", "log", log)
    assert await async_setup_component(hass, "automation", {"automation": [auto]})
    await hass.async_block_till_done()
    assert hass.states.get("automation.jarvis_solcast_mises_a_jour_de_la_prevision").state == "on"
    return appels, journal


async def _a(hass, freezer, quand, attendre=True):
    freezer.move_to(quand)
    async_fire_time_changed(hass, quand)
    if attendre:
        await hass.async_block_till_done()
    else:  # une attente de réponse est en cours : laisser tourner sans attendre sa fin
        for _ in range(20):
            await asyncio.sleep(0)


async def test_nuit_avant_minuit_utc_reportee(hass, freezer):
    """Réévaluation à 01h16 ; mise à jour de 00h56 reportée à 01h02 (00h02 UTC)."""
    freezer.move_to(dt.datetime(2030, 1, 15, 0, 50, tzinfo=PARIS))
    appels, journal = await _preparer(hass, "01:16:00")
    await _a(hass, freezer, dt.datetime(2030, 1, 15, 0, 56, 0, 500000, tzinfo=PARIS))
    assert appels == [], "aucun appel avant minuit UTC"
    assert len(journal) == 1 and "reportée à 01h02" in journal[0] and "minuit UTC (01h00)" in journal[0], journal
    await _a(hass, freezer, dt.datetime(2030, 1, 15, 1, 2, 0, 500000, tzinfo=PARIS))
    assert len(appels) == 1
    assert journal[-1].startswith("Prévision Solcast mise à jour (avant la réévaluation de nuit)"), journal
    assert "appels utilisés 8 / 10" in journal[-1]


async def test_nuit_apres_minuit_utc_normale(hass, freezer):
    """Réévaluation à 01h45 ; mise à jour à 01h25, rien de plus à 01h02."""
    freezer.move_to(dt.datetime(2030, 1, 14, 0, 58, tzinfo=PARIS))
    appels, journal = await _preparer(hass, "01:45:00", utilises="0")
    await _a(hass, freezer, dt.datetime(2030, 1, 14, 1, 2, 0, 500000, tzinfo=PARIS))
    assert appels == [] and journal == []
    await _a(hass, freezer, dt.datetime(2030, 1, 14, 1, 25, 0, 500000, tzinfo=PARIS))
    assert len(appels) == 1 and journal[-1].startswith("Prévision Solcast mise à jour (avant la réévaluation"), journal


async def test_nuit_trop_tot_prevision_gardee(hass, freezer):
    """Réévaluation à 00h55 (avant minuit UTC) : pas d'appel, la prévision du soir est gardée."""
    freezer.move_to(dt.datetime(2030, 1, 15, 0, 30, tzinfo=PARIS))
    appels, journal = await _preparer(hass, "00:55:00")
    await _a(hass, freezer, dt.datetime(2030, 1, 15, 0, 35, 0, 500000, tzinfo=PARIS))
    assert appels == [] and len(journal) == 1
    assert "non lancée" in journal[0] and "prévision du 14/01 16h26" in journal[0], journal
    await _a(hass, freezer, dt.datetime(2030, 1, 15, 1, 2, 0, 500000, tzinfo=PARIS))
    assert appels == [] and len(journal) == 1, "pas de report : la réévaluation est passée"


async def test_refus_annonce_comme_tel(hass, freezer):
    """Solcast ne répond pas (quota dépassé côté serveur) : le journal ne parle pas de mise à jour."""
    freezer.move_to(dt.datetime(2030, 1, 14, 12, 58, tzinfo=PARIS))
    appels, journal = await _preparer(hass, "01:16:00", utilises="2", repond=False)
    await _a(hass, freezer, dt.datetime(2030, 1, 14, 13, 0, 0, 500000, tzinfo=PARIS), attendre=False)
    assert len(appels) == 1 and journal == [], "attente de la réponse (1 min au plus)"
    await _a(hass, freezer, dt.datetime(2030, 1, 14, 13, 1, 5, tzinfo=PARIS))
    assert len(journal) == 1, journal
    assert journal[0].startswith("Mise à jour Solcast refusée ou sans réponse (mise à jour de jour)"), journal
    assert "prévision du 14/01 16h26 gardée" in journal[0]


@pytest.mark.parametrize("utilises", ["9", "10", "unavailable"])
async def test_quota_insuffisant(hass, freezer, utilises):
    freezer.move_to(dt.datetime(2030, 1, 14, 12, 58, tzinfo=PARIS))
    appels, journal = await _preparer(hass, "01:16:00", utilises=utilises)
    await _a(hass, freezer, dt.datetime(2030, 1, 14, 13, 0, 0, 500000, tzinfo=PARIS))
    assert appels == [] and len(journal) == 1 and "quota insuffisant" in journal[0], journal
