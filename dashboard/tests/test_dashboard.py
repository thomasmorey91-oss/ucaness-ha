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


def test_carte_ucan_conseil_et_reponse(cartes):
    etat = cartes.evaluate("""() => {
      const find = (root) => { for (const el of root.querySelectorAll('*')) {
        if (el.tagName === 'UCANESS-UCAN-CARD') return el;
        if (el.shadowRoot) { const f = find(el.shadowRoot); if (f) return f; } } return null; };
      const card = find(document);
      const r = card.shadowRoot;
      const boutons = [...r.querySelectorAll('button[data-r]')].map((b) => b.textContent.trim());
      r.querySelector('button[data-r="plus_tard"]').click();
      return { boutons, texte: r.querySelector('.b').textContent, svg: !!r.querySelector('.av svg'), appels: window.ucanAppels };
    }""")
    assert etat["svg"] and "7,9 kWh" in etat["texte"]
    assert etat["boutons"] == ["Je le fais", "Pas maintenant", "Ne plus proposer"]
    assert etat["appels"] == [["script", "ucan_conseil_reponse", {"reponse": "plus_tard"}]]


@pytest.mark.parametrize(("langue", "boutons"), [
    ("en", ["I'll do it", "Not now", "Don't suggest again"]),
    ("zh-Hans", ["我来做", "以后再说", "不再提示"]),
    ("zh-CN", ["我来做", "以后再说", "不再提示"]),
    ("de", ["Mache ich", "Nicht jetzt", "Nicht mehr vorschlagen"]),
    ("it", ["Lo faccio", "Non ora", "Non proporlo più"]),
    ("es", ["Lo hago", "Ahora no", "No volver a proponer"]),
    ("pt", ["Vou fazer", "Agora não", "Não voltar a sugerir"]),
    ("fr", ["Je le fais", "Pas maintenant", "Ne plus proposer"]),
])
def test_carte_ucan_traduite(cartes, langue, boutons):
    got = cartes.evaluate("""(langue) => {
      const find = (root) => { for (const el of root.querySelectorAll('*')) {
        if (el.tagName === 'UCANESS-UCAN-CARD') return el;
        if (el.shadowRoot) { const f = find(el.shadowRoot); if (f) return f; } } return null; };
      const card = find(document);
      card._hass = Object.assign({}, window.fakeHass, { locale: { language: langue }, language: langue });
      card._render();
      const out = [...card.shadowRoot.querySelectorAll('button[data-r]')].map((b) => b.textContent.trim());
      card._hass = window.fakeHass;
      card._render();
      return out;
    }""", langue)
    assert got == boutons


def test_ucan_en_bulle_en_bas_a_droite(cartes):
    etat = cartes.evaluate("""() => {
      const hote = document.querySelector('body > .ucaness-ucan-bulle');
      const r = hote.shadowRoot;
      const fab = r.querySelector('.fab');
      const avant = { pastille: !!r.querySelector('.pastille'), panneau: !!r.querySelector('.panneau'),
                      pos: getComputedStyle(hote).position, bas: getComputedStyle(hote).bottom };
      fab.click();
      const ouvert = { panneau: !!r.querySelector('.panneau'), boutons: r.querySelectorAll('button[data-r]').length,
                       expanded: r.querySelector('.fab').getAttribute('aria-expanded') };
      r.querySelector('.fermer').click();
      return { avant, ouvert, ferme: !r.querySelector('.panneau') };
    }""")
    assert etat["avant"] == {"pastille": True, "panneau": False, "pos": "fixed", "bas": "84px"}
    assert etat["ouvert"] == {"panneau": True, "boutons": 3, "expanded": "true"}
    assert etat["ferme"]


def test_ucan_bulle_deplacable(cartes):
    etat = cartes.evaluate("""() => {
      const hote = document.querySelector('body > .ucaness-ucan-bulle');
      const fab = () => hote.shadowRoot.querySelector('.fab');
      const r0 = fab().getBoundingClientRect();
      const ev = (t, x, y) => fab().dispatchEvent(new PointerEvent(t, { clientX: x, clientY: y, pointerId: 1, bubbles: true }));
      ev('pointerdown', r0.x + 30, r0.y + 30);
      ev('pointermove', r0.x - 170, r0.y - 170);
      ev('pointerup', r0.x - 170, r0.y - 170);
      const pos = JSON.parse(localStorage.getItem('ucaness-ucan-position'));
      const ferme = !hote.shadowRoot.querySelector('.panneau');
      fab().click();
      const replacer = !!hote.shadowRoot.querySelector('.replacer');
      hote.shadowRoot.querySelector('.replacer').click();
      const apres = { stocke: localStorage.getItem('ucaness-ucan-position'), bas: getComputedStyle(hote).bottom };
      hote.shadowRoot.querySelector('.fermer').click();
      return { pos, ferme, replacer, apres };
    }""")
    assert etat["pos"]["droite"] == 220 and etat["pos"]["bas"] == 284, etat["pos"]   # 20 + 200, 84 + 200
    assert etat["ferme"], "un glissement n'ouvre pas la fenêtre"
    assert etat["replacer"] and etat["apres"] == {"stocke": None, "bas": "84px"}


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
                return { light: UC_LIGHT, css: /\*:not\(\.uc-flow\) \{ animation: none !important; \}/.test(css) };
            }""")
            assert got == {"light": expected, "css": expected}, query or "sans paramètre"
            pg.close()
    finally:
        ctx.close()


# ---------------------------------------------------------------- 0.5.0 : vue 3D, ciel, animations, téléphone

SCENE = "document.querySelector('ucaness-layout-card').shadowRoot.querySelector('ucaness-flow-card').shadowRoot"
CIELS = DASH_DIR / "www" / "ucaness" / "ciel"


@pytest.fixture(scope="module")
def scene(site):
    pg = open_page(site, "/tests/scene.html", width=1600, height=1000)
    yield pg
    pg.close()


def scene_state(pg) -> dict:
    return pg.evaluate(f"""() => {{
        const r = {SCENE};
        const flows = [...r.querySelectorAll('path.uc-flow')];
        return {{ flows: flows.length, idle: r.querySelectorAll('path[stroke-dasharray="9 9"]').length,
                  reverse: flows.filter(p => p.style.animationDirection === 'reverse').length,
                  waves: r.querySelectorAll('.uc-wave').length, glow: r.querySelectorAll('ellipse').length,
                  text: r.querySelector('.lbls').textContent.replace(/\\s+/g, ' '),
                  uh: !!r.querySelector('.uh'), bulb: !!r.querySelector('.bulb.lit'), borne: !!r.querySelector('.borne'),
                  balls: r.querySelectorAll('.ball').length }};
    }}""")


def set_scene(pg, changes: dict):
    pg.evaluate("""(changes) => {
        const h = JSON.parse(JSON.stringify(window.fakeHass));
        h.callWS = window.fakeHass.callWS; h.connection = window.fakeHass.connection;
        for (const [k, v] of Object.entries(changes)) h.states[k].state = String(v);
        window.fakeHass = h;
        document.querySelector('ucaness-layout-card').hass = h;
    }""", changes)
    pg.wait_for_timeout(1100)                  # chiffres qui défilent : 0,8 s


def test_scene_sans_erreur_ni_pastille(scene):
    assert scene.errors == []
    st = scene_state(scene)
    assert st["uh"] and st["borne"] and st["balls"] == 0


def test_scene_flux_selon_l_etat(scene):
    set_scene(scene, {"sensor.uhome_puissance_solaire": 1240, "sensor.uhome_puissance_batterie": 820,
                      "sensor.uhome_puissance_reseau": 0, "sensor.uhome_puissance_maison": 420})
    st = scene_state(scene)
    assert st["flows"] == 2 and st["idle"] == 2          # soleil et maison ; réseau et borne au repos
    assert st["glow"] == 1 and st["bulb"]                  # panneaux illuminés, ampoule allumée
    assert "1,24 kW" in st["text"] and "42 % · 0,82 kW" in st["text"] and "en charge" in st["text"]
    assert "autoconsommation" in st["text"]
    set_scene(scene, {"sensor.uhome_puissance_solaire": 0, "sensor.uhome_puissance_batterie": -900,
                      "sensor.uhome_puissance_reseau": 500})
    st = scene_state(scene)
    assert st["flows"] == 2 and st["reverse"] == 0 and st["glow"] == 0
    assert "en décharge" in st["text"] and "0,50 kW" in st["text"]
    set_scene(scene, {"sensor.uhome_puissance_reseau": -600})
    st = scene_state(scene)
    assert st["reverse"] == 1 and "injection" in st["text"]   # le réseau change de sens
    set_scene(scene, {"sensor.borne_puissance_de_charge": 7.4, "sensor.borne_description_de_l_etat": "Charging"})
    st = scene_state(scene)
    assert st["flows"] == 3 and "7,40 kW" in st["text"] and "en charge" in st["text"]
    set_scene(scene, {"sensor.borne_puissance_de_charge": 0, "sensor.borne_description_de_l_etat": "Ready",
                      "sensor.uhome_puissance_reseau": 0, "sensor.uhome_puissance_solaire": 1240,
                      "sensor.uhome_puissance_batterie": 820})


@pytest.mark.parametrize(("langue", "attendu"), [
    ("en", ["Solar panels", "Battery: ", "charging", "Inverter: self-consumption"]),
    ("de", ["Solarmodule", "Batterie: ", "lädt", "Wechselrichter: Eigenverbrauch"]),
    ("zh-Hans", ["光伏板", "电池：", "充电中", "逆变器：自发自用"]),
    ("it", ["Pannelli solari", "Batteria: ", "in carica", "Inverter: autoconsumo"]),
    ("es", ["Placas solares", "Batería: ", "cargando", "Inversor: autoconsumo"]),
    ("pt", ["Painéis solares", "Bateria: ", "a carregar", "Inversor: autoconsumo"]),
    ("pt-BR", ["Painéis solares", "Bateria: "]),     # variante : langue de base
    ("nl", ["Solar panels", "Battery: "]),          # langue sans traduction : anglais
])
def test_scene_traduite(scene, langue, attendu):
    """Les textes des cartes suivent la langue du profil Home Assistant (les nombres aussi)."""
    def langue_de(code):
        scene.evaluate("""(code) => {
            const h = Object.assign({}, window.fakeHass, { locale: { language: code }, language: code });
            h.states = Object.assign({}, h.states);
            for (const k of Object.keys(h.states)) h.states[k] = Object.assign({}, h.states[k]);
            window.fakeHass = h;
            document.querySelector('ucaness-layout-card').hass = h;
        }""", code)
        scene.wait_for_timeout(300)
    try:
        langue_de(langue)
        st = scene_state(scene)
        assert all(x in st["text"] for x in attendu), st["text"]
        assert scene.errors == []
    finally:
        langue_de("fr")
    assert "Panneaux solaires" in scene_state(scene)["text"]


def test_scene_flux_garde_ses_animations_entre_deux_mesures(scene):
    """Une nouvelle mesure de même allure ne redessine que les chiffres (les tirets ne repartent pas de zéro)."""
    scene.evaluate(f"() => {{ window._flux = {SCENE}.querySelector('path.uc-flow'); }}")
    set_scene(scene, {"sensor.uhome_puissance_maison": 430})
    assert scene.evaluate(f"() => window._flux === {SCENE}.querySelector('path.uc-flow')")
    assert "0,43 kW" in scene_state(scene)["text"]


def test_scene_appui_sur_l_uhome(scene):
    path = scene.evaluate(f"""() => new Promise(res => {{
        window.addEventListener('location-changed', () => res(location.pathname), {{ once: true }});
        {SCENE}.querySelector('.uh').click();
    }})""")
    assert path == "/batterie"
    scene.evaluate("history.back()")


def test_scene_fiche_au_clic_sur_les_chiffres(scene):
    got = scene.evaluate(f"""() => new Promise(res => {{
        window.addEventListener('hass-more-info', e => res(e.detail.entityId), {{ once: true }});
        {SCENE}.querySelector('.lb[data-entity="sensor.uhome_puissance_maison"]').click();
    }})""")
    assert got == "sensor.uhome_puissance_maison"


def sky(pg, tag="ucaness-layout-card") -> dict:
    return pg.evaluate(f"""() => {{
        const host = document.querySelector('{tag}');
        const on = host.shadowRoot.querySelector('.uc-sl.on');
        return {{ night: host.style.getPropertyValue('--uc-night'), img: on ? on.style.backgroundImage : '',
                  meteo: host.shadowRoot.querySelector('.uc-sky').dataset.meteo,
                  drift: host.shadowRoot.querySelectorAll('.uc-sl.drift').length }};
    }}""")


def test_ciel_de_jour_et_bascule_de_nuit(scene):
    scene.wait_for_timeout(300)
    st = sky(scene)
    assert st["night"] == "0" and "ciel-jour-beau.jpg" in st["img"] and st["meteo"] == "0"
    set_scene(scene, {"sun.sun": "below_horizon", "weather.maison": "lightning"})
    scene.wait_for_timeout(1600)
    st = sky(scene)
    assert st["night"] == "1" and "ciel-nuit-orage.jpg" in st["img"] and st["meteo"] == "3"
    set_scene(scene, {"sun.sun": "above_horizon", "weather.maison": "sunny"})


def test_apercu_d_ambiance_par_l_adresse(site):
    for query, night, image in (("?ambiance=nuit", "1", "ciel-nuit-claire"), ("?ambiance=nuit&meteo=pluie", "1", "ciel-nuit-couverte"),
                                ("?meteo=nuageux", "0", "ciel-jour-nuageux"), ("?coucher=1", "0", "ciel-coucher")):
        pg = open_page(site, f"/tests/scene.html{query}", width=1280, height=800)
        try:
            pg.wait_for_timeout(300)
            st = sky(pg)
            assert pg.errors == [] and st["night"] == night and f"{image}.jpg" in st["img"], query
        finally:
            pg.close()


def vivant_state(pg) -> dict:
    return pg.evaluate(f"""() => {{
        const r = {SCENE};
        const q = (s) => r.querySelector(s);
        return {{ particules: r.querySelectorAll('animateMotion').length, tirets: r.querySelectorAll('path.uc-flow').length,
                  tag: q('.tag') ? q('.tag').textContent : null, carte: !!q('.niv.on'), veille: !!q('.uh.veille'), actif: !!q('.uh.actif'),
                  bandeau: q('.ban.on') ? q('.ban').textContent : null, bulle: q('.ucan .bulle') ? q('.ucan .bulle').textContent : null,
                  pastilles: [...r.querySelectorAll('.pastille')].map(e => e.className + '|' + e.textContent),
                  soleil: !!q('.astre.soleil'), lune: !!q('.astre.lune'), flocons: r.querySelectorAll('.flocon').length, arc: !!q('.arc'),
                  fenetres: r.querySelectorAll('.ov g path[fill^="rgba(255,196,90"]').length }};
    }}""")


def test_scene_vivante(site):
    pg = open_page(site, "/tests/scene.html?vivant=1", width=1600, height=1000)
    try:
        st = vivant_state(pg)
        assert pg.errors == []
        assert st["particules"] >= 4 and st["tirets"] == 0            # néons et points de lumière à la place des tirets
        assert st["actif"] and st["carte"] and "UHome" in st["tag"] and "0,82 kW" in st["tag"]
        assert st["bandeau"] is None                                   # rien n'est annoncé à l'ouverture
        assert st["bulle"] == "Je fais le plein de soleil" and st["soleil"] and not st["lune"]
        assert any("or|100 % autonome" in x for x in st["pastilles"]) and any("Seuil réseau 6,0 kW" in x for x in st["pastilles"])
        # La batterie se met à alimenter la maison : bandeau, autonomie estimée (42 % − 10 % de 10 kWh à 0,9 kW ≈ 3,6 h).
        set_scene(pg, {"sensor.uhome_puissance_solaire": 0, "sensor.uhome_puissance_batterie": -900, "sensor.uhome_puissance_maison": 900})
        st = vivant_state(pg)
        assert st["bandeau"] == "La batterie alimente la maison" and "≈ 3,6 h" in st["bulle"]
        assert not any("autonome" in x for x in st["pastilles"])
        # Veille : modules éteints, carte de niveau rentrée ; achat proche du seuil : pastille orange.
        set_scene(pg, {"sensor.uhome_puissance_batterie": 0, "sensor.uhome_puissance_reseau": 5200, "sensor.uhome_puissance_maison": 5200})
        st = vivant_state(pg)
        assert st["veille"] and not st["carte"] and st["bandeau"] == "Batterie en veille"
        assert any(x.startswith("pastille warn|") for x in st["pastilles"])
        # Nuit : lune, fenêtres éclairées, Ucan dort.
        set_scene(pg, {"sun.sun": "below_horizon", "sensor.uhome_puissance_reseau": 400, "sensor.uhome_puissance_maison": 400})
        st = vivant_state(pg)
        assert st["lune"] and not st["soleil"] and st["fenetres"] == 2 and st["bulle"] == "Zzz… bonne nuit !"
    finally:
        pg.close()


@pytest.mark.parametrize(("query", "cle"), [("&effet=neige", "flocons"), ("&effet=arcenciel", "arc")])
def test_scene_vivante_neige_et_arc_en_ciel(site, query, cle):
    pg = open_page(site, f"/tests/scene.html?vivant=1{query}", width=1280, height=800)
    try:
        assert pg.errors == [] and vivant_state(pg)[cle]
    finally:
        pg.close()


def test_scene_vivante_mode_allege(site):
    browser, _ = site
    ctx = browser.new_context()
    try:
        pg = open_page(site, "/tests/scene.html?vivant=1&leger=1", width=1280, height=800, context=ctx)
        st = vivant_state(pg)
        assert pg.errors == [] and st["particules"] == 0 and st["tirets"] >= 1 and st["flocons"] == 0   # tirets simples
        pg.close()
        open_page(site, "/tests/scene.html?leger=0", context=ctx).close()
    finally:
        ctx.close()


def test_ciels_fournis():
    js = JS.read_text(encoding="utf-8")
    assert "ciel/ciel-${amb.img}.jpg" in js
    noms = {"jour-beau", "jour-nuageux", "jour-pluie", "jour-orage", "coucher", "nuit-claire", "nuit-couverte", "nuit-orage"}
    for nom in noms:
        assert f"'{nom}'" in js, nom
        f = CIELS / f"ciel-{nom}.jpg"
        assert f.exists() and 20_000 < f.stat().st_size < 400_000, f
        assert f.read_bytes()[:3] == b"\xff\xd8\xff", f            # JPEG


def test_scene_mode_allege(site):
    browser, _ = site
    ctx = browser.new_context()
    try:
        pg = open_page(site, "/tests/scene.html?leger=1", width=1280, height=800, context=ctx)
        st = scene_state(pg)
        assert pg.errors == [] and st["flows"] >= 1 and st["waves"] == 0     # flux gardés, ni onde ni halo
        assert sky(pg)["drift"] == 0                                         # ciel figé
        pg.close()
        open_page(site, "/tests/scene.html?leger=0", context=ctx).close()
    finally:
        ctx.close()


def test_moins_de_mouvement(site):
    browser, base = site
    for reduced, expected in (("reduce", 0), ("no-preference", 1)):
        ctx = browser.new_context(reduced_motion=reduced, viewport={"width": 1280, "height": 800})
        try:
            pg = ctx.new_page()
            pg.goto(f"{base}/tests/scene.html")
            pg.wait_for_selector("body[data-ready='1']", timeout=5000)
            running = pg.evaluate("""() => {
                const layout = document.querySelector('ucaness-layout-card');
                return [...layout.shadowRoot.querySelectorAll('.col > *')].map(e => e.getAnimations().length).reduce((a, b) => a + b, 0);
            }""")
            assert (running > 0) == bool(expected), reduced
        finally:
            ctx.close()


@pytest.fixture(scope="module")
def tel(site):
    pg = open_page(site, "/tests/scene.html?ecran=tel", width=390, height=844)
    pg.wait_for_timeout(600)
    yield pg
    pg.close()


def test_ecran_de_telephone(tel):
    assert tel.errors == []
    got = tel.evaluate("""() => {
        const app = document.querySelector('ucaness-app-card').shadowRoot;
        const flow = app.querySelector('ucaness-flow-card').shadowRoot;
        const short = app.querySelector('ucaness-shortcuts-card').shadowRoot;
        const hours = app.querySelector('ucaness-hours-card').shadowRoot;
        return { nav: app.querySelectorAll('nav button').length, meteo: !!app.querySelector('.meteo ha-icon'),
                 sky: !!app.querySelector('.uc-sl.on'), scene: !!flow.querySelector('.stage.scene'),
                 details: [...flow.querySelectorAll('.lb .o')].every(e => getComputedStyle(e).display === 'none'),
                 shortcuts: short.querySelectorAll('button').length, on: short.querySelectorAll('button.on').length,
                 bars: hours.querySelectorAll('path.bar').length, width: document.documentElement.scrollWidth };
    }""")
    assert got["nav"] == 2 and got["meteo"] and got["sky"] and got["scene"]
    assert got["details"]                                   # téléphone : noms et puissances seulement
    assert got["shortcuts"] == 1 and got["on"] == 1         # raccourci sans entité masqué, appareil allumé en cyan
    assert got["bars"] > 0                                  # barres qui poussent à la première ouverture
    assert got["width"] <= 390                              # pas de défilement horizontal


def test_carte_de_decision_qui_se_retourne(tel):
    flips = tel.evaluate("""async () => {
        const det = document.querySelector('ucaness-app-card').shadowRoot.querySelector('ucaness-detail-card');
        window.annoncer('Recharge de 4,2 kWh');
        await new Promise(r => setTimeout(r, 50));
        const sec = det.shadowRoot.querySelector('section');
        return { anim: sec.getAnimations().length, text: sec.textContent };
    }""")
    assert flips["anim"] == 1 and "Recharge de 4,2 kWh" in flips["text"]


def test_courbe_qui_se_trace(tel):
    got = tel.evaluate("""async () => {
        const hours = document.querySelector('ucaness-app-card').shadowRoot.querySelector('ucaness-hours-card').shadowRoot;
        hours.querySelectorAll('.tabs button')[1].click();
        await new Promise(r => setTimeout(r, 300));
        return { trace: hours.querySelectorAll('path.trace').length, area: hours.querySelectorAll('path[fill="url(#ucarea)"]').length };
    }""")
    assert got["trace"] == 1 and got["area"] == 1


def test_chiffres_qui_defilent_jusqu_a_la_valeur(tel):
    got = tel.evaluate("""async () => {
        const stats = document.querySelector('ucaness-app-card').shadowRoot.querySelector('ucaness-stats-card').shadowRoot;
        await new Promise(r => setTimeout(r, 1000));
        return [...stats.querySelectorAll('.v')].map(v => v.textContent.replace(/\\s/g, ' '));
    }""")
    assert got[0].startswith("6,4") and got[1].startswith("42")
