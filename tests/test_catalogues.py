"""Grilles horaires et offres de référence par pays (catalogue.py, formule « plages » de tarifs.py).

Mesures INVENTÉES ; grilles et prix tels que publiés (sources dans catalogue.py).
Usage : pytest -p no:homeassistant -p no:socket tests/test_catalogues.py
"""
import datetime as dt
import importlib
import pathlib
import sys
import types
import zoneinfo

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Paquet de test sans le __init__.py de l'intégration (qui demande Home Assistant).
_pkg = types.ModuleType("ucaness_cat")
_pkg.__path__ = [str(ROOT / "custom_components" / "ucaness")]
sys.modules["ucaness_cat"] = _pkg
t = importlib.import_module("ucaness_cat.tarifs")
c = importlib.import_module("ucaness_cat.catalogue")

MADRID, ROME, LISBONNE = (zoneinfo.ZoneInfo(z) for z in ("Europe/Madrid", "Europe/Rome", "Europe/Lisbon"))


def heure(tz, y, m, d, h, mi=0):
    return dt.datetime(y, m, d, h, mi, tzinfo=tz)


def niveau(offre, debut, feries=()):
    parts = t.repartition_niveaux(debut, offre, feries)
    assert sum(parts.values()) == pytest.approx(1.0)
    return {k: round(v, 3) for k, v in parts.items() if v}


def offre(structure, **prix):
    return c.offre_plages("Essai", structure, {6.0: 100.0}, prix, source="essai", date_prix=dt.date(2026, 11, 27))


ES = offre("es_2.0td", punta=0.30, llano=0.20, valle=0.10)
IT3 = offre("it_f1f2f3", f1=0.30, f2=0.25, f3=0.20)
IT2 = offre("it_f1f23", f1=0.30, f23=0.22)
PT_BI = offre("pt_bi_diario", vazio=0.11, fora_vazio=0.20)
PT_TRI = offre("pt_tri_diario", vazio=0.11, cheias=0.17, ponta=0.25)


@pytest.mark.parametrize("o", [ES, IT3, IT2, PT_BI, PT_TRI, *c.OFFRES_PT])
def test_grilles_lisibles_sans_chevauchement(o):
    t.verifier(o, next(iter(o.abonnement_eur_an)))


# ------------------------------------------------------------------ Espagne, 2.0TD
@pytest.mark.parametrize(("debut", "attendu"), [
    (heure(MADRID, 2026, 11, 23, 3), {"valle": 1}),       # lundi
    (heure(MADRID, 2026, 11, 23, 8), {"llano": 1}),
    (heure(MADRID, 2026, 11, 23, 10), {"punta": 1}),
    (heure(MADRID, 2026, 11, 23, 13), {"punta": 1}),
    (heure(MADRID, 2026, 11, 23, 14), {"llano": 1}),
    (heure(MADRID, 2026, 11, 23, 19), {"punta": 1}),
    (heure(MADRID, 2026, 11, 23, 22), {"llano": 1}),
    (heure(MADRID, 2026, 11, 23, 23), {"llano": 1}),
    (heure(MADRID, 2026, 11, 28, 11), {"valle": 1}),      # samedi
    (heure(MADRID, 2026, 11, 29, 19), {"valle": 1}),      # dimanche
])
def test_espagne_2_0td(debut, attendu):
    assert niveau(ES, debut) == attendu


def test_espagne_ferie_en_vallee():
    lundi_ferie = heure(MADRID, 2026, 12, 8, 11)
    assert niveau(ES, lundi_ferie, [dt.date(2026, 12, 8)]) == {"valle": 1}


# ------------------------------------------------------------------ Italie, F1 F2 F3
@pytest.mark.parametrize(("debut", "attendu"), [
    (heure(ROME, 2026, 11, 23, 6), {"f3": 1}),            # lundi
    (heure(ROME, 2026, 11, 23, 7), {"f2": 1}),
    (heure(ROME, 2026, 11, 23, 8), {"f1": 1}),
    (heure(ROME, 2026, 11, 23, 18), {"f1": 1}),
    (heure(ROME, 2026, 11, 23, 19), {"f2": 1}),
    (heure(ROME, 2026, 11, 23, 23), {"f3": 1}),
    (heure(ROME, 2026, 11, 28, 6), {"f3": 1}),            # samedi
    (heure(ROME, 2026, 11, 28, 10), {"f2": 1}),
    (heure(ROME, 2026, 11, 28, 23), {"f3": 1}),
    (heure(ROME, 2026, 11, 29, 10), {"f3": 1}),           # dimanche
])
def test_italie_f1f2f3(debut, attendu):
    assert niveau(IT3, debut) == attendu


def test_italie_ferie_en_f3_et_bioraria():
    assert niveau(IT3, heure(ROME, 2026, 12, 8, 10), [dt.date(2026, 12, 8)]) == {"f3": 1}
    assert niveau(IT2, heure(ROME, 2026, 11, 23, 10)) == {"f1": 1}
    assert niveau(IT2, heure(ROME, 2026, 11, 28, 10)) == {"f23": 1}
    assert niveau(IT2, heure(ROME, 2026, 11, 23, 20)) == {"f23": 1}


# ------------------------------------------------------------------ Portugal, cycle quotidien
@pytest.mark.parametrize(("debut", "attendu"), [
    (heure(LISBONNE, 2026, 1, 12, 3), {"vazio": 1}),              # hiver
    (heure(LISBONNE, 2026, 1, 12, 8), {"cheias": 1}),
    (heure(LISBONNE, 2026, 1, 12, 9), {"ponta": 1}),
    (heure(LISBONNE, 2026, 1, 12, 10), {"ponta": 0.5, "cheias": 0.5}),
    (heure(LISBONNE, 2026, 1, 12, 18), {"ponta": 1}),
    (heure(LISBONNE, 2026, 1, 12, 20), {"ponta": 0.5, "cheias": 0.5}),
    (heure(LISBONNE, 2026, 1, 12, 22), {"vazio": 1}),
    (heure(LISBONNE, 2026, 7, 13, 9), {"cheias": 1}),             # été
    (heure(LISBONNE, 2026, 7, 13, 10), {"cheias": 0.5, "ponta": 0.5}),
    (heure(LISBONNE, 2026, 7, 13, 12), {"ponta": 1}),
    (heure(LISBONNE, 2026, 7, 13, 13), {"cheias": 1}),
    (heure(LISBONNE, 2026, 7, 13, 19), {"cheias": 0.5, "ponta": 0.5}),
    (heure(LISBONNE, 2026, 7, 18, 12), {"ponta": 1}),             # samedi : même cycle
])
def test_portugal_tri_horaria(debut, attendu):
    assert niveau(PT_TRI, debut) == attendu


def test_portugal_bi_horaria_tous_les_jours():
    for jour in (12, 17, 18):                                     # lundi, samedi, dimanche
        assert niveau(PT_BI, heure(LISBONNE, 2026, 1, jour, 7)) == {"vazio": 1}
        assert niveau(PT_BI, heure(LISBONNE, 2026, 1, jour, 8)) == {"fora_vazio": 1}


def test_heure_legale_exige_un_fuseau():
    with pytest.raises(t.OffreInvalide, match="fuseau"):
        t.repartition_niveaux(dt.datetime(2026, 1, 12, 9), PT_TRI)


def test_chevauchement_refuse():
    mauvaise = t.Offre("Mauvaise", t.PLAGES, {6: 1.0}, {"a": 0.2, "b": 0.1},
                       regles=(t.Regle("a", "08:00", "12:00"), t.Regle("a", "11:00", "13:00")), niveau_defaut="b")
    with pytest.raises(t.OffreInvalide, match="chevauchent"):
        t.verifier(mauvaise, 6)


def test_prix_manquant_refuse():
    with pytest.raises(t.OffreInvalide, match="ponta"):
        t.verifier(offre("pt_tri_diario", vazio=0.11, cheias=0.17), 6.0)


# ------------------------------------------------------------------ évaluation
def jours_de(tz, debut: dt.date, n: int, kwh=1.0):
    return [(dt.datetime(debut.year, debut.month, debut.day, tzinfo=tz) + dt.timedelta(days=j, hours=h), kwh)
            for j in range(n) for h in range(24)]


def test_cout_portugal_tri_horaria_hiver():
    """1 kWh chaque heure, en hiver : 10 h de vazio, 4 h de ponta, 10 h de cheias par jour."""
    tri = c.OFFRES_PT[2]
    e = t.evaluer(tri, jours_de(LISBONNE, dt.date(2026, 1, 5), 31), 6.9, aujourdhui=dt.date(2026, 11, 27))
    par_jour = 10 * 0.1143 + 4 * 0.2553 + 10 * 0.1747
    assert e.cout_annuel_eur == pytest.approx(round(0.3659 * 365, 2) + par_jour * 365, rel=1e-6)
    assert e.kwh_hc_mesures == pytest.approx(10 * 31)
    assert any("hors TVA" in r for r in e.remarques)


def test_grille_portugaise_datee():
    e = t.evaluer(c.OFFRES_PT[1], jours_de(LISBONNE, dt.date(2027, 8, 2), 31), 6.9, aujourdhui=dt.date(2027, 9, 1))
    assert any("valable jusqu'au 2027-06-30" in r for r in e.remarques)


def test_recharge_dans_le_niveau_le_moins_cher():
    batterie = t.Batterie(5.0, 0.95)
    e = t.evaluer(ES, jours_de(MADRID, dt.date(2026, 11, 23), 5), 6.0, batterie=batterie)
    assert e.gain_recharge_nuit_eur_an > 0
    sans = t.evaluer(ES, jours_de(MADRID, dt.date(2026, 11, 23), 5), 6.0, batterie=batterie, recharge_deja_active=True)
    assert sans.gain_recharge_nuit_eur_an == 0


def test_classement_portugal():
    mesures = jours_de(LISBONNE, dt.date(2026, 1, 5), 31)
    r = t.classer(c.OFFRES_PT, mesures, 6.9, aujourdhui=dt.date(2026, 11, 27))
    assert {l["nom"] for l in r["classement"]} == {o.nom for o in c.OFFRES_PT}
    assert r["offres_ecartees"] == []


# ------------------------------------------------------------------ par pays
def test_offres_et_paliers_par_pays():
    assert c.offres_reference(None) == c.OFFRES_REFERENCE          # pays non réglé : France
    assert c.offres_reference("pt") == c.OFFRES_PT
    assert c.offres_reference("ES") == () and c.offres_reference("IT") == ()
    assert c.offres_reference("BR") == ()
    assert c.paliers("PT")[2] == 3.45 and c.paliers("ES") is None
    assert c.puissance_defaut("PT") in c.OFFRES_PT[0].abonnement_eur_an
    assert set(c.POURQUOI_SANS_OFFRE) == {"ES", "IT"}


def test_puissance_sans_paliers_connus():
    r = t.analyser_puissance([3.0, 3.2], 4.6, paliers=None)
    assert r["puissance_recommandee_kva"] == pytest.approx(3.6) and r["conseil"] == "baisser"
    assert any("paliers" in x for x in r["remarques"])
    r = t.analyser_puissance([3.0, 3.2], 6.9, paliers=c.paliers("PT"))
    assert r["puissance_recommandee_kva"] == 4.6           # 3,2 kVA + 10 % = 3,52 : palier suivant
