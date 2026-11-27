"""Tests du véhicule électrique (vehicules.py, Python pur). Prix et prévisions INVENTÉS.

Usage : pytest -p no:homeassistant -p no:socket tests/test_vehicules.py
"""
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import zoneinfo

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ucaness_vehicules", ROOT / "custom_components" / "ucaness" / "vehicules.py")
v = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v
spec.loader.exec_module(v)

TZ = zoneinfo.ZoneInfo("Europe/Paris")
MARDI_18H = dt.datetime(2030, 1, 15, 18, 0, tzinfo=TZ)        # mardi inventé
PRIX = dict(prix_hp=0.30, prix_hc=0.17, hc_debut=dt.time(23), hc_fin=dt.time(6), jours_non_ouvres_hc=True)


# ------------------------------------------------------------------ catalogue


def test_catalogue_lisible_et_coherent():
    cat = v.charger_catalogue()
    assert len(cat) > 500
    assert {x.gabarit for x in cat} <= set(v.GABARITS)
    assert all(x.capacite_kwh > 0 and x.ac_kw > 0 and x.phases in (1, 2, 3) for x in cat)
    assert len({x.id for x in cat}) == len(cat)


def test_catalogue_porte_sa_source_et_sa_licence():
    meta = json.loads(v.CATALOGUE.read_text(encoding="utf-8"))
    assert "OpenEV Data" in meta["source"] and "CDLA-Permissive-2.0" in meta["licence"]


def test_marques_et_modeles():
    cat = v.charger_catalogue()
    ms = v.marques(cat)
    assert ms == sorted(ms, key=str.casefold) and len(ms) > 20
    une = v.de_la_marque(cat, ms[0])
    assert une and all(x.marque == ms[0] for x in une)
    assert v.par_id(cat, une[0].id) == une[0]
    assert v.par_id(cat, "inconnu") is None
    assert str(une[0].annee) in une[0].libelle


@pytest.mark.parametrize("pays", ["FR", "DE", "IT", "ES", "PT"])
def test_meilleures_ventes_par_pays(pays):
    cat = v.charger_catalogue()
    ventes = v.meilleures_ventes(cat, pays)
    assert len(ventes) == 10
    assert all(m.gabarit in v.GABARITS for m in ventes)
    # Un modèle annoncé dans le catalogue doit y être trouvé (sinon la fiche a changé de nom).
    meta = json.loads(v.MEILLEURES_VENTES.read_text(encoding="utf-8"))["pays"][pays]["modeles"]
    assert [m["nom"] for m in meta if m["marque"] and not next(x for x in ventes if x.nom == m["nom"]).versions] == []
    assert v.source_ventes(pays)


def test_meilleures_ventes_autre_pays():
    assert v.meilleures_ventes(v.charger_catalogue(), "US") == [] and v.source_ventes(None) is None


# ------------------------------------------------------------------ énergie


def test_puissance_du_plus_lent():
    assert v.puissance_recharge_kw(11, 7.4) == 7.4
    assert v.puissance_recharge_kw(3.7, 7.4) == 3.7
    with pytest.raises(ValueError):
        v.puissance_recharge_kw(0, 7.4)


def test_energie_a_prendre():
    # 60 kWh de 20 à 80 % : 36 kWh dans la batterie, 40 kWh à la prise (90 %)
    assert v.energie_a_prendre_kwh(60, 20, 80) == pytest.approx(40)
    assert v.energie_a_prendre_kwh(60, 85, 80) == 0
    with pytest.raises(ValueError):
        v.energie_a_prendre_kwh(60, -1, 80)


def test_estimer_soc():
    # 50 kWh, 80 % au branchement, 100 km à 15 kWh/100 km : −30 points
    assert v.estimer_soc(80, 100, 15, 50) == pytest.approx(50)
    assert v.estimer_soc(10, 500, 20, 50) == 0


# ------------------------------------------------------------------ prix


def test_prix_heure():
    assert v.prix_heure(MARDI_18H, **PRIX) == (0.30, False)
    assert v.prix_heure(MARDI_18H.replace(hour=23, minute=30), **PRIX) == (0.17, True)
    assert v.prix_heure(MARDI_18H.replace(hour=5), **PRIX) == (0.17, True)
    samedi = MARDI_18H + dt.timedelta(days=4)
    assert v.prix_heure(samedi, **PRIX) == (0.17, True)
    assert v.prix_heure(samedi, **{**PRIX, "jours_non_ouvres_hc": False}) == (0.30, False)
    assert v.prix_heure(MARDI_18H.replace(hour=2), **PRIX, type_tarif_base=True) == (0.30, False)


# ------------------------------------------------------------------ plan


def _creneaux(depart, surplus=lambda t: 0.0):
    return v.creneaux_horaires(MARDI_18H, depart, lambda t: v.prix_heure(t, **PRIX), surplus)


def test_creneaux_horaires_jusqu_au_depart():
    depart = MARDI_18H.replace(hour=20, minute=30)
    cs = _creneaux(depart)
    assert [c.debut.hour for c in cs] == [18, 19, 20] and cs[-1].fin == depart


def test_plan_heures_creuses_et_batterie_tenue():
    depart = MARDI_18H + dt.timedelta(hours=13, minutes=30)     # mercredi 7h30
    plan = v.plan_recharge(14.8, 7.4, _creneaux(depart), depart, prix_solaire=0.04)
    assert plan.manque_kwh == 0
    assert plan.cout_eur == pytest.approx(14.8 * 0.17)
    assert len(plan.plages) == 1
    p = plan.plages[0]
    assert p.debut.hour == 23 and p.fin.hour == 1 and p.tenir_batterie_maison
    d = plan.en_dict()
    assert d["complet"] and d["part_solaire_pct"] == 0


def test_plan_solaire_d_abord():
    depart = MARDI_18H + dt.timedelta(days=1)                    # mercredi 18h
    soleil = lambda t: 8.0 if 11 <= t.hour < 14 else 0.0         # 3 h de surplus prévu
    plan = v.plan_recharge(20, 7.4, _creneaux(depart, soleil), depart, prix_solaire=0.04)
    # 3 h × 7,4 kW = 22,2 kWh possibles au soleil : tout au soleil, rien du réseau
    assert plan.solaire_kwh == pytest.approx(20)
    assert all(not p.tenir_batterie_maison and 11 <= p.debut.hour < 14 for p in plan.plages)
    assert plan.cout_eur == pytest.approx(20 * 0.04)


def test_plan_trop_court():
    depart = MARDI_18H + dt.timedelta(hours=2)
    plan = v.plan_recharge(30, 7.4, _creneaux(depart), depart, prix_solaire=0.04)
    assert plan.manque_kwh == pytest.approx(30 - 14.8)
    assert not plan.en_dict()["complet"]


def test_plan_ignore_les_creneaux_apres_le_depart():
    depart = MARDI_18H + dt.timedelta(hours=3)
    creneaux = _creneaux(depart + dt.timedelta(hours=10))
    plan = v.plan_recharge(5, 7.4, creneaux, depart, prix_solaire=0.04)
    assert all(p.fin <= depart for p in plan.plages)
