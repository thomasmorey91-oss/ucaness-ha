"""Jours exceptionnels écartés de la prévision et calibration de la durée de charge.

Données INVENTÉES. Calcul joué avec le moteur de modèles de Home Assistant (comme test_v7.py) ;
mesure de la nuit et capteur de calibration joués dans un vrai Home Assistant.
Usage : python -m pytest -q test_calibration.py
"""
import asyncio
import datetime as dt
import json
import pathlib

import pytest
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml
from pytest_homeassistant_custom_component.common import async_fire_time_changed

import test_v7 as v7

PKG = pathlib.Path(__file__).resolve().parent.parent / "packages"
v7.CHEMIN = str(PKG / "jarvis_batterie.yaml")
QUAND = "2030-01-14 22:00:00+00:00"           # lundi 14/01, 23h à Paris : on prépare le mardi 15
MARDI_RECENT = (v7.JOUR - dt.timedelta(days=7)).isoformat()


@pytest.fixture(autouse=True)
def fuseau_rendu():
    """Le calcul (test_v7) crée son propre Home Assistant à l'heure de Paris : fuseau rendu ensuite."""
    yield
    dt_util.set_default_time_zone(dt.UTC)


# --- Jours exceptionnels -------------------------------------------------------------------------
async def test_sans_jour_exceptionnel_moyenne_ponderee():
    r = await v7.calcul(QUAND, v7.prevision(), v7.mesures_deux_jours())
    assert abs(r["conso_mesuree"][12] - (2.0 * 1 + 1.0 * 0.5) / 1.5) < 0.002
    assert r["jours_ecartes"] == []


async def test_jour_exceptionnel_ecarte():
    r = await v7.calcul(QUAND, v7.prevision(), v7.mesures_deux_jours(),
                        etats_en_plus={"input_text.jarvis_jours_exceptionnels": f"2029-12-01, {MARDI_RECENT}"})
    assert r["conso_mesuree"][12] == 1.0, "seul le mardi le plus ancien reste, avec le poids 1"
    assert r["jours_ecartes"] == [MARDI_RECENT]


async def test_tous_les_jours_ecartes_repli_sur_la_conso_par_defaut():
    anc = (v7.JOUR - dt.timedelta(days=14)).isoformat()
    r = await v7.calcul(QUAND, v7.prevision(), v7.mesures_deux_jours(),
                        etats_en_plus={"input_text.jarvis_jours_exceptionnels": f"{MARDI_RECENT} {anc}",
                                       "input_number.jarvis_conso_journaliere": "24"})
    assert r["calcul"]["heures_mesurees"] == 0
    assert r["calcul"]["calcul_valide"] is True


# --- Facteur de durée ----------------------------------------------------------------------------
@pytest.mark.parametrize(("choix", "capteur", "attendu"), [
    ("Désactivée", "1.0", 1.1),
    ("Automatique", "unknown", 1.1),         # moins de 3 nuits mesurées
    ("Automatique", "1.0", 1.0),
    ("Automatique", "0.5", 0.9),             # bornes
    ("Automatique", "2.0", 1.3),
])
async def test_facteur_de_duree(choix, capteur, attendu):
    r = await v7.calcul(QUAND, v7.prevision(facteur=0.2), v7.mesures_deux_jours(),
                        etats_en_plus={"input_select.jarvis_calibration_charge": choix,
                                       "sensor.jarvis_calibration_de_la_charge": capteur})
    c = r["calcul"]
    assert c["recharge_kwh"] > 1 and c["facteur_duree"] == attendu
    p_ch = 3.0
    attendu_min = -(-(c["recharge_kwh"] / p_ch * 60 * attendu) // 1)
    assert abs(c["duree_h"] * 60 - attendu_min) <= 1.5, (c["duree_h"], attendu_min)
    assert c["duree_limitee"] is False


# --- Mesure de la nuit et capteur de calibration --------------------------------------------------
PARIS = dt.timezone(dt.timedelta(hours=1))


async def _preparer(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    bat = load_yaml(str(PKG / "jarvis_batterie.yaml"))
    autos = [a for a in bat["automation"] if a.get("id") in (
        "jarvis_batterie_calibration_mesure", "jarvis_batterie_jours_exceptionnels_nettoyage")]
    capteur = [t for t in bat["template"] if any(e.get("event_type") == "jarvis_calibration_nuit" for e in t.get("triggers", []))]
    assert await async_setup_component(hass, "input_text", {"input_text": bat["input_text"]})
    assert await async_setup_component(hass, "input_datetime", {"input_datetime": {
        "jarvis_hc_fin": {"has_date": False, "has_time": True, "initial": "06:00"}}})
    assert await async_setup_component(hass, "template", {"template": capteur})
    journal = []
    hass.services.async_register("logbook", "log", lambda call: journal.append(" ".join(call.data["message"].split())))
    assert await async_setup_component(hass, "automation", {"automation": autos})
    await hass.async_block_till_done()
    return journal


async def _nuit(hass, freezer, jour, c0, c1, r, k=1.1, limitee=False, soc="60"):
    await hass.services.async_call("input_text", "set_value", {
        "entity_id": "input_text.jarvis_charge_suivi",
        "value": json.dumps({"c": c0, "r": r, "k": k, "l": limitee, "j": f"2030-01-{jour - 1:02d}"})}, blocking=True)
    hass.states.async_set("sensor.uhome_charge_batterie_totale", str(c1))
    hass.states.async_set("sensor.uhome_soc", soc)
    quand = dt.datetime(2030, 1, jour, 6, 20, 0, 500000, tzinfo=PARIS)
    freezer.move_to(quand)
    async_fire_time_changed(hass, quand)
    for _ in range(50):              # l'automatisation attend 2 s avant le journal : pas d'attente bloquante
        await asyncio.sleep(0)
    freezer.tick(3)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_calibration_apres_trois_nuits(hass, freezer):
    freezer.move_to(dt.datetime(2030, 1, 10, 12, 0, tzinfo=PARIS))
    journal = await _preparer(hass)
    cal = "sensor.jarvis_calibration_de_la_charge"
    # Recharge programmée 10 kWh, durée × 1,1 : 11,0 / 11,5 / 10,6 kWh chargés.
    await _nuit(hass, freezer, 11, 100.0, 111.0, 10.0)
    assert hass.states.get("input_text.jarvis_charge_suivi").state == "", "suivi vidé"
    assert hass.states.get(cal).state == "unknown"
    assert "nuit retenue" in journal[-1] and "100 %" in journal[-1], journal
    await _nuit(hass, freezer, 12, 200.0, 211.5, 10.0)
    await _nuit(hass, freezer, 13, 300.0, 310.6, 10.0)
    st = hass.states.get(cal)
    assert st.attributes["nuits_valides"] == 3
    q = sorted([11.0 / 11, 11.5 / 11, 10.6 / 11])[1]
    assert float(st.state) == round(1 / q, 3), st.state
    nuit = st.attributes["derniere_nuit"]
    assert nuit["valide"] is True and nuit["chargee_kwh"] == 10.6 and nuit["jour"] == "2030-01-12"


@pytest.mark.parametrize(("kwargs", "motif"), [
    ({"c1": 100.4, "r": 0.5}, "recharge programmée trop faible"),
    ({"c1": 111.0, "r": 10.0, "limitee": True}, "plage raccourcie"),
    ({"c1": 111.0, "r": 10.0, "soc": "97"}, "batterie pleine"),
    ({"c1": 102.0, "r": 10.0}, "écart hors bornes"),
    ({"c1": "unavailable", "r": 10.0}, "compteur de charge indisponible"),
])
async def test_nuits_non_retenues(hass, freezer, kwargs, motif):
    freezer.move_to(dt.datetime(2030, 1, 10, 12, 0, tzinfo=PARIS))
    journal = await _preparer(hass)
    await _nuit(hass, freezer, 11, 100.0, kwargs.pop("c1"), **kwargs)
    st = hass.states.get("sensor.jarvis_calibration_de_la_charge")
    assert st.attributes["nuits_valides"] == 0 and st.attributes["derniere_nuit"]["valide"] is False
    assert motif in st.attributes["derniere_nuit"]["motif"] and "nuit non retenue" in journal[-1], journal


async def test_sans_suivi_rien(hass, freezer):
    freezer.move_to(dt.datetime(2030, 1, 10, 12, 0, tzinfo=PARIS))
    journal = await _preparer(hass)
    quand = dt.datetime(2030, 1, 11, 6, 20, 0, 500000, tzinfo=PARIS)
    freezer.move_to(quand)
    async_fire_time_changed(hass, quand)
    await hass.async_block_till_done()
    assert journal == [] and hass.states.get("sensor.jarvis_calibration_de_la_charge").state == "unknown"


async def test_nettoyage_des_jours_exceptionnels(hass, freezer):
    freezer.move_to(dt.datetime(2030, 1, 20, 11, 59, tzinfo=PARIS))
    await _preparer(hass)
    await hass.services.async_call("input_text", "set_value", {
        "entity_id": "input_text.jarvis_jours_exceptionnels", "value": "2030-01-19, 2030-01-05 2030-01-12 2030-01-11"}, blocking=True)
    quand = dt.datetime(2030, 1, 20, 12, 0, 0, 500000, tzinfo=PARIS)
    freezer.move_to(quand)
    async_fire_time_changed(hass, quand)
    await hass.async_block_till_done()
    assert hass.states.get("input_text.jarvis_jours_exceptionnels").state == "2030-01-12 2030-01-19"
