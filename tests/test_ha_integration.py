"""Tests de bout en bout dans un vrai Home Assistant (banc pytest-homeassistant-custom-component).

Le client UCANESS est remplacé par un faux qui renvoie les jeux de données de test :
aucun appel réseau, aucune écriture possible.
"""
import json
import pathlib
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from custom_components.ucaness.api import (
    CONFIG_KEYS,
    SETTINGS_UPDATE_PATH,
    UcanessAuthError,
    UcanessClient,
    UcanessWriteRefused,
    validate_settings,
)
from custom_components.ucaness.const import CONF_DEVICE_CODE, DOMAIN

FIX = pathlib.Path(__file__).parent / "fixtures"


def fx(name):
    return json.loads((FIX / f"{name}.json").read_text())


def _client(hass, entry):
    """Client de l'API de l'entrée chargée."""
    return entry.runtime_data.client


class FakeClient:
    instances = []

    def __init__(self, session, email, password_md5, *a, **kw):
        self.email = email
        self.app_key = kw.get("app_key")
        self.writes = []
        self.apply_writes = True
        self.store_mode = True      # le cloud garde-t-il le mode dans la configuration ?
        self.mode_str = "Match Load Mode"
        self.settings = {"bat_grid_dod": 900, "charge_time1_start": 100, "charge_time1_end": 300}
        FakeClient.instances.append(self)

    async def login(self):
        if self.email == "bad@example.org":
            raise UcanessAuthError("refusé")

    async def get_detail(self, code, tz=3600):
        await self.login()
        detail = fx("detail_load")
        detail["status"]["work_mode_str"] = self.mode_str
        return detail

    async def get_config(self, code):
        return fx("device_config")

    async def get_events(self, code, page=1, page_size=20):
        return fx("events")

    async def resolve_device_v1(self, code):
        if not self.app_key:
            raise UcanessWriteRefused("Clé d'application absente")
        return f"MA_{code}", "mr"

    async def get_config_v1(self, code):
        # Comme le vrai cloud : les valeurs nulles sont omises.
        return {"inverter_model": "mr", "pcs": {"mr": {k: v for k, v in self.settings.items() if v != 0}}}

    async def update_settings(self, code, items):
        validate_settings(items)
        self.writes.append(dict(items))
        if self.apply_writes:
            for set_id, value in items.items():
                if set_id == 1:
                    self.mode_str = "Peak Shift Mode" if int(value) == 1 else "Match Load Mode"
                    if not self.store_mode:
                        continue
                self.settings[CONFIG_KEYS[set_id][0]] = int(value)
        return [{"set_id": k, "set_data": v} for k, v in items.items()]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def fake_client():
    with patch("custom_components.ucaness.config_flow.UcanessClient", FakeClient), patch(
        "custom_components.ucaness.UcanessClient", FakeClient
    ):
        yield


async def _create_entry(hass, email="user@example.org"):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: email, CONF_PASSWORD: "secret", CONF_DEVICE_CODE: "testcode01"},
    )


async def test_config_flow_stores_hash_not_password(hass, fake_client):
    result = await _create_entry(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Maison Test"
    data = result["data"]
    assert "password" not in data
    assert len(data["password_md5"]) == 32
    assert data["dev_sn"] == "S0000TEST"


async def test_config_flow_bad_credentials(hass, fake_client):
    result = await _create_entry(hass, email="bad@example.org")
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_entities_created_with_values(hass, fake_client):
    await _create_entry(hass)
    await hass.async_block_till_done()

    # Les entités lues par le pilotage portent d'emblée l'identifiant attendu (rien à renommer).
    soc = hass.states.get("sensor.uhome_soc")
    assert soc is not None and float(soc.state) == pytest.approx(41.0)
    assert soc.attributes["unit_of_measurement"] == "%"

    solar_total = hass.states.get("sensor.maison_test_production_solaire_totale")
    assert float(solar_total.state) == pytest.approx(5000.0)
    assert solar_total.attributes["state_class"] == "total_increasing"
    assert solar_total.attributes["device_class"] == "energy"

    dod = hass.states.get("sensor.maison_test_reglage_dod_raccorde_au_reseau")
    assert float(dod.state) == pytest.approx(90.0)

    fault = hass.states.get("binary_sensor.uhome_defaut_batterie")
    assert fault.state == "off"
    temp = hass.states.get("binary_sensor.uhome_temperature_hors_plage")
    assert temp.state == "off"


async def test_identifiants_attendus_par_le_pilotage(hass, fake_client):
    """Installation neuve : toutes les entités que lit le pilotage existent sous le bon identifiant."""
    from custom_components.ucaness.const import ENTITES_PILOTAGE, OBJECT_IDS

    await _create_entry(hass)
    await hass.async_block_till_done()
    assert [e for e in ENTITES_PILOTAGE if hass.states.get(e) is None] == []
    registre = er.async_get(hass)
    ids = {e.entity_id.split(".", 1)[1] for e in registre.entities.values() if e.platform == DOMAIN}
    assert set(OBJECT_IDS.values()) <= ids


async def test_identifiant_existant_conserve(hass, fake_client):
    """Une entité déjà enregistrée (installation existante, entité renommée) garde son identifiant."""
    registre = er.async_get(hass)
    registre.async_get_or_create("sensor", DOMAIN, "testcode01_soc", suggested_object_id="ma_batterie_soc")
    await _create_entry(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ma_batterie_soc") is not None
    assert hass.states.get("sensor.uhome_soc") is None


# ------------------------------------------------------------------ assistant d'installation
def _issues(hass):
    return sorted(i.translation_key for i in ir.async_get(hass).issues.values() if i.domain == DOMAIN)


async def _relire(hass):
    """Nouvelle lecture de l'onduleur : l'assistant réévalue l'installation."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_assistant_installation_pas_a_pas(hass, fake_client):
    """Batterie connectée, rien d'autre : une seule réparation à la fois, dans l'ordre du parcours."""
    await _create_entry(hass)
    await hass.async_block_till_done()
    etat = hass.states.get("sensor.ucaness_installation")
    assert etat.state == "a_configurer"
    assert etat.attributes["etape_suivante"]["cle"] == "packages"
    assert etat.attributes["etapes_faites"] == ["connexion", "entites"]
    assert _issues(hass) == ["etape_packages"]

    # Packages installés, capacité à 0 : étape « batterie ».
    hass.states.async_set("input_boolean.jarvis_mode_simulation", "on")
    hass.states.async_set("input_number.jarvis_batterie_capacite", "0")
    await _relire(hass)
    assert _issues(hass) == ["etape_batterie"]

    hass.states.async_set("input_number.jarvis_batterie_capacite", "10.24")
    hass.states.async_set("input_select.jarvis_type_tarif", "Heures pleines / heures creuses")
    hass.states.async_set("input_number.jarvis_prix_hp", "0.25")
    hass.states.async_set("input_number.jarvis_prix_hc", "0.18")
    await _relire(hass)
    assert _issues(hass) == ["etape_jours_ouvres"]

    hass.states.async_set("binary_sensor.workday_sensor", "on")
    await _relire(hass)
    assert _issues(hass) == ["etape_prevision_solaire"]
    assert hass.states.get("sensor.ucaness_installation").state == "a_configurer"

    # Capteur Solcast présent mais sans prévision heure par heure : l'étape reste à faire.
    hass.states.async_set("sensor.solcast_pv_forecast_prevision_demain", "12")
    await _relire(hass)
    assert _issues(hass) == ["etape_prevision_solaire"]
    hass.states.async_set("sensor.solcast_pv_forecast_prevision_demain", "12", {"detailedHourly": [{"pv_estimate": 1.0}]})
    await _relire(hass)

    # Tout l'obligatoire est fait : simulation, et seule l'étape facultative reste proposée.
    etat = hass.states.get("sensor.ucaness_installation")
    assert etat.state == "en_simulation"
    assert _issues(hass) == ["etape_notifications"]

    async def notifier(call):
        return None

    hass.services.async_register("notify", "mobile_app_essai", notifier)
    hass.states.async_set("input_text.jarvis_service_notification", "mobile_app_essai")
    await _relire(hass)
    etat = hass.states.get("sensor.ucaness_installation")
    assert _issues(hass) == []
    assert etat.attributes["progression"] == 100 and etat.attributes["etape_suivante"] is None


async def test_assistant_installation_en_service_ne_modifie_rien(hass, cloud, fast_readback):
    """Installation déjà en service : état « en_service », aucune réparation, aucune écriture."""
    for entite, valeur in (
        ("input_boolean.jarvis_mode_simulation", "off"), ("input_number.jarvis_batterie_capacite", "10.24"),
        ("input_select.jarvis_type_tarif", "Base"), ("input_number.jarvis_prix_hp", "0.25"),
        ("binary_sensor.workday_sensor", "on"), ("input_text.jarvis_service_notification", "mobile_app_essai"),
    ):
        hass.states.async_set(entite, valeur)
    hass.states.async_set("sensor.solcast_pv_forecast_prevision_aujourdhui", "8", {"detailedHourly": [{"pv_estimate": 1.0}]})

    async def notifier(call):
        return None

    hass.services.async_register("notify", "mobile_app_essai", notifier)
    avant = {e: hass.states.get(e).state for e in hass.states.async_entity_ids() if e.startswith("input_")}
    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=True)
    await _relire(hass)
    assert hass.states.get("sensor.ucaness_installation").state == "en_service"
    assert _issues(hass) == []
    assert {e: hass.states.get(e).state for e in avant} == avant
    assert cloud.updates == []          # rien n'est parti vers l'onduleur

    # Écriture retirée alors que la simulation est éteinte : à vérifier.
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options={**entry.options, "write_enabled": False})
    await hass.async_block_till_done()
    await _relire(hass)
    assert hass.states.get("sensor.ucaness_installation").state == "a_verifier"


async def test_assistant_installation_reparations_retirees_au_dechargement(hass, fake_client):
    await _create_entry(hass)
    await hass.async_block_till_done()
    assert _issues(hass) == ["etape_packages"]
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert _issues(hass) == []


# ------------------------------------------------------------------ pilotage

@pytest.fixture
def fast_readback():
    with patch("custom_components.ucaness.services.READBACK_DELAY_S", 0):
        yield


async def _entry_with_options(hass, **options):
    result = await _create_entry(hass)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(result["result"].entry_id)
    if options:
        hass.config_entries.async_update_entry(entry, options={"scan_interval": 60, **options})
        await hass.async_block_till_done()
    return entry


async def test_write_refused_when_option_disabled(hass, fake_client, fast_readback):
    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=False)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "definir_mode", {"mode": "arbitrage_horaire"}, blocking=True)
    assert all(c.writes == [] for c in FakeClient.instances)


async def test_backup_mode_is_not_offered(hass, fake_client, fast_readback):
    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=True)
    with pytest.raises(Exception):
        await hass.services.async_call(DOMAIN, "definir_mode", {"mode": "backup"}, blocking=True)


async def test_tester_api_is_read_only(hass, fake_client, fast_readback):
    await _entry_with_options(hass, app_key="k", app_secret="s")
    resp = await hass.services.async_call(DOMAIN, "tester_api", {}, blocking=True, return_response=True)
    assert resp["device_id"] == "MA_testcode01"
    assert resp["inverter_model"] == "mr"
    assert resp["ecriture_autorisee"] is False
    assert resp["modele_confirme_pour_ecriture"] is True
    assert resp["reglages_bruts"]["bat_grid_dod"] == 900
    assert resp["work_mode"] == 0            # absent de la configuration = autoconsommation
    assert resp["mode_affiche"] == "Match Load Mode"
    assert all(c.writes == [] for c in FakeClient.instances)


async def test_windows_then_mode_written_and_confirmed(hass, fake_client, fast_readback):
    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=True)
    client = FakeClient.instances[-1]
    resp = await hass.services.async_call(
        DOMAIN, "definir_plages_charge",
        {"plages": [{"debut": "2300", "fin": "2359"}, {"debut": "0000", "fin": "0130"}]},
        blocking=True, return_response=True,
    )
    assert resp["confirme"] is True
    assert client.writes[-1][44] == 2300 and client.writes[-1][49] == 130
    assert client.writes[-1][46] == 0  # décharge vidée
    resp = await hass.services.async_call(DOMAIN, "definir_mode", {"mode": "arbitrage_horaire"}, blocking=True, return_response=True)
    assert resp["confirme"] is True
    assert client.writes[-1] == {1: 1}


async def test_unconfirmed_write_raises(hass, fake_client, fast_readback):
    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=True)
    client = FakeClient.instances[-1]
    client.apply_writes = False  # l'onduleur ne reflète pas la consigne
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "definir_mode", {"mode": "arbitrage_horaire"}, blocking=True)


async def test_options_keep_secret_when_left_empty(hass, fake_client):
    entry = await _entry_with_options(hass)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"], {"scan_interval": 60, "app_key": "k", "app_secret": "s", "write_enabled": False}
    )
    await hass.async_block_till_done()
    assert entry.options["app_secret"] == "s"
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"], {"scan_interval": 60, "app_key": "k", "app_secret": "", "write_enabled": True}
    )
    await hass.async_block_till_done()
    assert entry.options["app_secret"] == "s"
    assert entry.options["write_enabled"] is True


async def test_mode_confirmed_by_inverter_state_when_cloud_does_not_store_it(hass, fake_client, fast_readback):
    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=True)
    client = FakeClient.instances[-1]
    client.store_mode = False   # comme le 18/11/2026 : le mode n'apparaît pas dans la configuration
    resp = await hass.services.async_call(DOMAIN, "definir_mode", {"mode": "arbitrage_horaire"}, blocking=True, return_response=True)
    assert resp["confirme"] is True
    resp = await hass.services.async_call(DOMAIN, "definir_mode", {"mode": "autoconsommation"}, blocking=True, return_response=True)
    assert resp["confirme"] is True
    assert client.writes[-1] == {1: 0}


async def test_zero_windows_absent_from_cloud_are_confirmed(hass, fake_client, fast_readback):
    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=True)
    resp = await hass.services.async_call(DOMAIN, "definir_plages_charge", {"plages": []}, blocking=True, return_response=True)
    assert resp["confirme"] is True
    client = FakeClient.instances[-1]
    assert client.writes[-1][44] == 0 and client.writes[-1][45] == 0


# --- Vrai client derrière un faux nuage (au niveau de UcanessClient._request) ---------------------
class FakeCloud:
    """Répond aux chemins du portail et de l'API tierce ; applique les réglages reçus.

    Le vrai UcanessClient est utilisé (envoi différentiel, plafond d'écritures, verrous) :
    seule la requête HTTP est remplacée. Données inventées.
    """

    def __init__(self):
        self.settings = {"charge_time1_start": 100, "charge_time1_end": 300}
        self.updates = []

    async def request(self, client, path, payload, auth, signed=False):
        ok = {"error_code": 2000, "msg": "ok"}
        if path == "/user/signin":
            return {**ok, "token": "jeton-test"}
        if path == "/device/detail/load":
            detail = fx("detail_load")
            detail["status"]["work_mode_str"] = "Peak Fill Mode" if self.settings.get("work_mode") else "Match Load Mode"
            return {**ok, "data": detail}
        if path == "/device/config":
            return {**ok, "data": fx("device_config")}
        if path == "/oss/event/info":
            return {**ok, "data": fx("events")}
        if path == "/api/v1/device/list":
            return {**ok, "list": [{"device_id": "MA_testcode01", "inverter_model": "mr"}]}
        if path == "/api/v1/device/config":
            pcs = {k: v for k, v in self.settings.items() if v != 0}
            return {**ok, "data": {"inverter_model": "mr", "pcs": {"mr": pcs}}}
        if path == SETTINGS_UPDATE_PATH:
            self.updates.append(payload["pcs"])
            for item in payload["pcs"]:
                self.settings[CONFIG_KEYS[item["set_id"]][0]] = item["set_data"]
            return ok
        raise AssertionError(f"chemin inattendu {path}")


@pytest.fixture
def cloud():
    fake = FakeCloud()

    async def _request(self, path, payload, auth, signed=False):
        return await fake.request(self, path, payload, auth, signed)

    with patch.object(UcanessClient, "_request", _request):
        yield fake


async def test_write_budget_survives_reload(hass, cloud, fast_readback):
    """Le plafond d'écritures par heure n'est pas remis à zéro par un rechargement (changement d'options)."""
    with patch("custom_components.ucaness.api.MAX_WRITES_PER_HOUR", 2), patch(
        "custom_components.ucaness.api.MIN_WRITE_INTERVAL_S", 0
    ):
        entry = await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=True)
        client_avant = _client(hass, entry)
        await hass.services.async_call(DOMAIN, "definir_mode", {"mode": "arbitrage_horaire"}, blocking=True)
        await hass.services.async_call(DOMAIN, "definir_mode", {"mode": "autoconsommation"}, blocking=True)
        assert len(cloud.updates) == 2

        # Changement d'options : l'intégration se recharge avec un nouveau client.
        hass.config_entries.async_update_entry(entry, options={**entry.options, "scan_interval": 120})
        await hass.async_block_till_done()
        assert _client(hass, entry) is not client_avant

        with pytest.raises(ServiceValidationError, match="écritures en une heure"):
            await hass.services.async_call(DOMAIN, "definir_mode", {"mode": "arbitrage_horaire"}, blocking=True)
        assert len(cloud.updates) == 2   # rien n'est parti vers l'onduleur


async def test_diagnostics_masquent_secrets_et_identifiants(hass, cloud):
    from custom_components.ucaness.api import hash_password
    from custom_components.ucaness.diagnostics import async_get_config_entry_diagnostics

    entry = await _entry_with_options(hass, app_key="cle-app-test-123", app_secret="secret-app-test-456", write_enabled=True)
    assert _client(hass, entry).has_token          # le jeton existe bien côté client
    diag = await async_get_config_entry_diagnostics(hass, entry)
    texte = json.dumps(diag, ensure_ascii=False)

    for secret in ("user@example.org", hash_password("secret"), "cle-app-test-123", "secret-app-test-456", "jeton-test"):
        assert secret not in texte, secret
    for identifiant in ("testcode01", "S0000TEST", "REWTEST", "Maison Test"):
        assert identifiant not in texte, identifiant
    # Ce qui sert au diagnostic reste lisible.
    assert diag["donnees"]["valeurs"]["soc"] == pytest.approx(41.0)
    assert diag["entree"]["options"]["scan_interval"] == 60
    assert diag["client"] == {"session_ouverte": True, "cle_application_presente": True, "ecriture_autorisee": True}


# --- Tarif dynamique : actions de calcul (rien n'est envoyé) -------------------------------------
def _prix_jour(debut, valeurs):
    import datetime as dt
    return [{"debut": (debut + dt.timedelta(hours=h)).isoformat(), "prix": p} for h, p in enumerate(valeurs)]


async def test_optimiser_charge_calcule_sans_ecrire(hass, fake_client, fast_readback):
    import datetime as dt
    from homeassistant.util import dt as dt_util

    deja = len(FakeClient.instances)
    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=True)
    debut = dt_util.now().replace(minute=0, second=0, microsecond=0)
    prix = _prix_jour(debut, [0.08] * 4 + [0.30] * 20)
    solaire = [{"debut": (debut + dt.timedelta(hours=h)).isoformat(), "kwh": 0.0} for h in range(24)]
    resp = await hass.services.async_call(
        DOMAIN, "optimiser_charge",
        {"prix": prix, "conso": [0.8] * 24, "solaire": solaire, "capacite_kwh": 10, "plancher_pct": 10,
         "soc_pct": 10, "puissance_charge_kw": 3},
        blocking=True, return_response=True,
    )
    assert resp["valide"] is True
    assert 1 <= resp["nombre_plages"] <= 3
    assert resp["prochaine_plage"] is not None or resp["charge_en_cours"] is True
    assert resp["gain_estime_eur"] > 0
    assert all(c.writes == [] for c in FakeClient.instances[deja:])


async def test_optimiser_charge_repli_sur_sans_prevision(hass, fake_client, fast_readback):
    from homeassistant.util import dt as dt_util

    await _entry_with_options(hass, app_key="k", app_secret="s")
    resp = await hass.services.async_call(
        DOMAIN, "optimiser_charge",
        {"prix": _prix_jour(dt_util.now(), [0.1] * 24), "conso": [0.5] * 24, "solaire": [],
         "capacite_kwh": 10, "plancher_pct": 10, "soc_pct": 50, "puissance_charge_kw": 3},
        blocking=True, return_response=True,
    )
    assert resp["valide"] is False and resp["plages"] == []
    assert "repli sûr" in resp["justification"]


async def test_plages_depuis_plan_emhass(hass, fake_client):
    import datetime as dt
    from homeassistant.util import dt as dt_util

    await _entry_with_options(hass, app_key="k", app_secret="s")
    t0 = dt_util.now().replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
    plan = [{"date": (t0 + dt.timedelta(minutes=30 * i)).isoformat(), "p_batt": -3000 if i < 4 else 800,
             "p_grid": 3200 if i < 4 else 0} for i in range(20)]
    resp = await hass.services.async_call(DOMAIN, "plages_depuis_plan", {"plan": plan}, blocking=True, return_response=True)
    assert resp["valide"] is True
    assert resp["charge_reseau_kwh"] == 6.0
    assert len(resp["plages"]) in (1, 2)


def test_services_yaml_selecteurs_valides():
    """Home Assistant refuse tout services.yaml dont un sélecteur est invalide (descriptions perdues)."""
    import yaml
    from homeassistant.helpers import selector

    d = yaml.safe_load((pathlib.Path(__file__).parents[1] / "custom_components" / "ucaness" / "services.yaml").read_text())
    for service, conf in d.items():
        for champ, f in (conf.get("fields") or {}).items():
            selector.validate_selector(f["selector"])
