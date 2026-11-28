"""Scène sur photo (cartes 0.12.0) : choix de la photo selon l'ambiance, fondu, image de l'UHome. Données INVENTÉES."""
from __future__ import annotations

from test_dashboard import open_page, site  # noqa: F401  (fixture partagée)

FLOW = "document.querySelector('ucaness-layout-card').shadowRoot.querySelector('ucaness-flow-card')"


def test_choix_de_la_photo(site):  # noqa: F811
    pg = open_page(site, "/tests/scene.html")
    got = pg.evaluate("""async () => {
        const { ucPhoto } = await import('/www/ucaness/ucaness-cards.js');
        const P = { jour: 'j', coucher: 'c', nuit: 'n', couvert: 'v', pluie: 'p' };
        const a = (night, dusk, meteo) => ({ night, dusk, meteo });
        return [ucPhoto(P, a(false, false, 0)), ucPhoto(P, a(false, true, 0)), ucPhoto(P, a(false, true, 2)),
                ucPhoto(P, a(true, false, 0)), ucPhoto(P, a(false, false, 1)), ucPhoto(P, a(false, false, 2)),
                ucPhoto(P, a(false, false, 3)), ucPhoto({ jour: 'j' }, a(false, false, 2)), ucPhoto({}, a(true, false, 0), 'base')];
    }""")
    pg.close()
    assert got == ["j", "c", "p", "n", "v", "p", "p", "j", "base"]


def test_scene_sur_photo_nuit(site):  # noqa: F811
    pg = open_page(site, "/tests/scene.html?vivant=1&ambiance=nuit")
    got = pg.evaluate(f"""async () => {{
        const f = {FLOW};
        const c = Object.assign({{}}, window.scene, {{
            photos: {{ jour: '../www/ucaness/maison-exemple.svg?j', nuit: '../www/ucaness/maison-exemple.svg?n' }},
            nodes: Object.assign({{}}, window.scene.nodes, {{ battery: {{ x: 26.5, y: 60, uhome: {{ x: 28, y: 58, w: 8, image: '../www/ucaness/maison-exemple.svg?u', ratio: 2.36 }} }} }}) }});
        f.setConfig(c); f.hass = window.fakeHass;
        await new Promise((r) => setTimeout(r, 600));
        const r = f.shadowRoot;
        return {{ calques: r.querySelectorAll('.house.ph').length, visible: [...r.querySelectorAll('.house.ph.on')].map((x) => x.getAttribute('src')),
                  reflet: !!r.querySelector('.reflet'), astre: !!r.querySelector('.sky2 .astre'), uhome: !!r.querySelector('.uh img') }};
    }}""")
    pg.close()
    assert got == {"calques": 2, "visible": ["../www/ucaness/maison-exemple.svg?n"], "reflet": False, "astre": False, "uhome": True}


def test_etiquettes_masquables(site):  # noqa: F811
    pg = open_page(site, "/tests/scene.html")
    got = pg.evaluate(f"""async () => {{
        const f = {FLOW};
        const avant = f.shadowRoot.querySelectorAll('.lbls .lb').length;
        const c = Object.assign({{}}, window.scene, {{ ev: Object.assign({{}}, window.scene.ev, {{ hide_label: true }}),
            nodes: Object.assign({{}}, window.scene.nodes, {{ battery: Object.assign({{}}, window.scene.nodes.battery, {{ hide_label: true }}) }}) }});
        f.setConfig(c); f.hass = window.fakeHass;
        await new Promise((r) => setTimeout(r, 100));
        return {{ avant, apres: f.shadowRoot.querySelectorAll('.lbls .lb').length, uhome: !!f.shadowRoot.querySelector('.uh') }};
    }}""")
    pg.close()
    assert got["apres"] == got["avant"] - 2 and got["uhome"] is True
