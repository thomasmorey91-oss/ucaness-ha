"""Tests du moteur de tarif dynamique (optimiseur.py), sans Home Assistant.

Données INVENTÉES : prix, consommation et production d'exemple, aucune mesure réelle.
"""
import datetime as dt
import importlib.util
import pathlib
import sys
import time
import zoneinfo

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ucaness_optimiseur", ROOT / "custom_components" / "ucaness" / "optimiseur.py")
opt = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = opt
spec.loader.exec_module(opt)

TZ = zoneinfo.ZoneInfo("Europe/Paris")
DEBUT = dt.datetime(2030, 1, 15, 0, 0, tzinfo=TZ)      # mardi inventé


def creneaux(prix, conso=1.0, solaire=None, debut=DEBUT, pas_min=60, vente=0.04):
    out = []
    for i, p in enumerate(prix):
        d = debut + dt.timedelta(minutes=pas_min * i)
        pv = solaire[i] if solaire else 0.0
        c = conso[i] if isinstance(conso, list) else conso * pas_min / 60
        out.append(opt.Creneau(d, d + dt.timedelta(minutes=pas_min), p, vente, c, pv))
    return out


def bat(stock=0.0, cap=10.0, p=3.0, eta=0.95):
    return opt.Batterie(capacite_utile_kwh=cap, stock_kwh=stock, rendement=eta, puissance_charge_kw=p)


def jour_type():
    """Nuit bon marché (0h-6h), journée moyenne, soirée chère (17h-22h)."""
    return [0.10] * 6 + [0.20] * 11 + [0.30] * 5 + [0.20] * 2


def verifier_plages(plan):
    assert len(plan.plages) <= 3
    for p in plan.plages:
        assert len(p["debut"]) == 4 and len(p["fin"]) == 4
        assert p["debut"] < p["fin"] or p["fin"] == "2359"


def test_prix_plats_aucune_charge():
    plan = opt.optimiser(creneaux([0.20] * 24), bat())
    assert plan.plages == []
    assert "Écart de prix insuffisant" in plan.justification
    assert plan.gain_eur == pytest.approx(0, abs=1e-6)


def test_charge_la_nuit_pour_le_soir():
    plan = opt.optimiser(creneaux(jour_type()), bat(), fuseau=TZ)
    verifier_plages(plan)
    assert plan.plages, plan.justification
    # Le stock ne monte que la nuit bon marché (0h-6h) ...
    stocks = [0.0] + plan.stocks
    assert all(stocks[h + 1] <= stocks[h] + 1e-6 for h in range(6, 24))
    assert stocks[6] == pytest.approx(10.0)      # batterie de 10 kWh remplie (0,10/0,95² < 0,20)
    # ... et la batterie est gardée pour couvrir toute la soirée chère (17h-22h).
    assert all(plan.achats_kwh[h] == pytest.approx(0) for h in range(17, 22))
    assert plan.recharge_reseau_kwh > 9
    assert plan.gain_eur > 1.0
    assert plan.cout_eur < plan.cout_autoconsommation_eur


def test_pas_de_charge_si_ecart_insuffisant_apres_pertes():
    prix = [0.19] * 6 + [0.20] * 18                # 0,20 × 0,95² = 0,1805 < 0,19
    plan = opt.optimiser(creneaux(prix), bat(), fuseau=TZ)
    assert plan.plages == []


def test_trois_plages_au_plus():
    prix = [0.05 if h % 2 == 0 else 0.40 for h in range(24)]
    plan = opt.optimiser(creneaux(prix), bat(cap=20, p=2), fuseau=TZ)
    verifier_plages(plan)
    assert len(plan.fenetres) <= 3


def test_fenetre_qui_passe_minuit_compte_double():
    debut = dt.datetime(2030, 1, 15, 20, 0, tzinfo=TZ)
    prix = [0.30, 0.30, 0.05, 0.05, 0.05, 0.05] + [0.30] * 18      # bon marché de 22h à 2h
    plan = opt.optimiser(creneaux(prix, debut=debut), bat(), fuseau=TZ)
    assert {"debut": "2200", "fin": "2359"} in plan.plages
    assert {"debut": "0000", "fin": "0200"} in plan.plages


def test_solaire_laisse_de_la_place():
    sans = opt.optimiser(creneaux(jour_type()), bat(), fuseau=TZ)
    solaire = [0.0] * 9 + [4.0] * 6 + [0.0] * 9        # 9h-15h : gros surplus
    avec = opt.optimiser(creneaux(jour_type(), solaire=solaire), bat(), fuseau=TZ)
    assert avec.recharge_reseau_kwh < sans.recharge_reseau_kwh - 2


def test_charge_interdite_sous_zero():
    plan = opt.optimiser(creneaux(jour_type()), bat(), fuseau=TZ, charge_interdite=True)
    assert plan.plages == [] and set(plan.actions) == {"auto"}


def test_batterie_pleine_gardee_pour_les_heures_cheres():
    """Batterie pleine à minuit : la nuit bon marché, la maison passe sur le réseau (plage de charge)
    pour garder la batterie pour le soir."""
    plan = opt.optimiser(creneaux(jour_type()), bat(stock=10), fuseau=TZ)
    assert plan.plages
    assert plan.recharge_reseau_kwh < 1.5
    assert plan.gain_eur > 0


def test_prix_negatif_maison_sur_le_reseau():
    prix = [0.20] * 12 + [-0.05] * 2 + [0.20] * 10
    plan = opt.optimiser(creneaux(prix), bat(stock=10), fuseau=TZ)
    assert {"debut": "1200", "fin": "1400"} in plan.plages


def test_reserve_de_secours():
    debut_r = DEBUT + dt.timedelta(hours=18)
    reserve = opt.Reserve(debut_r, debut_r + dt.timedelta(hours=6), stock_kwh=8.0)
    plan = opt.optimiser(creneaux([0.20] * 24), bat(stock=2), fuseau=TZ, reserves=[reserve])
    assert plan.plages
    i = 18
    assert min(plan.stocks[i:]) >= 7.9


def test_temps_de_calcul_48h_au_quart_d_heure():
    prix = [0.10 + 0.2 * ((i // 4) % 24 >= 17) for i in range(192)]
    t0 = time.perf_counter()
    plan = opt.optimiser(creneaux(prix, pas_min=15), bat(cap=12.0, p=3.0), fuseau=TZ)
    assert time.perf_counter() - t0 < 20
    verifier_plages(plan)


def test_debut_de_plage_arrondi_au_quart_d_heure():
    """Premier créneau raccourci à l'instant du calcul : la plage garde un début stable."""
    maintenant = DEBUT + dt.timedelta(minutes=7)
    cr = creneaux(jour_type())
    cr[0] = opt.Creneau(maintenant, cr[0].fin, cr[0].prix_achat, cr[0].prix_vente, cr[0].conso_kwh * 53 / 60, 0.0)
    plan = opt.optimiser(cr, bat(), fuseau=TZ)
    assert plan.plages and plan.plages[0]["debut"] in ("0000", "0100", "0200", "0300")
    assert plan.resume(maintenant)["fenetres"][0]["debut"].startswith("2030-01-15T0")


def test_resume_serialisable():
    plan = opt.optimiser(creneaux(jour_type()), bat(), fuseau=TZ)
    r = plan.resume(DEBUT)
    assert r["nombre_plages"] == len(r["plages"])
    assert r["prix_min"] == 0.10 and r["prix_max"] == 0.30
    assert len(r["detail"]) == 24


# --- Construction des créneaux -----------------------------------------------------------------
def test_construire_creneaux_solcast_et_profil():
    maintenant = dt.datetime(2030, 1, 15, 10, 20, tzinfo=TZ)
    prix = [{"start": (DEBUT + dt.timedelta(hours=h)).isoformat(), "price": 0.2} for h in range(48)]
    solcast = [{"period_start": (DEBUT + dt.timedelta(minutes=30 * i)).isoformat(), "pv_estimate": 2.0}
               for i in range(96)]                                    # 2 kW moyens par demi-heure
    profil = [0.5] * 24
    cr = opt.construire_creneaux(prix, profil, solcast, maintenant=maintenant, fuseau="Europe/Paris", marge=0.1)
    assert cr[0].debut == maintenant and cr[0].fin.hour == 11
    assert cr[0].solaire_kwh == pytest.approx(2.0 * 40 / 60)
    assert cr[1].solaire_kwh == pytest.approx(2.0)
    assert cr[1].conso_kwh == pytest.approx(0.55)
    assert cr[-1].fin == DEBUT + dt.timedelta(hours=48)


def test_construire_creneaux_horizon_borne_par_le_solaire():
    maintenant = DEBUT
    prix = [{"debut": (DEBUT + dt.timedelta(hours=h)).isoformat(), "prix": 0.2} for h in range(48)]
    sol = [{"debut": (DEBUT + dt.timedelta(hours=h)).isoformat(), "kwh": 1.0} for h in range(24)]
    cr = opt.construire_creneaux(prix, [0.5] * 24, sol, maintenant=maintenant, fuseau=TZ)
    assert len(cr) == 24


def test_construire_creneaux_donnees_manquantes():
    with pytest.raises(opt.DonneesManquantes):
        opt.construire_creneaux([], [0.5] * 24, [{"debut": DEBUT.isoformat(), "kwh": 1}], maintenant=DEBUT)
    with pytest.raises(opt.DonneesManquantes):
        opt.construire_creneaux([{"debut": DEBUT.isoformat(), "prix": 0.2}], [0.5] * 24, [], maintenant=DEBUT)


def test_construire_creneaux_quart_d_heure():
    prix = [{"start": (DEBUT + dt.timedelta(minutes=15 * i)).isoformat(),
             "end": (DEBUT + dt.timedelta(minutes=15 * (i + 1))).isoformat(), "price": 0.1} for i in range(96)]
    sol = [{"debut": (DEBUT + dt.timedelta(hours=h)).isoformat(), "kwh": 1.0} for h in range(24)]
    cr = opt.construire_creneaux(prix, [1.0] * 24, sol, maintenant=DEBUT, fuseau=TZ)
    assert len(cr) == 96
    assert cr[0].conso_kwh == pytest.approx(0.25) and cr[0].solaire_kwh == pytest.approx(0.25)


# --- Plan externe (EMHASS) -----------------------------------------------------------------------
def test_emhass_charge_reseau():
    assert opt.charge_reseau_emhass_kw(-3000, 3500) == pytest.approx(3.0)
    assert opt.charge_reseau_emhass_kw(-3000, 1000) == pytest.approx(1.0)   # le reste vient du solaire
    assert opt.charge_reseau_emhass_kw(2000, 0) == 0.0                       # décharge
    assert opt.charge_reseau_emhass_kw(-3000, -500) == 0.0                   # charge solaire seule


def test_plages_depuis_plan_emhass():
    plan = []
    for i in range(48):                                   # demi-heures à partir de 20h
        d = dt.datetime(2030, 1, 15, 20, 0, tzinfo=TZ) + dt.timedelta(minutes=30 * i)
        charge = 22 <= d.hour or d.hour < 2               # 22h-2h : charge réseau
        plan.append({"date": d.isoformat(), "p_batt": -3000 if charge else 500, "p_grid": 3500 if charge else 0})
    r = opt.plages_depuis_plan(plan, maintenant=dt.datetime(2030, 1, 15, 20, 5, tzinfo=TZ), fuseau=TZ)
    assert r["plages"] == [{"debut": "2200", "fin": "2359"}, {"debut": "0000", "fin": "0200"}]
    assert r["charge_reseau_kwh"] == pytest.approx(12.0)


def test_plages_depuis_plan_garde_les_plus_grosses():
    plan = []
    for h in range(24):
        d = DEBUT + dt.timedelta(hours=h)
        kw = {1: 3.0, 2: 3.0, 5: 1.0, 9: 2.0, 13: 3.0, 14: 3.0, 15: 3.0}.get(h, 0.0)
        plan.append({"debut": d.isoformat(), "charge_reseau_kw": kw})
    r = opt.plages_depuis_plan(plan, maintenant=DEBUT, fuseau=TZ)
    assert r["plages"] == [{"debut": "0100", "fin": "0300"}, {"debut": "0900", "fin": "1000"},
                           {"debut": "1300", "fin": "1600"}]
    assert r["charge_ecartee_kwh"] == pytest.approx(1.0)
