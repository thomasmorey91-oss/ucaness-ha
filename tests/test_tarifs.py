"""Tests du moteur « évaluer une offre » (tarifs.py, Python pur). Offres et mesures INVENTÉES.

Usage : pytest -p no:homeassistant -p no:socket tests/test_tarifs.py
"""
import datetime as dt
import importlib.util
import pathlib
import sys
import zoneinfo

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ucaness_tarifs", ROOT / "custom_components" / "ucaness" / "tarifs.py")
t = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = t
spec.loader.exec_module(t)

TZ = zoneinfo.ZoneInfo("Europe/Paris")
LUNDI = dt.datetime(2030, 1, 14, 0, 0, tzinfo=TZ)      # lundi inventé
JOUR = dt.date(2030, 2, 1)

BASE = t.Offre("Prix unique", t.BASE, {6: 150.0, 9: 190.0}, {"base": 0.25}, "Fournisseur A",
               source="https://exemple.invalid/grille-a", date_prix=dt.date(2030, 1, 20))
HPHC = t.Offre("Nuit", t.HPHC, {6: 160.0, 9: 200.0}, {"hp": 0.30, "hc": 0.20}, "Fournisseur B",
               plages_hc=(("22:30", "06:30"),), source="https://exemple.invalid/grille-b", date_prix=dt.date(2030, 1, 20))
WEEKEND = t.Offre("Nuit et week-end", t.HPHC, {6: 170.0}, {"hp": 0.32, "hc": 0.19}, "Fournisseur C",
                  plages_hc=(("23:00", "06:00"),), weekend_hc=True, source="https://exemple.invalid/grille-c",
                  date_prix=dt.date(2030, 1, 20))


def _soutirage(jours, kwh_par_heure=lambda d: 1.0, debut=LUNDI):
    return [(debut + dt.timedelta(hours=h), kwh_par_heure(debut + dt.timedelta(hours=h))) for h in range(24 * jours)]


# --- heures creuses ------------------------------------------------------------------------------
@pytest.mark.parametrize(("heure", "minute", "part"), [
    (12, 0, 0.0), (23, 0, 1.0), (3, 0, 1.0), (22, 0, 0.5), (6, 0, 0.5), (7, 0, 0.0), (22, 30, 1.0), (6, 30, 0.0),
])
def test_part_heures_creuses_plage_qui_passe_minuit(heure, minute, part):
    assert t.part_heures_creuses(LUNDI.replace(hour=heure, minute=minute), HPHC) == pytest.approx(part)


def test_part_heures_creuses_heure_a_cheval_sur_minuit():
    offre = t.Offre("x", t.HPHC, {6: 1.0}, {"hp": 0.3, "hc": 0.2}, plages_hc=(("23:45", "00:15"),))
    assert t.part_heures_creuses(LUNDI.replace(hour=23, minute=30), offre) == pytest.approx(0.5)


def test_part_heures_creuses_week_end_et_jour_ferie():
    samedi = LUNDI + dt.timedelta(days=5, hours=12)
    assert t.part_heures_creuses(samedi, WEEKEND) == 1.0
    assert t.part_heures_creuses(samedi, HPHC) == 0.0                      # offre sans week-end
    mardi_midi = LUNDI + dt.timedelta(days=1, hours=12)
    assert t.part_heures_creuses(mardi_midi, WEEKEND) == 0.0
    assert t.part_heures_creuses(mardi_midi, WEEKEND, [mardi_midi.date()]) == 1.0
    assert t.part_heures_creuses(mardi_midi, BASE) == 0.0


# --- coût ----------------------------------------------------------------------------------------
def test_evaluer_base_sur_une_annee():
    e = t.evaluer(BASE, _soutirage(365), 6, aujourdhui=JOUR)
    assert e.cout_annuel_eur == pytest.approx(150 + 365 * 24 * 0.25)
    assert e.fiabilite == t.FIABLE and e.remarques == []
    assert e.resume()["energie_eur_an"] == pytest.approx(2190.0)


def test_evaluer_hphc_compte_les_demi_heures():
    e = t.evaluer(HPHC, _soutirage(7), 6, aujourdhui=JOUR)
    # 8 h creuses par jour (22h30-6h30), 16 h pleines, 1 kWh par heure.
    assert e.kwh_hc_mesures == pytest.approx(7 * 8)
    assert e.cout_energie_mesure_eur == pytest.approx(7 * (8 * 0.20 + 16 * 0.30))
    assert e.cout_annuel_eur == pytest.approx(160 + 365 * (8 * 0.20 + 16 * 0.30))
    assert e.resume()["part_heures_creuses_pct"] == pytest.approx(33.3)


def test_evaluer_week_end_en_heures_creuses():
    e = t.evaluer(WEEKEND, _soutirage(7), 6, aujourdhui=JOUR)
    assert e.kwh_hc_mesures == pytest.approx(5 * 7 + 2 * 24)              # 7 h par jour ouvré, week-end entier


def test_evaluer_peu_de_jours_signale():
    e = t.evaluer(BASE, _soutirage(5), 6, aujourdhui=JOUR)
    assert e.fiabilite == t.INSUFFISANT and "règle de trois" in e.remarques[0]
    assert t.evaluer(BASE, _soutirage(60), 6, aujourdhui=JOUR).fiabilite == t.INDICATIF


def test_evaluer_prix_ancien_ou_sans_source_signale():
    vieille = t.Offre("Vieille", t.BASE, {6: 150.0}, {"base": 0.25}, date_prix=dt.date(2029, 6, 1))
    remarques = " ".join(t.evaluer(vieille, _soutirage(365), 6, aujourdhui=JOUR).remarques)
    assert "à revérifier" in remarques and "Source du prix non indiquée" in remarques
    sans_date = t.Offre("Sans date", t.BASE, {6: 150.0}, {"base": 0.25}, source="x")
    assert "Date du prix inconnue" in " ".join(t.evaluer(sans_date, _soutirage(365), 6, aujourdhui=JOUR).remarques)


def test_evaluer_ignore_les_mesures_absentes_sans_les_inventer():
    mesures = _soutirage(2)
    mesures[5] = (mesures[5][0], None)
    mesures[6] = (mesures[6][0], float("nan"))
    mesures[7] = (mesures[7][0], -1.0)
    e = t.evaluer(BASE, mesures, 6, aujourdhui=JOUR)
    assert e.kwh_mesures == pytest.approx(45) and e.jours_mesures == pytest.approx(45 / 24)


@pytest.mark.parametrize("offre", [
    t.Offre("Sans prix", t.BASE, {6: 150.0}, {}),
    t.Offre("Prix nul", t.BASE, {6: 150.0}, {"base": 0}),
    t.Offre("Sans HC", t.HPHC, {6: 150.0}, {"hp": 0.3}, plages_hc=(("22:00", "06:00"),)),
    t.Offre("Sans plage", t.HPHC, {6: 150.0}, {"hp": 0.3, "hc": 0.2}),
    t.Offre("Autre puissance", t.BASE, {9: 190.0}, {"base": 0.25}),
    t.Offre("Tempo", "tempo", {6: 150.0}, {"bleu": 0.2}),
    t.Offre("Heure fausse", t.HPHC, {6: 150.0}, {"hp": 0.3, "hc": 0.2}, plages_hc=(("25:00", "06:00"),)),
])
def test_offre_incomplete_ecartee_jamais_chiffree(offre):
    with pytest.raises(t.OffreInvalide):
        t.evaluer(offre, _soutirage(30), 6)


def test_aucune_mesure():
    with pytest.raises(t.OffreInvalide):
        t.evaluer(BASE, [], 6)


# --- classement ----------------------------------------------------------------------------------
def test_classer_par_cout_annuel_seul_critere():
    nuit = lambda d: 2.0 if (d.hour >= 23 or d.hour < 6) else 0.2        # maison qui recharge la nuit
    r = t.classer([BASE, HPHC, WEEKEND, t.Offre("Incomplète", t.BASE, {6: 1.0}, {})], _soutirage(365, nuit), 6,
                  contrat_actuel=BASE, aujourdhui=JOUR)
    noms = [l["nom"] for l in r["classement"]]
    couts = [l["cout_annuel_eur"] for l in r["classement"]]
    assert couts == sorted(couts) and [l["rang"] for l in r["classement"]] == [1, 2, 3]
    assert noms[0] == "Nuit et week-end" and noms[-1] == "Prix unique"
    assert r["classement"][-1]["ecart_avec_contrat_actuel_eur_an"] == 0
    assert r["classement"][0]["ecart_avec_contrat_actuel_eur_an"] < 0
    assert r["offres_ecartees"] == [{"nom": "Incomplète", "fournisseur": "", "raison": "prix « base » manquant"}]
    assert "coût annuel" in r["critere"] and r["limites"] and r["fiabilite"] == t.FIABLE


def test_classer_maison_qui_consomme_le_jour_prefere_le_prix_unique():
    jour = lambda d: 1.5 if 9 <= d.hour < 19 else 0.1
    r = t.classer([BASE, HPHC], _soutirage(365, jour), 6, aujourdhui=JOUR)
    assert r["classement"][0]["nom"] == "Prix unique" and r["contrat_actuel"] is None


# --- puissance souscrite -------------------------------------------------------------------------
@pytest.mark.parametrize(("pointe", "souscrite", "conseil", "recommandee"), [
    (4.9, 9, "baisser", 6), (5.6, 6, "augmenter", 9), (5.0, 6, "garder", 6), (8.5, 9, "augmenter", 12), (2.0, 6, "baisser", 3),
])
def test_analyser_puissance(pointe, souscrite, conseil, recommandee):
    r = t.analyser_puissance([1.0, pointe, 2.0] * 122, souscrite, mesure_fine=True)
    assert r["conseil"] == conseil and r["puissance_recommandee_kva"] == recommandee
    assert r["pointe_mesuree_kva"] == pointe and r["sur"] is True


def test_baisse_jamais_donnee_comme_sure_sans_annee_complete_ni_mesure_du_compteur():
    court = t.analyser_puissance([3.0] * 20, 9, mesure_fine=True)
    assert court["conseil"] == "baisser" and court["sur"] is False and "année complète" in court["remarques"][0]
    estime = t.analyser_puissance([3.0] * 365, 9, mesure_fine=False)
    assert estime["conseil"] == "baisser" and estime["sur"] is False and "prise TIC" in estime["remarques"][0]
    # Une hausse, elle, se signale tout de suite.
    assert t.analyser_puissance([8.9] * 3, 6)["sur"] is True


def test_analyser_puissance_sans_mesure():
    assert t.analyser_puissance([None, float("nan")], 6)["conseil"] == "inconnu"
