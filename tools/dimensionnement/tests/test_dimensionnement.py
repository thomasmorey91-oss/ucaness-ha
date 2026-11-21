"""Tests de l'outil de dimensionnement, avec des données INVENTÉES (aucune mesure réelle).

Usage : python -m pytest -q tools/dimensionnement/tests
Dépendances : numpy, pandas, pyyaml (pvlib et breos facultatifs).
"""
import importlib.util
import pathlib
import sys
import time

import numpy as np
import pandas as pd
import pytest

ICI = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dimensionnement", ICI.parent / "dimensionnement.py")
dim = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = dim
spec.loader.exec_module(dim)

TZ = "Europe/Paris"


def pv_synthetique(annees=(2021, 2022), facteur=1.0):
    """kWh par kWc et par heure (UTC) : cloche journalière, plus forte l'été, années un peu différentes."""
    out = []
    for k, a in enumerate(annees):
        idx = pd.date_range(f"{a}-01-01", f"{a}-12-31 23:00", freq="h", tz="UTC")
        jour = idx.day_of_year.to_numpy()
        h = idx.hour.to_numpy() + 1                      # ≈ heure locale d'hiver
        saison = 0.65 + 0.35 * np.cos((jour - 172) / 365 * 2 * np.pi)
        longueur = 8 + 8 * (saison - 0.3)
        cloche = np.clip(np.cos((h - 13) / longueur * np.pi), 0, None)
        out.append(pd.Series(0.75 * saison * cloche * facteur * (1 - 0.05 * k), index=idx))
    return pd.concat(out)


def conso_synthetique(annee=2025, kw_base=0.35, hiver_pct=0.6):
    idx = pd.date_range(f"{annee}-01-01", f"{annee}-12-31 23:00", freq="h", tz=TZ)
    h = idx.hour.to_numpy()
    hiver = 1 + hiver_pct * np.cos((idx.day_of_year.to_numpy() - 15) / 365 * 2 * np.pi)
    pointe = np.where((h >= 18) & (h <= 21), 0.9, 0.0) + np.where((h >= 7) & (h <= 8), 0.5, 0.0)
    return pd.Series((kw_base + pointe) * hiver, index=idx)


def cfg_exemple(**kw):
    base = dict(latitude=45.0, longitude=5.0, fuseau=TZ,
                toitures=[dim.Toiture("Sud", 3.0, 20, 0, 14, 6.0), dim.Toiture("Ouest", 0.0, 20, 90, 14, 3.0)],
                capacite_kwh=5.12, plancher_pct=10, rendement=0.95, puissance_batterie_kw=5.0,
                module_kwh=5.12, capacite_max_kwh=40.96, onduleur_kw=6.0, pv_max_onduleur_kwc=9.0, secours_kw=6.0,
                pas_pv_kwc=1.0, batterie_max_recherche_kwh=120)
    base.update(kw)
    return dim.Config(**base)


# --- Modèle de simulation -------------------------------------------------------------------------
def test_sans_batterie_bilan_exact():
    L = np.array([1.0, 1.0, 0.5, 0.2, 2.0])
    P = np.array([0.0, 2.0, 0.5, 1.0, 0.0])
    r = dim.simuler(L, P[None, :], [0.0], rendement=0.95, p_batterie_kw=5, p_onduleur_kw=10)
    assert r.achat[0, 0] == pytest.approx(3.0)
    assert r.revente[0, 0] == pytest.approx(1.8)


def test_scalaire_identique_au_vectoriel():
    L = conso_synthetique().to_numpy()[:2000]
    P = 3 * pv_synthetique().to_numpy()[:2000]
    for cap in (0.0, 4.6, 9.2):
        v = dim.simuler(L, P[None, :], [cap], rendement=0.95, p_batterie_kw=5, p_onduleur_kw=6).achat[0, 0]
        s = dim._achat_scalaire(list(L), list(P), cap, 0.95, 5, 6, 1e12)
        assert s == pytest.approx(v, rel=1e-9, abs=1e-9)


def test_ecretage_par_l_onduleur():
    L = np.zeros(3)
    P = np.array([8.0, 5.0, 0.0])
    r = dim.simuler(L, P[None, :], [0.0], rendement=1, p_batterie_kw=5, p_onduleur_kw=6)
    assert r.ecretage[0] == pytest.approx(2.0)
    assert r.revente[0, 0] == pytest.approx(11.0)


def test_capacite_autonomie_totale_cas_simple():
    """1 kWh/h de consommation, 3 kWh/h de solaire 12 h sur 24, sans pertes : 12 kWh pour la nuit."""
    jours = 10
    L = np.ones(24 * jours)
    P = np.tile(np.r_[np.zeros(6), np.full(12, 3.0), np.zeros(6)], jours)
    c = dim.capacite_autonomie_totale(L, [P], rendement=1.0, p_batterie_kw=10, p_onduleur_kw=10, cap_max=50)
    assert c == pytest.approx(12.0, abs=0.15)
    # Avec 95 % dans chaque sens, il faut un peu plus.
    c2 = dim.capacite_autonomie_totale(L, [P], rendement=0.95, p_batterie_kw=10, p_onduleur_kw=10, cap_max=50)
    assert c2 > 12.5


def test_autonomie_totale_impossible_sans_assez_de_solaire():
    L = np.ones(48)
    P = np.full(48, 0.5)
    assert dim.capacite_autonomie_totale(L, [P], rendement=1, p_batterie_kw=10, p_onduleur_kw=10, cap_max=500) is None


# --- Répartition du solaire ------------------------------------------------------------------------
def test_repartition_sur_les_pans_les_plus_productifs():
    cfg = cfg_exemple()
    rend = {"Sud": 1300, "Ouest": 1100}
    r, tient = dim.repartir(cfg, 7.0, rend)
    assert r == {"Sud": 6.0, "Ouest": 1.0} and tient
    r, tient = dim.repartir(cfg, 12.0, rend)
    assert not tient
    r, tient = dim.repartir(cfg, 1.5, rend)
    assert r["Sud"] == pytest.approx(1.5) and tient


# --- Lecture des fichiers ---------------------------------------------------------------------------
def test_lecture_historique_home_assistant(tmp_path):
    f = tmp_path / "ha.csv"
    f.write_text("entity_id,state,last_changed\n"
                 "sensor.puissance_maison,1000,2025-01-01T00:00:00.000Z\n"
                 "sensor.puissance_maison,2000,2025-01-01T00:30:00.000Z\n"
                 "sensor.puissance_maison,500,2025-01-01T01:00:00.000Z\n"
                 "sensor.puissance_maison,500,2025-01-01T01:59:00.000Z\n")
    s = dim.lire_serie_horaire(str(f), "W", "UTC")
    assert s.iloc[0] == pytest.approx(1.5)          # 30 min à 1 kW + 30 min à 2 kW
    assert s.iloc[1] == pytest.approx(0.5)


def test_lecture_courbe_de_charge_enedis(tmp_path):
    f = tmp_path / "enedis.csv"
    lignes = ["Identifiant PRM;Type de donnees;Date de debut;Date de fin;Grandeur physique;Grandeur metier;Etape metier;Unite;Pas en minutes",
              "00000000000000;Courbe de charge;01/01/2025;02/01/2025;Energie active;Consommation;Comptage Brut;W;",
              "Horodate;Valeur"]
    lignes += [f"2025-01-01T{h:02d}:{m:02d}:00+01:00;{800 if h < 12 else 400}" for h in range(24) for m in (30, 0)]
    f.write_text("\n".join(lignes))
    s = dim.lire_serie_horaire(str(f), "W", TZ)
    assert s.loc["2025-01-01 03:00"] == pytest.approx(0.8)
    assert s.loc["2025-01-01 15:00"] == pytest.approx(0.4)


def test_lecture_energie_en_kwh(tmp_path):
    f = tmp_path / "kwh.csv"
    f.write_text("date;kwh\n2025-03-01 00:00;0,25\n2025-03-01 00:15;0,25\n2025-03-01 00:30;0,25\n2025-03-01 00:45;0,25\n")
    s = dim.lire_serie_horaire(str(f), "kWh", TZ)
    assert s.iloc[0] == pytest.approx(1.0)


def test_calage_annee_pvgis_sur_les_dates_de_consommation():
    pv = pv_synthetique((2021,))
    idx = pd.date_range("2024-02-28", "2024-03-01 23:00", freq="h", tz=TZ)   # année bissextile
    v = dim.caler_sur_periode(pv, idx, 2021)
    assert len(v) == len(idx) and not np.isnan(v).any()
    assert v[24 + 13] == pytest.approx(v[13])                                # 29/02 = veille


# --- Analyse complète --------------------------------------------------------------------------------
def test_analyse_complete_et_rapport():
    cfg = cfg_exemple(prix_achat=0.25, prix_revente=0.04, cout_kwc=1500, cout_kwh=500, batterie_max_recherche_kwh=200)
    pv = {"Sud": pv_synthetique(), "Ouest": pv_synthetique(facteur=0.85)}
    t0 = time.perf_counter()
    an = dim.analyser(cfg, conso=conso_synthetique(kw_base=0.2, hiver_pct=-0.3), pv_kwc=pv)
    assert time.perf_counter() - t0 < 240
    ex = an.existant
    assert 0 < ex["autonomie"] < 1 and ex["autonomie_min"] <= ex["autonomie"]
    assert ex["conso_kwh"] == pytest.approx(conso_synthetique(kw_base=0.2, hiver_pct=-0.3).sum())
    # L'autonomie croît avec le solaire et la batterie.
    aut = 1 - an.achat.min(axis=0) / ex["conso_kwh"]
    assert (np.diff(aut, axis=1) >= -1e-9).all()
    # Autonomie totale : la batterie nécessaire baisse quand le solaire augmente.
    caps = [o["capacite_utile_kwh"] for o in an.autonomie_totale if o["capacite_utile_kwh"] is not None]
    assert caps and all(b <= a + 0.2 for a, b in zip(caps, caps[1:]))
    texte = dim.rapport(an)
    for titre in ("## 1. Installation existante", "## 2. Autonomie totale", "## 3. Autonomie élevée réaliste",
                  "## 4. Optimum économique", "### Secours", "## Hypothèses et limites"):
        assert titre in texte
    eco = dim.optimum_economique(an)
    assert eco and eco[0]["bilan"] >= eco[-1]["bilan"]
    assert len(dim.grille_csv(an)) == len(an.grille_pv) * len(an.grille_bat)


def test_contre_verification_breos():
    pytest.importorskip("breos")
    cfg = cfg_exemple()
    an = dim.analyser(cfg, conso=conso_synthetique(), pv_kwc={"Sud": pv_synthetique(), "Ouest": pv_synthetique()},
                      avec_breos=True)
    assert "erreur" not in an.breos, an.breos
    assert abs(an.breos["autonomie"] - an.existant["autonomie"]) < 0.1
    assert 80 < an.breos["soh_fin"] <= 100


def test_hiver_trop_long_stockage_saisonnier():
    """Consommation d'hiver forte : l'autonomie totale est hors de portée d'une batterie domestique."""
    cfg = cfg_exemple(batterie_max_recherche_kwh=60)
    an = dim.analyser(cfg, conso=conso_synthetique(), pv_kwc={"Sud": pv_synthetique(), "Ouest": pv_synthetique()})
    assert all(o["capacite_utile_kwh"] is None for o in an.autonomie_totale)
    assert "stockage saisonnier" in dim.rapport(an)


def test_ligne_de_commande_avec_cache_pvgis(tmp_path):
    """Chaîne complète hors ligne : configuration d'exemple, CSV de consommation, cache PVGIS."""
    import json
    import yaml

    conf = yaml.safe_load((ICI.parent / "exemple-installation.yaml").read_text(encoding="utf-8"))
    conf["pvgis"] = {"annees": [2021, 2022], "cache": "cache"}
    conf["recherche"] = {"pv_pas_kwc": 1.0, "batterie_max_kwh": 60}
    (tmp_path / "conf.yaml").write_text(yaml.safe_dump(conf, allow_unicode=True), encoding="utf-8")
    c = conso_synthetique(kw_base=0.25, hiver_pct=0.2) * 1000
    pd.DataFrame({"last_changed": c.index.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"), "state": c.values,
                  "entity_id": "sensor.puissance_maison"}).to_csv(tmp_path / "consommation.csv", index=False)
    cfg = dim.lire_config(tmp_path / "conf.yaml")
    (tmp_path / "cache").mkdir()
    for t in cfg.toitures:
        pv = pv_synthetique((2021, 2022))
        cle = f"pvgis_{cfg.latitude:.2f}_{cfg.longitude:.2f}_{t.inclinaison:g}_{t.azimut:g}_{t.pertes:g}_2021_2022.json"
        (tmp_path / "cache" / cle).write_text(json.dumps({"t": [x.isoformat() for x in pv.index], "kwh": pv.tolist()}))
    sortie = tmp_path / "rapport.md"
    assert dim.main([str(tmp_path / "conf.yaml"), "-o", str(sortie)]) == 0
    texte = sortie.read_text(encoding="utf-8")
    assert "## 1. Installation existante" in texte and "365 jours" in texte
    assert (tmp_path / "rapport.csv").exists()
