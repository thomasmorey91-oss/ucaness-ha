"""Traductions de l'intégration : complètes, cohérentes, et couvrant tout ce que le code affiche.

Le français (translations/fr.json) est la langue de référence : chaque autre langue doit avoir
exactement les mêmes clés, et chaque texte les mêmes paramètres {…}. strings.json (attendu en
anglais par les outils de Home Assistant) est une copie de translations/en.json.

Sans Home Assistant : pytest -p no:homeassistant -p no:socket tests/test_traductions.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

COMPOSANT = Path(__file__).resolve().parent.parent / "custom_components" / "ucaness"
TRADUCTIONS = COMPOSANT / "translations"
REFERENCE = "fr"
PARAMETRE = re.compile(r"\{(\w+)\}")


def _charger(chemin: Path) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8"))


def _aplatir(d: dict, prefixe: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for cle, valeur in d.items():
        chemin = f"{prefixe}.{cle}" if prefixe else cle
        if isinstance(valeur, dict):
            out.update(_aplatir(valeur, chemin))
        else:
            out[chemin] = valeur
    return out


REF = _aplatir(_charger(TRADUCTIONS / f"{REFERENCE}.json"))
LANGUES = sorted(p.stem for p in TRADUCTIONS.glob("*.json") if p.stem != REFERENCE)


def test_langues_presentes():
    assert "en" in LANGUES


@pytest.mark.parametrize("langue", LANGUES)
def test_memes_cles_que_le_francais(langue):
    autre = _aplatir(_charger(TRADUCTIONS / f"{langue}.json"))
    assert sorted(set(REF) - set(autre)) == [], f"{langue}.json : clés manquantes"
    assert sorted(set(autre) - set(REF)) == [], f"{langue}.json : clés absentes du français"


@pytest.mark.parametrize("langue", LANGUES)
def test_memes_parametres_que_le_francais(langue):
    autre = _aplatir(_charger(TRADUCTIONS / f"{langue}.json"))
    ecarts = {
        cle: (sorted(set(PARAMETRE.findall(REF[cle]))), sorted(set(PARAMETRE.findall(autre[cle]))))
        for cle in REF
        if cle in autre and set(PARAMETRE.findall(REF[cle])) != set(PARAMETRE.findall(autre[cle]))
    }
    assert ecarts == {}


@pytest.mark.parametrize("langue", [REFERENCE, *LANGUES])
def test_aucun_texte_vide(langue):
    vides = [cle for cle, texte in _aplatir(_charger(TRADUCTIONS / f"{langue}.json")).items() if not str(texte).strip()]
    assert vides == []


def test_strings_json_identique_a_l_anglais():
    assert _charger(COMPOSANT / "strings.json") == _charger(TRADUCTIONS / "en.json")


def _source(nom: str) -> str:
    return (COMPOSANT / nom).read_text(encoding="utf-8")


def test_toutes_les_entites_ont_un_nom_traduit():
    attendus = {f"entity.sensor.{k}.name" for k in re.findall(r'Measure\("(\w+)"', _source("parser.py"))}
    attendus |= {f"entity.binary_sensor.{k}.name" for k in re.findall(r'Check\("(\w+)"', _source("binary_sensor.py"))}
    attendus |= {
        f"entity.{type_.lower()}.{cle}.name"
        for cle, type_ in re.findall(r'Reglage\("(\w+)", (NUMBER|SELECT|TIME|SWITCH)\b', _source("reglages.py"))
    }
    attendus.add("entity.sensor.installation.name")
    assert len(attendus) > 60
    assert sorted(attendus - set(REF)) == []


def test_etats_traduits():
    etats = re.search(r"ETATS = \(([^)]*)\)", _source("installation.py")).group(1)
    valeurs = dict(re.findall(r'^(\w+) = "(\w+)"', _source("installation.py"), re.M))
    for nom in (n.strip() for n in etats.split(",") if n.strip()):
        assert f"entity.sensor.installation.state.{valeurs[nom]}" in REF
    for cle in re.search(r'cles_options=\(([^)]*)\)', _source("reglages.py")).group(1).replace('"', "").split(","):
        assert f"entity.select.type_tarif.state.{cle.strip()}" in REF
        assert f"selector.type_tarif.options.{cle.strip()}" in REF


def test_toutes_les_erreurs_ont_un_message_traduit():
    code = "".join(_source(f.name) for f in COMPOSANT.glob("*.py"))
    cles = set(re.findall(r'translation_key="(\w+)"', code)) | set(re.findall(r'"(reglage_\w+)"', code))
    cles |= set(re.findall(r'"((?:plages|mode)_(?:non_\w+|relecture_impossible))"', code))
    cles -= {"type_tarif", "marque_vehicule", "gabarit", "phases"}   # clés de sélecteur
    assert len(cles) > 10
    assert sorted(f"exceptions.{c}.message" for c in cles if f"exceptions.{c}.message" not in REF) == []


def test_plus_de_nom_en_dur_dans_les_entites():
    for nom in ("sensor.py", "binary_sensor.py", "entite_reglage.py", "select.py", "number.py", "time.py", "switch.py"):
        assert not re.search(r"_attr_name\s*=", _source(nom)), nom
