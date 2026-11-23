"""Cumuls du gain réel (mois, année) rendus par le vrai moteur de modèles de Home Assistant.

Home Assistant convertit un attribut rendu « 2026 » en nombre : le cumul de l'année doit
quand même retrouver l'année en cours et additionner les jours (anomalie du 20 au 22/11/2026,
où le cumul de l'année repartait de zéro chaque jour). Données inventées.
Usage : python -m pytest -q test_cumuls_gain.py
"""
import pathlib

import pytest
from homeassistant.helpers.template import Template
from homeassistant.util.yaml import load_yaml

PKG = pathlib.Path(__file__).resolve().parent.parent / "packages"


class _This:
    def __init__(self, state, attributes):
        self.state = state
        self.attributes = attributes


def _capteur(nom):
    bat = load_yaml(str(PKG / "jarvis_batterie.yaml"))
    for bloc in bat["template"]:
        for s in bloc.get("sensor", []):
            if s.get("unique_id") == nom:
                return s
    raise AssertionError(nom)


def _rendre(hass, texte, **v):
    return Template(texte, hass).async_render(v)


@pytest.mark.parametrize("nom,cle,valeur", [
    ("jarvis_gain_reel_annee", "annee", 2026),       # attribut relu comme nombre
    ("jarvis_gain_reel_annee", "annee", "2026"),
    ("jarvis_gain_reel_mois", "mois", "2026-11"),
])
async def test_cumul_additionne_le_nouveau_jour(hass, nom, cle, valeur):
    s = _capteur(nom)
    gain = {"valide": True, "gain": -0.05, "jour": "2026-11-22"}
    this = _This("-0.14", {cle: valeur, "dernier_jour": "2026-11-21", "jours_comptes": 3})
    assert float(_rendre(hass, s["state"], gain=gain, this=this)) == pytest.approx(-0.19)
    assert int(_rendre(hass, s["attributes"]["jours_comptes"], gain=gain, this=this)) == 4


async def test_cumul_annee_ne_compte_pas_deux_fois_le_meme_jour(hass):
    s = _capteur("jarvis_gain_reel_annee")
    gain = {"valide": True, "gain": -0.05, "jour": "2026-11-22"}
    this = _This("-0.19", {"annee": 2026, "dernier_jour": "2026-11-22", "jours_comptes": 4})
    assert float(_rendre(hass, s["state"], gain=gain, this=this)) == pytest.approx(-0.19)


async def test_cumul_annee_repart_de_zero_au_changement_d_annee(hass):
    s = _capteur("jarvis_gain_reel_annee")
    gain = {"valide": True, "gain": 0.40, "jour": "2027-01-01"}
    this = _This("12.5", {"annee": 2026, "dernier_jour": "2026-12-31", "jours_comptes": 44})
    assert float(_rendre(hass, s["state"], gain=gain, this=this)) == pytest.approx(0.40)
    assert int(_rendre(hass, s["attributes"]["jours_comptes"], gain=gain, this=this)) == 1
