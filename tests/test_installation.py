"""Tests de l'assistant d'installation (installation.py, Python pur). Données INVENTÉES.

Usage : pytest -p no:homeassistant -p no:socket tests/test_installation.py
"""
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ucaness_installation", ROOT / "custom_components" / "ucaness" / "installation.py")
inst = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = inst
spec.loader.exec_module(inst)

COMPLET = {
    "connexion": True, "packages": True, "entites_manquantes": [], "capacite_kwh": "10.24",
    "type_tarif": "Heures pleines / heures creuses", "prix_hp": "0.25", "prix_hc": "0.18",
    "jours_ouvres": True, "prevision_solaire": True, "notification": True,
    "simulation": True, "ecriture": False,
}


def _ctx(**changements):
    return {**COMPLET, **changements}


def test_installation_vide_commence_par_la_connexion():
    b = inst.evaluer({})
    assert b.etat == inst.A_CONFIGURER
    assert b.suivante.cle == "connexion"
    assert b.faites == [] and b.progression == 0
    assert b.restantes == list(inst.CLES)


def test_parcours_une_etape_a_la_fois_dans_l_ordre():
    ctx, ordre = {"entites_manquantes": ["sensor.uhome_soc"]}, []
    ajouts = [
        {"connexion": True}, {"packages": True}, {"entites_manquantes": []}, {"capacite_kwh": 10.24},
        {"type_tarif": "Base", "prix_hp": 0.25}, {"jours_ouvres": True}, {"prevision_solaire": True},
        {"notification": True},
    ]
    for ajout in ajouts:
        ordre.append(inst.evaluer(ctx).suivante.cle)
        ctx.update(ajout)
    assert ordre == list(inst.CLES)
    assert inst.evaluer(ctx).suivante is None


def test_complet_en_simulation():
    b = inst.evaluer(COMPLET)
    assert b.etat == inst.EN_SIMULATION and b.suivante is None
    assert b.progression == 100 and b.restantes == []


def test_complet_en_service():
    assert inst.evaluer(_ctx(simulation=False, ecriture=True)).etat == inst.EN_SERVICE


def test_mode_reel_sans_ecriture_a_verifier():
    assert inst.evaluer(_ctx(simulation=False, ecriture=False)).etat == inst.A_VERIFIER


def test_mode_reel_avec_une_etape_obligatoire_manquante_a_verifier():
    b = inst.evaluer(_ctx(simulation=False, ecriture=True, prevision_solaire=False))
    assert b.etat == inst.A_VERIFIER and b.suivante.cle == "prevision_solaire"


def test_simulation_inconnue_jamais_prise_pour_le_mode_reel():
    assert inst.evaluer(_ctx(simulation=None, ecriture=True)).etat == inst.EN_SIMULATION


def test_etape_facultative_ne_bloque_pas_et_passe_apres_les_obligatoires():
    b = inst.evaluer(_ctx(notification=False))
    assert b.etat == inst.EN_SIMULATION and b.suivante.cle == "notifications" and not b.suivante.obligatoire
    b = inst.evaluer(_ctx(notification=False, jours_ouvres=False))
    assert b.etat == inst.A_CONFIGURER and b.suivante.cle == "jours_ouvres"


@pytest.mark.parametrize("valeur", [None, "", "unknown", "unavailable", "0", 0, "abc", -1])
def test_capacite_absente_ou_nulle_non_faite(valeur):
    b = inst.evaluer(_ctx(capacite_kwh=valeur))
    assert b.suivante.cle == "batterie" and b.etat == inst.A_CONFIGURER


@pytest.mark.parametrize(("ctx", "fait"), [
    ({"type_tarif": "Base", "prix_hp": "0.25", "prix_hc": "0"}, True),
    ({"type_tarif": "Heures pleines / heures creuses", "prix_hp": "0.25", "prix_hc": "0"}, False),
    ({"type_tarif": "Heures pleines / heures creuses", "prix_hp": "0", "prix_hc": "0.18"}, False),
    ({"type_tarif": None, "prix_hp": "0.25", "prix_hc": "0.18"}, True),
    ({"type_tarif": None, "prix_hp": "0.25", "prix_hc": None}, False),
])
def test_contrat(ctx, fait):
    assert ("contrat" in inst.evaluer(_ctx(**ctx)).faites) is fait


def test_entites_manquantes_listees():
    b = inst.evaluer(_ctx(entites_manquantes=["sensor.uhome_soc", "binary_sensor.uhome_connexion_cloud"]))
    assert b.suivante.cle == "entites"
    assert b.attributs()["entites_manquantes"] == ["binary_sensor.uhome_connexion_cloud", "sensor.uhome_soc"]


def test_attributs_lisibles_par_un_tableau_de_bord_ou_un_agent():
    a = inst.evaluer(_ctx(jours_ouvres=False)).attributs()
    assert a["etape_suivante"]["cle"] == "jours_ouvres"
    assert a["etape_suivante"]["lien"].startswith("/_my_redirect/config_flow_start")
    assert a["etape_suivante"]["raison"] and a["etape_suivante"]["titre"]
    assert "jours_ouvres" in a["etapes_restantes"] and "connexion" in a["etapes_faites"]
    assert inst.evaluer(COMPLET).attributs()["etape_suivante"] is None


def test_chaque_etape_a_ses_textes():
    """Une réparation par étape : titre et description en français et en anglais."""
    import json

    for fichier in ("strings.json", "translations/fr.json", "translations/en.json"):
        issues = json.loads((ROOT / "custom_components" / "ucaness" / fichier).read_text())["issues"]
        for cle in inst.CLES:
            assert issues[f"etape_{cle}"]["title"] and "{lien}" in issues[f"etape_{cle}"]["description"], (fichier, cle)
