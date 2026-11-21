"""Tests du package tarif dynamique (jarvis_dynamique.yaml) dans un vrai Home Assistant.

Les actions ucaness.*, workday.check_date et recorder.get_statistics sont remplacées par des
fausses ; aucune connexion à l'onduleur. Données INVENTÉES.
Usage : cd pilotage/tests && python -m pytest -q test_dynamique.py
"""
import datetime as dt
import pathlib

import pytest
from homeassistant.core import SupportsResponse
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml

PKG = pathlib.Path(__file__).resolve().parent.parent / "packages"
V7 = "Heures pleines / heures creuses (calcul v7)"
MOTEUR = "Tarif dynamique (moteur intégré)"


def _pkg(name):
    return load_yaml(str(PKG / name))


def _hhmm(t):
    return t.strftime("%H%M")


@pytest.fixture
async def maison(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    bat, tarif, alertes, dyn = (_pkg(n) for n in ("jarvis_batterie.yaml", "jarvis_tarif.yaml", "jarvis_alertes.yaml", "jarvis_dynamique.yaml"))
    calls = []

    async def plages(call):
        calls.append(("plages", call.data["plages"]))
        return {"confirme": True}

    async def mode(call):
        calls.append(("mode", call.data["mode"]))
        hass.states.async_set("sensor.uhome_mode", "Peak Fill Mode" if call.data["mode"] == "arbitrage_horaire" else "Match Load Mode")
        return {"confirme": True}

    async def log(call):
        calls.append(("log", call.data.get("message", "")))

    hass.services.async_register("ucaness", "definir_plages_charge", plages, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register("ucaness", "definir_mode", mode, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register("logbook", "log", log)

    assert await async_setup_component(hass, "input_boolean", {"input_boolean": {**bat["input_boolean"], **tarif["input_boolean"], **alertes["input_boolean"], **dyn["input_boolean"]}})
    assert await async_setup_component(hass, "input_select", {"input_select": {**tarif["input_select"], **dyn["input_select"]}})
    assert await async_setup_component(hass, "input_text", {"input_text": {**alertes["input_text"], **dyn["input_text"]}})
    assert await async_setup_component(hass, "input_number", {"input_number": {**bat["input_number"], **tarif["input_number"], **dyn["input_number"]}})
    assert await async_setup_component(hass, "input_datetime", {"input_datetime": {
        **bat["input_datetime"],
        "jarvis_hc_debut": {"has_date": False, "has_time": True, "initial": "22:00"},
        "jarvis_hc_fin": {"has_date": False, "has_time": True, "initial": "06:00"},
    }})
    assert await async_setup_component(hass, "script", {"script": {**bat["script"], **alertes["script"]}})
    appliquer = next(a for a in dyn["automation"] if a["id"] == "jarvis_dyn_appliquer")
    assert await async_setup_component(hass, "automation", {"automation": [appliquer]})
    await hass.async_block_till_done()

    hass.states.async_set("sensor.uhome_mode", "Match Load Mode")
    hass.states.async_set("binary_sensor.uhome_temperature_hors_plage", "off")
    for e, v in (("input_text.jarvis_mode_attendu", "Match Load Mode"),):
        await hass.services.async_call("input_text", "set_value", {"entity_id": e, "value": v}, blocking=True)
    await hass.services.async_call("input_boolean", "turn_off", {"entity_id": "input_boolean.jarvis_mode_simulation"}, blocking=True)
    await hass.services.async_call("input_select", "select_option", {"entity_id": "input_select.jarvis_strategie", "option": MOTEUR}, blocking=True)
    await hass.async_block_till_done()
    calls.clear()
    return calls


def _fenetres(plages, jours=0):
    """Fenêtres datées correspondant aux plages (aujourd'hui, ou décalées de quelques jours)."""
    minuit = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(days=jours)
    out = []
    for p in plages:
        d = minuit + dt.timedelta(hours=int(p["debut"][:2]), minutes=int(p["debut"][2:]))
        f = minuit + dt.timedelta(hours=int(p["fin"][:2]), minutes=int(p["fin"][2:]))
        out.append({"debut": d.isoformat(), "fin": f.isoformat()})
    return out


def _plan(hass, plages, age_min=1, valide=True, jours=0):
    hass.states.async_set("sensor.jarvis_plan_tarif_dynamique", "3.0", {
        "valide": valide, "plages": plages, "fenetres": _fenetres(plages, jours), "justification": "plan d'essai",
        "calcule_le": (dt_util.now() - dt.timedelta(minutes=age_min)).isoformat(),
    })


async def _tourner(hass):
    await hass.services.async_call("automation", "trigger", {"entity_id": "automation.jarvis_tarif_dynamique_appliquer_le_plan"}, blocking=True)
    await hass.async_block_till_done()


async def test_plage_en_cours_programme_puis_arbitrage(hass, maison):
    n = dt_util.now()
    plages = [{"debut": _hhmm(n - dt.timedelta(minutes=5)), "fin": _hhmm(n + dt.timedelta(minutes=50))}]
    if plages[0]["fin"] < plages[0]["debut"]:
        pytest.skip("test lancé juste avant minuit")
    _plan(hass, plages)
    await _tourner(hass)
    actions = [c for c in maison if c[0] != "log"]
    assert actions == [("plages", plages), ("mode", "arbitrage_horaire")]
    assert hass.states.get("input_boolean.jarvis_dyn_plan_actif").state == "on"
    assert hass.states.get("input_text.jarvis_mode_attendu").state == "Peak Fill Mode"
    # Même plan une minute plus tard : rien n'est renvoyé.
    maison.clear()
    await _tourner(hass)
    assert [c for c in maison if c[0] != "log"] == []


async def test_hors_plage_retour_autoconsommation(hass, maison):
    n = dt_util.now()
    _plan(hass, [{"debut": _hhmm(n - dt.timedelta(minutes=5)), "fin": _hhmm(n + dt.timedelta(minutes=50))}])
    await _tourner(hass)
    maison.clear()
    plus_tard = [{"debut": _hhmm(n + dt.timedelta(hours=3)), "fin": _hhmm(n + dt.timedelta(hours=4))}]
    if plus_tard[0]["fin"] < plus_tard[0]["debut"]:
        pytest.skip("test lancé juste avant minuit")
    _plan(hass, plus_tard)
    await _tourner(hass)
    actions = [c for c in maison if c[0] != "log"]
    assert actions == [("plages", plus_tard), ("mode", "autoconsommation")]
    assert hass.states.get("input_boolean.jarvis_dyn_plan_actif").state == "off"


async def test_plan_trop_ancien_repli_sur(hass, maison):
    n = dt_util.now()
    _plan(hass, [{"debut": _hhmm(n - dt.timedelta(minutes=5)), "fin": _hhmm(n + dt.timedelta(minutes=50))}])
    await _tourner(hass)
    maison.clear()
    _plan(hass, [{"debut": _hhmm(n - dt.timedelta(minutes=5)), "fin": _hhmm(n + dt.timedelta(minutes=50))}], age_min=45)
    await _tourner(hass)
    assert [c for c in maison if c[0] != "log"] == [("mode", "autoconsommation")]


async def test_simulation_journalise_seulement_puis_ecrit_en_reel(hass, maison):
    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": "input_boolean.jarvis_mode_simulation"}, blocking=True)
    await hass.async_block_till_done()
    maison.clear()
    n = dt_util.now()
    plages = [{"debut": _hhmm(n - dt.timedelta(minutes=5)), "fin": _hhmm(n + dt.timedelta(minutes=50))}]
    if plages[0]["fin"] < plages[0]["debut"]:
        pytest.skip("test lancé juste avant minuit")
    _plan(hass, plages)
    await _tourner(hass)
    assert [c[0] for c in maison] == ["log"]
    assert "[simulation]" in maison[0][1]
    # Passage en réel : l'automatisation se déclenche et écrit les plages (la clé « sim » ne les
    # masque pas).
    maison.clear()
    await hass.services.async_call("input_boolean", "turn_off", {"entity_id": "input_boolean.jarvis_mode_simulation"}, blocking=True)
    await hass.async_block_till_done()
    assert [c for c in maison if c[0] != "log"] == [("plages", plages), ("mode", "arbitrage_horaire")]


async def test_plage_de_demain_a_la_meme_heure_pas_d_arbitrage(hass, maison):
    """Les plages de l'onduleur n'ont pas de date : une plage prévue demain à l'heure qu'il est
    maintenant est écrite, mais l'onduleur reste en autoconsommation aujourd'hui."""
    n = dt_util.now()
    plages = [{"debut": _hhmm(n - dt.timedelta(minutes=5)), "fin": _hhmm(n + dt.timedelta(minutes=50))}]
    if plages[0]["fin"] < plages[0]["debut"]:
        pytest.skip("test lancé juste avant minuit")
    _plan(hass, plages, jours=1)
    await _tourner(hass)
    assert [c for c in maison if c[0] != "log"] == [("plages", plages)]
    assert hass.states.get("input_boolean.jarvis_dyn_plan_actif").state == "off"


async def test_temperature_hors_plage_pas_d_arbitrage(hass, maison):
    hass.states.async_set("binary_sensor.uhome_temperature_hors_plage", "on")
    n = dt_util.now()
    _plan(hass, [{"debut": _hhmm(n - dt.timedelta(minutes=5)), "fin": _hhmm(n + dt.timedelta(minutes=50))}])
    await _tourner(hass)
    assert ("mode", "arbitrage_horaire") not in maison


async def test_retour_a_la_strategie_de_nuit(hass, maison):
    n = dt_util.now()
    _plan(hass, [{"debut": _hhmm(n - dt.timedelta(minutes=5)), "fin": _hhmm(n + dt.timedelta(minutes=50))}])
    await _tourner(hass)
    maison.clear()
    await hass.services.async_call("input_select", "select_option", {"entity_id": "input_select.jarvis_strategie", "option": V7}, blocking=True)
    await hass.async_block_till_done()
    assert ("mode", "autoconsommation") in maison
    assert hass.states.get("input_boolean.jarvis_dyn_plan_actif").state == "off"
    assert hass.states.get("input_text.jarvis_dyn_plages_appliquees").state == ""


# --- Prix TTC ------------------------------------------------------------------------------------
async def test_prix_ttc_heures_pleines_et_creuses(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    dyn = _pkg("jarvis_dynamique.yaml")
    assert await async_setup_component(hass, "input_select", {"input_select": dyn["input_select"]})
    assert await async_setup_component(hass, "input_text", {"input_text": dyn["input_text"]})
    assert await async_setup_component(hass, "input_number", {"input_number": {
        **dyn["input_number"],
        "jarvis_dyn_tva": {**dyn["input_number"]["jarvis_dyn_tva"], "initial": 20},
        "jarvis_dyn_cout_ajoute_hp": {**dyn["input_number"]["jarvis_dyn_cout_ajoute_hp"], "initial": 0.1},
        "jarvis_dyn_cout_ajoute_hc": {**dyn["input_number"]["jarvis_dyn_cout_ajoute_hc"], "initial": 0.05},
    }})
    assert await async_setup_component(hass, "input_datetime", {"input_datetime": {
        "jarvis_hc_debut": {"has_date": False, "has_time": True, "initial": "22:00"},
        "jarvis_hc_fin": {"has_date": False, "has_time": True, "initial": "06:00"},
    }})
    minuit = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
    marche = [{"debut": (minuit + dt.timedelta(hours=h)).isoformat(), "fin": (minuit + dt.timedelta(hours=h + 1)).isoformat(),
               "eur_mwh": 100.0} for h in range(24)]
    hass.states.async_set("sensor.jarvis_prix_marche_nordpool", "100", {"prix": marche})
    assert await async_setup_component(hass, "template", {"template": [dyn["template"][1]]})
    await hass.async_block_till_done()
    prix = hass.states.get("sensor.jarvis_prix_dynamiques").attributes["prix"]
    assert len(prix) == 24
    assert prix[3]["prix"] == pytest.approx((0.1 + 0.05) * 1.2)       # 3h : heures creuses
    assert prix[12]["prix"] == pytest.approx((0.1 + 0.1) * 1.2)       # 12h : heures pleines


# --- Données envoyées au moteur ------------------------------------------------------------------
async def test_plan_moteur_recoit_les_donnees(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    bat, dyn = _pkg("jarvis_batterie.yaml"), _pkg("jarvis_dynamique.yaml")
    recu = {}

    async def check_date(call):
        return {"binary_sensor.workday_sensor": {"workday": True}}

    async def stats(call):
        debut = dt_util.now().replace(minute=0, second=0, microsecond=0) - dt.timedelta(days=2)
        return {"statistics": {"sensor.uhome_puissance_maison": [
            {"start": (debut + dt.timedelta(hours=i)).isoformat(), "mean": 500.0} for i in range(48)]}}

    async def optimiser(call):
        recu.update(call.data)
        return {"valide": True, "plages": [{"debut": "0200", "fin": "0400"}], "nombre_plages": 1,
                "charge_en_cours": False, "recharge_reseau_kwh": 5.2, "gain_estime_eur": 0.8, "justification": "essai"}

    hass.services.async_register("workday", "check_date", check_date, supports_response=SupportsResponse.ONLY)
    hass.services.async_register("recorder", "get_statistics", stats, supports_response=SupportsResponse.ONLY)
    hass.services.async_register("ucaness", "optimiser_charge", optimiser, supports_response=SupportsResponse.ONLY)
    assert await async_setup_component(hass, "input_select", {"input_select": {
        **dyn["input_select"], "jarvis_strategie": {**dyn["input_select"]["jarvis_strategie"], "initial": MOTEUR}}})
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": bat["input_boolean"]})
    assert await async_setup_component(hass, "input_number", {"input_number": {
        **bat["input_number"], **dyn["input_number"],
        "jarvis_batterie_capacite": {**bat["input_number"]["jarvis_batterie_capacite"], "initial": 10.24}}})
    minuit = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
    hass.states.async_set("sensor.uhome_soc", "55")
    hass.states.async_set("sensor.jarvis_prix_dynamiques", "0.2", {"prix": [
        {"debut": (minuit + dt.timedelta(hours=h)).isoformat(), "prix": 0.2} for h in range(48)]})
    for capteur, j in (("sensor.solcast_pv_forecast_prevision_aujourdhui", 0), ("sensor.solcast_pv_forecast_prevision_demain", 1)):
        hass.states.async_set(capteur, "10", {"detailedHourly": [
            {"period_start": (minuit + dt.timedelta(days=j, hours=h)).isoformat(), "pv_estimate": 1.0} for h in range(24)]})
    assert await async_setup_component(hass, "template", {"template": [dyn["template"][2]]})
    await hass.async_block_till_done()
    hass.bus.async_fire("jarvis_recalcul_dynamique")
    await hass.async_block_till_done()

    assert len(recu["conso"]) == 48
    assert recu["conso"][5]["kwh"] == pytest.approx(0.5)                # 500 W mesurés
    assert len(recu["solaire"]) == 48 and len(recu["prix"]) == 48
    assert recu["soc_pct"] == 55 and recu["capacite_kwh"] == pytest.approx(10.24)
    assert recu["reserve"] is None and recu["charge_interdite"] is False
    etat = hass.states.get("sensor.jarvis_plan_tarif_dynamique")
    assert float(etat.state) == pytest.approx(5.2)
    assert etat.attributes["plages"] == [{"debut": "0200", "fin": "0400"}]
    assert etat.attributes["valide"] is True


# --- Configuration complète acceptée -------------------------------------------------------------
async def test_package_dynamique_charge(hass, caplog):
    bat, tarif, alertes, dyn = (_pkg(n) for n in ("jarvis_batterie.yaml", "jarvis_tarif.yaml", "jarvis_alertes.yaml", "jarvis_dynamique.yaml"))
    for domaine in ("input_boolean", "input_datetime", "input_number", "input_select", "input_text"):
        conf = {**tarif.get(domaine, {}), **bat.get(domaine, {}), **alertes.get(domaine, {}), **dyn.get(domaine, {})}
        assert await async_setup_component(hass, domaine, {domaine: conf})
    assert await async_setup_component(hass, "script", {"script": {**bat["script"], **alertes["script"]}})
    assert await async_setup_component(hass, "template", {"template": bat["template"] + dyn["template"]})
    assert await async_setup_component(hass, "automation", {"automation": bat["automation"] + dyn["automation"]})
    await hass.async_block_till_done()
    for e in ("sensor.jarvis_prix_dynamiques", "input_select.jarvis_strategie",
              "automation.jarvis_tarif_dynamique_appliquer_le_plan",
              "automation.jarvis_batterie_decision_du_soir_journal"):
        assert hass.states.get(e) is not None, e
    assert hass.states.get("input_select.jarvis_strategie").state == V7
    assert "Invalid config" not in caplog.text and "Error" not in caplog.text, caplog.text


# --- Adaptateur EMHASS ---------------------------------------------------------------------------
async def test_plan_emhass_lu_et_traduit(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    bat, dyn = _pkg("jarvis_batterie.yaml"), _pkg("jarvis_dynamique.yaml")
    recu = {}

    async def depuis_plan(call):
        recu.update(call.data)
        return {"valide": True, "plages": [{"debut": "0100", "fin": "0300"}], "charge_reseau_kwh": 6.0,
                "charge_ecartee_kwh": 0, "fenetres": 1, "charge_en_cours": False}

    hass.services.async_register("ucaness", "plages_depuis_plan", depuis_plan, supports_response=SupportsResponse.ONLY)
    assert await async_setup_component(hass, "input_select", {"input_select": {
        **dyn["input_select"], "jarvis_strategie": {**dyn["input_select"]["jarvis_strategie"], "initial": "Tarif dynamique (EMHASS)"}}})
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": bat["input_boolean"]})
    textes = dict(dyn["input_text"])
    for k, v in (("jarvis_dyn_emhass_batterie", "sensor.p_batt_forecast"), ("jarvis_dyn_emhass_attribut_batterie", "battery_scheduled_power"),
                 ("jarvis_dyn_emhass_reseau", "sensor.p_grid_forecast"), ("jarvis_dyn_emhass_attribut_reseau", "forecasts")):
        textes[k] = {**textes[k], "initial": v}
    assert await async_setup_component(hass, "input_text", {"input_text": textes})
    t0 = dt_util.now().replace(minute=0, second=0, microsecond=0)
    hass.states.async_set("sensor.p_batt_forecast", "0", {"battery_scheduled_power": [
        {"date": (t0 + dt.timedelta(minutes=30 * i)).isoformat(), "p_batt_forecast": "-3000.0" if i < 4 else "500.0"} for i in range(10)]})
    hass.states.async_set("sensor.p_grid_forecast", "0", {"forecasts": [
        {"date": (t0 + dt.timedelta(minutes=30 * i)).isoformat(), "p_grid_forecast": "3400.0" if i < 4 else "0.0"} for i in range(10)]})
    hass.states.async_set("binary_sensor.uhome_temperature_hors_plage", "off")
    assert await async_setup_component(hass, "template", {"template": [dyn["template"][3]]})
    await hass.async_block_till_done()
    hass.bus.async_fire("jarvis_recalcul_dynamique")
    await hass.async_block_till_done()
    assert len(recu["plan"]) == 10
    assert recu["plan"][0]["p_batt"] == -3000.0 and recu["plan"][0]["p_grid"] == 3400.0
    etat = hass.states.get("sensor.jarvis_plan_emhass")
    assert etat.attributes["plages"] == [{"debut": "0100", "fin": "0300"}] and etat.attributes["valide"] is True
