"""Tests du package météo (jarvis_meteo.yaml) dans un vrai Home Assistant. Données INVENTÉES.
Usage : cd pilotage/tests && python -m pytest -q test_meteo.py
"""
import pathlib

import pytest
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml

PKG = pathlib.Path(__file__).resolve().parent.parent / "packages"


@pytest.fixture
async def meteo(hass, caplog):
    pkg = load_yaml(str(PKG / "jarvis_meteo.yaml"))
    hass.states.async_set("weather.maison", "sunny", {"temperature": 11.5, "temperature_unit": "°C"})
    hass.states.async_set("weather.zz_autre", "cloudy", {"temperature": 9.0})
    assert await async_setup_component(hass, "input_text", {"input_text": pkg["input_text"]})
    assert await async_setup_component(hass, "template", {"template": pkg["template"]})
    await hass.async_block_till_done()
    assert "Invalid config" not in caplog.text, caplog.text


async def test_temperature_premiere_entite(hass, meteo):
    t = hass.states.get("sensor.jarvis_temperature_exterieure")
    assert float(t.state) == 11.5
    assert t.attributes["source"] == "weather.maison"
    assert t.attributes["state_class"] == "measurement" and t.attributes["unit_of_measurement"] == "°C"


async def test_temperature_entite_choisie(hass, meteo):
    await hass.services.async_call("input_text", "set_value", {"entity_id": "input_text.jarvis_meteo_entite", "value": "weather.zz_autre"}, blocking=True)
    await hass.async_block_till_done()
    assert float(hass.states.get("sensor.jarvis_temperature_exterieure").state) == 9.0


async def test_temperature_indisponible(hass, meteo):
    hass.states.async_set("weather.maison", "unavailable", {})
    hass.states.async_set("weather.zz_autre", "unavailable", {})
    await hass.async_block_till_done()
    assert hass.states.get("sensor.jarvis_temperature_exterieure").state == "unavailable"
