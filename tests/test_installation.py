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
    "connexion": True, "packages": True, "entites_manquantes": [], "capacite_kwh": "10.24", "solaire": True,
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
        {"connexion": True}, {"packages": True}, {"entites_manquantes": []}, {"capacite_kwh": 10.24}, {"solaire": True},
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


def test_batterie_sans_panneaux_pas_de_prevision_solaire_a_fournir():
    """Une batterie peut être installée sans panneaux : l'étape « prévision solaire » est alors faite d'office."""
    b = inst.evaluer(_ctx(solaire=False, prevision_solaire=False))
    assert b.etat == inst.EN_SIMULATION and b.suivante is None
    assert "prevision_solaire" in b.faites and "solaire" in b.faites
    # Avec des panneaux, la prévision reste obligatoire.
    assert inst.evaluer(_ctx(solaire=True, prevision_solaire=False)).suivante.cle == "prevision_solaire"


@pytest.mark.parametrize("valeur", [None, "", "unknown"])
def test_panneaux_question_posee_tant_qu_on_ne_sait_pas(valeur):
    b = inst.evaluer(_ctx(solaire=valeur))
    assert b.suivante.cle == "solaire" and b.etat == inst.A_CONFIGURER


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
            texte = issues[f"etape_{cle}"]
            assert texte["title"], (fichier, cle)
            # Une étape se règle soit par un lien (description), soit par des questions (fix_flow).
            if "fix_flow" in texte:
                assert "description" not in texte and texte["fix_flow"]["step"]["init"]["data"], (fichier, cle)
            else:
                assert "{lien}" in texte["description"], (fichier, cle)


def test_traductions_lisibles_par_home_assistant():
    """Home Assistant lit chaque texte avec string.Formatter : une accolade imbriquée ou seule
    le fait échouer (« Error while parsing localized string »)."""
    import json
    import pathlib
    import string

    racine = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "ucaness"
    fichiers = [racine / "strings.json", *sorted((racine / "translations").glob("*.json"))]

    def textes(o, chemin=""):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from textes(v, f"{chemin}.{k}")
        elif isinstance(o, str):
            yield chemin, o

    erreurs = []
    for f in fichiers:
        for chemin, texte in textes(json.loads(f.read_text(encoding="utf-8"))):
            try:
                list(string.Formatter().parse(texte))
            except ValueError as err:
                erreurs.append(f"{f.name}{chemin} : {err}")
    assert not erreurs, erreurs
