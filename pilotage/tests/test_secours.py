"""Tests du package secours (jarvis_secours.yaml) dans un vrai Home Assistant.

Aucune écriture vers l'onduleur ; les notifications sont captées. Données INVENTÉES.
Usage : cd pilotage/tests && python -m pytest -q test_secours.py
"""
import asyncio
import datetime as dt
import pathlib

import pytest
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml
from pytest_homeassistant_custom_component.common import async_fire_time_changed

PKG = pathlib.Path(__file__).resolve().parent.parent / "packages"


def _pkg(name):
    return load_yaml(str(PKG / name))


# Temps écoulé depuis le début du test. Les avances se CUMULENT : sans cela, chaque avance repartait
# de l'heure réelle, et le relevé périodique (toutes les 2 min, aux minutes paires) pouvait tomber
# pendant une avance courte puis ne plus se représenter pendant l'avance de 120 s. Le test échouait
# alors selon la seconde à laquelle il était lancé.
_HORLOGE = {"decalage": 0}


@pytest.fixture(autouse=True)
def _horloge_a_zero():
    _HORLOGE["decalage"] = 0


async def _avancer(hass, secondes):
    _HORLOGE["decalage"] += secondes
    async_fire_time_changed(hass, dt_util.utcnow() + dt.timedelta(seconds=_HORLOGE["decalage"]))
    await hass.async_block_till_done()


@pytest.fixture
async def maison(hass, caplog):
    await hass.config.async_set_time_zone("Europe/Paris")
    bat, alertes, sec, dyn = (_pkg(n) for n in ("jarvis_batterie.yaml", "jarvis_alertes.yaml", "jarvis_secours.yaml", "jarvis_dynamique.yaml"))
    notes, ecritures = [], []

    async def notifier(call):
        notes.append((call.data.get("title", ""), call.data.get("message", "")))

    async def ecrire(call):
        ecritures.append(call.data)

    hass.services.async_register("notify", "mobile_app_essai", notifier)
    hass.services.async_register("logbook", "log", lambda call: None)
    hass.services.async_register("ucaness", "definir_mode", ecrire)
    hass.services.async_register("ucaness", "definir_plages_charge", ecrire)

    nombres = {**bat["input_number"], **sec["input_number"]}
    nombres["jarvis_batterie_capacite"] = {**nombres["jarvis_batterie_capacite"], "initial": 10.24}
    nombres["jarvis_batterie_plancher"] = {**nombres["jarvis_batterie_plancher"], "initial": 10}
    nombres["jarvis_batterie_rendement"] = {**nombres["jarvis_batterie_rendement"], "initial": 95}
    nombres["jarvis_secours_puissance_max"] = {**nombres["jarvis_secours_puissance_max"], "initial": 5}
    nombres["jarvis_secours_seuil_tension"] = {**nombres["jarvis_secours_seuil_tension"], "initial": 100}
    booleens = {**bat["input_boolean"], **alertes["input_boolean"], **sec["input_boolean"]}
    booleens["jarvis_secours_cablee"] = {**booleens["jarvis_secours_cablee"], "initial": True}
    booleens["jarvis_alertes_actives"] = {**booleens["jarvis_alertes_actives"], "initial": True}
    textes = {**alertes["input_text"], **sec["input_text"]}
    textes["jarvis_service_notification"] = {**textes["jarvis_service_notification"], "initial": "mobile_app_essai"}
    textes["jarvis_secours_vigilance"] = {**textes["jarvis_secours_vigilance"], "initial": "sensor.99_weather_alert"}
    assert await async_setup_component(hass, "input_number", {"input_number": nombres})
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": booleens})
    assert await async_setup_component(hass, "input_text", {"input_text": textes})
    assert await async_setup_component(hass, "input_select", {"input_select": dyn["input_select"]})
    assert await async_setup_component(hass, "input_datetime", {"input_datetime": sec["input_datetime"]})
    assert await async_setup_component(hass, "script", {"script": alertes["script"]})
    hass.states.async_set("binary_sensor.uhome_connexion_cloud", "on")
    hass.states.async_set("sensor.uhome_tension_reseau", "231.0")
    hass.states.async_set("sensor.uhome_etat", "PV on grid")
    hass.states.async_set("sensor.uhome_soc", "60")
    hass.states.async_set("sensor.uhome_puissance_maison", "800")
    hass.states.async_set("sensor.uhome_mode", "Match Load Mode")
    hass.states.async_set("sensor.99_weather_alert", "Jaune", {"Vent violent": "Jaune", "Orages": "Vert"})
    assert await async_setup_component(hass, "template", {"template": sec["template"]})
    assert await async_setup_component(hass, "automation", {"automation": sec["automation"]})
    await hass.async_block_till_done()
    assert "Invalid config" not in caplog.text, caplog.text
    return notes, ecritures


async def test_autonomie_de_secours(hass, maison):
    etat = hass.states.get("sensor.jarvis_autonomie_de_secours")
    # (60 - 10) % de 10,24 kWh × 0,95 / 0,8 kW = 6,1 h
    assert float(etat.state) == pytest.approx(6.1, abs=0.05)
    assert etat.attributes["stock_utile_kwh"] == pytest.approx(5.12)


async def test_coupure_alerte_suivi_et_bilan(hass, maison):
    notes, ecritures = maison
    hass.states.async_set("sensor.uhome_tension_reseau", "0.0")
    await hass.async_block_till_done()
    await _avancer(hass, 25)                                   # délai de 20 s
    assert hass.states.get("binary_sensor.jarvis_coupure_reseau").state == "on"
    assert hass.states.get("input_boolean.jarvis_secours_coupure_en_cours").state == "on"
    assert notes and "Coupure du réseau" in notes[-1][0]
    assert "6.1 h" in notes[-1][1] and "5.0 kW" in notes[-1][1]
    # La batterie descend, la maison tire 4,8 kW (90 % de 5 kW dépassés).
    hass.states.async_set("sensor.uhome_soc", "40")
    hass.states.async_set("sensor.uhome_puissance_maison", "4800")
    await hass.async_block_till_done()
    await _avancer(hass, 40)
    assert any("proche de sa limite" in t for t, _ in notes)
    await _avancer(hass, 120)                                  # relevé périodique
    assert float(hass.states.get("input_number.jarvis_secours_soc_min").state) == 40
    assert float(hass.states.get("input_number.jarvis_secours_charge_max").state) == pytest.approx(4.8)
    # Retour du réseau.
    hass.states.async_set("sensor.uhome_tension_reseau", "232.0")
    hass.states.async_set("sensor.uhome_puissance_maison", "700")
    await hass.async_block_till_done()
    await _avancer(hass, 65)
    assert hass.states.get("input_boolean.jarvis_secours_coupure_en_cours").state == "off"
    bilan = hass.states.get("sensor.jarvis_derniere_coupure")
    assert bilan.attributes["energie_fournie_kwh"] == pytest.approx(2.05, abs=0.01)   # 20 % de 10,24 kWh
    assert bilan.attributes["coupures_annee"] == 1
    assert "Réseau rétabli" in notes[-1][0]
    assert ecritures == []                                     # rien n'est écrit sur l'onduleur


async def test_pas_de_coupure_si_onduleur_hors_ligne(hass, maison):
    hass.states.async_set("binary_sensor.uhome_connexion_cloud", "off")
    hass.states.async_set("sensor.uhome_tension_reseau", "0.0")
    await hass.async_block_till_done()
    await _avancer(hass, 25)
    assert hass.states.get("binary_sensor.jarvis_coupure_reseau").state != "on"


async def test_etat_hors_reseau_detecte(hass, maison):
    hass.states.async_set("sensor.uhome_etat", "Off Grid")
    await hass.async_block_till_done()
    await _avancer(hass, 25)
    assert hass.states.get("binary_sensor.jarvis_coupure_reseau").state == "on"


async def test_risque_vigilance_orange(hass, maison):
    notes, _ = maison
    hass.states.async_set("sensor.99_weather_alert", "Orange", {"Vent violent": "Orange", "Orages": "Jaune"})
    await hass.async_block_till_done()
    risque = hass.states.get("binary_sensor.jarvis_risque_de_coupure")
    assert risque.state == "on"
    assert risque.attributes["motif"] == "Vent violent (orange)"
    await hass.async_block_till_done()
    assert any("Risque de coupure" in t for t, _ in notes), notes
    assert "Aucune réserve automatique" in notes[-1][1]


async def test_risque_coupure_programmee(hass, maison):
    debut = dt_util.now() + dt.timedelta(hours=6)
    fin = debut + dt.timedelta(hours=3)
    for e, t in (("input_datetime.jarvis_secours_coupure_prevue_debut", debut), ("input_datetime.jarvis_secours_coupure_prevue_fin", fin)):
        await hass.services.async_call("input_datetime", "set_datetime", {"entity_id": e, "timestamp": t.timestamp()}, blocking=True)
    await hass.async_block_till_done()
    risque = hass.states.get("binary_sensor.jarvis_risque_de_coupure")
    assert risque.state == "on" and "coupure programmée" in risque.attributes["motif"]
    assert dt_util.parse_datetime(risque.attributes["fin"]) == fin.replace(microsecond=0)


async def test_bilan_au_redemarrage(hass, maison):
    notes, _ = maison
    vieux = dt_util.now() - dt.timedelta(hours=2)
    await hass.services.async_call("input_datetime", "set_datetime",
                                   {"entity_id": "input_datetime.jarvis_secours_battement", "timestamp": vieux.timestamp()}, blocking=True)
    await hass.services.async_call("automation", "trigger",
                                   {"entity_id": "automation.jarvis_secours_bilan_au_redemarrage_de_home_assistant"}, blocking=False)
    for _ in range(20):
        await asyncio.sleep(0)
    async_fire_time_changed(hass, dt_util.utcnow() + dt.timedelta(seconds=125), fire_all=True)
    for _ in range(20):
        await asyncio.sleep(0)
    await hass.async_block_till_done()
    assert any("redémarré après un arrêt" in t for t, _ in notes)
