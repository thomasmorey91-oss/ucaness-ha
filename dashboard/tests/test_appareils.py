"""Vue « Appareils » automatique (stratégie custom:ucaness-appareils) et carte inerte (custom:ucaness-appareil-card).

Données INVENTÉES. Rendu dans Chrome sans fenêtre (Playwright), comme test_dashboard.py.
"""
from __future__ import annotations

import json

import pytest

from test_dashboard import open_page, site  # noqa: F401  (fixture partagée)


def _ent(eid, dc=None, cat=None, state="0", unit=None):
    attrs = {}
    if dc:
        attrs["device_class"] = dc
    if unit:
        attrs["unit_of_measurement"] = unit
    return eid, {"cat": cat, "state": state, "attrs": attrs}


APPAREILS = {
    "d1": ("Prise lave-linge", "S60ZBTPF", "garage", [
        _ent("switch.prise_ll", state="on"), _ent("sensor.prise_ll_puissance", "power", unit="W"),
        _ent("sensor.prise_ll_energie", "energy", unit="kWh"), _ent("select.prise_ll_comportement", cat="config")]),
    "d2": ("Prise lave-vaisselle", "S60ZBTPF", "cuisine", [
        _ent("switch.prise_lv"), _ent("sensor.prise_lv_puissance", "power", unit="W")]),
    "d3": ("Prise bureau", "S60ZBTPF", "bureau", [
        _ent("switch.prise_bureau"), _ent("sensor.prise_bureau_puissance", "power", unit="W")]),
    "d4": ("Volet salon", "RollerShutter", "salon", [_ent("cover.volet_salon", "shutter", state="open")]),
    "d5": ("Porte de garage", "GarageDoor", "garage", [_ent("cover.porte_garage", "garage", state="closed")]),
    "d6": ("Sonde chambre", "SNZB-02D", "chambre", [
        _ent("sensor.chambre_temperature", "temperature", unit="°C"), _ent("sensor.chambre_humidite", "humidity", unit="%"),
        _ent("sensor.chambre_batterie", "battery", cat="diagnostic")]),
    "d7": ("Baie salon", "SNZB-04", "salon", [_ent("binary_sensor.baie_salon", "opening", state="off")]),
    "d8": ("Sonnette entrée", "Video Doorbell", None, [
        _ent("camera.sonnette"), _ent("binary_sensor.sonnette_mouvement", "motion"), _ent("binary_sensor.sonnette_visiteur")]),
    "d9": ("Caméra jardin", "IPCamera", "jardin", [
        _ent("camera.jardin"), _ent("camera.jardin_vignette"), _ent("binary_sensor.jardin_mouvement", "motion")]),
    "d10": ("Borne voiture", "Wallbox", "garage", [
        _ent("lock.borne_verrou", state="locked"), _ent("sensor.borne_puissance", "power", unit="W"),
        _ent("sensor.borne_description_de_l_etat", state="Prête")]),
    "d11": ("Compteur Linky", "ZLinky_TIC", "garage", [
        _ent("sensor.linky_puissance", "power", unit="W"), _ent("sensor.linky_apparente", "apparent_power", unit="VA")]),
    "d12": ("Batterie maison", "Batterie 10", "garage", [
        _ent("sensor.batterie_soc", "battery", unit="%"), _ent("sensor.batterie_puissance_batterie", "power", unit="W")]),
    "d13": ("TV salon", "Box TV", "salon", [_ent("media_player.tv_salon", "tv", state="off")]),
    "d14": ("Portail piéton", "Relais", None, [_ent("switch.portail_pieton", state="off")]),
    "d15": ("Téléphone", "Phone", None, [_ent("notify.telephone"), _ent("sensor.telephone_batterie", "battery", cat="diagnostic")]),
    "d16": ("Serveur de l'assistant", "Service", None, [_ent("switch.assistant", cat="config")]),
}


def _hass():
    devices, entities, states = {}, {}, {}
    for did, (nom, model, area, ents) in APPAREILS.items():
        devices[did] = {"id": did, "name": nom, "model": model, "manufacturer": "Essai", "area_id": area}
        for eid, e in ents:
            entities[eid] = {"entity_id": eid, "device_id": did, "entity_category": e["cat"]}
            states[eid] = {"entity_id": eid, "state": e["state"], "attributes": e["attrs"]}
    areas = {a: {"area_id": a, "name": a.capitalize()} for a in ("garage", "cuisine", "bureau", "salon", "chambre", "jardin")}
    return {"devices": devices, "entities": entities, "states": states, "areas": areas, "language": "fr", "locale": {"language": "fr"}}


@pytest.fixture(scope="module")
def module_page(site):  # noqa: F811
    pg = open_page(site, "/tests/apercu.html")
    yield pg
    pg.close()


def _cartes(pg, cfg):
    return pg.evaluate("""async ([hass, cfg]) => {
        const m = await import('/www/ucaness/ucaness-cards.js');
        return m.ucAppareilsCartes(hass, cfg);
    }""", [_hass(), cfg])


def _par_nom(groupes):
    return {c["nom"]: c for g in groupes for c in g["cartes"]}


def test_chaque_appareil_recoit_sa_carte(module_page):
    cartes = _par_nom(_cartes(module_page, {}))
    types = {n: c["card"]["type"] for n, c in cartes.items()}
    assert types == {
        "Prise lave-linge": "custom:appliance-washer-card",
        "Prise lave-vaisselle": "custom:appliance-dishwasher-card",
        "Prise bureau": "custom:appliance-smart-plug-card",
        "Volet salon": "custom:appliance-roller-shutter-card",
        "Porte de garage": "custom:appliance-garage-door-card",
        "Sonde chambre": "custom:appliance-room-climate-card",
        "Baie salon": "custom:appliance-door-sensor-card",
        "Sonnette entrée": "custom:appliance-video-doorbell-card",
        "Caméra jardin": "custom:appliance-camera-card",
        "Borne voiture": "custom:appliance-ev-charger-card",
        "Compteur Linky": "custom:appliance-linky-card",
        "Batterie maison": "custom:appliance-battery-card",
        "TV salon": "custom:appliance-tv-box-card",
        "Portail piéton": "custom:appliance-swing-gate-card",
    }
    assert all(c["type"] == "custom:ucaness-appareil-card" for c in cartes.values())
    ll = cartes["Prise lave-linge"]["card"]
    assert ll["power"] == "sensor.prise_ll_puissance" and ll["energy"] == "sensor.prise_ll_energie" and ll["energy_period"] == "day"
    assert cartes["Caméra jardin"]["card"]["entity_camera"] == "camera.jardin"          # pas la vignette
    assert cartes["Borne voiture"]["card"]["entity_status"] == "sensor.borne_description_de_l_etat"
    assert cartes["Compteur Linky"]["card"]["entity_power"] == "sensor.linky_apparente"
    assert cartes["Baie salon"]["card"]["model"] == "window"


def test_aucune_commande_dans_les_cartes(module_page):
    for c in _par_nom(_cartes(module_page, {})).values():
        card = c["card"]
        assert card["show_controls"] is False and card["show_toggle"] is False and card["show_modes"] is False
        assert card["tap_action"] == {"action": "none"} and card["hold_action"] == {"action": "none"}
        assert "switch" not in card                       # bouton de la prise jamais relié
        assert c["plus"]                                  # un appui ouvre une fiche


def test_pieces_reglages_exclusions_et_prix(module_page):
    groupes = _cartes(module_page, {
        "exclure": ["Portail piéton"],
        "prix": "sensor.prix_kwh",
        "appareils": {"prise lave-linge": {"entity": "binary_sensor.lave_linge_en_marche"}, "TV salon": False},
    })
    pieces = [g["piece"] for g in groupes]
    assert pieces == sorted(p for p in pieces if p) + [""]          # pièces triées, « Autres appareils » à la fin
    cartes = _par_nom(groupes)
    assert "Portail piéton" not in cartes and "TV salon" not in cartes
    ll = cartes["Prise lave-linge"]
    assert ll["card"]["entity"] == "binary_sensor.lave_linge_en_marche" and ll["plus"] == "binary_sensor.lave_linge_en_marche"
    assert ll["card"]["price_per_kwh"] == "sensor.prix_kwh"
    assert "Téléphone" not in cartes and "Serveur de l'assistant" not in cartes   # rien d'utile à montrer


def test_nouvel_appareil_sans_rien_modifier(module_page):
    hass = _hass()
    hass["devices"]["d99"] = {"id": "d99", "name": "Prise sèche-linge", "model": "Prise", "area_id": "garage"}
    hass["entities"]["sensor.sl_puissance"] = {"entity_id": "sensor.sl_puissance", "device_id": "d99"}
    hass["states"]["sensor.sl_puissance"] = {"entity_id": "sensor.sl_puissance", "state": "0", "attributes": {"device_class": "power"}}
    vue = module_page.evaluate("""async ([hass]) => {
        await import('/www/ucaness/ucaness-cards.js');
        const S = customElements.get('ll-strategy-view-ucaness-appareils');
        return S.generate({ theme: 'UCANESS' }, hass);
    }""", [hass])
    assert vue["type"] == "sections" and vue["theme"] == "UCANESS" and vue["title"] == "Appareils"
    cartes = [c for s in vue["sections"] for c in s["cards"]]
    assert any(c.get("card", {}).get("type") == "custom:appliance-dryer-card" for c in cartes)
    assert any(c.get("type") == "heading" and c.get("heading") == "Autres appareils" for c in cartes)


def test_carte_inerte_ouvre_la_fiche(module_page):
    got = module_page.evaluate("""async () => {
        await import('/www/ucaness/ucaness-cards.js');
        if (!customElements.get('appliance-essai-card')) {
            customElements.define('appliance-essai-card', class extends HTMLElement {
                setConfig(c) { this.c = c; this.clics = 0; this.innerHTML = '<button style="display:block;width:300px;height:200px">Arrêt</button>';
                    this.querySelector('button').addEventListener('click', () => { this.clics += 1; }); }
            });
        }
        const el = document.createElement('ucaness-appareil-card');
        el.setConfig({ plus: 'switch.prise_essai', nom: 'Prise essai', card: { type: 'custom:appliance-essai-card', name: 'Prise essai' } });
        el.hass = { language: 'fr', locale: { language: 'fr' }, states: {} };
        document.body.appendChild(el);
        await new Promise(r => setTimeout(r, 50));
        const vus = [];
        el.addEventListener('hass-more-info', (e) => vus.push(e.detail.entityId));
        const r = el.getBoundingClientRect();
        const cible = el.shadowRoot.elementFromPoint ? el.shadowRoot.elementFromPoint(r.x + 50, r.y + 50) : null;
        const dessous = el.shadowRoot.querySelector('.l').firstElementChild;
        dessous.querySelector('button').focus();
        const focusInterne = document.activeElement === dessous.querySelector('button');
        el.shadowRoot.querySelector('.voile').click();
        const libelle = el.shadowRoot.querySelector('.voile').getAttribute('aria-label');
        el.remove();
        return { vus, clics: dessous.clics, classe: cible && cible.className, focusInterne, libelle, inert: el.shadowRoot.querySelector('.l').inert };
    }""")
    assert got["vus"] == ["switch.prise_essai"]
    assert got["clics"] == 0 and got["classe"] == "voile"
    assert got["inert"] is True and got["focusInterne"] is False
    assert got["libelle"] == "Ouvrir la fiche de Prise essai"
