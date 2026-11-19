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
def page():
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
        pg = browser.new_page(viewport={"width": 1280, "height": 800})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(f"http://127.0.0.1:{server.server_address[1]}/tests/apercu.html")
        pg.wait_for_selector("body[data-ready='1']", timeout=5000)
        pg.wait_for_timeout(400)
        pg.errors = errors
        yield pg
        browser.close()
    server.shutdown()


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
