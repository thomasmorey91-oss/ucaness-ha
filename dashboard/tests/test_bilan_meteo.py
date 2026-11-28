"""Bilan du jour, météo des 5 jours et résumé du soir d'Ucan (cartes 0.10.0). Données INVENTÉES.

Rendu dans Chrome sans fenêtre (Playwright), comme test_dashboard.py.
"""
from __future__ import annotations

import pytest

from test_dashboard import open_page, site  # noqa: F401  (fixture partagée)

ETATS = {
    "sensor.soleil_jour": {"state": "9.8", "attributes": {"unit_of_measurement": "kWh"}},
    "sensor.maison_jour": {"state": "12.5", "attributes": {"unit_of_measurement": "kWh"}},
    "sensor.achat_hp": {"state": "1500", "attributes": {"unit_of_measurement": "Wh"}},
    "sensor.achat_hc": {"state": "1.0", "attributes": {"unit_of_measurement": "kWh"}},
    "sensor.injection_jour": {"state": "0.8", "attributes": {"unit_of_measurement": "kWh"}},
    "sensor.prix_kwh": {"state": "0.25", "attributes": {"unit_of_measurement": "EUR/kWh"}},
    "sun.sun": {"state": "above_horizon", "attributes": {}},
}
BILAN = {"production": "sensor.soleil_jour", "consommation": "sensor.maison_jour",
         "achat": ["sensor.achat_hp", "sensor.achat_hc"], "injection": "sensor.injection_jour", "prix": "sensor.prix_kwh"}


@pytest.fixture(scope="module")
def pg(site):  # noqa: F811
    p = open_page(site, "/tests/apercu.html")
    yield p
    p.close()


def test_calcul_du_bilan(pg):
    b = pg.evaluate("""async ([etats, cfg]) => {
        const m = await import('/www/ucaness/ucaness-cards.js');
        return m.ucBilanJour({ states: etats, language: 'fr' }, cfg);
    }""", [ETATS, BILAN])
    assert b["achat"] == pytest.approx(2.5)                     # 1 500 Wh + 1,0 kWh
    assert b["autonomie"] == pytest.approx(0.8)                 # 1 − 2,5 / 12,5
    assert b["autoconso"] == pytest.approx(9.0 / 9.8)           # soleil moins l'injection
    assert b["cout"] == pytest.approx(0.625)                    # 2,5 kWh × 0,25 €
    assert b["economie"] == pytest.approx(2.5) and b["economieEstimee"] is True   # (12,5 − 2,5) × 0,25 €


def test_carte_bilan(pg):
    got = pg.evaluate("""async ([etats, cfg]) => {
        await import('/www/ucaness/ucaness-cards.js');
        const el = document.createElement('ucaness-bilan-card');
        el.setConfig(cfg);
        el.hass = { states: etats, language: 'fr', locale: { language: 'fr' } };
        document.body.appendChild(el);
        const vus = [];
        el.addEventListener('hass-more-info', (e) => vus.push(e.detail.entityId));
        el.shadowRoot.querySelector('.tu').click();
        const r = { pct: el.shadowRoot.querySelector('.p').textContent, tuiles: [...el.shadowRoot.querySelectorAll('.tu .v')].map((x) => x.textContent),
                    phrase: el.shadowRoot.querySelector('.ph').textContent, vus };
        el.remove();
        return r;
    }""", [ETATS, BILAN])
    assert got["pct"] == "80 %"
    assert [t.replace(" ", " ").replace("\xa0", " ") for t in got["tuiles"]] == ["9,8 kWh", "12,5 kWh", "2,5 kWh", "2,50 €"]
    assert "80 %" in got["phrase"] and "9,8 kWh" in got["phrase"]
    assert got["vus"] == ["sensor.soleil_jour"]


def test_meteo_cinq_jours(pg):
    got = pg.evaluate("""async () => {
        await import('/www/ucaness/ucaness-cards.js');
        const jours = [...Array(7).keys()].map((i) => ({ datetime: new Date(Date.now() + i * 86400000).toISOString(),
            condition: i % 2 ? 'rainy' : 'sunny', temperature: 14 + i, templow: 5 + i, precipitation_probability: i * 10 }));
        let abonnement = null;
        const hass = { language: 'fr', locale: { language: 'fr' }, states: {
                'weather.maison': { state: 'sunny', attributes: {} },
                'sensor.pv_j1': { state: '11.2', attributes: { unit_of_measurement: 'kWh' } } },
            connection: { subscribeMessage: async (cb, msg) => { abonnement = msg; setTimeout(() => cb({ type: 'daily', forecast: jours }), 10); return () => {}; } } };
        const el = document.createElement('ucaness-forecast-card');
        el.setConfig({ entity: 'weather.maison', solaire: ['sensor.pv_j1'] });
        document.body.appendChild(el);
        el.hass = hass;
        await new Promise((r) => setTimeout(r, 80));
        const r = { msg: abonnement, n: el.shadowRoot.querySelectorAll('.j').length,
                    premier: el.shadowRoot.querySelector('.j .n').textContent, icone: el.shadowRoot.querySelector('.j ha-icon').getAttribute('icon'),
                    t: el.shadowRoot.querySelector('.j .t').textContent.trim(), sol: [...el.shadowRoot.querySelectorAll('.j .s')].map((x) => x.textContent) };
        el.remove();
        return r;
    }""")
    assert got["msg"] == {"type": "weather/subscribe_forecast", "forecast_type": "daily", "entity_id": "weather.maison"}
    assert got["n"] == 5 and got["premier"] == "Auj."
    assert got["icone"] == "mdi:weather-sunny" and got["t"].startswith("14°")
    assert got["sol"][0].replace(" ", " ") == "11,2 kWh" and got["sol"][1] == "—"


def test_resume_du_soir_d_ucan(pg):
    got = pg.evaluate("""async ([etats, cfg]) => {
        await import('/www/ucaness/ucaness-cards.js');
        const el = document.createElement('ucaness-ucan-card');
        el.setConfig({ conseil: 'sensor.pas_de_conseil', resume: Object.assign({ heure: '00:00' }, cfg) });
        el.hass = { states: etats, language: 'fr', locale: { language: 'fr' } };
        document.body.appendChild(el);
        await new Promise((r) => setTimeout(r, 30));
        const txt = el.shadowRoot.textContent;
        el.remove();
        return txt;
    }""", [ETATS, BILAN])
    assert "Ma journée" in got and "9,8 kWh de soleil" in got and "80 %" in got and "2,50 €" in got
