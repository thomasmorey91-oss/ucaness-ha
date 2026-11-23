"""Test des scripts de pilotage du package batterie dans un vrai Home Assistant.

Les actions ucaness.* sont remplacées par des fausses qui enregistrent les appels et
font évoluer le mode affiché ; aucune connexion à l'onduleur.
Usage : python -m pytest -q test_scripts_pilotage.py
"""
import pathlib

import pytest
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml

PKG = pathlib.Path(__file__).resolve().parent.parent / "packages"


def _pkg(name):
    return load_yaml(str(PKG / name))


@pytest.fixture
async def maison(hass):
    bat = _pkg("jarvis_batterie.yaml")
    alertes = _pkg("jarvis_alertes.yaml")
    calls = []
    state = {"fail_mode": False, "fail_plages": 0}  # fail_plages : nombre d'échecs à venir (-1 : toujours)

    async def plages(call):
        calls.append(("plages", call.data["plages"]))
        if state["fail_plages"]:
            state["fail_plages"] -= 1 if state["fail_plages"] > 0 else 0
            raise HomeAssistantError("Erreur API UCANESS 5019 : Device operation timeout")
        return {"confirme": True}

    async def mode(call):
        if state["fail_mode"]:
            raise HomeAssistantError("non confirmé")
        calls.append(("mode", call.data["mode"]))
        hass.states.async_set(
            "sensor.uhome_mode", "Peak Shift Mode" if call.data["mode"] == "arbitrage_horaire" else "Match Load Mode"
        )
        return {"confirme": True}

    async def log(call):
        calls.append(("log", call.data.get("message", "")))

    hass.services.async_register("ucaness", "definir_plages_charge", plages, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register("ucaness", "definir_mode", mode, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register("logbook", "log", log)

    assert await async_setup_component(hass, "input_boolean", {"input_boolean": bat["input_boolean"]})
    assert await async_setup_component(hass, "input_datetime", {"input_datetime": {
        **bat["input_datetime"],
        "jarvis_hc_debut": {"has_date": False, "has_time": True, "initial": "23:00"},
        "jarvis_hc_fin": {"has_date": False, "has_time": True, "initial": "06:00"},
    }})
    assert await async_setup_component(hass, "input_text", {"input_text": alertes["input_text"]})
    assert await async_setup_component(hass, "script", {"script": bat["script"]})
    await hass.async_block_till_done()

    hass.states.async_set("sensor.uhome_mode", "Match Load Mode")
    hass.states.async_set("binary_sensor.uhome_temperature_hors_plage", "off")
    await hass.services.async_call("input_text", "set_value", {"entity_id": "input_text.jarvis_mode_attendu", "value": "Match Load Mode"}, blocking=True)
    await hass.services.async_call("input_boolean", "turn_off", {"entity_id": "input_boolean.jarvis_mode_simulation"}, blocking=True)
    hass.states.async_set(
        "sensor.jarvis_recharge_reseau_prevue", "7.08",
        {"plages": [{"debut": "2300", "fin": "2359"}, {"debut": "0000", "fin": "0024"}], "plan_fin": "0024", "maintien": True},
    )
    return calls, state


async def test_appliquer_programme_puis_change_de_mode(hass, maison):
    calls, _ = maison
    resp = await hass.services.async_call("script", "jarvis_batterie_appliquer", {}, blocking=True, return_response=True)
    assert resp["ok"] is True
    actions = [c[0] for c in calls if c[0] != "log"]
    assert actions == ["plages", "mode"]                     # plages d'abord, mode ensuite
    assert calls[0][1][1] == {"debut": "0000", "fin": "0024"}
    assert ("mode", "arbitrage_horaire") in calls
    assert hass.states.get("input_boolean.jarvis_batterie_plan_actif").state == "on"
    assert hass.states.get("input_datetime.jarvis_batterie_fin_plan").state == "00:24:00"
    assert hass.states.get("input_text.jarvis_mode_attendu").state == "Peak Shift Mode"


async def test_appliquer_ne_fait_rien_en_simulation(hass, maison):
    calls, _ = maison
    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": "input_boolean.jarvis_mode_simulation"}, blocking=True)
    await hass.services.async_call("script", "jarvis_batterie_appliquer", {}, blocking=True, return_response=True)
    assert calls == []


async def test_appliquer_ne_fait_rien_sans_recharge(hass, maison):
    calls, _ = maison
    hass.states.async_set("sensor.jarvis_recharge_reseau_prevue", "0", {"plages": [], "plan_fin": None, "maintien": False})
    await hass.services.async_call("script", "jarvis_batterie_appliquer", {}, blocking=True, return_response=True)
    assert calls == []


async def test_appliquer_bloque_si_temperature_hors_plage(hass, maison):
    calls, _ = maison
    hass.states.async_set("binary_sensor.uhome_temperature_hors_plage", "on")
    await hass.services.async_call("script", "jarvis_batterie_appliquer", {}, blocking=True, return_response=True)
    assert calls == []


async def test_echec_du_mode_laisse_le_retour_arme(hass, maison):
    calls, state = maison
    state["fail_mode"] = True
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("script", "jarvis_batterie_appliquer", {}, blocking=True, return_response=True)
    # Les plages sont posées, le mode n'a pas changé, le retour en autoconsommation reste armé.
    assert [c[0] for c in calls if c[0] != "log"] == ["plages"]
    assert hass.states.get("input_boolean.jarvis_batterie_plan_actif").state == "on"


async def test_retour_autoconsommation(hass, maison):
    calls, _ = maison
    await hass.services.async_call("script", "jarvis_batterie_appliquer", {}, blocking=True, return_response=True)
    await hass.services.async_call("script", "jarvis_batterie_retour_autoconsommation", {}, blocking=True)
    assert calls[-2] == ("mode", "autoconsommation") or ("mode", "autoconsommation") in calls
    assert hass.states.get("input_boolean.jarvis_batterie_plan_actif").state == "off"
    assert hass.states.get("input_text.jarvis_mode_attendu").state == "Match Load Mode"
    assert hass.states.get("sensor.uhome_mode").state == "Match Load Mode"


async def test_reserve_seule_vide_les_plages_puis_arbitrage(hass, maison):
    calls, _ = maison
    hass.states.async_set("sensor.jarvis_recharge_reseau_prevue", "0", {"plages": [], "plan_fin": None, "maintien": True})
    resp = await hass.services.async_call("script", "jarvis_batterie_appliquer", {}, blocking=True, return_response=True)
    assert resp["ok"] is True
    assert [c for c in calls if c[0] != "log"] == [("plages", []), ("mode", "arbitrage_horaire")]
    assert hass.states.get("input_datetime.jarvis_batterie_fin_plan").state == "23:00:00"
    assert hass.states.get("input_boolean.jarvis_batterie_plan_actif").state == "on"


async def test_reserve_seule_permise_par_temperature_basse(hass, maison):
    calls, _ = maison
    hass.states.async_set("binary_sensor.uhome_temperature_hors_plage", "on")
    hass.states.async_set("sensor.jarvis_recharge_reseau_prevue", "0", {"plages": [], "plan_fin": None, "maintien": True})
    await hass.services.async_call("script", "jarvis_batterie_appliquer", {}, blocking=True, return_response=True)
    assert ("mode", "arbitrage_horaire") in calls


async def test_plage_unique_dont_la_fin_est_relue_comme_un_nombre(hass, maison):
    calls, _ = maison
    hass.states.async_set("sensor.jarvis_recharge_reseau_prevue", "1.91",
                          {"plages": [{"debut": "2300", "fin": "2323"}], "plan_fin": 2323, "maintien": True})
    resp = await hass.services.async_call("script", "jarvis_batterie_appliquer", {}, blocking=True, return_response=True)
    assert resp["ok"] is True
    assert ("plages", [{"debut": "2300", "fin": "2323"}]) in calls
    assert hass.states.get("input_datetime.jarvis_batterie_fin_plan").state == "23:23:00"


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_retour_2_min_avant_la_fin_des_heures_creuses(hass, maison, freezer):
    """L'automatisation de retour se déclenche à 05:58 (fin des heures creuses à 06:00)."""
    import datetime as dt
    from pytest_homeassistant_custom_component.common import async_fire_time_changed
    import homeassistant.util.dt as dt_util

    calls, _ = maison
    await hass.config.async_set_time_zone("Europe/Paris")
    bat = _pkg("jarvis_batterie.yaml")
    retour = [a for a in bat["automation"] if a["id"] == "jarvis_batterie_retour_autoconsommation"]
    hass.services.async_register("script", "jarvis_notifier", lambda call: None)
    assert await async_setup_component(hass, "automation", {"automation": retour})
    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": "input_boolean.jarvis_batterie_plan_actif"}, blocking=True)
    hass.states.async_set("sensor.uhome_mode", "Peak Shift Mode")

    tz = dt_util.get_default_time_zone()
    jour = dt_util.now().date() + dt.timedelta(days=1)
    freezer.move_to(dt.datetime.combine(jour, dt.time(5, 57, 50), tz))
    async_fire_time_changed(hass, dt.datetime.combine(jour, dt.time(5, 57, 50), tz))
    await hass.async_block_till_done()
    assert ("mode", "autoconsommation") not in calls
    freezer.move_to(dt.datetime.combine(jour, dt.time(5, 58, 0), tz))
    async_fire_time_changed(hass, dt.datetime.combine(jour, dt.time(5, 58, 0), tz))
    await hass.async_block_till_done()
    assert ("mode", "autoconsommation") in calls
    assert hass.states.get("input_boolean.jarvis_batterie_plan_actif").state == "off"


# ----------------------------------------------------------------- version 4

def _sans_delais(node):
    """Délais ramenés à 0, y compris dans les boucles : le banc de test ne fait pas avancer le temps des tâches."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "delay":
                node[key] = "00:00:00"
            else:
                _sans_delais(value)
    elif isinstance(node, list):
        for item in node:
            _sans_delais(item)


async def _automatisations(hass, ids, notes=None):
    bat = _pkg("jarvis_batterie.yaml")
    autos = [a for a in bat["automation"] if a["id"] in ids]
    _sans_delais(autos)
    hass.services.async_register(
        "script", "jarvis_notifier", lambda call: notes.append(dict(call.data)) if notes is not None else None
    )
    assert await async_setup_component(hass, "automation", {"automation": autos})
    await hass.async_block_till_done()


def _jour_de_la_decision():
    """Jour où jouer la décision de 23 h : aujourd'hui, ou demain si l'essai est lancé après
    22 h 59 (on ne peut pas remonter le temps du banc ; un saut de plusieurs jours le bloque)."""
    import datetime as dt

    from homeassistant.util import dt as dt_util

    maintenant = dt_util.now()
    return maintenant.date() + dt.timedelta(days=0 if maintenant.time() < dt.time(22, 59) else 1)


async def _a(hass, freezer, jour, heure):
    import datetime as dt
    from pytest_homeassistant_custom_component.common import async_fire_time_changed
    import homeassistant.util.dt as dt_util
    t = dt.datetime.combine(jour, heure, dt_util.get_default_time_zone())
    freezer.move_to(t)
    async_fire_time_changed(hass, t)
    await hass.async_block_till_done()


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_decision_a_23h_programme_la_fin_de_nuit(hass, maison, freezer):
    import datetime as dt
    calls, _ = maison
    await hass.config.async_set_time_zone("Europe/Paris")
    hass.states.async_set("sensor.jarvis_recharge_reseau_prevue", "1.27", {
        "plages": [{"debut": "0528", "fin": "0545"}], "plan_fin": "0545", "maintien": True,
        "reevaluation": "04:28", "calcul_valide": True, "mode": "réel", "justification": "test"})
    await _automatisations(hass, {"jarvis_batterie_decision_du_soir"})
    import homeassistant.util.dt as dt_util
    jour = _jour_de_la_decision()
    await _a(hass, freezer, jour, dt.time(22, 59, 50))
    await _a(hass, freezer, jour, dt.time(23, 0, 0))
    assert [c for c in calls if c[0] != "log"] == [("plages", [{"debut": "0528", "fin": "0545"}]), ("mode", "arbitrage_horaire")]
    assert hass.states.get("input_datetime.jarvis_batterie_reevaluation").state == "04:28:00"
    assert hass.states.get("input_datetime.jarvis_batterie_fin_plan").state == "05:45:00"
    assert hass.states.get("input_boolean.jarvis_batterie_plan_actif").state == "on"


async def _decision_23h(hass, freezer, notes):
    import datetime as dt
    import homeassistant.util.dt as dt_util
    await hass.config.async_set_time_zone("Europe/Paris")
    hass.states.async_set("sensor.jarvis_recharge_reseau_prevue", "4.2", {
        "plages": [{"debut": "0410", "fin": "0545"}], "plan_fin": "0545", "maintien": True,
        "reevaluation": "03:10", "calcul_valide": True, "mode": "réel", "justification": "test"})
    await _automatisations(hass, {"jarvis_batterie_decision_du_soir"}, notes)
    jour = _jour_de_la_decision()
    await _a(hass, freezer, jour, dt.time(22, 59, 50))
    await _a(hass, freezer, jour, dt.time(23, 0, 0))


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_decision_reessaie_apres_un_echec(hass, maison, freezer):
    """Un 5019 au premier essai ne doit plus coûter la recharge de la nuit."""
    calls, state = maison
    state["fail_plages"] = 1
    notes = []
    await _decision_23h(hass, freezer, notes)
    actions = [c for c in calls if c[0] != "log"]
    assert actions == [("plages", [{"debut": "0410", "fin": "0545"}])] * 2 + [("mode", "arbitrage_horaire")]
    assert any("Essai 1 de programmation non abouti ; nouvel essai à 23h10" in c[1] for c in calls if c[0] == "log")
    assert notes == []                                                       # pas d'alerte : le 2e essai a réussi
    assert hass.states.get("input_boolean.jarvis_batterie_plan_actif").state == "on"
    assert hass.states.get("input_datetime.jarvis_batterie_reevaluation").state == "03:10:00"


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_decision_alerte_apres_trois_echecs(hass, maison, freezer):
    calls, state = maison
    state["fail_plages"] = -1
    notes = []
    await _decision_23h(hass, freezer, notes)
    assert [c[0] for c in calls if c[0] != "log"] == ["plages"] * 3          # 23h00, 23h10, 23h30
    assert any("nouvel essai à 23h30" in c[1] for c in calls if c[0] == "log")
    assert len(notes) == 1 and notes[0]["titre"] == "Recharge de nuit non programmée"
    assert "après 3 essais" in notes[0]["message"]
    assert hass.states.get("input_boolean.jarvis_batterie_plan_actif").state == "off"
    assert hass.states.get("sensor.uhome_mode").state == "Match Load Mode"


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_decision_sans_recharge_ne_reessaie_pas(hass, maison, freezer):
    import datetime as dt
    import homeassistant.util.dt as dt_util
    calls, _ = maison
    notes = []
    await hass.config.async_set_time_zone("Europe/Paris")
    hass.states.async_set("sensor.jarvis_recharge_reseau_prevue", "0", {
        "plages": [], "plan_fin": None, "maintien": False, "calcul_valide": True, "mode": "réel", "justification": "test"})
    await _automatisations(hass, {"jarvis_batterie_decision_du_soir"}, notes)
    jour = _jour_de_la_decision()
    await _a(hass, freezer, jour, dt.time(22, 59, 50))
    await _a(hass, freezer, jour, dt.time(23, 0, 0))
    assert [c for c in calls if c[0] != "log"] == []
    assert not any("Essai" in c[1] for c in calls if c[0] == "log")
    assert notes == []


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_reevaluation_ajuste_la_plage(hass, maison, freezer):
    import datetime as dt
    calls, _ = maison
    await hass.config.async_set_time_zone("Europe/Paris")
    await hass.services.async_call("input_datetime", "set_datetime", {"entity_id": "input_datetime.jarvis_batterie_reevaluation", "time": "04:28:00"}, blocking=True)
    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": "input_boolean.jarvis_batterie_plan_actif"}, blocking=True)
    hass.states.async_set("sensor.jarvis_recharge_reseau_prevue", "0.9", {
        "plages": [{"debut": "0533", "fin": "0545"}], "maintien": True, "calcul_valide": True, "mode": "réel", "justification": "test"})
    await _automatisations(hass, {"jarvis_batterie_reevaluation"})
    import homeassistant.util.dt as dt_util
    jour = dt_util.now().date() + dt.timedelta(days=2)
    await _a(hass, freezer, jour, dt.time(4, 27, 50))
    await _a(hass, freezer, jour, dt.time(4, 28, 0))
    assert ("plages", [{"debut": "0533", "fin": "0545"}]) in calls
    assert not any(c[0] == "mode" for c in calls)
    assert any("Réévaluation appliquée et confirmée : plages 0533-0545" in c[1] for c in calls if c[0] == "log")


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_reevaluation_conserve_la_plage_si_calcul_incomplet(hass, maison, freezer):
    import datetime as dt
    calls, _ = maison
    await hass.config.async_set_time_zone("Europe/Paris")
    await hass.services.async_call("input_datetime", "set_datetime", {"entity_id": "input_datetime.jarvis_batterie_reevaluation", "time": "04:28:00"}, blocking=True)
    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": "input_boolean.jarvis_batterie_plan_actif"}, blocking=True)
    hass.states.async_set("sensor.jarvis_recharge_reseau_prevue", "0", {
        "plages": [], "maintien": False, "calcul_valide": False, "mode": "réel", "justification": "Prévision météo indisponible"})
    await _automatisations(hass, {"jarvis_batterie_reevaluation"})
    import homeassistant.util.dt as dt_util
    jour = dt_util.now().date() + dt.timedelta(days=2)
    await _a(hass, freezer, jour, dt.time(4, 27, 50))
    await _a(hass, freezer, jour, dt.time(4, 28, 0))
    assert not any(c[0] == "plages" for c in calls)
    assert not any("appliquée et confirmée" in c[1] for c in calls if c[0] == "log")


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_apercu_de_22h30_journalise_sans_commande(hass, maison, freezer):
    import datetime as dt
    calls, _ = maison
    await hass.config.async_set_time_zone("Europe/Paris")
    hass.states.async_set("sensor.uhome_soc", "40")
    hass.states.async_set("sensor.jarvis_recharge_reseau_prevue", "6.9", {
        "plages": [{"debut": "0339", "fin": "0545"}], "maintien": True, "calcul_valide": True,
        "mode": "réel", "justification": "Recharge de 6.9 kWh.", "solaire_prevu_kwh": 10.6,
        "solaire_p10_kwh": 6.9, "solaire_p90_kwh": 12.6, "prevision_solaire_maj": "22/11 16h29"})
    await _automatisations(hass, {"jarvis_batterie_apercu_journal"})
    import homeassistant.util.dt as dt_util
    jour = dt_util.now().date() + dt.timedelta(days=2)
    await _a(hass, freezer, jour, dt.time(22, 29, 50))
    await _a(hass, freezer, jour, dt.time(22, 30, 0))
    logs = [c[1] for c in calls if c[0] == "log"]
    # Le saut de date du test peut déclencher 22h30 deux fois : on vérifie le contenu.
    assert logs and all(x.startswith("[aperçu] SOC 40 %, Recharge de 6.9 kWh.") for x in logs)
    assert "P10-P90 : 6.9 à 12.6 kWh" in logs[0]
    assert [c for c in calls if c[0] != "log"] == []


async def test_notification_vers_le_service_renseigne(hass):
    """Le service de notification est lu dans une entrée : aucun nom de téléphone dans le code."""
    alertes = _pkg("jarvis_alertes.yaml")
    recu = []
    hass.services.async_register("notify", "mobile_app_test", lambda call: recu.append(dict(call.data)))
    hass.services.async_register("logbook", "log", lambda call: None)
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": alertes["input_boolean"]})
    assert await async_setup_component(hass, "input_text", {"input_text": alertes["input_text"]})
    assert await async_setup_component(hass, "script", {"script": alertes["script"]})
    await hass.async_block_till_done()
    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": "input_boolean.jarvis_alertes_actives"}, blocking=True)
    # service non renseigné : rien n'est envoyé, sans erreur
    await hass.services.async_call("script", "jarvis_notifier", {"niveau": "info", "titre": "Essai", "message": "vide"}, blocking=True)
    assert recu == []
    await hass.services.async_call("input_text", "set_value", {"entity_id": "input_text.jarvis_service_notification", "value": "notify.mobile_app_test"}, blocking=True)
    await hass.services.async_call("script", "jarvis_notifier", {"niveau": "intervention", "titre": "Essai", "message": "ok"}, blocking=True)
    assert recu and recu[0]["message"] == "ok"


@pytest.mark.parametrize("conserver,attendu", [("off", "on"), ("on", "off")])
async def test_simulation_au_demarrage(hass, conserver, attendu):
    """Par défaut, simulation à chaque démarrage ; le mode réel est gardé si l'option est allumée."""
    from homeassistant.core import CoreState
    hass.set_state(CoreState.not_running)
    bat = _pkg("jarvis_batterie.yaml")
    assert "initial" not in bat["input_boolean"]["jarvis_mode_simulation"]
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": bat["input_boolean"]})
    autos = [a for a in bat["automation"] if a["id"] == "jarvis_batterie_simulation_au_demarrage"]
    assert await async_setup_component(hass, "automation", {"automation": autos})
    await hass.async_block_till_done()
    await hass.services.async_call("input_boolean", "turn_off", {"entity_id": "input_boolean.jarvis_mode_simulation"}, blocking=True)
    await hass.services.async_call("input_boolean", "turn_" + conserver, {"entity_id": "input_boolean.jarvis_simulation_conserver"}, blocking=True)
    await hass.async_start()
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.jarvis_mode_simulation").state == attendu
