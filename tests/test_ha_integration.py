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

from custom_components.ucaness.api import CONFIG_KEYS, UcanessAuthError, UcanessWriteRefused, validate_settings
from custom_components.ucaness.const import CONF_DEVICE_CODE, DOMAIN

FIX = pathlib.Path(__file__).parent / "fixtures"


def fx(name):
    return json.loads((FIX / f"{name}.json").read_text())


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

    soc = hass.states.get("sensor.maison_test_charge_batterie_soc")
    assert soc is not None and float(soc.state) == pytest.approx(41.0)
    assert soc.attributes["unit_of_measurement"] == "%"

    solar_total = hass.states.get("sensor.maison_test_production_solaire_totale")
    assert float(solar_total.state) == pytest.approx(5000.0)
    assert solar_total.attributes["state_class"] == "total_increasing"
    assert solar_total.attributes["device_class"] == "energy"

    dod = hass.states.get("sensor.maison_test_reglage_dod_raccorde_au_reseau")
    assert float(dod.state) == pytest.approx(90.0)

    fault = hass.states.get("binary_sensor.maison_test_defaut_ou_alarme_batterie")
    assert fault.state == "off"
    temp = hass.states.get("binary_sensor.maison_test_temperature_batterie_hors_plage_de_charge_0_50_degc")
    assert temp.state == "off"


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
