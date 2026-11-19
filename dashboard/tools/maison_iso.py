#!/usr/bin/env python3
"""Dessine une maison en perspective isométrique (SVG) dans le style du tableau de bord UCANESS.

Usage :
    python maison_iso.py description.json maison.svg

La description (JSON) liste des volumes posés sur une grille en mètres :
  - axe X : vers la façade visible à DROITE,
  - axe Y : vers la façade visible à GAUCHE,
  - axe Z : vers le haut.
On regarde donc la maison depuis l'angle entre ses deux façades les plus intéressantes
(en général celles qui portent les panneaux). Les volumes sont dessinés dans l'ordre
de la liste : du fond vers l'avant, du bas vers le haut.

Le script affiche ensuite les positions conseillées des boules de la carte
« ucaness-flow-card » (en % de la carte), à recopier dans le tableau de bord.

Aucune dépendance hors de la bibliothèque standard.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field

C30 = math.cos(math.radians(30))
PANEL_W, PANEL_L = 1.0, 1.65   # panneau en portrait : 1,0 m le long du faîtage, 1,65 m dans la pente

DEFS = """<defs>
<linearGradient id="uc-wallFront" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7A869F"/><stop offset="1" stop-color="#58637D"/></linearGradient>
<linearGradient id="uc-wallSide" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#525D78"/><stop offset="1" stop-color="#3B4560"/></linearGradient>
<linearGradient id="uc-roofFront" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4A546C"/><stop offset="1" stop-color="#363F56"/></linearGradient>
<linearGradient id="uc-roofSide" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3A4359"/><stop offset="1" stop-color="#262E42"/></linearGradient>
<linearGradient id="uc-roofBack" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2C3449"/><stop offset="1" stop-color="#3A4459"/></linearGradient>
<linearGradient id="uc-pv" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2A64B4"/><stop offset=".55" stop-color="#173E84"/><stop offset="1" stop-color="#0E2A60"/></linearGradient>
<linearGradient id="uc-glass" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#36598E"/><stop offset="1" stop-color="#121F3E"/></linearGradient>
<linearGradient id="uc-glassLit" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F3D48F"/><stop offset="1" stop-color="#C08A3E"/></linearGradient>
<linearGradient id="uc-water" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5FD0F2"/><stop offset="1" stop-color="#1E74B6"/></linearGradient>
<linearGradient id="uc-stone" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7A6F70"/><stop offset="1" stop-color="#4F4855"/></linearGradient>
<radialGradient id="uc-tree" cx=".35" cy=".35" r=".7"><stop offset="0" stop-color="#3C5F6E"/><stop offset="1" stop-color="#1B2E3E"/></radialGradient>
<radialGradient id="uc-ground" cx=".55" cy=".5" r=".6"><stop offset="0" stop-color="#1A3C72" stop-opacity=".95"/><stop offset=".7" stop-color="#0D2248" stop-opacity=".55"/><stop offset="1" stop-color="#081633" stop-opacity="0"/></radialGradient>
</defs>"""


@dataclass
class Canvas:
    scale: float = 15.0
    shapes: list = field(default_factory=list)
    pts: list = field(default_factory=list)
    panels: list = field(default_factory=list)   # centres des panneaux (coordonnées écran)

    def P(self, x, y, z):
        return ((x - y) * C30 * self.scale, (x + y) * 0.5 * self.scale - z * self.scale)

    def poly(self, pts3, fill, stroke="#9AA6BE", sw=0.6, so=0.35, op=None):
        pts = [self.P(*p) for p in pts3]
        self.pts.extend(pts)
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        o = f' opacity="{op}"' if op is not None else ""
        self.shapes.append(f'<polygon points="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-opacity="{so}" stroke-linejoin="round"{o}></polygon>')

    def line(self, a, b, color, sw=1.0, op=1.0):
        (x1, y1), (x2, y2) = self.P(*a), self.P(*b)
        self.pts.extend([(x1, y1), (x2, y2)])
        self.shapes.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{sw}" stroke-opacity="{op}" stroke-linecap="round"></line>')

    def circle(self, p, r, fill):
        cx, cy = self.P(*p)
        self.pts.extend([(cx - r * self.scale, cy - r * self.scale), (cx + r * self.scale, cy + r * self.scale)])
        self.shapes.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r * self.scale:.1f}" fill="{fill}" stroke="#6E86A8" stroke-opacity="0.25"></circle>')

    def svg(self):
        minx = min(p[0] for p in self.pts) - 6
        maxx = max(p[0] for p in self.pts) + 6
        miny = min(p[1] for p in self.pts) - 6
        maxy = max(p[1] for p in self.pts) + 6
        w, h = maxx - minx, maxy - miny
        body = "".join(self.shapes)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{minx:.0f} {miny:.0f} {w:.0f} {h:.0f}" '
               f'width="{w:.0f}" height="{h:.0f}">{DEFS}{body}</svg>')
        return svg, (minx, miny, w, h)


def lerp(a, b, t):
    return tuple(a[k] + (b[k] - a[k]) * t for k in range(3))


def pv(cv: Canvas, a, b, c, d, cells=(2, 3)):
    """Un panneau : quadrilatère a-b-c-d (a-b le long du faîtage, a-d dans la pente)."""
    cv.poly([a, b, c, d], "url(#uc-pv)", stroke="#9CC0F0", sw=0.7, so=0.8)
    for i in range(1, cells[0]):
        cv.line(lerp(a, b, i / cells[0]), lerp(d, c, i / cells[0]), "#6E98D6", 0.5, 0.7)
    for j in range(1, cells[1]):
        cv.line(lerp(a, d, j / cells[1]), lerp(b, c, j / cells[1]), "#6E98D6", 0.5, 0.7)
    cx, cy = cv.P(*lerp(a, c, 0.5))
    cv.panels.append((cx, cy))


def face_rect(cv: Canvas, vol, face, u0, u1, z0, z1, fill, eps=0.03, **kw):
    """Rectangle sur une façade visible : « gauche » (plan Y = y1) ou « droite » (plan X = x1)."""
    x0, x1 = vol["x"]
    y0, y1 = vol["y"]
    if face == "gauche":
        y = y1 + eps
        cv.poly([(x0 + u0, y, z0), (x0 + u1, y, z0), (x0 + u1, y, z1), (x0 + u0, y, z1)], fill, **kw)
    else:
        x = x1 + eps
        cv.poly([(x, y0 + u0, z0), (x, y0 + u1, z0), (x, y0 + u1, z1), (x, y0 + u0, z1)], fill, **kw)


def face_line(cv, vol, face, u0, u1, z, color, sw, op):
    x0, x1 = vol["x"]
    y0, y1 = vol["y"]
    if face == "gauche":
        cv.line((x0 + u0, y1 + .05, z), (x0 + u1, y1 + .05, z), color, sw, op)
    else:
        cv.line((x1 + .05, y0 + u0, z), (x1 + .05, y0 + u1, z), color, sw, op)


def face_vline(cv, vol, face, u, z0, z1, color, sw, op):
    x0, x1 = vol["x"]
    y0, y1 = vol["y"]
    if face == "gauche":
        cv.line((x0 + u, y1 + .05, z0), (x0 + u, y1 + .05, z1), color, sw, op)
    else:
        cv.line((x1 + .05, y0 + u, z0), (x1 + .05, y0 + u, z1), color, sw, op)


def draw_walls(cv, vol):
    x0, x1 = vol["x"]
    y0, y1 = vol["y"]
    z0, z1 = vol["z"]
    cv.poly([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], "url(#uc-wallFront)")
    cv.poly([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], "url(#uc-wallSide)")
    for p in vol.get("parements", []):   # pierre, bardage
        face_rect(cv, vol, p["face"], p["de"], p["a"], p.get("bas", 0), p["haut"], "url(#uc-stone)", stroke="#8C8494", so=.4)
        n = max(1, int((p["haut"] - p.get("bas", 0)) / .35))
        for k in range(1, n):
            z = p.get("bas", 0) + k * (p["haut"] - p.get("bas", 0)) / n
            face_line(cv, vol, p["face"], p["de"], p["a"], z, "#3E3946", .5, .55)
    for f in vol.get("fenetres", []):
        face_rect(cv, vol, f["face"], f["de"] - .12, f["a"] + .12, f["bas"] - .12, f["haut"] + .12, "#A9B4CB", eps=.02, stroke="#A9B4CB", so=.5)
        face_rect(cv, vol, f["face"], f["de"], f["a"], f["bas"], f["haut"], "url(#uc-glassLit)" if f.get("eclairee") else "url(#uc-glass)", eps=.04, stroke="#081530", so=.6)
        if f["a"] - f["de"] > 1.6:
            face_vline(cv, vol, f["face"], (f["de"] + f["a"]) / 2, f["bas"], f["haut"], "#A9B4CB", .8, .7)
    for g in vol.get("portes_garage", []):
        face_rect(cv, vol, g["face"], g["de"], g["a"], 0, g.get("haut", 2.4), "#3E4A68", stroke="#B3BDD0", so=.6)
        for k in range(1, 6):
            face_line(cv, vol, g["face"], g["de"], g["a"], k * g.get("haut", 2.4) / 6, "#B3BDD0", .6, .35)


def pitched_panels(cv, eave_a, eave_b, ridge_a, ridge_b, cols, rows, margin=0.35, hip=0.0):
    """Panneaux sur un pan : eave_a/eave_b = égout, ridge_a/ridge_b = haut du pan (même ordre).
    hip > 0 : retrait des croupes (toit 4 pans), en mètres au sommet du pan."""
    run_len = math.dist(eave_a, eave_b)
    slope = math.dist(eave_a, ridge_a)
    pl = min(PANEL_L, (slope - 2 * margin) / max(rows, 1))
    v_top = (margin + rows * pl) / slope
    usable = run_len - 2 * margin - 2 * hip * v_top
    pw = min(PANEL_W, usable / max(cols, 1))
    u_start = (run_len - cols * pw) / 2 / run_len
    for r in range(rows):
        for c in range(cols):
            u0 = u_start + c * pw / run_len
            u1 = u0 + pw * 0.96 / run_len
            v0 = (margin + r * pl) / slope
            v1 = v0 + pl * 0.96 / slope

            def at(u, v):
                e = lerp(eave_a, eave_b, u)
                t = lerp(ridge_a, ridge_b, u)
                p = lerp(e, t, v)
                return (p[0], p[1], p[2] + 0.04)
            pv(cv, at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1), cells=(2, 3))


def check_pan(p, expected, kind):
    pan = p.get("pan", expected)
    if pan != expected:
        raise ValueError(f"panneaux sur le pan {pan!r} impossibles pour un toit {kind} : le grand pan visible est {expected!r}")


def draw_roof(cv, vol):
    roof = vol.get("toit", {"type": "plat"})
    x0, x1 = vol["x"]
    y0, y1 = vol["y"]
    ze = vol["z"][1]
    kind = roof.get("type", "plat")
    ov = roof.get("debord", 0.35)
    rise = roof.get("hauteur", 1.8)
    edge = dict(stroke="#B3BDD0", so=.4)
    panels = vol.get("panneaux", [])
    a, b, c, d = x0 - ov, x1 + ov, y0 - ov, y1 + ov
    z = ze - 0.12
    if kind == "plat":
        cv.poly([(x0, y0, ze), (x1, y0, ze), (x1, y1, ze), (x0, y1, ze)], "#2A3350", stroke="#A9B4CB", so=.45)
        ac = roof.get("acrotere", 0.25)
        if ac:
            cv.poly([(x0, y1, ze), (x1, y1, ze), (x1, y1, ze + ac), (x0, y1, ze + ac)], "#7E8AA6", stroke="#C9D1E0", so=.4)
            cv.poly([(x1, y0, ze), (x1, y1, ze), (x1, y1, ze + ac), (x1, y0, ze + ac)], "#56627F", stroke="#C9D1E0", so=.4)
        for p in panels:   # rangées inclinées de quelques degrés vers la façade choisie
            cols, rows = p.get("colonnes", 4), p.get("rangees", 2)
            toward = p.get("incline_vers", "droite")
            m = p.get("marge", 0.35)
            if toward == "droite":   # rangées parallèles à Y, pente vers +X
                span_y = y1 - y0 - 2 * m
                pw = min(PANEL_W, span_y / cols)
                gap = max(0.0, ((x1 - x0) - 2 * m - rows * PANEL_L) / max(rows - 1, 1))
                for r in range(rows):
                    xa = x0 + m + r * (PANEL_L + gap)
                    for k in range(cols):
                        ya = y0 + m + (span_y - cols * pw) / 2 + k * pw
                        pv(cv, (xa, ya, ze + .45), (xa, ya + pw * .96, ze + .45), (xa + PANEL_L, ya + pw * .96, ze + .25), (xa + PANEL_L, ya, ze + .25), cells=(2, 3))
            else:                    # rangées parallèles à X, pente vers +Y
                span_x = x1 - x0 - 2 * m
                pw = min(PANEL_W, span_x / cols)
                gap = max(0.0, ((y1 - y0) - 2 * m - rows * PANEL_L) / max(rows - 1, 1))
                for r in range(rows):
                    ya = y0 + m + r * (PANEL_L + gap)
                    for k in range(cols):
                        xa = x0 + m + (span_x - cols * pw) / 2 + k * pw
                        pv(cv, (xa, ya, ze + .45), (xa + pw * .96, ya, ze + .45), (xa + pw * .96, ya + PANEL_L, ze + .25), (xa, ya + PANEL_L, ze + .25), cells=(2, 3))
        return
    if kind in ("2pans-gauche", "2pans-droite"):
        if kind == "2pans-gauche":   # faîtage selon X, pans vers la gauche (+Y) et l'arrière
            ym = (y0 + y1) / 2
            cv.poly([(a, c, z), (b, c, z), (b, ym, z + rise), (a, ym, z + rise)], "url(#uc-roofBack)", **edge)
            cv.poly([(x1, y0, ze), (x1, y1, ze), (x1, ym, ze + rise - .1)], "url(#uc-wallSide)")
            cv.poly([(a, d, z), (b, d, z), (b, ym, z + rise), (a, ym, z + rise)], "url(#uc-roofFront)", **edge)
            cv.line((a, ym, z + rise), (b, ym, z + rise), "#D3DAE6", 1.2, .6)
            cv.line((a, d, z), (b, d, z), "#8E9BB8", 1.6, .8)
            for p in panels:
                check_pan(p, "gauche", kind)
                pitched_panels(cv, (a, d, z), (b, d, z), (a, ym, z + rise), (b, ym, z + rise), p.get("colonnes", 6), p.get("rangees", 2), p.get("marge", .35))
        else:                        # faîtage selon Y, pans vers la droite (+X) et l'arrière
            xm = (x0 + x1) / 2
            cv.poly([(a, c, z), (a, d, z), (xm, d, z + rise), (xm, c, z + rise)], "url(#uc-roofBack)", **edge)
            cv.poly([(x0, y1, ze), (x1, y1, ze), (xm, y1, ze + rise - .1)], "url(#uc-wallFront)")
            cv.poly([(b, c, z), (b, d, z), (xm, d, z + rise), (xm, c, z + rise)], "url(#uc-roofSide)", **edge)
            cv.line((xm, c, z + rise), (xm, d, z + rise), "#D3DAE6", 1.2, .6)
            cv.line((b, c, z), (b, d, z), "#8E9BB8", 1.6, .8)
            for p in panels:
                check_pan(p, "droite", kind)
                pitched_panels(cv, (b, c, z), (b, d, z), (xm, c, z + rise), (xm, d, z + rise), p.get("colonnes", 6), p.get("rangees", 2), p.get("marge", .35))
        return
    if kind == "4pans":
        w, l = b - a, d - c
        if w <= l:   # faîtage selon Y
            h = w / 2
            xm = (a + b) / 2
            r1, r2 = (xm, c + h, z + rise), (xm, d - h, z + rise)
            cv.poly([(a, c, z), (b, c, z), r1], "#232B3F", **edge)
            cv.poly([(a, c, z), (a, d, z), r2, r1], "url(#uc-roofBack)", **edge)
            cv.poly([(b, c, z), (b, d, z), r2, r1], "url(#uc-roofSide)", **edge)
            cv.poly([(a, d, z), (b, d, z), r2], "url(#uc-roofFront)", **edge)
            ridge = (r1, r2)
            hips = [((b, d, z), r2), ((a, d, z), r2), ((b, c, z), r1)]
            for p in panels:
                check_pan(p, "droite", "4pans au faîtage parallèle à Y (volume plus profond que large)")
                pitched_panels(cv, (b, c, z), (b, d, z), (xm, c, z + rise), (xm, d, z + rise), p.get("colonnes", 6), p.get("rangees", 2), p.get("marge", .35), hip=h)
        else:        # faîtage selon X
            h = l / 2
            ym = (c + d) / 2
            r1, r2 = (a + h, ym, z + rise), (b - h, ym, z + rise)
            cv.poly([(a, c, z), (a, d, z), r1], "url(#uc-roofBack)", **edge)
            cv.poly([(a, c, z), (b, c, z), r2, r1], "#232B3F", **edge)
            cv.poly([(b, c, z), (b, d, z), r2], "url(#uc-roofSide)", **edge)
            cv.poly([(a, d, z), (b, d, z), r2, r1], "url(#uc-roofFront)", **edge)
            ridge = (r1, r2)
            hips = [((b, d, z), r2), ((a, d, z), r1), ((b, c, z), r2)]
            for p in panels:
                check_pan(p, "gauche", "4pans au faîtage parallèle à X (volume plus large que profond)")
                pitched_panels(cv, (a, d, z), (b, d, z), (a, ym, z + rise), (b, ym, z + rise), p.get("colonnes", 6), p.get("rangees", 2), p.get("marge", .35), hip=h)
        cv.line(*ridge, "#D3DAE6", 1.2, .6)
        for p, q in hips:
            cv.line(p, q, "#C9D1E0", .8, .4)
        return
    raise ValueError(f"type de toit inconnu : {kind!r} (plat, 2pans-gauche, 2pans-droite, 4pans)")


def draw_pergola(cv, pg):
    x0, x1 = pg["x"]
    y0, y1 = pg["y"]
    zb, zt = pg.get("sol", 3.0), pg.get("hauteur", 5.3)
    for px in (x0, (x0 + x1) / 2, x1):
        cv.line((px, y1, zb), (px, y1, zt), "#C9D1E0", 1.6, .85)
    cv.line((x0, y1, zt), (x1, y1, zt), "#C9D1E0", 1.4, .8)
    n = pg.get("panneaux", 0)
    if n:
        pw = (x1 - x0) / n
        for i in range(n):
            xa = x0 + i * pw
            pv(cv, (xa, y0, zt + .3), (xa + pw * .96, y0, zt + .3), (xa + pw * .96, y1 - .2, zt + .05), (xa, y1 - .2, zt + .05))


def render(desc: dict):
    cv = Canvas(scale=desc.get("echelle", 15.0))
    sol = desc.get("sol", {"x": [-6, 24], "y": [-3, 20]})
    (sx0, sx1), (sy0, sy1) = sol["x"], sol["y"]
    cv.poly([(sx0, sy0, 0), (sx1, sy0, 0), (sx1, sy1, 0), (sx0, sy1, 0)], "url(#uc-ground)", stroke="#2A5C9A", so=.25)
    pool = desc.get("piscine")
    if pool:
        (px0, px1), (py0, py1) = pool["x"], pool["y"]
        cv.poly([(px0 - .5, py0 - .5, .02), (px1 + .5, py0 - .5, .02), (px1 + .5, py1 + .5, .02), (px0 - .5, py1 + .5, .02)], "#B7C2D6", stroke="#D6DDEA", so=.5)
        cv.poly([(px0, py0, .03), (px1, py0, .03), (px1, py1, .03), (px0, py1, .03)], "url(#uc-water)", stroke="#86D8F5", so=.5)
    for t in desc.get("arbres", []):
        x, y, r = t
        cv.line((x, y, 0), (x, y, 1.7), "#3A4660", 2.2, .9)
        cv.circle((x, y, 3.4), r, "url(#uc-tree)")
    for item in desc.get("volumes", []):
        if item.get("pergola"):
            draw_pergola(cv, item["pergola"])
            continue
        draw_walls(cv, item)
        draw_roof(cv, item)
    pole = desc.get("poteau")
    if pole:
        x, y = pole
        cv.line((x, y, 0), (x, y, 8.6), "#9AA6BE", 2.2, .85)
        cv.line((x - .8, y, 8.1), (x + .8, y, 8.1), "#9AA6BE", 1.6, .85)
        cv.line((x - .8, y, 7.5), (x + .8, y, 7.5), "#9AA6BE", 1.2, .7)
    return cv


def suggest_positions(cv: Canvas, box, aspect=1.45, area=(0.0, 6.5, 100.0)):
    """Positions conseillées des boules (en % de la carte) pour l'image produite."""
    minx, miny, w, h = box
    ax, ay, aw = area

    def to_card(px, py):
        x = ax + (px - minx) / w * aw
        y = (ay / 100 * (100 / aspect) + (py - miny) / w * aw) * aspect   # % de la hauteur de la carte
        return round(x, 1), round(y, 1)

    if cv.panels:
        cx = sum(p[0] for p in cv.panels) / len(cv.panels)
        bottom = max(p[1] for p in cv.panels)
        sx, by = to_card(cx, bottom)
    else:
        sx, by = 60.0, 30.0
    sx = max(22.0, min(70.0, sx))
    inv_y = max(34.0, min(55.0, by + 8))   # onduleur sous les panneaux, pour ne pas les cacher
    return {
        "solar": {"x": sx, "y": 11.5},
        "inverter": {"x": sx, "y": inv_y},
        "grid": {"x": min(88.0, sx + 21), "y": 11.5},
        "battery": {"x": max(14.0, sx - 24), "y": 79},
        "home": {"x": min(86.0, sx + 16), "y": 79},
    }


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        desc = json.load(f)
    cv = render(desc)
    svg, box = cv.svg()
    with open(argv[2], "w", encoding="utf-8") as f:
        f.write(svg)
    pos = suggest_positions(cv, box)
    print(f"{argv[2]} : {box[2]:.0f} x {box[3]:.0f}, {len(cv.panels)} panneaux")
    print("Positions conseillées pour ucaness-flow-card (nodes) :")
    for k, v in pos.items():
        print(f"  {k}: {{x: {v['x']}, y: {v['y']}}}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
