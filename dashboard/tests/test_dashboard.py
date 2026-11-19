"""Tests du tableau de bord UCANESS HOME ASSISTANT (aucune donnée réelle : valeurs inventées)."""
from __future__ import annotations

import functools
import http.server
import importlib.util
import ipaddress
import pathlib
import re
import sys
import threading
import xml.etree.ElementTree as ET

import pytest
import yaml

DASH_DIR = pathlib.Path(__file__).resolve().parents[1]
REPO = DASH_DIR.parent
JS = DASH_DIR / "www" / "ucaness" / "ucaness-cards.js"
DASHBOARD = DASH_DIR / "dashboards" / "ucaness-home-assistant.yaml"
EXAMPLE_JSON = DASH_DIR / "tools" / "maison-exemple.json"
EXAMPLE_SVG = DASH_DIR / "www" / "ucaness" / "maison-exemple.svg"
UHOME_ID = re.compile(r"\b(?:binary_)?sensor\.uhome_[a-z0-9_]+\b")


def load_dashboard() -> dict:
    return yaml.safe_load(DASHBOARD.read_text(encoding="utf-8"))


def iter_cards(node):
    if isinstance(node, dict):
        if "type" in node:
            yield node
        for v in node.values():
            yield from iter_cards(v)
    elif isinstance(node, list):
        for v in node:
            yield from iter_cards(v)


def load_generator():
    spec = importlib.util.spec_from_file_location("maison_iso", DASH_DIR / "tools" / "maison_iso.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["maison_iso"] = mod          # requis par les dataclasses
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- tableau de bord YAML

def test_deux_onglets_avec_theme_et_en_tete():
    d = load_dashboard()
    paths = [v["path"] for v in d["views"]]
    assert paths == ["maison", "batterie"]
    for view in d["views"]:
        assert view["theme"] == "UCANESS"
        assert view["panel"] is True
        layout = view["cards"][0]
        assert layout["type"] == "custom:ucaness-layout-card"
        tabs = [t["path"] for t in layout["header"]["tabs"]]
        assert tabs == ["/ucaness-maison/maison", "/ucaness-maison/batterie"]


def test_cartes_personnalisees_definies_dans_le_script():
    defined = set(re.findall(r"\['(ucaness-[a-z-]+)', Ucaness", JS.read_text(encoding="utf-8")))
    used = {c["type"][len("custom:"):] for c in iter_cards(load_dashboard()) if str(c["type"]).startswith("custom:")}
    assert used, "aucune carte personnalisée utilisée"
    assert used <= defined, f"cartes non définies : {used - defined}"


def test_actions_sensibles_avec_confirmation_et_sans_bouton_rapide():
    sensibles = ("cover.portail", "cover.porte_garage", "input_boolean.jarvis_mode_simulation")
    vues = [c for c in iter_cards(load_dashboard()) if c.get("entity") in sensibles]
    assert {c["entity"] for c in vues} == set(sensibles)
    for card in vues:
        assert "features" not in card, f"{card['entity']} : les boutons rapides agissent sans confirmation"
        assert card["tap_action"]["confirmation"]["text"], card["entity"]


def test_entites_uhome_documentees():
    used = set(UHOME_ID.findall(DASHBOARD.read_text(encoding="utf-8"))) | set(UHOME_ID.findall(JS.read_text(encoding="utf-8")))
    documented = set(UHOME_ID.findall((DASH_DIR / "README.md").read_text(encoding="utf-8")))
    documented |= set(UHOME_ID.findall((REPO / "pilotage" / "README.md").read_text(encoding="utf-8")))
    assert used - documented == set(), f"entités à ajouter au tableau de renommage : {sorted(used - documented)}"


def test_theme_ucaness():
    theme = yaml.safe_load((DASH_DIR / "themes" / "ucaness.yaml").read_text(encoding="utf-8"))
    assert "UCANESS" in theme
    assert "Times New Roman" in theme["UCANESS"]["primary-font-family"]
    assert theme["UCANESS"]["primary-color"].upper() == "#00D1D6"


def test_version_des_cartes_dans_le_readme():
    version = re.search(r"const UC_VERSION = '([0-9.]+)'", JS.read_text(encoding="utf-8")).group(1)
    readme = (DASH_DIR / "README.md").read_text(encoding="utf-8")
    assert f"ucaness-cards.js?v={version}`" in readme, "mettre à jour l'adresse de la ressource dans le README"


# ---------------------------------------------------------------- générateur de maison

def test_generateur_maison_exemple():
    gen = load_generator()
    import json
    desc = json.loads(EXAMPLE_JSON.read_text(encoding="utf-8"))
    cv = gen.render(desc)
    svg, box = cv.svg()
    ET.fromstring(svg)                       # XML valide
    assert len(cv.panels) == 12
    pos = gen.suggest_positions(cv, box)
    for key in ("solar", "inverter", "grid", "battery", "home"):
        assert 0 <= pos[key]["x"] <= 100 and 0 <= pos[key]["y"] <= 100
    assert pos["inverter"]["y"] > pos["solar"]["y"] and pos["battery"]["y"] > pos["inverter"]["y"]


def test_svg_exemple_a_jour():
    gen = load_generator()
    import json
    svg, _ = gen.render(json.loads(EXAMPLE_JSON.read_text(encoding="utf-8"))).svg()
    assert EXAMPLE_SVG.read_text(encoding="utf-8") == svg, "relancer tools/maison_iso.py sur maison-exemple.json"


def test_generateur_types_de_toit():
    gen = load_generator()
    base = {"x": [0, 8], "y": [0, 6], "z": [0, 3]}
    for kind, pan in (("2pans-gauche", "gauche"), ("2pans-droite", "droite"), ("4pans", "gauche"), ("plat", None)):
        vol = dict(base, toit={"type": kind}, panneaux=[{"pan": pan, "colonnes": 3, "rangees": 1}] if pan else [{"colonnes": 3, "rangees": 1}])
        cv = gen.render({"volumes": [vol]})
        assert len(cv.panels) == 3, kind
    with pytest.raises(ValueError):
        gen.render({"volumes": [dict(base, toit={"type": "mansarde"})]})
    with pytest.raises(ValueError):   # volume plus large que profond : le grand pan visible est à gauche
        gen.render({"volumes": [dict(base, toit={"type": "4pans"}, panneaux=[{"pan": "droite"}])]})


# ---------------------------------------------------------------- données personnelles

def test_aucune_donnee_personnelle_dans_le_dossier():
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    ipv4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    gps = re.compile(r"\b\d{1,2}\.\d{4,}\s*,\s*-?\d{1,3}\.\d{4,}\b")
    for path in DASH_DIR.rglob("*"):
        if path.suffix not in {".js", ".json", ".yaml", ".md", ".svg", ".html", ".py", ".txt"} or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        assert not email.search(text), f"adresse e-mail dans {path}"
        for ip in ipv4.findall(text):
            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                continue
            assert addr.is_loopback or addr.is_unspecified, f"adresse IP {ip} dans {path}"
        assert not gps.search(text), f"coordonnées GPS dans {path}"


# ---------------------------------------------------------------- rendu dans Chrome

@pytest.fixture(scope="module")
def site():
    """Serveur local du dossier dashboard/ et Chrome sans fenêtre : (navigateur, adresse de base)."""
    sync_api = pytest.importorskip("playwright.sync_api")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DASH_DIR))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as err:  # navigateur absent
            server.shutdown()
            pytest.skip(f"Chrome indisponible : {err}")
        yield browser, f"http://127.0.0.1:{server.server_address[1]}"
        browser.close()
    server.shutdown()


def open_page(site, path: str, width: int = 1280, height: int = 800, context=None):
    browser, base = site
    if context is None:
        pg = browser.new_page(viewport={"width": width, "height": height})
    else:                                    # contexte partagé : même stockage local d'une page à l'autre
        pg = context.new_page()
        pg.set_viewport_size({"width": width, "height": height})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{base}{path}")
    pg.wait_for_selector("body[data-ready='1']", timeout=5000)
    pg.wait_for_timeout(400)
    pg.errors = errors
    return pg


@pytest.fixture(scope="module")
def page(site):
    pg = open_page(site, "/tests/apercu.html")
    yield pg
    pg.close()


FLOW = "document.querySelector('ucaness-layout-card').shadowRoot.querySelector('ucaness-flow-card').shadowRoot"


def arrows(page):
    """Pointes des flèches (x, y) dans l'ordre solaire, réseau, batterie, maison, et centre de l'onduleur."""
    return page.evaluate(f"""() => {{
        const root = {FLOW};
        const svg = root.querySelector('svg.lines');
        const [, , W, H] = svg.getAttribute('viewBox').split(' ').map(Number);
        const tips = [...root.querySelectorAll('path.arrow')].map(p => p.getAttribute('d').match(/L([\\d.]+) ([\\d.]+)/).slice(1).map(Number));
        const inv = root.querySelector('.inv').style.top || getComputedStyle(root.querySelector('.inv')).top;
        return {{ tips, H, idle: root.querySelectorAll('path.idle').length, pulses: root.querySelectorAll('path.pulse').length,
                  text: root.textContent }};
    }}""")


def set_states(page, changes: dict):
    page.evaluate("""(changes) => {
        const h = JSON.parse(JSON.stringify(window.fakeHass));
        for (const [k, v] of Object.entries(changes)) h.states[k].state = String(v);
        window.fakeHass = h;
        document.querySelector('ucaness-layout-card').hass = h;
    }""", changes)
    page.wait_for_timeout(100)


def test_rendu_sans_erreur(page):
    assert page.errors == []


def test_flux_charge_solaire(page):
    set_states(page, {"sensor.uhome_puissance_batterie": 820, "sensor.uhome_puissance_reseau": 0})
    a = arrows(page)
    assert a["pulses"] == 3 and a["idle"] == 1          # réseau au repos
    inv_y = 46 / 100 * a["H"]
    solar, battery, home = a["tips"]
    assert solar[1] < inv_y                             # du solaire vers l'onduleur
    assert battery[1] > inv_y and home[1] > inv_y       # de l'onduleur vers la batterie et la maison
    assert "1,24" in a["text"] and "Chargement" in a["text"]


def test_flux_decharge_et_soutirage(page):
    set_states(page, {"sensor.uhome_puissance_batterie": -900, "sensor.uhome_puissance_reseau": 500})
    a = arrows(page)
    assert a["pulses"] == 4 and a["idle"] == 0
    inv_y = 46 / 100 * a["H"]
    solar, grid, battery, home = a["tips"]
    inv_bottom = inv_y + 4.5 / 100 * 1000               # demi-hauteur de l'onduleur : 4,5 % de la largeur
    assert abs(battery[1] - inv_bottom) < 2             # de la batterie vers le bas de l'onduleur
    assert abs(grid[1] - inv_y) < 2                     # du réseau vers le côté de l'onduleur
    assert "Décharge" in a["text"] and "−0,90" in a["text"]


def test_fiche_entite_au_clic(page):
    got = page.evaluate(f"""() => new Promise(res => {{
        window.addEventListener('hass-more-info', e => res(e.detail.entityId), {{ once: true }});
        {FLOW}.querySelector('.ball.solar').click();
    }})""")
    assert got == "sensor.uhome_puissance_solaire"


def test_carrousel_et_onglets(page):
    title = page.evaluate("""() => {
        const layout = document.querySelector('ucaness-layout-card').shadowRoot;
        const panel = [...layout.querySelectorAll('ucaness-panel-card')].find(p => p.shadowRoot.querySelector('.dots'));
        panel.shadowRoot.querySelectorAll('.dots button')[1].click();
        return panel.shadowRoot.querySelector('.titlebar h2').textContent;
    }""")
    assert title == "Caméras"
    path = page.evaluate("""() => new Promise(res => {
        window.addEventListener('location-changed', () => res(location.pathname), { once: true });
        const header = document.querySelector('ucaness-layout-card').shadowRoot.querySelector('ucaness-header-card');
        header.shadowRoot.querySelectorAll('.tab')[1].click();
    })""")
    assert path == "/batterie"


# ---------------------------------------------------------------- texte repliable, onglets, mode allégé

NOTE = """(id) => {
    function all(root, sel, out = []) {
        root.querySelectorAll(sel).forEach(e => out.push(e));
        root.querySelectorAll('*').forEach(e => { if (e.shadowRoot) all(e.shadowRoot, sel, out); });
        return out;
    }
    return all(document, 'ucaness-note-card').find(n => n._config.id === id);
}"""


def note_state(pg, note_id: str) -> dict:
    return pg.evaluate(f"""(id) => {{
        const n = ({NOTE})(id);
        const r = n.shadowRoot, clip = r.querySelector('.clip'), more = r.querySelector('.more'), less = r.querySelector('.less');
        return {{ cut: clip.classList.contains('cut'), open: clip.classList.contains('open'), max: clip.style.maxHeight,
                  height: clip.getBoundingClientRect().height, full: r.querySelector('.slot').scrollHeight,
                  more: getComputedStyle(more).display !== 'none', less: !less.hidden && getComputedStyle(less).display !== 'none',
                  expanded: more.getAttribute('aria-expanded'), children: r.querySelector('.slot').children.length }};
    }}""", note_id)


@pytest.fixture(scope="module")
def cartes(site):
    pg = open_page(site, "/tests/cartes.html")
    yield pg
    pg.close()


def test_cartes_sans_erreur(cartes):
    assert cartes.errors == []


def test_texte_court_non_replie(cartes):
    st = note_state(cartes, "court")
    assert not st["cut"] and not st["more"] and not st["less"]


def test_texte_long_replie_puis_deplie(cartes):
    st = note_state(cartes, "long")
    assert st["cut"] and st["more"] and not st["less"]
    assert st["max"] == "100px" and st["height"] <= 100      # 4 lignes : 4 × 21 + 16 px
    assert st["full"] > 200
    cartes.evaluate(f"(id) => ({NOTE})(id).shadowRoot.querySelector('.more').click()", "long")
    st = note_state(cartes, "long")
    assert st["open"] and st["less"] and st["expanded"] == "true"
    assert abs(st["height"] - st["full"]) < 2                 # tout le texte est visible
    cartes.evaluate(f"(id) => ({NOTE})(id).shadowRoot.querySelector('.less').click()", "long")
    st = note_state(cartes, "long")
    assert not st["open"] and st["more"] and st["height"] <= 100


def test_appui_sur_le_texte_le_deplie(cartes):
    cartes.evaluate(f"(id) => ({NOTE})(id).shadowRoot.querySelector('.clip').click()", "reconfig")
    assert note_state(cartes, "reconfig")["open"]
    cartes.evaluate(f"(id) => ({NOTE})(id).shadowRoot.querySelector('.less').click()", "reconfig")
    assert not note_state(cartes, "reconfig")["open"]


def test_lien_dans_un_texte_replie(cartes):
    """Le lien est dans le shadow DOM de la carte markdown : il s'ouvre sans déplier le texte."""
    cartes.evaluate(f"""(id) => ({NOTE})(id).shadowRoot.querySelector('faux-markdown').shadowRoot.querySelector('a').click()""", "lien")
    assert cartes.evaluate("location.hash") == "#lien-suivi"
    st = note_state(cartes, "lien")
    assert st["cut"] and not st["open"]


def test_nouvelle_configuration_sans_doublon(cartes):
    """Home Assistant peut rappeler setConfig avant la fin de la construction : un seul texte affiché."""
    cartes.evaluate(f"""(id) => {{
        const n = ({NOTE})(id);
        const c = Object.assign({{}}, n._config);
        n.setConfig(c); n.setConfig(c);
    }}""", "reconfig")
    cartes.wait_for_timeout(300)
    st = note_state(cartes, "reconfig")
    assert st["children"] == 1 and st["cut"] and st["max"] == "79px"


def test_texte_replie_sur_telephone(site):
    pg = open_page(site, "/tests/cartes.html", width=390, height=844)
    try:
        assert pg.errors == []
        st = note_state(pg, "long")
        assert st["cut"] and st["max"] == "58px"              # mobile_lines : 2 × 21 + 16 px
        assert note_state(pg, "reconfig")["max"] == "79px"    # sans mobile_lines : lines
    finally:
        pg.close()


def test_panneau_a_onglets(cartes):
    got = cartes.evaluate("""() => {
        const layout = document.querySelector('ucaness-layout-card').shadowRoot;
        const panel = [...layout.querySelectorAll('ucaness-panel-card')].find(p => p.shadowRoot.querySelector('.tabs'));
        const r = panel.shadowRoot;
        const buttons = [...r.querySelectorAll('.tabs button')];
        const visible = () => [...r.querySelectorAll('.slide')].map(s => !s.hidden);
        const before = visible();
        buttons[1].click();
        return { labels: buttons.map(b => b.textContent.trim()), icons: r.querySelectorAll('.tabs ha-icon').length,
                 before, after: visible(), selected: buttons.map(b => b.getAttribute('aria-selected')),
                 title: r.querySelector('.titlebar h2').textContent, dots: !!r.querySelector('.dots'), timer: !!panel._timer };
    }""")
    assert got["labels"] == ["Principe", "Cette nuit", "Santé"] and got["icons"] == 2
    assert got["before"] == [True, False, False] and got["after"] == [False, True, False]
    assert got["selected"] == ["false", "true", "false"]
    assert got["title"] == "Détails" and not got["dots"] and not got["timer"]   # pas de défilement automatique


def test_redessin_limite_aux_entites_de_la_carte(cartes):
    got = cartes.evaluate("""async () => {
        const { ucChanged } = await import('../www/ucaness/ucaness-cards.js');
        const a = { state: '1' }, b = { state: '2' }, autre = { state: 'x' };
        const card = {};
        return [
            ucChanged(card, { states: { 'sensor.a': a, 'sensor.autre': autre } }, ['sensor.a']),
            ucChanged(card, { states: { 'sensor.a': a, 'sensor.autre': { state: 'y' } } }, ['sensor.a']),
            ucChanged(card, { states: { 'sensor.a': b } }, ['sensor.a']),
            ucChanged(card, { states: { 'sensor.a': b } }, ['sensor.a', 'sensor.b']),
        ];
    }""")
    assert got == [True, False, True, True]


def test_mode_allege_memorise(site):
    browser, _ = site
    ctx = browser.new_context()
    try:
        for query, expected in (("?leger=1", True), ("", True), ("?leger=0", False), ("", False)):
            pg = open_page(site, f"/tests/cartes.html{query}", context=ctx)
            got = pg.evaluate("""async () => {
                const { UC_LIGHT } = await import('../www/ucaness/ucaness-cards.js');
                const css = document.querySelector('ucaness-layout-card').shadowRoot.querySelector('style').textContent;
                return { light: UC_LIGHT, css: /\* \{ animation: none !important; transition: none !important; \}/.test(css) };
            }""")
            assert got == {"light": expected, "css": expected}, query or "sans paramètre"
            pg.close()
    finally:
        ctx.close()
