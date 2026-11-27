"""Contrôles des ajouts v7 du package batterie, joués avec le moteur de modèles de Home Assistant.

Données INVENTÉES (batterie de 10,24 kWh, prix d'exemple) : aucune mesure réelle.
Usage : python pilotage/tests/test_v7.py [chemin/jarvis_batterie.yaml]
Dépendances : homeassistant, freezegun, pyyaml.
"""
import asyncio
import datetime as dt
import pathlib
import sys
import tempfile
import zoneinfo

import yaml
from freezegun import freeze_time
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import template as tpl
from homeassistant.helpers.script_variables import ScriptVariables

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import test_calcul as base  # noqa: E402  (jeu d'essai de la v6)

PAQUET = pathlib.Path(__file__).resolve().parent.parent / "packages" / "jarvis_batterie.yaml"
TZ = zoneinfo.ZoneInfo("Europe/Paris")
JOUR = base.JOUR                                   # mardi 15/01/2030
ETATS = {
    "input_number.jarvis_batterie_capacite": "10.24", "input_number.jarvis_batterie_plancher": "15",
    "input_number.jarvis_batterie_rendement": "95", "input_number.jarvis_batterie_puissance_charge": "3",
    "input_number.jarvis_batterie_marge": "10", "input_number.jarvis_conso_journaliere": "0",
    "input_number.jarvis_prix_hp": "0.25", "input_number.jarvis_prix_hc": "0.18",
    "input_number.jarvis_prix_injection": "0.04", "input_select.jarvis_type_tarif": "Heures pleines / heures creuses",
    "input_boolean.jarvis_hc_jours_non_ouvres": "on",
    "input_datetime.jarvis_hc_debut": "23:00:00", "input_datetime.jarvis_hc_fin": "06:00:00",
    "sensor.uhome_soc": "15", "sensor.uhome_temperature_batterie": "20",
    "sensor.solcast_pv_forecast_derniere_interrogation_de_l_api": "2030-01-14T16:30:00+00:00",
}


def paquet():
    return yaml.safe_load(open(CHEMIN, encoding="utf-8"))


async def nouveau_hass(d, etats):
    hass = HomeAssistant(d)
    await hass.config.async_set_time_zone("Europe/Paris")
    for k, v in etats.items():
        hass.states.async_set(k, v)
    return hass


# --- Calcul de la recharge ------------------------------------------------------------------------
async def calcul(quand, prevision, mesures, ouvre=True, etats_en_plus=None):
    with tempfile.TemporaryDirectory() as d:
        hass = await nouveau_hass(d, {**ETATS, **(etats_en_plus or {})})
        for capteur in ("sensor.solcast_pv_forecast_prevision_demain", "sensor.solcast_pv_forecast_prevision_aujourdhui"):
            hass.states.async_set(capteur, "0", {"detailedHourly": prevision})
        actions = paquet()["template"][0]["actions"]
        v1 = actions[0]["variables"]
        v2 = next(a["variables"] for a in actions[1:] if "variables" in a)
        with freeze_time(quand):
            r1 = ScriptVariables({k: tpl.Template(v, hass) for k, v in v1.items()}).async_render(hass, {})
            run = {**r1, "jour": {"binary_sensor.workday_sensor": {"workday": ouvre}}, "mesures": mesures}
            r = ScriptVariables({k: tpl.Template(v, hass) if isinstance(v, str) else v for k, v in v2.items()}).async_render(hass, run)
        await hass.async_stop(force=True)
        return r


def prevision(jour=JOUR, facteur=1.0):
    return [{"period_start": dt.datetime.combine(jour, dt.time(h), TZ).isoformat(), "pv_estimate": v * facteur,
             "pv_estimate10": v * facteur * 0.6, "pv_estimate90": v * facteur * 1.3}
            for h, v in base.SOLAIRE.items()]


def mesures_deux_jours():
    """Deux mardis : le plus récent à 2 000 W toute la journée, le plus ancien à 1 000 W."""
    lignes = []
    for semaines, w in ((1, 2000), (2, 1000)):
        d = JOUR - dt.timedelta(days=7 * semaines)
        lignes += [{"start": dt.datetime.combine(d, dt.time(h), TZ).isoformat(), "mean": w} for h in range(24)]
    return {"statistics": {"sensor.uhome_puissance_maison": lignes}}


# --- Gain réel ------------------------------------------------------------------------------------
HP, HC, INJ, ETA, CAP_B, PL = 0.25, 0.18, 0.04, 0.95, 10.24, 15
DEB = dt.datetime.combine(JOUR - dt.timedelta(days=1), dt.time(23), TZ)
CHARGE = [1.0] * 24                                          # kW, de 23h à 22h
SOLAIRE = [0.0] * 11 + [3.0] * 6 + [0.0] * 7                 # 10h-15h (indices 11 à 16)


def prix(i):
    h = (23 + i) % 24
    return HC if (h >= 23 or h < 6) else HP


def autoconsommation(stock, recharge=0.0):
    """Simulation de référence, écrite indépendamment du package. recharge : énergie prise sur le
    réseau de 4h à 6h (moitié par heure), la maison étant alors alimentée par le réseau."""
    cap = CAP_B * (1 - PL / 100)
    cout, achats, injections = 0.0, [], []
    for i in range(24):
        net = SOLAIRE[i] - CHARGE[i]
        if recharge and i in (5, 6):
            g = min(recharge / 2, (cap - stock) / ETA)
            stock += g * ETA
            achats.append(CHARGE[i] + g)
            injections.append(0.0)
            cout += (CHARGE[i] + g) * prix(i)
            continue
        if net >= 0:
            c = min(net, (cap - stock) / ETA)
            stock += c * ETA
            cout -= (net - c) * INJ
            achats.append(0.0)
            injections.append(net - c)
        else:
            d = min(-net, stock * ETA)
            stock -= d / ETA
            achats.append(-net - d)
            injections.append(0.0)
            cout += (-net - d) * prix(i)
    return cout, stock, achats, injections


def stats(soutirage, soc0, soc1, injection=None, compteur_injection=None, fictive=None):
    """compteur_injection : variations horaires du compteur d'injection de l'onduleur (absent si None).
    fictive : injection fictive ajoutée à l'estimation (puissance réseau moyenne trop basse, comme
    quand la puissance est « inconnue » une partie de l'heure)."""
    injection = injection or [0.0] * 24
    fictive = fictive or [0.0] * 24
    t = lambda i: (DEB + dt.timedelta(hours=i)).isoformat()
    moy = {"sensor.uhome_puissance_maison": [{"start": t(i), "mean": CHARGE[i] * 1000} for i in range(24)],
           # Comme sur un UHome 6K : pas de valeur MPPT la nuit (ni statistique).
           "sensor.uhome_puissance_mppt_1": [{"start": t(i), "mean": SOLAIRE[i] * 600} for i in range(8, 19)],
           "sensor.uhome_puissance_mppt_2": [{"start": t(i), "mean": SOLAIRE[i] * 400} for i in range(8, 19)],
           "sensor.uhome_puissance_reseau": [{"start": t(i), "mean": (soutirage[i] - injection[i] - fictive[i]) * 1000} for i in range(24)],
           "sensor.uhome_soc": [{"start": t(-1), "mean": soc0}] + [{"start": t(i), "mean": 50} for i in range(23)]
           + [{"start": t(23), "mean": soc1}]}
    cpt = {"sensor.uhome_soutirage_reseau_total": [{"start": t(i), "change": soutirage[i]} for i in range(24)]}
    if compteur_injection is not None:
        cpt["sensor.uhome_injection_reseau_totale"] = [{"start": t(i), "change": compteur_injection[i]}
                                                       for i in range(24) if compteur_injection[i] is not None]
    return {"statistics": moy}, {"statistics": cpt}


async def gain(soutirage, soc0, soc1, injection=None, quand="2030-01-15 22:25:00", compteur_injection=None, fictive=None):
    with tempfile.TemporaryDirectory() as d:
        hass = await nouveau_hass(d, ETATS)
        bloc = next(b for b in paquet()["template"]
                    if any(t.get("event_type") == "jarvis_calcul_gain" for t in b.get("triggers", [])))
        v1 = bloc["actions"][0]["variables"]
        v2 = bloc["actions"][-1]["variables"]
        moy, cpt = stats(soutirage, soc0, soc1, injection, compteur_injection, fictive)
        with freeze_time(quand):
            r1 = ScriptVariables({k: tpl.Template(v, hass) for k, v in v1.items()}).async_render(hass, {})
            run = {**r1, "jour_debut": {"binary_sensor.workday_sensor": {"workday": True}},
                   "jour_fin": {"binary_sensor.workday_sensor": {"workday": True}}, "moyennes": moy, "compteurs": cpt}
            g = ScriptVariables({k: tpl.Template(v, hass) for k, v in v2.items()}).async_render(hass, run)["gain"]
            capteurs = {c["name"]: c for c in bloc["sensor"]}
            mois = capteurs["Jarvis gain réel du mois"]
            rendu = {}
            for nom, this in (("vide", State("sensor.x", "unknown", {})),
                              ("deja", State("sensor.x", "10.0", {"mois": g["jour"][:7], "dernier_jour": g["jour"], "jours_comptes": 3})),
                              ("suite", State("sensor.x", "10.0", {"mois": g["jour"][:7], "dernier_jour": "2030-01-14", "jours_comptes": 3})),
                              ("nouveau_mois", State("sensor.x", "10.0", {"mois": "2029-12", "dernier_jour": "2029-12-31", "jours_comptes": 31}))):
                v = {"gain": g, "this": this}
                rendu[nom] = (tpl.Template(mois["state"], hass).async_render(v),
                              tpl.Template(mois["attributes"]["jours_comptes"], hass).async_render(v))
        await hass.async_stop(force=True)
        return g, rendu


def stock(soc):
    return max(0.0, (soc - PL) / 100 * CAP_B)


def verifier():
    # 1. Prévision solaire absente ou d'un autre jour : aucune recharge, calcul invalide.
    for nom, prev in (("absente", []), ("d'un autre jour", prevision(JOUR - dt.timedelta(days=2)))):
        r = asyncio.run(calcul(base.SOIR, prev, base.statistiques()))
        c = r["calcul"]
        assert c["recharge_kwh"] == 0 and c["calcul_valide"] is False, (nom, c)
        assert c["justification"].startswith("Prévision solaire indisponible"), c["justification"]
        assert r["pv_info"]["ok"] is False
        print(f"Prévision {nom} :", c["justification"])

    # 1 bis. Batterie sans panneaux solaires : pas de prévision à attendre, la recharge en heures
    # creuses est calculée avec une production nulle. Le repli sûr des maisons avec panneaux
    # (« inconnu » compris) est inchangé.
    sans = {"binary_sensor.jarvis_sans_solaire": "on"}
    r = asyncio.run(calcul(base.SOIR, [], base.statistiques(), etats_en_plus=sans))
    c = r["calcul"]
    assert r["pv_info"]["ok"] is True and r["pv_info"]["sans_solaire"] is True and r["pv_h"] == [0.0] * 24
    assert c["calcul_valide"] is True and c["recharge_kwh"] > 0 and c["solaire_prevu_kwh"] == 0, c
    avec = asyncio.run(calcul(base.SOIR, prevision(), base.statistiques()))["calcul"]
    assert c["recharge_kwh"] >= avec["recharge_kwh"], (c["recharge_kwh"], avec["recharge_kwh"])
    # Une prévision Solcast présente n'est pas lue quand il n'y a pas de panneaux.
    r2 = asyncio.run(calcul(base.SOIR, prevision(), base.statistiques(), etats_en_plus=sans))
    assert r2["pv_h"] == [0.0] * 24 and r2["calcul"]["recharge_kwh"] == c["recharge_kwh"]
    for etat in ("off", "unknown", "unavailable"):
        r3 = asyncio.run(calcul(base.SOIR, [], base.statistiques(), etats_en_plus={"binary_sensor.jarvis_sans_solaire": etat}))
        assert r3["calcul"]["calcul_valide"] is False and r3["calcul"]["recharge_kwh"] == 0, etat
        assert r3["calcul"]["justification"].startswith("Prévision solaire indisponible"), etat
    print(f"Sans panneaux solaires : recharge {c['recharge_kwh']} kWh (avec panneaux : {avec['recharge_kwh']} kWh)")

    # 2. Prévision présente : fourchette P10-P90 et heure de mise à jour.
    r = asyncio.run(calcul(base.SOIR, prevision(), base.statistiques()))
    tot = sum(base.SOLAIRE.values())
    assert r["pv_info"]["ok"] and abs(r["pv_info"]["p10"] - round(0.6 * tot, 1)) < 0.05
    assert abs(r["pv_info"]["p90"] - round(1.3 * tot, 1)) < 0.05 and r["pv_info"]["maj"] == "14/01 17h30"
    assert r["calcul"]["recharge_kwh"] > 0 and r["calcul"]["borne_capacite"] in (True, False)
    print("Fourchette solaire :", r["pv_info"])

    # 3. Moyenne pondérée : le jour le plus récent compte deux fois plus que le précédent.
    r = asyncio.run(calcul(base.SOIR, prevision(), mesures_deux_jours()))
    attendu = (1 * 2.0 + 0.5 * 1.0) / 1.5
    assert all(abs(x - attendu) < 0.002 for x in r["conso_mesuree"]), r["conso_mesuree"][:3]
    print(f"Moyenne pondérée : {r['conso_mesuree'][0]} kWh/h (moyenne simple : 1.5)")

    # 4. Gain réel nul quand la maison a fonctionné exactement en autoconsommation simple.
    cout_ref, fin_ref, achats, injections = autoconsommation(stock(40))
    soc_fin = PL + fin_ref / CAP_B * 100
    g, _ = asyncio.run(gain(achats, 40, soc_fin, injections))
    assert abs(g["injection_kwh"] - round(sum(injections), 1)) < 0.05
    assert g["valide"] and abs(g["gain"]) < 0.01 and g["heures_mesurees"] == 24, g
    assert abs(g["cout_autoconsommation_eur"] - round(cout_ref, 2)) < 0.01
    print("Jour sans recharge : gain", g["gain"], "€")

    # 5. Nuit avec recharge réseau : 4,2 kWh pris en heures creuses (4h-6h) pour couvrir le matin.
    soc0 = 15
    cout_reel, fin_reel, reel, inj_reel = autoconsommation(stock(soc0), recharge=4.2)
    soc1 = PL + fin_reel / CAP_B * 100
    g, rendu = asyncio.run(gain(reel, soc0, soc1, inj_reel))
    cout_auto, fin_auto, _, _ = autoconsommation(stock(soc0))
    v = HC * ETA
    attendu = (cout_auto - v * fin_auto) - (cout_reel - v * stock(soc1))
    assert g["valide"] and abs(g["gain"] - round(attendu, 2)) < 0.011 and g["gain"] > 0, (g["gain"], attendu)
    assert g["fenetre"] == "14/01 23h - 15/01 23h" and g["jour"] == "2030-01-15"
    print(f"Nuit avec recharge : gain {g['gain']} € (attendu {attendu:.2f} €), coût réel {g['cout_reel_eur']} €,"
          f" autoconsommation {g['cout_autoconsommation_eur']} €")

    # 6. Cumul du mois : un jour n'est compté qu'une fois ; remise à zéro au changement de mois.
    assert float(rendu["vide"][0]) == round(g["gain"], 2) and int(rendu["vide"][1]) == 1
    assert float(rendu["deja"][0]) == 10.0 and int(rendu["deja"][1]) == 3
    assert abs(float(rendu["suite"][0]) - round(10 + g["gain"], 2)) < 0.001 and int(rendu["suite"][1]) == 4
    assert float(rendu["nouveau_mois"][0]) == round(g["gain"], 2) and int(rendu["nouveau_mois"][1]) == 1
    print("Cumul du mois :", rendu)

    # 6 bis. Injection : le compteur de l'onduleur passe avant l'estimation soutirage - puissance
    # réseau, qui compte une injection fictive quand la puissance réseau manque une partie de
    # l'heure (batterie à l'arrêt au plancher).
    fictive = [0.0] * 24
    for i in (0, 1, 2, 21, 22):          # heures de nuit, batterie au plancher
        fictive[i] = 0.4
    g_estime, _ = asyncio.run(gain(reel, soc0, soc1, inj_reel, fictive=fictive))
    assert abs(g_estime["injection_kwh"] - round(sum(inj_reel) + 2.0, 1)) < 0.05, g_estime["injection_kwh"]
    assert g_estime["gain"] > round(attendu, 2) and g_estime["injection_source"] == "estimée"
    g_cpt, _ = asyncio.run(gain(reel, soc0, soc1, inj_reel, fictive=fictive, compteur_injection=inj_reel))
    assert abs(g_cpt["injection_kwh"] - round(sum(inj_reel), 1)) < 0.05, g_cpt["injection_kwh"]
    assert abs(g_cpt["gain"] - round(attendu, 2)) < 0.011 and g_cpt["injection_source"] == "compteur", g_cpt
    # Compteur absent pour deux heures : estimation pour ces deux heures seulement.
    trous = [None if i in (21, 22) else x for i, x in enumerate(inj_reel)]
    g_mix, _ = asyncio.run(gain(reel, soc0, soc1, inj_reel, fictive=fictive, compteur_injection=trous))
    assert abs(g_mix["injection_kwh"] - round(sum(inj_reel) + 0.8, 1)) < 0.05, g_mix["injection_kwh"]
    assert g_mix["injection_source"] == "compteur 22 h sur 24", g_mix["injection_source"]
    print(f"Injection fictive 2,0 kWh : gain {g_estime['gain']} € estimé, {g_cpt['gain']} € avec le compteur"
          f" ({g_mix['gain']} € avec 2 h sans compteur)")

    # 7. Mesures incomplètes : pas de gain.
    g, _ = asyncio.run(gain(reel, None, soc1))
    assert g["valide"] is False and g["gain"] is None
    print("Tous les contrôles v7 sont passés.")


if __name__ == "__main__":
    CHEMIN = sys.argv[1] if len(sys.argv) > 1 else str(PAQUET)
    verifier()
