"""Tests du client (contre un faux serveur local) et du décodage des mesures.

Les modules api.py et parser.py sont chargés directement, sans Home Assistant.
"""
import asyncio
import hashlib
import importlib.util
import json
import pathlib
import sys

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "ucaness"
FIX = ROOT / "tests" / "fixtures"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"ucaness_{name}", PKG / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


api = _load("api")
parser = _load("parser")


def fixture(name):
    return json.loads((FIX / f"{name}.json").read_text())


# ----------------------------------------------------------------- parser

def test_extract_scales_and_units():
    data = {"detail": fixture("detail_load"), "config": fixture("device_config"), "events": fixture("events"), "now": 1893456060}
    v = parser.extract(data)
    assert v["soc"] == pytest.approx(41.0)
    assert v["soh"] == pytest.approx(98.0)
    assert v["grid_voltage"] == pytest.approx(237.5)
    assert v["grid_frequency"] == pytest.approx(50.01)
    assert v["battery_temp"] == pytest.approx(22.0)
    assert v["cell_temp_min"] == pytest.approx(20.0)
    assert v["cell_voltage_max"] == pytest.approx(3.34)
    assert v["energy_solar_total"] == pytest.approx(5000.0)
    assert v["energy_grid_export_today"] == pytest.approx(0.02)
    assert v["grid_power"] == pytest.approx(581 + 1591 - 2172)  # ~0 W : bilan équilibré
    assert v["setting_dod"] == pytest.approx(90.0)
    assert v["setting_hysteresis"] == pytest.approx(10.0)
    assert v["setting_charge_current"] == pytest.approx(100.0)
    assert v["setting_charge1_start"] == "01:00"
    assert v["setting_charge1_end"] == "03:00"
    assert v["battery_modules"] == 3
    assert v["data_age"] == 60
    assert v["event_count"] == 0
    assert v["work_mode"] == "Match Load Mode"


def test_extract_tolerates_missing_blocks():
    v = parser.extract({"detail": {}, "config": {}, "events": {}})
    assert all(value is None for value in v.values())


# ----------------------------------------------------------------- client

class FakeUcaness:
    """Imite le serveur app.ucaness.com pour les chemins utilisés."""

    def __init__(self):
        self.password_md5 = hashlib.md5(b"secret").hexdigest()
        self.valid_tokens = set()
        self.calls = []
        self.expire_next = False
        self.signin_delay = 0.0  # lenteur de la connexion, pour faire se chevaucher des appels

    async def handle(self, request):
        path = request.path
        body = await request.json()
        self.calls.append(path)
        if path == "/user/signin":
            await asyncio.sleep(self.signin_delay)
            if body.get("sign") == "user@example.org" and body.get("password") == self.password_md5:
                tok = f"tok{len(self.valid_tokens)}"
                self.valid_tokens.add(tok)
                return web.json_response({"error_code": 2000, "token": tok})
            return web.json_response({"error_code": "5032", "msg": "bad credentials"})
        auth = request.headers.get("Authorization", "")
        if self.expire_next:
            self.expire_next = False
            self.valid_tokens.clear()
        if not auth.startswith("Bearer ") or auth[7:] not in self.valid_tokens:
            return web.json_response({"error_code": 4018, "msg": "Login timed out."})
        if path == "/device/detail/load":
            assert body == {"code": "testcode01", "tz": 3600}
            return web.json_response({"error_code": 2000, "msg": "ok", "data": fixture("detail_load")})
        if path == "/device/config":
            return web.json_response({"error_code": "2000", "msg": "Ok", "data": fixture("device_config")})
        if path == "/oss/event/info":
            return web.json_response({"error_code": 2000, "msg": "ok", "data": fixture("events")})
        return web.json_response({"error_code": 404, "msg": "unknown"})


async def _with_server(test):
    fake = FakeUcaness()
    app = web.Application()
    app.router.add_post("/{tail:.*}", fake.handle)
    server = TestServer(app)
    await server.start_server()
    try:
        async with aiohttp.ClientSession() as session:
            await test(fake, session, str(server.make_url("")))
    finally:
        await server.close()


def test_login_and_read_detail():
    async def scenario(fake, session, base):
        client = api.UcanessClient(session, "user@example.org", api.hash_password("secret"), base_url=base)
        detail = await client.get_detail("testcode01")
        assert detail["status"]["soc"] == 410
        cfg = await client.get_config("testcode01")
        assert cfg["pcs"]["mr"]["bat_grid_dod"] == 900
        assert fake.calls[0] == "/user/signin"
    asyncio.run(_with_server(scenario))


def test_relogin_when_session_expired():
    async def scenario(fake, session, base):
        client = api.UcanessClient(session, "user@example.org", api.hash_password("secret"), base_url=base)
        await client.get_detail("testcode01")
        fake.expire_next = True
        detail = await client.get_detail("testcode01")
        assert detail["is_online"] is True
        assert fake.calls.count("/user/signin") == 2
    asyncio.run(_with_server(scenario))


def test_concurrent_calls_sign_in_once():
    """Trois lectures simultanées sans session : une seule connexion, le jeton est partagé."""
    async def scenario(fake, session, base):
        fake.signin_delay = 0.05
        client = api.UcanessClient(session, "user@example.org", api.hash_password("secret"), base_url=base)
        await asyncio.gather(
            client.get_detail("testcode01"), client.get_config("testcode01"), client.get_events("testcode01")
        )
        assert fake.calls.count("/user/signin") == 1
    asyncio.run(_with_server(scenario))


def test_bad_credentials():
    async def scenario(fake, session, base):
        client = api.UcanessClient(session, "user@example.org", api.hash_password("wrong"), base_url=base)
        with pytest.raises(api.UcanessAuthError):
            await client.get_detail("testcode01")
    asyncio.run(_with_server(scenario))


def test_write_paths_are_refused_before_network():
    async def scenario(fake, session, base):
        client = api.UcanessClient(session, "user@example.org", api.hash_password("secret"), base_url=base)
        for path in ("/device/settings/update", "/device/config/update", "/device/ems/config/save"):
            with pytest.raises(ValueError):
                await client._request(path, {}, auth=True)
        assert fake.calls == []  # rien n'a atteint le serveur
    asyncio.run(_with_server(scenario))


def test_md5_matches_portal():
    # Le portail envoie md5(mot de passe) en hexadécimal minuscule.
    assert api.hash_password("tourist123") == hashlib.md5(b"tourist123").hexdigest()


def test_grid_power_at_night_without_solar_value():
    """19/11/2026 : la nuit, pas de « solar_power » : l'estimation ne doit pas être inconnue."""
    raw = {"detail": {"status": {"load_power": 250, "battery_power": -222}}, "config": {}, "events": {}, "now": 0}
    values = parser.extract(raw)
    assert values["grid_power"] == 28
    assert values["solar_power"] == 0
