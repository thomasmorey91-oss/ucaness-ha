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


# --- recharge de nuit ----------------------------------------------------------------------------
BATTERIE = t.Batterie(capacite_utile_kwh=10.0, rendement=0.95)
JOURNEE = lambda d: 1.0 if 7 <= d.hour < 22 else 0.1          # maison qui consomme le jour : 15 kWh en heures pleines


def test_recharge_de_nuit_estimee_pour_une_offre_a_heures_creuses():
    sans = t.evaluer(HPHC, _soutirage(365, JOURNEE), 6, aujourdhui=JOUR)
    avec = t.evaluer(HPHC, _soutirage(365, JOURNEE), 6, aujourdhui=JOUR, batterie=BATTERIE)
    assert sans.gain_recharge_nuit_eur_an == 0 and sans.cout_retenu_eur == sans.cout_annuel_eur
    # Chaque jour : 15,1 kWh en heures pleines (6h30-22h30), la batterie en fournit 10 × 0,95 = 9,5 kWh,
    # rechargés en heures creuses à 0,20 / 0,95² au lieu de 0,30.
    gain_jour = 9.5 * (0.30 - 0.20 / 0.95 ** 2)
    assert avec.gain_recharge_nuit_eur_an == pytest.approx(365 * gain_jour)
    assert avec.cout_annuel_eur == pytest.approx(sans.cout_annuel_eur)          # le coût mesuré reste donné
    assert avec.cout_retenu_eur == pytest.approx(sans.cout_annuel_eur - 365 * gain_jour)
    assert "estimation haute" in " ".join(avec.remarques)
    r = avec.resume()
    assert r["cout_annuel_eur"] < r["cout_annuel_tel_que_mesure_eur"] and r["gain_recharge_de_nuit_eur_an"] > 0


def test_recharge_de_nuit_limitee_par_le_besoin_du_jour():
    petite = lambda d: 0.2 if 7 <= d.hour < 22 else 0.1                         # 3,1 kWh en heures pleines (6h30-22h30)
    e = t.evaluer(HPHC, _soutirage(30, petite), 6, aujourdhui=JOUR, batterie=BATTERIE)
    assert e.gain_recharge_nuit_eur_an == pytest.approx(365 * 3.10 * (0.30 - 0.20 / 0.95 ** 2))


def test_recharge_de_nuit_non_comptee_si_elle_n_est_pas_rentable_ou_deja_active_ou_prix_unique():
    serree = t.Offre("Écart faible", t.HPHC, {6: 160.0}, {"hp": 0.21, "hc": 0.20}, plages_hc=(("22:30", "06:30"),))
    e = t.evaluer(serree, _soutirage(60, JOURNEE), 6, batterie=BATTERIE)
    assert e.gain_recharge_nuit_eur_an == 0 and "trop faible" in " ".join(e.remarques)
    assert t.evaluer(HPHC, _soutirage(60, JOURNEE), 6, batterie=BATTERIE, recharge_deja_active=True).gain_recharge_nuit_eur_an == 0
    assert t.evaluer(BASE, _soutirage(60, JOURNEE), 6, batterie=BATTERIE).gain_recharge_nuit_eur_an == 0
    mal = t.evaluer(HPHC, _soutirage(60, JOURNEE), 6, batterie=t.Batterie(0, 0.95))
    assert mal.gain_recharge_nuit_eur_an == 0 and "mal décrite" in " ".join(mal.remarques)


def test_meilleure_offre_change_avec_la_batterie():
    """Maison qui consomme le jour : sans batterie le prix unique gagne ; avec la recharge de nuit,
    l'offre à heures creuses passe devant, et le conseil est de changer de formule."""
    mesures = _soutirage(365, JOURNEE)
    sans = t.classer([BASE, HPHC], mesures, 6, contrat_actuel=BASE, aujourdhui=JOUR)
    assert sans["meilleure_offre"]["nom"] == "Prix unique" and sans["conseil"] == "garder_le_contrat_actuel"
    avec = t.classer([BASE, HPHC], mesures, 6, contrat_actuel=BASE, aujourdhui=JOUR, batterie=BATTERIE)
    assert avec["meilleure_offre"]["nom"] == "Nuit" and avec["conseil"] == "changer_de_formule"
    assert avec["meilleure_offre"]["ecart_avec_contrat_actuel_eur_an"] < 0
    assert avec["meilleure_offre"] == avec["classement"][0]


def test_conseils():
    mesures = _soutirage(365)
    assert t.classer([], mesures, 6)["conseil"] == "aucune_offre_evaluee"
    assert t.classer([BASE], mesures, 6)["conseil"] == "meilleure_offre_evaluee"
    moins_chere = t.Offre("Moins chère", t.BASE, {6: 140.0}, {"base": 0.24}, "Fournisseur D")
    assert t.classer([moins_chere], mesures, 6, contrat_actuel=BASE)["conseil"] == "changer_d_offre"


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


# --- Tempo ---------------------------------------------------------------------------------------
PRIX_TEMPO = {"bleu_hp": 0.16, "bleu_hc": 0.13, "blanc_hp": 0.19, "blanc_hc": 0.15, "rouge_hp": 0.70, "rouge_hc": 0.16}
TEMPO = t.Offre("Tempo", t.TEMPO, {6: 160.0}, PRIX_TEMPO, "Fournisseur T",
                source="https://exemple.invalid/grille-t", date_prix=dt.date(2030, 1, 20))
DEBUT_6H = LUNDI.replace(hour=6)


def test_tempo_heures_creuses_22h_6h():
    assert t.part_heures_creuses(LUNDI.replace(hour=22), TEMPO) == 1.0
    assert t.part_heures_creuses(LUNDI.replace(hour=5), TEMPO) == 1.0
    assert t.part_heures_creuses(LUNDI.replace(hour=6), TEMPO) == 0.0
    assert t.part_heures_creuses(LUNDI.replace(hour=21), TEMPO) == 0.0


def test_tempo_jour_de_6h_a_6h():
    assert t.jour_tempo(LUNDI.replace(hour=5)) == dt.date(2030, 1, 13)
    assert t.jour_tempo(LUNDI.replace(hour=6)) == dt.date(2030, 1, 14)


def test_tempo_sans_couleurs_jour_moyen_et_annee_reconstituee():
    # 1 kWh par heure : 16 kWh en heures pleines, 8 kWh en heures creuses par jour.
    e = t.evaluer(TEMPO, _soutirage(7, debut=DEBUT_6H), 6, aujourdhui=JOUR)
    attendu = 160 + 300 * (16 * 0.16 + 8 * 0.13) + 43 * (16 * 0.19 + 8 * 0.15) + 22 * (16 * 0.70 + 8 * 0.16)
    assert e.cout_annuel_eur == pytest.approx(attendu)
    assert any("Couleurs Tempo des jours mesurés inconnues" in r for r in e.remarques)
    assert any("300 jours bleus, 43 blancs, 22 rouges" in r for r in e.remarques)


def test_tempo_couleurs_connues_moyenne_par_couleur():
    # Jours rouges plus gourmands (2 kWh/h) que les bleus (1 kWh/h) ; pas de jour blanc mesuré.
    couleurs = {dt.date(2030, 1, 14) + dt.timedelta(days=i): ("rouge" if i in (1, 2) else "bleu") for i in range(5)}
    conso = lambda d: 2.0 if couleurs.get(t.jour_tempo(d)) == "rouge" else 1.0
    e = t.evaluer(TEMPO, _soutirage(5, conso, DEBUT_6H), 6, aujourdhui=JOUR, couleurs_tempo=couleurs)
    moyen = (3 * 24 + 2 * 48) / 5 / 24                       # kWh par heure d'un jour moyen (tous jours)
    attendu = (160 + 300 * (16 * 0.16 + 8 * 0.13) + 22 * (32 * 0.70 + 16 * 0.16)
               + 43 * (16 * moyen * 0.19 + 8 * moyen * 0.15))
    assert e.cout_annuel_eur == pytest.approx(attendu)
    assert any("Aucun jour blanc mesuré" in r for r in e.remarques)
    assert not any("sous-estimé" in r for r in e.remarques)
    # Coût mesuré : chaque heure au prix de sa couleur.
    mesure = 3 * (16 * 0.16 + 8 * 0.13) + 2 * (32 * 0.70 + 16 * 0.16)
    assert e.cout_energie_mesure_eur == pytest.approx(mesure)


def test_tempo_sans_jour_rouge_mesure_signale_la_sous_estimation():
    couleurs = {dt.date(2030, 1, 14) + dt.timedelta(days=i): "bleu" for i in range(3)}
    e = t.evaluer(TEMPO, _soutirage(3, debut=DEBUT_6H), 6, couleurs_tempo=couleurs)
    assert any("rouge" in r and "sous-estimé" in r for r in e.remarques)


def test_tempo_recharge_de_nuit_couleur_par_couleur():
    bat = t.Batterie(10.0, 0.95)
    e = t.evaluer(TEMPO, _soutirage(7, debut=DEBUT_6H), 6, batterie=bat)
    r2 = 0.95 ** 2
    deplace = min(16.0, 10.0 * 0.95)
    attendu = sum(n * deplace * max(0.0, PRIX_TEMPO[f"{c}_hp"] - PRIX_TEMPO[f"{c}_hc"] / r2)
                  for c, n in (("bleu", 300), ("blanc", 43), ("rouge", 22)))
    assert e.gain_recharge_nuit_eur_an == pytest.approx(attendu)
    # Bleu : 0,16 - 0,13 / 0,9025 = 0,016 € gagné par kWh, encore rentable ici.
    assert attendu > 22 * deplace * (0.70 - 0.16 / r2)


def test_tempo_jours_par_couleur_precises():
    offre = t.Offre("Tempo", t.TEMPO, {6: 160.0}, PRIX_TEMPO, jours_tempo={"bleu": 301, "blanc": 43, "rouge": 22})
    e = t.evaluer(offre, _soutirage(2, debut=DEBUT_6H), 6)
    assert any("301 jours bleus" in r for r in e.remarques)
    with pytest.raises(t.OffreInvalide):
        t.evaluer(t.Offre("Tempo", t.TEMPO, {6: 160.0}, PRIX_TEMPO, jours_tempo={"bleu": 300, "blanc": 43}),
                  _soutirage(2, debut=DEBUT_6H), 6)


def test_tempo_incomplet_ecarte():
    prix = dict(PRIX_TEMPO)
    del prix["rouge_hp"]
    with pytest.raises(t.OffreInvalide, match="rouge_hp"):
        t.evaluer(t.Offre("Tempo", t.TEMPO, {6: 160.0}, prix), _soutirage(2), 6)


def test_classer_avec_tempo():
    res = t.classer([BASE, HPHC, TEMPO], _soutirage(7, debut=DEBUT_6H), 6, aujourdhui=JOUR,
                    couleurs_tempo={dt.date(2030, 1, 15): "rouge"})
    assert {l["nom"] for l in res["classement"]} == {"Prix unique", "Nuit", "Tempo"}
    assert any("Tempo" in x for x in res["limites"])
