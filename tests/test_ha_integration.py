"""Tests de bout en bout dans un vrai Home Assistant (banc pytest-homeassistant-custom-component).

Le client UCANESS est remplacé par un faux qui renvoie les jeux de données de test :
aucun appel réseau, aucune écriture possible.
"""
import json
import pathlib
from unittest.mock import patch

import pytest
import voluptuous as vol
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
    # Home Assistant en français : noms et identifiants identiques à ceux d'avant les traductions (0.4.2).
    hass.config.language = "fr"
    await _create_entry(hass)
    await hass.async_block_till_done()

    # Les entités lues par le pilotage portent d'emblée l'identifiant attendu (rien à renommer).
    soc = hass.states.get("sensor.uhome_soc")
    assert soc is not None and float(soc.state) == pytest.approx(41.0)
    assert soc.attributes["unit_of_measurement"] == "%"

    solar_total = hass.states.get("sensor.uhome_production_solaire_totale")
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
    # « solaire » : l'onduleur a déjà mesuré une production, la question n'est pas posée.
    assert etat.attributes["etapes_faites"] == ["connexion", "entites", "solaire"]
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


async def test_textes_traduits_en_anglais(hass, fake_client, fast_readback):
    """Home Assistant en anglais : noms d'entités, états et messages d'erreur en anglais."""
    hass.config.language = "en"
    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=False)
    assert hass.states.get("sensor.uhome_soc").attributes["friendly_name"].endswith("Battery charge (SOC)")
    assert hass.states.get("sensor.maison_test_on_grid_dod_setting") is not None     # identifiant tiré du nom anglais
    with pytest.raises(ServiceValidationError, match="Writing to the inverter is disabled") as erreur:
        await hass.services.async_call(DOMAIN, "definir_mode", {"mode": "arbitrage_horaire"}, blocking=True)
    assert erreur.value.translation_key == "ecriture_desactivee"
    from custom_components.ucaness import reglages
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    with pytest.raises(ServiceValidationError, match="outside the range 0 to 40") as erreur:
        await reglages.async_definir(hass, entry, {"capacite": 99})
    assert erreur.value.translation_placeholders["reglage"] == "Battery: capacity"


async def test_textes_traduits_en_chinois(hass, fake_client, fast_readback):
    """Home Assistant en chinois simplifié : noms en chinois, identifiants tirés de l'anglais."""
    hass.config.language = "zh-Hans"
    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=False)
    assert hass.states.get("sensor.uhome_soc").attributes["friendly_name"].endswith("电池电量（SOC）")
    assert hass.states.get("sensor.maison_test_on_grid_dod_setting") is not None
    assert hass.states.get("select.ucaness_type_tarif") is not None


async def test_textes_traduits_en_allemand(hass, fake_client, fast_readback):
    """Home Assistant en allemand : noms en allemand, identifiants tirés de l'allemand (langue à identifiants natifs)."""
    hass.config.language = "de"
    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=False)
    assert hass.states.get("sensor.uhome_soc").attributes["friendly_name"].endswith("Batterieladestand (SOC)")
    assert hass.states.get("sensor.maison_test_einstellung_dod_am_netz") is not None
    from custom_components.ucaness import reglages
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    with pytest.raises(ServiceValidationError) as erreur:
        await reglages.async_definir(hass, entry, {"capacite": 99})
    assert erreur.value.translation_placeholders["reglage"] == "Batterie: Kapazität"


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
    assert diag["client"] == {"session_ouverte": True, "cle_application_presente": True,
                              "origine_cle_application": "personnelle", "ecriture_autorisee": True}


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


# ------------------------------------------------------------------ réglages dans l'intégration
PAQUETS = pathlib.Path(__file__).parents[1] / "pilotage" / "packages"


async def _entrees_du_pilotage(hass):
    """Les vraies entrées des packages batterie et tarif (celles que lit le pilotage)."""
    from homeassistant.setup import async_setup_component
    from homeassistant.util.yaml import load_yaml

    bat, tarif = (load_yaml(str(PAQUETS / n)) for n in ("jarvis_batterie.yaml", "jarvis_tarif.yaml"))
    for domaine in ("input_number", "input_select", "input_boolean", "input_datetime"):
        assert await async_setup_component(hass, domaine, {domaine: {**bat.get(domaine, {}), **tarif.get(domaine, {})}})
    # Sans valeur restaurée, une liste de choix prend sa première option (« Détection automatique »).
    await hass.async_block_till_done()


async def test_reglages_crees_et_vides_au_depart(hass, fake_client):
    from custom_components.ucaness.reglages import REGLAGES

    await _create_entry(hass)
    await hass.async_block_till_done()
    for r in REGLAGES:
        etat = hass.states.get(f"{r.type}.ucaness_{r.cle}")
        assert etat is not None, r.cle
        assert etat.state == "unknown", r.cle       # jamais renseigné : pas de valeur inventée


async def test_reglage_enregistre_sans_recharger_l_integration(hass, fake_client):
    entry = await _entry_with_options(hass)
    coordinateur = entry.runtime_data
    await hass.services.async_call("number", "set_value", {"entity_id": "number.ucaness_capacite", "value": 10.24}, blocking=True)
    await hass.services.async_call("select", "select_option", {"entity_id": "select.ucaness_type_tarif", "option": "base"}, blocking=True)
    await hass.services.async_call("time", "set_value", {"entity_id": "time.ucaness_hc_debut", "time": "23:00:00"}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.ucaness_hc_jours_non_ouvres"}, blocking=True)
    await hass.async_block_till_done()
    assert entry.options["reglages"] == {"capacite": 10.24, "type_tarif": "Base", "hc_debut": "23:00:00", "hc_jours_non_ouvres": True}
    assert float(hass.states.get("number.ucaness_capacite").state) == pytest.approx(10.24)
    assert hass.states.get("select.ucaness_type_tarif").state == "base"      # clé traduite ; l'entrée garde « Base »
    assert hass.states.get("time.ucaness_hc_debut").state == "23:00:00"
    assert hass.states.get("switch.ucaness_hc_jours_non_ouvres").state == "on"
    assert entry.runtime_data is coordinateur            # pas de rechargement, pas de nouvelle connexion


async def test_reglage_hors_bornes_refuse(hass, fake_client):
    from custom_components.ucaness import reglages

    entry = await _entry_with_options(hass)
    with pytest.raises(ServiceValidationError):
        await reglages.async_definir(hass, entry, {"capacite": 400})
    with pytest.raises(ServiceValidationError):
        await reglages.async_definir(hass, entry, {"type_tarif": "Tempo"})
    with pytest.raises(ServiceValidationError):
        await reglages.async_definir(hass, entry, {"inconnu": 1})
    assert "reglages" not in entry.options


async def test_reglage_et_entree_du_package_une_seule_valeur(hass, fake_client):
    """Tant que le pilotage lit ses entrées, l'entrée est la référence : écrire le réglage la met à
    jour, la modifier met à jour le réglage."""
    await _entrees_du_pilotage(hass)
    entry = await _entry_with_options(hass)
    await hass.services.async_call("number", "set_value", {"entity_id": "number.ucaness_capacite", "value": 10.24}, blocking=True)
    await hass.services.async_call("time", "set_value", {"entity_id": "time.ucaness_hc_fin", "time": "06:00:00"}, blocking=True)
    await hass.services.async_call("select", "select_option", {"entity_id": "select.ucaness_type_tarif", "option": "base"}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.ucaness_hc_jours_non_ouvres"}, blocking=True)
    await hass.async_block_till_done()
    assert float(hass.states.get("input_number.jarvis_batterie_capacite").state) == pytest.approx(10.24)
    assert hass.states.get("input_datetime.jarvis_hc_fin").state == "06:00:00"
    assert hass.states.get("input_select.jarvis_type_tarif").state == "Base"
    assert hass.states.get("input_boolean.jarvis_hc_jours_non_ouvres").state == "on"

    # Modification dans Paramètres > Entrées : le réglage de l'intégration suit.
    await hass.services.async_call("input_number", "set_value", {"entity_id": "input_number.jarvis_batterie_capacite", "value": 15}, blocking=True)
    await hass.async_block_till_done()
    assert float(hass.states.get("number.ucaness_capacite").state) == pytest.approx(15)
    assert entry.runtime_data is not None


async def test_options_conservent_les_reglages(hass, fake_client):
    from custom_components.ucaness import reglages

    entry = await _entry_with_options(hass)
    await reglages.async_definir(hass, entry, {"capacite": 10.24})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {"scan_interval": 90, "write_enabled": False})
    await hass.async_block_till_done()
    assert entry.options["scan_interval"] == 90
    assert entry.options["reglages"] == {"capacite": 10.24}


async def test_diagnostics_masquent_les_reglages(hass, cloud):
    from custom_components.ucaness import reglages
    from custom_components.ucaness.diagnostics import async_get_config_entry_diagnostics

    entry = await _entry_with_options(hass)
    await reglages.async_definir(hass, entry, {"prix_hp": 0.31234, "capacite": 10.24})
    texte = json.dumps(await async_get_config_entry_diagnostics(hass, entry), default=str)
    assert "0.31234" not in texte and "10.24" not in texte


# ------------------------------------------------------------------ écrans de questions
async def _flux(hass, cle):
    from custom_components.ucaness.repairs import async_create_fix_flow

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    issue = next(i for i in ir.async_get(hass).issues.values() if i.domain == DOMAIN and i.translation_key == f"etape_{cle}")
    assert issue.is_fixable
    flux = await async_create_fix_flow(hass, issue.issue_id, issue.data)
    flux.hass = hass
    return flux, entry


async def test_question_batterie(hass, fake_client):
    """Capacité proposée d'après le nombre de modules lu, confirmée par l'utilisateur, recopiée
    dans l'entrée du pilotage ; l'assistant passe à l'étape suivante."""
    await _entrees_du_pilotage(hass)
    await _create_entry(hass)
    await _relire(hass)
    assert _issues(hass) == ["etape_batterie"]
    flux, entry = await _flux(hass, "batterie")
    ecran = await flux.async_step_init()
    assert ecran["type"] is FlowResultType.FORM
    modules = entry.runtime_data.data["values"]["battery_modules"]
    assert ecran["description_placeholders"]["modules"] == str(int(modules))
    assert ecran["description_placeholders"]["proposition"] == f"{round(modules * 5.12, 2):g}"

    refus = await flux.async_step_init({"capacite": 0, "plancher": 20, "puissance_charge": 3})
    assert refus["errors"] == {"capacite": "capacite_nulle"}
    fin = await flux.async_step_init({"capacite": 10.24, "plancher": 15, "puissance_charge": 3.3})
    assert fin["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert float(hass.states.get("input_number.jarvis_batterie_capacite").state) == pytest.approx(10.24)
    assert float(hass.states.get("input_number.jarvis_batterie_plancher").state) == pytest.approx(15)
    assert float(hass.states.get("number.ucaness_puissance_charge").state) == pytest.approx(3.3)
    assert _issues(hass) == ["etape_contrat"]


@pytest.mark.parametrize(("reponses", "ecran_attendu", "gain"), [
    ({"type_tarif": "Heures pleines / heures creuses", "prix_hp": 0.30, "prix_hc": 0.18}, "bilan", "9,1"),            # 0,95² × 0,30 − 0,18
    ({"type_tarif": "Heures pleines / heures creuses", "prix_hp": 0.22, "prix_hc": 0.21}, "bilan_non_rentable", "1,1"),   # 0,95² × 0,22 − 0,21
    ({"type_tarif": "Base", "prix_hp": 0.25}, "bilan_base", "0,0"),
])
async def test_question_contrat(hass, fake_client, reponses, ecran_attendu, gain):
    hass.config.language = "fr"     # gain affiché avec une virgule
    await _entrees_du_pilotage(hass)
    await _create_entry(hass)
    await hass.services.async_call("number", "set_value", {"entity_id": "number.ucaness_capacite", "value": 10.24}, blocking=True)
    await _relire(hass)
    assert _issues(hass) == ["etape_contrat"]
    flux, entry = await _flux(hass, "contrat")
    assert (await flux.async_step_init())["type"] is FlowResultType.FORM
    bilan = await flux.async_step_init({**reponses, "hc_debut": "23:00:00", "hc_fin": "06:00:00", "hc_jours_non_ouvres": True})
    assert bilan["step_id"] == ecran_attendu
    assert bilan["description_placeholders"]["gain"] == gain
    # Rien n'est enregistré avant la validation du bilan.
    assert float(hass.states.get("input_number.jarvis_prix_hp").state) == 0
    fin = await getattr(flux, f"async_step_{ecran_attendu}")({})
    assert fin["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert float(hass.states.get("input_number.jarvis_prix_hp").state) == pytest.approx(reponses["prix_hp"])
    assert hass.states.get("input_select.jarvis_type_tarif").state == reponses["type_tarif"]
    assert hass.states.get("input_datetime.jarvis_hc_debut").state == "23:00:00"
    assert hass.states.get("input_boolean.jarvis_hc_jours_non_ouvres").state == "on"
    assert _issues(hass) == ["etape_jours_ouvres"]


async def test_question_contrat_prix_manquant(hass, fake_client):
    await _entrees_du_pilotage(hass)
    await _create_entry(hass)
    await hass.services.async_call("number", "set_value", {"entity_id": "number.ucaness_capacite", "value": 10.24}, blocking=True)
    await _relire(hass)
    flux, _ = await _flux(hass, "contrat")
    refus = await flux.async_step_init({"type_tarif": "Heures pleines / heures creuses", "prix_hp": 0.30})
    assert refus["errors"] == {"prix_hc": "prix_nul"}
    refus = await flux.async_step_init({"type_tarif": "Base", "prix_hp": 0})
    assert refus["errors"] == {"prix_hp": "prix_nul"}


# ------------------------------------------------------------------ évaluer des offres
async def test_evaluer_offres_calcul_seul(hass, cloud):
    import datetime as dt
    from homeassistant.util import dt as dt_util

    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=True)
    debut = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(days=40)
    heures = [debut + dt.timedelta(hours=h) for h in range(24 * 40)]
    soutirage = [{"debut": h.isoformat(), "kwh": 2.0 if (h.hour >= 23 or h.hour < 6) else 0.2} for h in heures]
    aujourdhui = dt_util.now().date().isoformat()
    unique = {"nom": "Prix unique", "fournisseur": "Fournisseur A", "formule": "base",
              "abonnement_eur_an": {"6": 150, "9": 190}, "prix_kwh": {"base": 0.25},
              "source": "https://exemple.invalid/a", "date_prix": aujourdhui}
    nuit = {"nom": "Nuit", "fournisseur": "Fournisseur B", "formule": "hphc",
            "abonnement_eur_an": {"6": 160}, "prix_kwh": {"hp": 0.30, "hc": 0.20},
            "plages_hc": [{"debut": "2230", "fin": "0630"}], "source": "https://exemple.invalid/b", "date_prix": aujourdhui}
    tempo = {"nom": "Couleurs", "formule": "tempo", "abonnement_eur_an": {"6": 160}, "prix_kwh": {"bleu": 0.2}}
    resp = await hass.services.async_call(DOMAIN, "evaluer_offres", {
        "offres": [unique, nuit, tempo], "contrat_actuel": unique, "soutirage": soutirage, "puissance_kva": 6,
        "puissances_max_kva": [2.5] * 40,       # pointe de 2,5 kVA : 3 kVA suffiraient
    }, blocking=True, return_response=True)
    assert [l["nom"] for l in resp["classement"]] == ["Nuit", "Prix unique"]
    assert resp["classement"][0]["ecart_avec_contrat_actuel_eur_an"] < 0
    assert resp["classement"][0]["fiabilite"] == "indicatif"
    assert resp["offres_ecartees"][0]["nom"] == "Couleurs"
    assert resp["puissance"]["conseil"] == "baisser" and resp["puissance"]["sur"] is False
    assert cloud.updates == []          # rien n'est parti vers l'onduleur

    # Tempo complet, avec la couleur de deux jours mesurés.
    tempo_complet = {"nom": "Tempo", "formule": "tempo", "abonnement_eur_an": {"6": 160},
                     "prix_kwh": {"bleu_hp": 0.16, "bleu_hc": 0.13, "blanc_hp": 0.19, "blanc_hc": 0.15,
                                  "rouge_hp": 0.70, "rouge_hc": 0.16},
                     "jours_tempo": {"bleu": 300, "blanc": 43, "rouge": 22},
                     "source": "https://exemple.invalid/t", "date_prix": aujourdhui}
    j1, j2 = (debut + dt.timedelta(days=3)).date().isoformat(), (debut + dt.timedelta(days=4)).date().isoformat()
    resp = await hass.services.async_call(DOMAIN, "evaluer_offres", {
        "offres": [unique, tempo_complet], "soutirage": soutirage, "puissance_kva": 6,
        "couleurs_tempo": {j1: "Rouge", j2: "blanc"},
    }, blocking=True, return_response=True)
    noms = {l["nom"]: l for l in resp["classement"]}
    assert set(noms) == {"Prix unique", "Tempo"} and resp["offres_ecartees"] == []
    assert any("Aucun jour bleu mesuré" in r for r in noms["Tempo"]["remarques"])
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "evaluer_offres", {
            "offres": [tempo_complet], "soutirage": soutirage, "puissance_kva": 6, "couleurs_tempo": {j1: "vert"},
        }, blocking=True, return_response=True)


# ------------------------------------------------------------------ batterie sans panneaux
async def _detail_sans_solaire(self, code, tz=3600):
    """Réponse du portail d'un onduleur qui n'a jamais rien produit (batterie sans panneaux)."""
    detail = fx("detail_load")
    for cle in ("solar_power", "usage_solar_today", "usage_solar_month", "usage_solar_total"):
        detail["status"][cle] = 0
    return detail


async def test_production_mesuree_la_question_des_panneaux_n_est_pas_posee(hass, fake_client):
    """L'onduleur a déjà mesuré une production : l'assistant sait qu'il y a des panneaux."""
    await _entrees_du_pilotage(hass)
    await _create_entry(hass)
    await hass.services.async_call("number", "set_value", {"entity_id": "number.ucaness_capacite", "value": 10.24}, blocking=True)
    await _relire(hass)
    assert "solaire" in hass.states.get("sensor.ucaness_installation").attributes["etapes_faites"]
    assert _issues(hass) == ["etape_contrat"]
    assert hass.states.get("switch.ucaness_solaire").state == "unknown"       # constaté, pas déclaré


async def test_batterie_sans_panneaux(hass, fake_client):
    """Aucune production mesurée : la question est posée ; sans panneaux, la prévision solaire
    n'est plus demandée et l'installation peut passer en simulation."""
    with patch.object(FakeClient, "get_detail", _detail_sans_solaire):
        await _entrees_du_pilotage(hass)
        await _create_entry(hass)
        await hass.services.async_call("number", "set_value", {"entity_id": "number.ucaness_capacite", "value": 10.24}, blocking=True)
        await _relire(hass)
        assert _issues(hass) == ["etape_solaire"]
        flux, entry = await _flux(hass, "solaire")
        assert (await flux.async_step_init())["type"] is FlowResultType.FORM
        fin = await flux.async_step_init({"solaire": False})
        assert fin["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert entry.options["reglages"]["solaire"] is False
        assert hass.states.get("switch.ucaness_solaire").state == "off"
        # Le pilotage est prévenu : il calculera la recharge de nuit sans prévision solaire.
        assert hass.states.get("input_select.jarvis_solaire").state == "Sans panneaux"
        assert _issues(hass) == ["etape_contrat"]

        hass.states.async_set("input_boolean.jarvis_mode_simulation", "on")
        for entite, valeur in (("number.ucaness_prix_hp", 0.30), ("number.ucaness_prix_hc", 0.18)):
            await hass.services.async_call("number", "set_value", {"entity_id": entite, "value": valeur}, blocking=True)
        hass.states.async_set("binary_sensor.workday_sensor", "on")
        await _relire(hass)
        etat = hass.states.get("sensor.ucaness_installation")
        assert etat.state == "en_simulation"
        assert "prevision_solaire" in etat.attributes["etapes_faites"]
        assert _issues(hass) == ["etape_notifications"]


async def test_reglage_solaire_suit_le_choix_du_pilotage(hass, fake_client):
    """« Batterie : panneaux solaires » du package : un choix net fait foi ; en détection
    automatique, c'est la valeur enregistrée (ou la production mesurée) qui compte."""
    await _entrees_du_pilotage(hass)
    await _create_entry(hass)
    await hass.async_block_till_done()
    assert hass.states.get("input_select.jarvis_solaire").state == "Détection automatique"
    assert hass.states.get("switch.ucaness_solaire").state == "unknown"
    await hass.services.async_call("input_select", "select_option", {"entity_id": "input_select.jarvis_solaire", "option": "Sans panneaux"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("switch.ucaness_solaire").state == "off"
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.ucaness_solaire"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("input_select.jarvis_solaire").state == "Avec panneaux"
    assert hass.states.get("switch.ucaness_solaire").state == "on"


# ------------------------------------------------------------------ clé d'application livrée
@pytest.fixture
def cle_livree(monkeypatch):
    """Clé livrée avec l'intégration (valeurs INVENTÉES)."""
    from custom_components.ucaness import cle_application

    monkeypatch.setattr(cle_application, "CLE_LIVREE", "cle-livree-essai")
    monkeypatch.setattr(cle_application, "SECRET_LIVRE", "secret-livre-essai")


@pytest.mark.parametrize(("options", "attendu"), [
    ({}, ("cle-livree-essai", "secret-livre-essai", "livree")),
    ({"app_key": "perso", "app_secret": "s-perso"}, ("perso", "s-perso", "personnelle")),
    ({"app_key": "perso", "app_secret": ""}, ("cle-livree-essai", "secret-livre-essai", "livree")),   # clé incomplète
    ({"app_key": "", "app_secret": "s-perso"}, ("cle-livree-essai", "secret-livre-essai", "livree")),  # champ de clé vidé
    ({"app_key": "  ", "app_secret": " "}, ("cle-livree-essai", "secret-livre-essai", "livree")),
])
def test_cle_effective(cle_livree, options, attendu):
    from custom_components.ucaness.cle_application import cle_effective

    assert cle_effective(options) == attendu


def test_cle_effective_sans_cle_livree(monkeypatch):
    """Dépôt sans clé livrée : seule une clé personnelle complète sert."""
    from custom_components.ucaness import cle_application
    from custom_components.ucaness.cle_application import cle_effective

    monkeypatch.setattr(cle_application, "CLE_LIVREE", "")
    monkeypatch.setattr(cle_application, "SECRET_LIVRE", "")

    assert cle_effective({}) == ("", "", None)
    assert cle_effective({"app_key": "perso", "app_secret": "s"}) == ("perso", "s", "personnelle")


async def test_cle_livree_transmise_au_client(hass, fake_client, cle_livree):
    """Aucune clé saisie : le client reçoit la clé livrée et l'écriture fonctionne."""
    FakeClient.instances.clear()
    await _entry_with_options(hass, write_enabled=True)
    assert FakeClient.instances[-1].app_key == "cle-livree-essai"
    resp = await hass.services.async_call(DOMAIN, "tester_api", {}, blocking=True, return_response=True)
    assert resp["inverter_model"] == "mr"


async def test_cle_personnelle_passe_avant_la_cle_livree(hass, fake_client, cle_livree):
    FakeClient.instances.clear()
    await _entry_with_options(hass, app_key="perso", app_secret="s-perso", write_enabled=True)
    assert FakeClient.instances[-1].app_key == "perso"


async def test_assistant_en_service_avec_la_cle_livree(hass, cloud, fast_readback, cle_livree):
    """Mode réel, écriture autorisée, aucune clé saisie : l'installation est « en service »."""
    for entite, valeur in (
        ("input_boolean.jarvis_mode_simulation", "off"), ("input_number.jarvis_batterie_capacite", "10.24"),
        ("input_select.jarvis_type_tarif", "Base"), ("input_number.jarvis_prix_hp", "0.25"),
        ("binary_sensor.workday_sensor", "on"),
    ):
        hass.states.async_set(entite, valeur)
    hass.states.async_set("sensor.solcast_pv_forecast_prevision_aujourdhui", "8", {"detailedHourly": [{"pv_estimate": 1.0}]})
    await _entry_with_options(hass, write_enabled=True)
    await _relire(hass)
    assert hass.states.get("sensor.ucaness_installation").state == "en_service"


async def test_diagnostics_origine_de_la_cle_sans_la_cle(hass, cloud, cle_livree):
    from custom_components.ucaness.diagnostics import async_get_config_entry_diagnostics

    entry = await _entry_with_options(hass, write_enabled=True)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["client"]["origine_cle_application"] == "livree"
    texte = json.dumps(diag, default=str)
    assert "cle-livree-essai" not in texte and "secret-livre-essai" not in texte


def test_fichier_de_cle_livree_coherent():
    """Le fichier livré contient la clé ET le secret, ou ni l'un ni l'autre (jamais à moitié)."""
    from custom_components.ucaness import cle_application as c

    assert isinstance(c.CLE_LIVREE, str) and isinstance(c.SECRET_LIVRE, str)
    assert bool(c.CLE_LIVREE.strip()) == bool(c.SECRET_LIVRE.strip())


# ------------------------------------------------------------------ simulateur « et si »
async def test_simuler_contrat_et_puissance(hass, cloud):
    import datetime as dt
    from unittest.mock import MagicMock
    from homeassistant.util import dt as dt_util

    await _entry_with_options(hass, app_key="k", app_secret="s", write_enabled=True)
    for e, v in (("input_number.jarvis_prix_hp", "0.30638"), ("input_number.jarvis_prix_hc", "0.1729"),
                 ("input_select.jarvis_type_tarif", "Heures pleines / heures creuses"),
                 ("input_datetime.jarvis_hc_debut", "23:00:00"), ("input_datetime.jarvis_hc_fin", "06:00:00"),
                 ("input_boolean.jarvis_hc_jours_non_ouvres", "on"), ("input_boolean.jarvis_mode_simulation", "off")):
        hass.states.async_set(e, v)
    fin = dt_util.now().replace(minute=0, second=0, microsecond=0)
    heures = [fin - dt.timedelta(hours=h) for h in range(1, 24 * 30 + 1)]

    def stats(_hass, debut, fin_, ids, period, units, types):
        (eid,) = ids
        if "change" in types:
            return {eid: [{"start": h.timestamp(), "change": 1.0 if 7 <= h.hour < 22 else 0.4} for h in heures]}
        return {eid: [{"start": h.timestamp(), "max": 3500.0 if h.hour == 19 else 800.0} for h in heures]}

    instance = MagicMock()
    instance.async_add_executor_job = hass.async_add_executor_job
    with patch("homeassistant.components.recorder.get_instance", return_value=instance), \
         patch("homeassistant.components.recorder.statistics.statistics_during_period", side_effect=stats):
        r = await hass.services.async_call(DOMAIN, "simuler", {
            "question": "contrat", "puissance_actuelle_kva": 10, "abonnement_actuel_eur_an": 267}, blocking=True, return_response=True)
        p = await hass.services.async_call(DOMAIN, "simuler", {
            "question": "puissance", "puissance_actuelle_kva": 12}, blocking=True, return_response=True)
    noms = [l["nom"] for l in r["classement"]]
    assert "Tempo (tarif réglementé) (12 kVA)" in noms and "Heures creuses (tarif réglementé) (9 kVA)" in noms
    assert r["contrat_actuel"]["nom"] == "Contrat actuel" and r["contrat_actuel"]["jours_mesures"] == 30
    assert r["puissance_kva"] == 10 and r["question"] == "contrat"
    assert p["question"] == "puissance" and p["pointe_mesuree_kva"] == 3.5 and p["conseil"] == "baisser"
    assert p["puissance_recommandee_kva"] == 6 and p["sur"] is False
    assert cloud.updates == []
