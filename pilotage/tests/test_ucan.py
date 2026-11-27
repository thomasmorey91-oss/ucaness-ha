"""Conseils d'Ucan (ucan_conseils.yaml) dans un vrai Home Assistant. Données INVENTÉES.

Usage : python -m pytest -q test_ucan.py
"""
import datetime as dt
import pathlib

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from homeassistant.core import SupportsResponse
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml

PKG = pathlib.Path(__file__).resolve().parent.parent / "packages"
PARIS = dt.timezone(dt.timedelta(hours=1))
CONSEIL = "sensor.ucan_conseil"


def talons(recentes, anciennes, debut=dt.date(2030, 1, 2)):
    """Statistiques horaires de la maison : 14 nuits, talon (2h-4h) donné, 600 W le reste de la nuit."""
    lignes = []
    for i, w in enumerate(list(anciennes) + list(recentes)):
        d = debut + dt.timedelta(days=i)
        for h, v in ((1, 600), (2, w + 20), (3, w), (4, w + 40)):
            lignes.append({"start": dt.datetime.combine(d, dt.time(h), PARIS).isoformat(), "mean": v})
    return {"statistics": {"sensor.uhome_puissance_maison": lignes}}


async def _maison(hass, freezer, hp=7.9, jour="2030-01-15", ouvre=True, valide=True, stats=None):
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
    hass.services.async_register("recorder", "get_statistics", lambda c: stats or {"statistics": {}},
                                 supports_response=SupportsResponse.ONLY)
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


async def _recalcul(hass):
    hass.bus.async_fire("ucan_recalcul")
    await hass.async_block_till_done()


async def _cycles(hass, valeurs):
    for jour, kwh in valeurs:
        hass.bus.async_fire("ucan_cycle_lave_linge", {"jour": jour, "kwh": kwh})
        await hass.async_block_till_done()


async def test_ancien_format_du_jour_traite(hass, freezer):
    """Une date seule (version précédente) vaut « machines:date » : le conseil reste traité."""
    await _maison(hass, freezer)
    await hass.services.async_call("input_text", "set_value", {"entity_id": "input_text.ucan_jour_traite", "value": "2030-01-15"}, blocking=True)
    await _recalcul(hass)
    assert hass.states.get(CONSEIL).state == "aucun"


async def test_lavage_chaud_puis_priorite(hass, freezer):
    await _maison(hass, freezer)
    await _cycles(hass, [("2030-01-08", 0.6), ("2030-01-09", 0.55), ("2030-01-10", 0.7), ("2030-01-12", 0.6),
                         ("2030-01-13", 0.65), ("2030-01-15", 1.9)])
    await _recalcul(hass)
    st = hass.states.get(CONSEIL)
    assert st.state == "machines" and st.attributes["candidats"] == ["machines", "lavage"], "machines d'abord"
    await _repondre(hass, "fait")
    st = hass.states.get(CONSEIL)
    assert st.state == "lavage", st.attributes
    assert st.attributes["constat"].startswith("Hier, un cycle du lave-linge a pris 1,9 kWh, contre 0,6 kWh")
    assert st.attributes["gain"] == "Environ " + ("%.2f" % ((1.9 - 0.6) * 0.30638)).replace(".", ",") + " € de moins par cycle."
    await _repondre(hass, "fait")
    assert hass.states.get(CONSEIL).state == "aucun"
    assert hass.states.get("input_datetime.ucan_pause_lavage").state == "2030-01-30", "14 jours pour mesurer"
    assert hass.states.get("input_text.ucan_jour_traite").state == "machines:2030-01-15 lavage:2030-01-15"


async def test_lavage_ordinaire_ou_trop_peu_de_cycles(hass, freezer):
    await _maison(hass, freezer, hp=1.0)
    await _cycles(hass, [("2030-01-10", 0.6), ("2030-01-12", 0.6), ("2030-01-15", 1.9)])
    await _recalcul(hass)
    assert hass.states.get(CONSEIL).state == "aucun", "moins de 5 cycles de référence"
    await _cycles(hass, [("2030-01-11", 0.6), ("2030-01-13", 0.6), ("2030-01-14", 0.6), ("2030-01-15", 0.8)])
    await _recalcul(hass)
    assert hass.states.get(CONSEIL).attributes["candidats"] == ["lavage"], "le cycle à 1,9 kWh d'hier compte"


@pytest.mark.parametrize(("recentes", "anciennes", "seuil", "attendu"), [
    ([180] * 7, [120] * 7, 0, "veilles"),          # +60 W, +50 %
    ([140] * 7, [120] * 7, 0, "aucun"),            # +20 W seulement
    ([180] * 7, [], 0, "aucun"),                   # pas de nuits de référence
    ([180] * 7, [], 120, "veilles"),               # seuil fixé
    ([180] * 6 + [130], [120] * 7, 0, "aucun"),    # une nuit basse : pas de veille permanente
])
async def test_veilles(hass, freezer, recentes, anciennes, seuil, attendu):
    await _maison(hass, freezer, hp=1.0, stats=talons(recentes, anciennes))
    await hass.services.async_call("input_number", "set_value", {"entity_id": "input_number.ucan_talon_seuil", "value": seuil}, blocking=True)
    await _recalcul(hass)
    st = hass.states.get(CONSEIL)
    assert st.state == attendu, st.attributes
    if attendu == "veilles":
        assert "jamais descendue sous 180 W, contre 120 W" in st.attributes["constat"]
        gain = 60 / 1000 * 8760 * (0.30638 + 0.1729) / 2
        assert st.attributes["gain"] == f"Environ {round(gain)} € par an."


async def test_cycle_du_lave_linge_mesure(hass, freezer):
    await _maison(hass, freezer, hp=1.0)
    for e, v in (("input_text.ucan_lave_linge_puissance", "sensor.ll_puissance"), ("input_text.ucan_lave_linge_energie", "sensor.ll_energie")):
        await hass.services.async_call("input_text", "set_value", {"entity_id": e, "value": v}, blocking=True)
    hass.states.async_set("sensor.ll_energie", "10.0")
    hass.states.async_set("sensor.ll_puissance", "2")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.ll_puissance", "2000")
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.ucan_lave_linge_en_cycle").state == "on"
    hass.states.async_set("sensor.ll_puissance", "8")            # pause du tambour
    await hass.async_block_till_done()
    freezer.tick(300)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.ll_puissance", "500")
    hass.states.async_set("sensor.ll_energie", "10.9")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.ll_puissance", "1")
    await hass.async_block_till_done()
    freezer.tick(601)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.ucan_lave_linge_en_cycle").state == "off"
    st = hass.states.get("sensor.ucan_cycles_du_lave_linge")
    assert st.attributes["cycles"] == [{"jour": "2030-01-16", "kwh": 0.9}]
