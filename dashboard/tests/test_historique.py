"""Replay de la journée et trophées (cartes 0.13.0). Données INVENTÉES."""
from __future__ import annotations

import pytest

from test_dashboard import open_page, site  # noqa: F401  (fixture partagée)

FLOW = "document.querySelector('ucaness-layout-card').shadowRoot.querySelector('ucaness-flow-card')"


@pytest.fixture
def page(site):  # noqa: F811
    pg = open_page(site, "/tests/scene.html?vivant=1")
    yield pg
    pg.close()


def test_soleil_paris(page):
    got = page.evaluate("""async () => {
        const { ucSoleil } = await import('/www/ucaness/ucaness-cards.js');
        const hm = (d) => d.toISOString().slice(11, 16);
        const h = ucSoleil(new Date('2026-11-28T11:00:00Z'), 48.85, 2.35);
        const e = ucSoleil(new Date('2026-06-21T12:00:00Z'), 48.85, 2.35);
        return { lever: hm(h.lever), coucher: hm(h.coucher), hiver: h.elevation, ete: e.elevation, az: e.azimuth, matin: ucSoleil(new Date('2026-06-21T07:00:00Z'), 48.85, 2.35).rising };
    }""")
    # Paris, 28/11/2026 : lever 07h19 UTC, coucher 15h57 UTC (± 3 min) ; 21/06 vers midi : 64,6° plein sud.
    assert "07:16" <= got["lever"] <= "07:22" and "15:54" <= got["coucher"] <= "16:00"
    assert 19 < got["hiver"] < 21 and 63 < got["ete"] < 65.5 and 170 < got["az"] < 200 and got["matin"] is True


def test_images_du_replay(page):
    got = page.evaluate("""async () => {
        const { ucReplayFrames } = await import('/www/ucaness/ucaness-cards.js');
        const t0 = Date.UTC(2026, 10, 28, 0, 0);
        const st = { a: [{ start: t0, mean: 10 }, { start: t0 + 600000, mean: 30 }], b: [{ start: t0 + 300000, mean: 50 }] };
        return ucReplayFrames(st, ['a', 'b'], t0, t0 + 900000);
    }""")
    assert got == [
        {"t": got[0]["t"], "v": {"a": 10}},
        {"t": got[0]["t"] + 300000, "v": {"a": 10, "b": 50}},
        {"t": got[0]["t"] + 600000, "v": {"a": 30, "b": 50}},
    ]


def test_trophees(page):
    got = page.evaluate("""async () => {
        const { ucTrophees } = await import('/www/ucaness/ucaness-cards.js');
        // Trois jours inventés à Paris (heures UTC) : le 25 sans achat en journée, le 26 avec 2 kWh achetés à 12h, le 27 record.
        const prod = [], achat = [];
        for (const [j, kwh] of [[25, 8], [26, 5], [27, 12.34], [28, 3]]) {
          for (let h = 0; h < 24; h++) {
            const t = Date.UTC(2026, 10, j, h);
            prod.push({ start: t, change: h >= 9 && h < 15 ? kwh / 6 : 0 });
            achat.push({ start: t, change: h < 7 || h > 17 ? 0.8 : (j === 26 && h === 12 ? 2 : 0) });
          }
        }
        return ucTrophees(prod, achat, 48.85, 2.35, Date.UTC(2026, 10, 28, 12), 0.1);
    }""")
    assert got["record"] == {"kwh": 12.3, "date": "2026-11-27"}
    assert got["autonomes"] == 2 and got["derniere"] == "2026-11-27"


def test_replay_dans_la_scene(page):
    got = page.evaluate(f"""async () => {{
        const f = {FLOW};
        const t0 = new Date(); t0.setHours(0, 0, 0, 0);
        const stats = {{}};
        for (const id of ['sensor.uhome_puissance_solaire', 'sensor.uhome_soc']) {{
          stats[id] = [...Array(6).keys()].map((i) => ({{ start: t0.getTime() + i * 300000, mean: id.endsWith('soc') ? 50 + i : 0 }}));
        }}
        const h = Object.assign({{}}, window.fakeHass, {{ config: {{ latitude: 48.85, longitude: 2.35 }}, callWS: async () => stats }});
        f.hass = h;
        f.shadowRoot.querySelector('[data-outil="replay"]').click();
        await new Promise((r) => setTimeout(r, 300));
        const box = f.shadowRoot.querySelector('.replay');
        const pendant = {{ visible: !box.hidden, titre: box.querySelector('.h').textContent.slice(0, 8), soc: f._hass.states['sensor.uhome_soc'].state }};
        box.querySelector('[data-stop]').click();
        return {{ pendant, apres: {{ cache: box.hidden, soc: f._hass.states['sensor.uhome_soc'].state }} }};
    }}""")
    assert got["pendant"]["visible"] is True and got["pendant"]["titre"] == "Replay ·"
    assert got["pendant"]["soc"] != "42"
    assert got["apres"] == {"cache": True, "soc": "42"}


def test_carte_trophees(page):
    got = page.evaluate("""async () => {
        await import('/www/ucaness/ucaness-cards.js');
        const c = document.createElement('ucaness-trophees-card');
        c.setConfig({ production: 'sensor.production_du_jour', achat: 'sensor.achat' });
        document.body.appendChild(c);
        const t = Date.UTC(2026, 10, 20, 11);
        c.hass = Object.assign({}, window.fakeHass, { config: { latitude: 48.85, longitude: 2.35 },
          callWS: async () => ({ 'sensor.production_du_jour': [{ start: t, change: 9.5 }], 'sensor.achat': [] }) });
        await new Promise((r) => setTimeout(r, 200));
        return [...c.shadowRoot.querySelectorAll('.t')].map((x) => x.textContent.replace(/\\s+/g, ' ').trim());
    }""")
    assert got[0].startswith("Record de production 9,5 kWh le 20/11/2026")
    assert got[1].startswith("Journées 100 % autonomes 0")
