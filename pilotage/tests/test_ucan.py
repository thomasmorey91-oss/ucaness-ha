"""Conseils d'Ucan (ucan_conseils.yaml) dans un vrai Home Assistant. Données INVENTÉES.

Usage : python -m pytest -q test_ucan.py
"""
import datetime as dt
import pathlib

import pytest
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml

PKG = pathlib.Path(__file__).resolve().parent.parent / "packages"
PARIS = dt.timezone(dt.timedelta(hours=1))
CONSEIL = "sensor.ucan_conseil"


async def _maison(hass, freezer, hp=7.9, jour="2030-01-15", ouvre=True, valide=True):
    freezer.move_to(dt.datetime(2030, 1, 16, 7, 0, tzinfo=PARIS))
    await hass.config.async_set_time_zone("Europe/Paris")
    u = load_yaml(str(PKG / "ucan_conseils.yaml"))
    for dom in ("input_number", "input_boolean", "input_text", "input_datetime"):
        conf = dict(u[dom])
        if dom == "input_number":
            conf |= {"jarvis_prix_hp": {"min": 0, "max": 2, "step": 0.0001, "initial": 0.30638},
                     "jarvis_prix_hc": {"min": 0, "max": 2, "step": 0.0001, "initial": 0.1729}}
        assert await async_setup_component(hass, dom, {dom: conf})
    hass.states.async_set("sensor.jarvis_gain_reel_du_jour", "1.1", {
        "jour": jour, "jour_ouvre": ouvre, "calcul_valide": valide, "soutirage_hp_kwh": hp})
    journal, notes = [], []
    hass.services.async_register("logbook", "log", lambda c: journal.append(" ".join(c.data["message"].split())))
    hass.services.async_register("script", "jarvis_notifier", lambda c: notes.append(dict(c.data)))
    assert await async_setup_component(hass, "template", {"template": u["template"]})
    assert await async_setup_component(hass, "script", {"script": u["script"]})
    assert await async_setup_component(hass, "automation", {"automation": u["automation"]})
    await hass.async_block_till_done()
    hass.bus.async_fire("ucan_recalcul")
    await hass.async_block_till_done()
    return journal, notes


async def _repondre(hass, reponse):
    await hass.services.async_call("script", "ucan_conseil_reponse", {"reponse": reponse}, blocking=True)
    await hass.async_block_till_done()


async def test_conseil_machines_avec_son_gain(hass, freezer):
    await _maison(hass, freezer)
    st = hass.states.get(CONSEIL)
    assert st.state == "machines"
    assert st.attributes["constat"] == "Le mardi 15/01, 7,9 kWh ont été achetés en heures pleines."
    assert st.attributes["gain_eur"] == round(7.9 * (0.30638 - 0.1729), 2)
    assert st.attributes["gain"] == "Jusqu'à 1,05 € de moins ce jour-là."


@pytest.mark.parametrize("kwargs", [
    {"hp": 2.0},                    # sous le seuil de 3 kWh
    {"ouvre": False},               # jour non ouvré
    {"valide": False},              # gain réel non calculé
    {"jour": "2030-01-10"},         # mesure trop ancienne
])
async def test_pas_de_conseil(hass, freezer, kwargs):
    await _maison(hass, freezer, **kwargs)
    assert hass.states.get(CONSEIL).state == "aucun"


async def test_je_le_fais(hass, freezer):
    journal, _ = await _maison(hass, freezer)
    await _repondre(hass, "fait")
    assert hass.states.get(CONSEIL).state == "aucun", "conseil traité, plus montré"
    assert hass.states.get("input_datetime.ucan_engagement_machines").state == "2030-01-16"
    assert "accepté" in journal[-1]


async def test_deux_fois_pas_maintenant_puis_pause(hass, freezer):
    journal, _ = await _maison(hass, freezer)
    await _repondre(hass, "plus_tard")
    assert hass.states.get("input_text.ucan_refus_machines").state == "1"
    assert hass.states.get("input_datetime.ucan_pause_machines").state <= "2030-01-16"
    # Le lendemain, nouveau jour chargé : conseil de nouveau proposé.
    freezer.move_to(dt.datetime(2030, 1, 17, 7, 0, tzinfo=PARIS))
    hass.states.async_set("sensor.jarvis_gain_reel_du_jour", "1", {
        "jour": "2030-01-16", "jour_ouvre": True, "calcul_valide": True, "soutirage_hp_kwh": 6.0})
    hass.bus.async_fire("ucan_recalcul")
    await hass.async_block_till_done()
    assert hass.states.get(CONSEIL).state == "machines"
    await _repondre(hass, "plus_tard")
    assert hass.states.get("input_datetime.ucan_pause_machines").state == "2030-02-16"
    assert "plus proposé pendant 30 jours" in journal[-1]
    # Pendant la pause, plus de conseil.
    freezer.move_to(dt.datetime(2030, 1, 18, 7, 0, tzinfo=PARIS))
    hass.states.async_set("sensor.jarvis_gain_reel_du_jour", "1", {
        "jour": "2030-01-17", "jour_ouvre": True, "calcul_valide": True, "soutirage_hp_kwh": 9.0})
    hass.bus.async_fire("ucan_recalcul")
    await hass.async_block_till_done()
    assert hass.states.get(CONSEIL).state == "aucun"


async def test_ne_plus_proposer(hass, freezer):
    await _maison(hass, freezer)
    await _repondre(hass, "jamais")
    assert hass.states.get("input_datetime.ucan_pause_machines").state == "2030-02-15"
    assert hass.states.get("input_text.ucan_refus_machines").state == "0"


async def test_reponse_sans_conseil_ignoree(hass, freezer):
    journal, _ = await _maison(hass, freezer, hp=1.0)
    await _repondre(hass, "jamais")
    assert hass.states.get("input_datetime.ucan_pause_machines").state <= "2030-01-16" and journal == []
