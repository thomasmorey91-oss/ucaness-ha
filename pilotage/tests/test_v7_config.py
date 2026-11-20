"""Chargement du package batterie (modèles et automatisations) dans un vrai Home Assistant.

Vérifie que la configuration v7 est acceptée : capteurs à déclenchement (recharge, gain réel et
cumuls), automatisations (journal du gain, mises à jour Solcast). Aucune connexion à l'onduleur.
Usage : python -m pytest -q test_v7_config.py
"""
import pathlib

from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml

PKG = pathlib.Path(__file__).resolve().parent.parent / "packages"


async def test_package_v7_charge(hass, caplog):
    bat = load_yaml(str(PKG / "jarvis_batterie.yaml"))
    tarif = load_yaml(str(PKG / "jarvis_tarif.yaml"))
    for domaine in ("input_boolean", "input_datetime", "input_number"):
        conf = {**tarif.get(domaine, {}), **bat.get(domaine, {})}
        assert await async_setup_component(hass, domaine, {domaine: conf})
    assert await async_setup_component(hass, "input_select", {"input_select": tarif["input_select"]})
    assert await async_setup_component(hass, "template", {"template": bat["template"]})
    assert await async_setup_component(hass, "automation", {"automation": bat["automation"]})
    await hass.async_block_till_done()

    for e in ("sensor.jarvis_recharge_reseau_prevue", "sensor.jarvis_gain_reel_du_jour",
              "sensor.jarvis_gain_reel_du_mois", "sensor.jarvis_gain_reel_de_l_annee"):
        assert hass.states.get(e) is not None, e
    for e in ("automation.jarvis_batterie_journal_du_gain_reel", "automation.jarvis_solcast_mises_a_jour_de_la_prevision"):
        assert hass.states.get(e) is not None and hass.states.get(e).state == "on", e
    assert all(a.state == "on" for a in hass.states.async_all("automation")), "automatisation invalide"
    assert hass.states.get("input_boolean.jarvis_solcast_pilote").state == "off"
    assert "Invalid config" not in caplog.text and "Error" not in caplog.text, caplog.text
