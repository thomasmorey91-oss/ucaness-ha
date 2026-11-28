"""Outils de la scène vivante, reflet, glissement entre vues et cadran à aiguille (cartes 0.11.0). Données INVENTÉES."""
from __future__ import annotations

import pytest

from test_dashboard import open_page, site  # noqa: F401  (fixture partagée)

FLOW = "document.querySelector('ucaness-layout-card').shadowRoot.querySelector('ucaness-flow-card')"


@pytest.fixture
def scene(site):  # noqa: F811
    pg = open_page(site, "/tests/scene.html?vivant=1&meteo=pluie")
    pg.evaluate("localStorage.removeItem('ucaness-animations')")
    yield pg
    pg.close()


def test_glissement_page_voisine(scene):
    got = scene.evaluate("""async () => {
        const m = await import('/www/ucaness/ucaness-cards.js');
        const l = ['/t/maison', '/t/batterie', '/t/borne'];
        return [m.ucVoisin(l, '/t/batterie', -120, 10, 300), m.ucVoisin(l, '/t/batterie', 120, 10, 300),
                m.ucVoisin(l, '/t/maison', 120, 0, 300), m.ucVoisin(l, '/t/borne', -120, 0, 300),
                m.ucVoisin(l, '/t/batterie', -50, 0, 300), m.ucVoisin(l, '/t/batterie', -120, 100, 300),
                m.ucVoisin(l, '/t/batterie', -120, 0, 900), m.ucVoisin(l, '/ailleurs', -120, 0, 300)];
    }""")
    assert got == ["/t/borne", "/t/maison", None, None, None, None, None, None]


def test_reflet_sous_la_pluie_et_menu_des_animations(scene):
    got = scene.evaluate(f"""async () => {{
        const f = {FLOW}, r = f.shadowRoot, st = r.querySelector('.stage.scene');
        const avant = {{ mouille: st.classList.contains('mouille'), reflet: getComputedStyle(r.querySelector('.reflet')).display }};
        r.querySelector('[data-outil="animations"]').click();
        const cases = [...r.querySelectorAll('.tiroir input[data-pref]')].map((x) => x.dataset.pref);
        const ucan = r.querySelector('.tiroir input[data-pref="ucan"]');
        ucan.checked = false; ucan.dispatchEvent(new Event('change', {{ bubbles: true }}));
        const apres = {{ sans: st.classList.contains('sans-ucan'), cache: getComputedStyle(r.querySelector('.ucan')).display,
                        garde: JSON.parse(localStorage.getItem('ucaness-animations')).ucan }};
        r.querySelector('.tiroir [data-fermer]').click();
        return {{ avant, cases, apres, ferme: r.querySelector('.tiroir').hidden }};
    }}""")
    assert got["avant"] == {"mouille": True, "reflet": "block"}
    assert got["cases"] == ["ucan", "ciel", "bandeau", "reflet"]
    assert got["apres"] == {"sans": True, "cache": "none", "garde": False}
    assert got["ferme"] is True


def test_tiroir_d_infos_du_jour(scene):
    got = scene.evaluate(f"""async () => {{
        const r = {FLOW}.shadowRoot;
        r.querySelector('[data-outil="infos"]').click();
        return {{ titre: r.querySelector('.tiroir .k').textContent, lignes: [...r.querySelectorAll('.tiroir .li span')].map((x) => x.textContent),
                  ouvert: r.querySelector('[data-outil="infos"]').getAttribute('aria-expanded') }};
    }}""")
    assert got["titre"] == "Infos du jour" and got["ouvert"] == "true"
    assert got["lignes"] == ["Lever du soleil", "Coucher du soleil", "Météo", "Batterie"]


def test_visite_guidee(scene):
    got = scene.evaluate(f"""async () => {{
        const r = {FLOW}.shadowRoot, v = r.querySelector('.visite');
        r.querySelector('[data-outil="visite"]').click();
        const etapes = [];
        for (let i = 0; i < 10 && !v.hidden; i++) {{ etapes.push(v.querySelector('.k').textContent); v.querySelector('button.p').click(); }}
        return {{ etapes, fin: v.hidden }};
    }}""")
    assert got["etapes"][0] == "Étape 1 sur 5" and len(got["etapes"]) == 5     # solaire, réseau, batterie, maison, borne
    assert got["fin"] is True


def test_mode_cinema(scene):
    got = scene.evaluate(f"""async () => {{
        const f = {FLOW}, st = f.shadowRoot.querySelector('.stage');
        f.shadowRoot.querySelector('[data-outil="cinema"]').click();
        await new Promise((x) => setTimeout(x, 200));
        const plein = document.fullscreenElement === f || st.classList.contains('cinema');
        f.shadowRoot.querySelector('[data-outil="cinema"]').click();
        await new Promise((x) => setTimeout(x, 200));
        return {{ plein, sorti: document.fullscreenElement !== f && !st.classList.contains('cinema') }};
    }}""")
    assert got == {"plein": True, "sorti": True}


def test_cadran_a_aiguille(scene):
    got = scene.evaluate("""async () => {
        await import('/www/ucaness/ucaness-cards.js');
        const el = document.createElement('ucaness-gauge-card');
        el.setConfig({ entity: 'sensor.uhome_puissance_solaire', name: 'Production', max: 5000, unit: 'W', digits: 0, zones: [{ from: 0, color: '#2AB7E2' }, { from: 1000, color: '#F5C542' }] });
        el.hass = window.fakeHass;
        document.body.appendChild(el);
        const r = el.shadowRoot;
        const out = { rot: r.querySelector('.aig').style.transform, val: r.querySelector('.v').textContent.replace(/\\s+/g, ' ').trim(),
                      arc: [...r.querySelectorAll('path')].map((p) => p.getAttribute('stroke')).filter(Boolean), nom: r.querySelector('.n').textContent };
        el.remove();
        return out;
    }""")
    assert got["rot"] == "rotate(-45.4deg)"                  # 1 240 W sur 5 000 : un quart du cadran
    assert got["val"].replace(" ", " ") == "1 240 W"
    assert "#F5C542" in got["arc"] and got["nom"] == "Production"
