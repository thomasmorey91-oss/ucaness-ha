"""Tests de l'API tierce signée et des garde-fous d'écriture (sans Home Assistant).

Un faux serveur imite app.ucaness.com : il vérifie la signature de chaque requête
/api/v1, applique les réglages reçus et les renvoie à la relecture.
"""
import asyncio
import hashlib
import hmac
import importlib.util
import pathlib
import sys

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "ucaness"

spec = importlib.util.spec_from_file_location("ucaness_api_pilotage", PKG / "api.py")
api = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = api
spec.loader.exec_module(api)

APP_KEY = "cle-test"
APP_SECRET = "secret-test"


# ------------------------------------------------------------------ fonctions pures

def test_signature_matches_documentation_example():
    # Exemple du § 3.4 de la documentation UCanpower.
    assert (
        api.sign("/api/v1/device/info", "123456", "1697182127", "abcde")
        == "43f3464bca5aed8ef3f35739285069251ad560b37c7ac0dc38fde2414b19a1e3"
    )


@pytest.mark.parametrize(
    "items",
    [
        {2: 50},      # DOD
        {3: 100},     # courant de charge
        {8: 2000},    # protection tension réseau
        {20: 1},      # norme réseau
        {23: 1},      # retour usine
        {25: 20},     # hystérésis
        {1: 2},       # mode Backup
        {1: 7},       # mode inconnu
        {44: 2400},   # heure impossible
        {45: 1260},   # minutes impossibles
        {},           # rien
    ],
)
def test_guard_refuses_everything_outside_the_whitelist(items):
    with pytest.raises(api.UcanessWriteRefused):
        api.validate_settings(items)


def test_guard_accepts_mode_and_windows():
    pcs = api.validate_settings({1: 1, 44: "2300", 45: "23:59"})
    assert pcs == [
        {"set_id": 1, "set_data": 1},
        {"set_id": 44, "set_data": 2300},
        {"set_id": 45, "set_data": 2359},
    ]


def test_windows_clear_other_charge_and_all_discharge_windows():
    items = api.windows_to_settings([("2300", "2359"), ("0000", "0130")])
    assert items[44] == 2300 and items[45] == 2359
    assert items[48] == 0 and items[49] == 130
    assert items[52] == 0 and items[53] == 0
    for start, end in api.DISCHARGE_WINDOWS:
        assert items[start] == 0 and items[end] == 0
    assert set(items) == api.WINDOW_SET_IDS
    with pytest.raises(api.UcanessWriteRefused):
        api.windows_to_settings([("2300", "2359")] * 4)


# ------------------------------------------------------------------ faux serveur

class FakeUcanessV1:
    def __init__(self):
        self.password_md5 = hashlib.md5(b"secret").hexdigest()
        self.tokens = set()
        self.calls = []
        self.writes = []
        self.settings = {
            "work_mode": 0,
            "bat_grid_dod": 900,
            "battery_return_difference": 100,
            "charge_time1_start": 100,
            "charge_time1_end": 300,
            "charge_time2_start": 0,
            "charge_time2_end": 0,
            "charge_time3_start": 0,
            "charge_time3_end": 0,
            "discharge_time1_star": 1800,
            "discharge_time1_end": 2000,
            "discharge_time2_star": 0,
            "discharge_time2_end": 0,
            "discharge_time3_star": 0,
            "discharge_time3_end": 0,
        }
        self.ignore_writes = False
        self.model = "mr"  # modèle déclaré par l'UHome 6K réel
        self.timeout_over = None  # répond 5019 si un envoi contient plus de N réglages
        self.timeout_but_applied = 0  # répond 5019 aux N prochains envois, mais les applique
        self.apply_after_reads = 0    # ... seulement après ce nombre de lectures de la configuration
        self.pending = []
        self.config_reads = 0

    def _apply(self, pcs):
        for item in pcs:
            key = api.CONFIG_KEYS[item["set_id"]][0]
            self.settings[key] = item["set_data"]

    async def handle(self, request):
        path = request.path
        body = await request.json()
        self.calls.append(path)
        if path == "/user/signin":
            if body.get("password") == self.password_md5:
                tok = f"tok{len(self.tokens)}"
                self.tokens.add(tok)
                return web.json_response({"error_code": 2000, "token": tok})
            return web.json_response({"error_code": 5032, "msg": "bad"})
        auth = request.headers.get("Authorization", "")
        if auth[7:] not in self.tokens:
            return web.json_response({"error_code": 4018, "msg": "Login timed out."})
        if path.startswith("/api/v1/"):
            ts = request.headers.get("timestamp", "")
            expected = hmac.new(
                APP_SECRET.encode(), f"url={path}&app_key={APP_KEY}&timestamp={ts}".encode(), hashlib.sha256
            ).hexdigest()
            if request.headers.get("app_key") != APP_KEY or request.headers.get("signature") != expected:
                return web.json_response({"error_code": 4001, "msg": "bad signature"}, status=401)
        if path == "/api/v1/device/list":
            return web.json_response(
                {"error_code": 2000, "msg": "ok", "list": [
                    {"device_id": "MA_autre", "inverter_model": "uhc"},
                    {"device_id": "MA_testcode01", "inverter_model": self.model},
                ]}
            )
        if path == "/api/v1/device/config":
            assert body == {"device_id": "MA_testcode01"}
            self.config_reads += 1
            if self.pending:
                remaining, pcs = self.pending[0]
                if remaining <= 0:
                    self._apply(pcs)
                    self.pending.pop(0)
                else:
                    self.pending[0] = (remaining - 1, pcs)
            return web.json_response(
                {"error_code": 2000, "msg": "ok", "data": {"inverter_model": self.model, "pcs": {self.model: dict(self.settings)}}}
            )
        if path == "/api/v1/device/settings/update":
            assert body["device_id"] == "MA_testcode01"
            assert body["inverter_model"] == self.model
            if self.timeout_over is not None and len(body["pcs"]) > self.timeout_over:
                return web.json_response({"error_code": 5019, "msg": "Device operation timeout"})
            self.writes.append(body["pcs"])
            if self.timeout_but_applied:
                self.timeout_but_applied -= 1
                self.pending.append((self.apply_after_reads, body["pcs"]))
                return web.json_response({"error_code": 5019, "msg": "Device operation timeout"})
            if not self.ignore_writes:
                self._apply(body["pcs"])
            return web.json_response({"error_code": 2000, "msg": "ok"})
        return web.json_response({"error_code": 404, "msg": "unknown"})


async def _with_server(test):
    fake = FakeUcanessV1()
    app = web.Application()
    app.router.add_post("/{tail:.*}", fake.handle)
    server = TestServer(app)
    await server.start_server()
    try:
        async with aiohttp.ClientSession() as session:
            client = api.UcanessClient(
                session, "user@example.org", api.hash_password("secret"),
                base_url=str(server.make_url("")), app_key=APP_KEY, app_secret=APP_SECRET,
            )
            await test(fake, client)
    finally:
        await server.close()


def test_signed_read_resolves_device_and_reads_config():
    async def scenario(fake, client):
        device_id, model = await client.resolve_device_v1("testcode01")
        assert (device_id, model) == ("MA_testcode01", "mr")
        settings = api.pcs_settings(await client.get_config_v1("testcode01"))
        assert settings["work_mode"] == 0
        assert api.read_back(settings, 46) == 1800  # orthographe « star » de la documentation
    asyncio.run(_with_server(scenario))


def test_write_sends_only_whitelisted_items_and_is_read_back():
    async def scenario(fake, client):
        fake.model = "uhome"
        items = api.windows_to_settings([("2300", "2359"), ("0000", "0130")])
        before = api.pcs_settings(await client.get_config_v1("testcode01"))
        changed = {k for k, v in items.items() if api.read_back_value(before, k) != v}
        sent = await client.update_settings("testcode01", items)
        assert {i["set_id"] for i in sent} == changed                  # seulement ce qui change
        assert all(len(w) <= api.MAX_ITEMS_PER_WRITE for w in fake.writes)
        assert {i["set_id"] for w in fake.writes for i in w} <= api.WINDOW_SET_IDS
        settings = api.pcs_settings(await client.get_config_v1("testcode01"))
        assert all(int(api.read_back(settings, k)) == v for k, v in items.items())
        assert settings["bat_grid_dod"] == 900               # réglage de fond intact
        assert settings["battery_return_difference"] == 100  # réglage de fond intact
        assert settings["discharge_time1_star"] == 0         # décharge vidée
    asyncio.run(_with_server(scenario))


def test_refused_write_never_reaches_the_server():
    async def scenario(fake, client):
        for items in ({2: 50}, {1: 2}, {23: 1}):
            with pytest.raises(api.UcanessWriteRefused):
                await client.update_settings("testcode01", items)
        assert fake.writes == []
        assert "/api/v1/device/settings/update" not in fake.calls
    asyncio.run(_with_server(scenario))


def test_unconfirmed_model_is_refused_before_sending():
    async def scenario(fake, client):
        assert api.model_write_confirmed("mr")  # table confirmée le 18/11/2026
        fake.model = "inconnu"
        assert not api.model_write_confirmed("inconnu")
        for items in ({1: 0}, api.windows_to_settings([("2300", "2359")])):
            with pytest.raises(api.UcanessWriteRefused, match="non confirmée"):
                await client.update_settings("testcode01", items)
        assert fake.writes == []
        assert "/api/v1/device/settings/update" not in fake.calls
    asyncio.run(_with_server(scenario))


def test_dangerous_paths_are_refused_before_network():
    async def scenario(fake, client):
        for path in ("/api/v1/device/command", "/api/v1/device/config/update", "/device/settings/update",
                     "/api/v1/device/delete", "/device/ems/config/save"):
            with pytest.raises(ValueError):
                await client._request(path, {}, auth=True, signed=True)
            with pytest.raises(ValueError):
                await client._request(path, {}, auth=True, signed=False)
        assert fake.calls == []
    asyncio.run(_with_server(scenario))


def test_write_budget_blocks_bursts(monkeypatch):
    monkeypatch.setattr(api, "MIN_WRITE_INTERVAL_S", 0.05)
    monkeypatch.setattr(api, "MAX_WRITES_PER_HOUR", 2)

    async def scenario(fake, client):
        fake.model = "uhome"
        await client.update_settings("testcode01", {1: 1})
        await client.update_settings("testcode01", {1: 0})   # attend l'intervalle minimal
        with pytest.raises(api.UcanessWriteRefused):
            await client.update_settings("testcode01", {1: 1})  # budget horaire épuisé
        assert len(fake.writes) == 2
    asyncio.run(_with_server(scenario))


def test_nothing_sent_when_already_in_place():
    async def scenario(fake, client):
        assert await client.update_settings("testcode01", {1: 0}) == []
        assert fake.writes == []
    asyncio.run(_with_server(scenario))


def test_device_timeout_falls_back_to_one_setting_per_write(monkeypatch):
    monkeypatch.setattr(api, "MIN_WRITE_INTERVAL_S", 0.01)
    monkeypatch.setattr(api, "TIMEOUT_CONFIRM_DELAY_S", 0.01)

    async def scenario(fake, client):
        fake.timeout_over = 1
        items = api.windows_to_settings([("0100", "0300"), ("0400", "0430")])
        sent = await client.update_settings("testcode01", items)
        assert all(len(w) == 1 for w in fake.writes)
        settings = api.pcs_settings(await client.get_config_v1("testcode01"))
        assert all(api.read_back_value(settings, k) == v for k, v in items.items())
        assert sent
    asyncio.run(_with_server(scenario))


def test_timeout_but_applied_counts_as_success(monkeypatch):
    """Un 5019 sur un envoi que l'onduleur applique quelques lectures plus tard : succès, sans renvoi."""
    monkeypatch.setattr(api, "MIN_WRITE_INTERVAL_S", 0.01)
    monkeypatch.setattr(api, "TIMEOUT_CONFIRM_DELAY_S", 0.01)

    async def scenario(fake, client):
        fake.timeout_but_applied = 1
        fake.apply_after_reads = 2
        sent = await client.update_settings("testcode01", {44: 410})  # début de plage seul
        assert sent == [{"set_id": 44, "set_data": 410}]
        assert fake.writes == [[{"set_id": 44, "set_data": 410}]]     # un seul envoi, pas de renvoi
        settings = api.pcs_settings(await client.get_config_v1("testcode01"))
        assert api.read_back_value(settings, 44) == 410
    asyncio.run(_with_server(scenario))


def test_timeout_not_applied_still_fails(monkeypatch):
    """Un 5019 sur un réglage jamais appliqué : l'erreur remonte après 2 min de relecture."""
    monkeypatch.setattr(api, "MIN_WRITE_INTERVAL_S", 0.01)
    monkeypatch.setattr(api, "TIMEOUT_CONFIRM_DELAY_S", 0.01)

    async def scenario(fake, client):
        fake.timeout_over = 0  # 5019 à chaque envoi, rien n'est appliqué
        reads_before = fake.config_reads
        with pytest.raises(api.UcanessApiError) as err:
            await client.update_settings("testcode01", {44: 410})
        assert str(err.value.code) == "5019"
        # 1 lecture avant l'envoi + TIMEOUT_CONFIRM_ATTEMPTS relectures
        assert fake.config_reads - reads_before == 1 + api.TIMEOUT_CONFIRM_ATTEMPTS
    asyncio.run(_with_server(scenario))


def test_timeout_on_first_window_does_not_block_the_next(monkeypatch):
    """Un 5019 appliqué sur le premier paquet : le paquet suivant est quand même envoyé."""
    monkeypatch.setattr(api, "MIN_WRITE_INTERVAL_S", 0.01)
    monkeypatch.setattr(api, "TIMEOUT_CONFIRM_DELAY_S", 0.01)

    async def scenario(fake, client):
        fake.timeout_but_applied = 1
        items = api.windows_to_settings([("0410", "0545")])
        sent = await client.update_settings("testcode01", items)
        settings = api.pcs_settings(await client.get_config_v1("testcode01"))
        assert all(api.read_back_value(settings, k) == v for k, v in items.items())
        assert len(fake.writes) == len(range(0, len(sent), api.MAX_ITEMS_PER_WRITE))  # aucun renvoi
    asyncio.run(_with_server(scenario))


def test_no_app_key_means_no_signed_call():
    async def scenario(session):
        client = api.UcanessClient(session, "user@example.org", "x", base_url="http://127.0.0.1:9")
        with pytest.raises(api.UcanessWriteRefused):
            await client.update_settings("testcode01", {1: 1})

    async def run():
        async with aiohttp.ClientSession() as session:
            await scenario(session)
    asyncio.run(run())


def test_absent_setting_reads_as_zero_like_the_portal():
    settings = {"charge_time1_start": 100, "charge_time1_end": 300}  # configuration type renvoyée par le cloud
    assert api.read_back_value(settings, 1) == 0     # mode absent = autoconsommation
    assert api.read_back_value(settings, 44) == 100
    assert api.read_back_value(settings, 48) == 0    # plage 2 absente = vide
    assert api.read_back_value({"work_mode": "x"}, 1) is None


def test_real_model_write_payload_matches_the_portal():
    async def scenario(fake, client):
        await client.update_settings("testcode01", {1: 1})
        assert fake.writes == [[{"set_id": 1, "set_data": 1}]]   # même forme que la requête du portail
    asyncio.run(_with_server(scenario))
