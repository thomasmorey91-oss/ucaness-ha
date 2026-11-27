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
    assert await async_setup_component(hass, "input_select", {"input_select": {**tarif["input_select"], **bat["input_select"]}})
    assert await async_setup_component(hass, "input_text", {"input_text": bat["input_text"]})
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


# --- Batterie sans panneaux solaires -------------------------------------------------------------
import pytest  # noqa: E402
from homeassistant.setup import async_setup_component  # noqa: E402
from homeassistant.util.yaml import load_yaml  # noqa: E402

PAQUETS = pathlib.Path(__file__).resolve().parent.parent / "packages"


@pytest.mark.parametrize(("choix", "total", "mppt1", "mppt2", "attendu"), [
    # Détection : jamais rien produit ET les deux MPPT à 0.
    ("Détection automatique", "0", "0", "0", "on"),
    ("Détection automatique", "1250.4", "0", "0", "off"),          # a déjà produit (la nuit, les MPPT sont à 0)
    ("Détection automatique", "0", "120", "0", "off"),             # un MPPT produit
    ("Détection automatique", "0", "0", "35", "off"),
    # Dans le doute, la maison est considérée avec panneaux (la prévision reste exigée).
    ("Détection automatique", "unknown", "0", "0", "off"),
    ("Détection automatique", "unavailable", "0", "0", "off"),
    ("Détection automatique", "0", "unavailable", "0", "off"),
    ("Détection automatique", "0", "0", "unknown", "off"),
    ("Détection automatique", None, "0", "0", "off"),              # capteur absent
    # Le choix de l'utilisateur passe avant la détection.
    ("Sans panneaux", "1250.4", "800", "600", "on"),
    ("Avec panneaux", "0", "0", "0", "off"),
])
async def test_sans_solaire(hass, choix, total, mppt1, mppt2, attendu):
    bat = load_yaml(str(PAQUETS / "jarvis_batterie.yaml"))
    assert await async_setup_component(hass, "input_select", {"input_select": {
        "jarvis_solaire": {**bat["input_select"]["jarvis_solaire"], "initial": choix}}})
    for entite, valeur in (("sensor.uhome_production_solaire_totale", total),
                           ("sensor.uhome_puissance_mppt_1", mppt1), ("sensor.uhome_puissance_mppt_2", mppt2)):
        if valeur is not None:
            hass.states.async_set(entite, valeur)
    sans_solaire = next(t for t in bat["template"] if "binary_sensor" in t and "triggers" not in t)
    assert await async_setup_component(hass, "template", {"template": [sans_solaire]})
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.jarvis_sans_solaire").state == attendu


async def test_sans_solaire_choix_absent_detection(hass):
    """Entrée absente (package batterie plus ancien) : détection, donc avec panneaux dans le doute."""
    bat = load_yaml(str(PAQUETS / "jarvis_batterie.yaml"))
    sans_solaire = next(t for t in bat["template"] if "binary_sensor" in t and "triggers" not in t)
    assert await async_setup_component(hass, "template", {"template": [sans_solaire]})
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.jarvis_sans_solaire").state == "off"
