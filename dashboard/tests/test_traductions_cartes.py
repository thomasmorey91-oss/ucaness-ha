"""Traductions des cartes (ucaness-cards.js) : complètes, cohérentes, et couvrant ce que le code affiche.

Le bloc UC_I18N est du JSON strict entre les marqueurs I18N-DEBUT et I18N-FIN. Le français est la
référence : chaque autre langue a exactement les mêmes clés, et chaque texte les mêmes paramètres {…}.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

JS = pathlib.Path(__file__).resolve().parents[1] / "www" / "ucaness" / "ucaness-cards.js"
SOURCE = JS.read_text(encoding="utf-8")
BLOC = json.loads(re.search(r"/\* I18N-DEBUT \*/(.*?)/\* I18N-FIN \*/", SOURCE, re.S).group(1))
REF = BLOC["fr"]
PARAMETRE = re.compile(r"\{(\w+)\}")
LANGUES = [l for l in BLOC if l != "fr"]


def test_sept_langues():
    assert sorted(BLOC) == ["de", "en", "es", "fr", "it", "pt", "zh-Hans"]


@pytest.mark.parametrize("langue", LANGUES)
def test_memes_cles_et_parametres_que_le_francais(langue):
    autre = BLOC[langue]
    assert sorted(set(REF) ^ set(autre)) == []
    ecarts = {k: (REF[k], autre[k]) for k in REF if set(PARAMETRE.findall(REF[k])) != set(PARAMETRE.findall(autre[k]))}
    assert ecarts == {}
    assert [k for k, v in autre.items() if not v.strip()] == []


def _code_sans_dictionnaire() -> str:
    return SOURCE.replace(re.search(r"/\* I18N-DEBUT \*/.*?/\* I18N-FIN \*/", SOURCE, re.S).group(0), "")


def _appels_uct(code: str) -> list[str]:
    """Texte de chaque appel ucT(...), parenthèses imbriquées comprises."""
    appels = []
    for m in re.finditer(r"\bucT\(", code):
        i, profondeur = m.end(), 1
        while profondeur and i < len(code):
            profondeur += {"(": 1, ")": -1}.get(code[i], 0)
            i += 1
        appels.append(code[m.end():i - 1])
    return appels


def test_toute_cle_utilisee_existe():
    code = _code_sans_dictionnaire()
    appels = _appels_uct(code)
    assert len(appels) > 80
    utilisees = {k for a in appels for k in re.findall(r"(?<!=== )'(\w+)'", a) if not k.endswith("_")}   # pas les comparaisons (=== 'out')
    # clés composées dans le code : préfixe + valeur connue
    utilisees |= {f"borne_{k}" for k in re.findall(r"\bB\('(\w+)'\)", code)}
    utilisees |= {f"fiab_{k}" for k in ("fiable", "indicatif", "insuffisant")}
    utilisees |= {f"puissance_{k}" for k in ("garder", "baisser", "augmenter")}
    # outils de la scène vivante (0.11.0) : outil_…, anim_…, visite_…
    utilisees |= {f"outil_{k}" for k in ("infos", "visite", "animations", "replay", "cinema")}
    utilisees |= {f"anim_{k}" for k in ("ucan", "ciel", "bandeau", "reflet")}
    utilisees |= {f"visite_{k}" for k in ("solaire", "reseau", "batterie", "maison", "borne")}
    assert sorted(k for k in utilisees if k not in REF) == []


def test_cles_inutilisees():
    """Une clé du dictionnaire que plus rien n'utilise est à retirer."""
    code = SOURCE.replace(re.search(r"/\* I18N-DEBUT \*/.*?/\* I18N-FIN \*/", SOURCE, re.S).group(0), "")
    inutiles = [k for k in REF if f"'{k}'" not in code and not any(
        k.startswith(p) and f"'{p}" in code for p in ("borne_", "fiab_", "puissance_", "carte_", "outil_", "anim_", "visite_"))]
    assert inutiles == []
