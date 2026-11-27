#!/usr/bin/env python3
"""Dessine une maison en perspective isométrique (SVG) dans le style du tableau de bord UCANESS.

Usage :
    python maison_iso.py description.json maison.svg [--style soir]

Style « soir » (ou "style": "soir" dans la description) : murs sombres, fenêtres chaudes qui éclairent le sol,
sol mouillé avec reflets, liserés lumineux, bassin éclairé, pylône en treillis ; "lampes": [[x, y], ...] pour des
lampes de jardin, et ["sapin"] en 4e valeur d'un arbre pour un conifère.

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


# Style « soir » (0.8.0) : murs anthracite, fenêtres chaudes qui éclairent le sol, sol mouillé avec reflets,
# liserés lumineux cyan, bassin éclairé, lampes de jardin. Mêmes identifiants de dégradés, autres couleurs.
SOIR = {
    "#7A869F": "#565F78", "#58637D": "#2C3348",      # mur de face
    "#525D78": "#3A4258", "#3B4560": "#1C2233",      # mur de côté
    "#4A546C": "#2E3548", "#363F56": "#1B2030",      # toit, pan de face
    "#3A4359": "#262C3E", "#262E42": "#141826",      # toit, pan de côté
    "#2C3449": "#1A1F2E", "#3A4459": "#262C3D",      # toit, pan arrière
    "#F3D48F": "#FFF3C4", "#C08A3E": "#FFB03A",      # vitre éclairée
    "#36598E": "#27508C", "#121F3E": "#060D1E",      # vitre éteinte
    "#5FD0F2": "#8AF6FF", "#1E74B6": "#0AA3C8",      # eau
    "#3C5F6E": "#2F6B5A", "#1B2E3E": "#0B1F22",      # arbre
}
DEFS_SOIR = """<linearGradient id="uc-wet" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#16294D"/><stop offset=".55" stop-color="#0A1630"/><stop offset="1" stop-color="#050C1C" stop-opacity=".2"/></linearGradient>
<linearGradient id="uc-spill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFC25A" stop-opacity=".55"/><stop offset="1" stop-color="#FFC25A" stop-opacity="0"/></linearGradient>
<radialGradient id="uc-halo"><stop offset="0" stop-color="#FFE2A0" stop-opacity=".9"/><stop offset=".35" stop-color="#FFB84A" stop-opacity=".35"/><stop offset="1" stop-color="#FFB84A" stop-opacity="0"/></radialGradient>
<filter id="uc-flou" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3.2"/></filter>
<filter id="uc-flou2" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="1.6"/></filter>
<filter id="uc-lueur" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>"""


@dataclass
class Canvas:
    scale: float = 15.0
    shapes: list = field(default_factory=list)
    pts: list = field(default_factory=list)
    panels: list = field(default_factory=list)   # centres des panneaux (coordonnées écran)
    style: str = ""
    kz: float = 1.0                              # −0,55 pendant le dessin des reflets (hauteurs retournées et tassées)

    def P(self, x, y, z):
        return ((x - y) * C30 * self.scale, (x + y) * 0.5 * self.scale - z * self.kz * self.scale)

    def raw(self, svg):
        self.shapes.append(svg)

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
        defs = DEFS
        if self.style == "soir":
            for avant, apres in SOIR.items():
                defs = defs.replace(avant, apres)
            defs = defs.replace("</defs>", DEFS_SOIR)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{minx:.0f} {miny:.0f} {w:.0f} {h:.0f}" '
               f'width="{w:.0f}" height="{h:.0f}">{defs}{body}</svg>')
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


def _fenetres_eclairees(desc):
    for vol in desc.get("volumes", []):
        if vol.get("pergola"):
            continue
        for f in vol.get("fenetres", []):
            if f.get("eclairee"):
                yield vol, f


def _soir_avant(cv, desc, sol):
    """Sous la maison : sol mouillé, dallage, reflets des façades, lumière des fenêtres au sol."""
    (sx0, sx1), (sy0, sy1) = sol["x"], sol["y"]
    cv.poly([(sx0, sy0, 0), (sx1, sy0, 0), (sx1, sy1, 0), (sx0, sy1, 0)], "url(#uc-wet)", stroke="#22E0F0", sw=0.8, so=.35)
    pas = 3.0
    x = math.ceil(sx0 / pas) * pas
    while x < sx1:
        cv.line((x, sy0, 0), (x, sy1, 0), "#3B6EA8", 0.5, .16)
        x += pas
    y = math.ceil(sy0 / pas) * pas
    while y < sy1:
        cv.line((sx0, y, 0), (sx1, y, 0), "#3B6EA8", 0.5, .16)
        y += pas
    # Reflets : les façades redessinées tête en bas, tassées, floues et à demi effacées.
    cv.raw('<g opacity=".34" filter="url(#uc-flou2)">')
    cv.kz = -0.55
    for vol in desc.get("volumes", []):
        if not vol.get("pergola"):
            draw_walls(cv, vol)
    cv.kz = 1.0
    cv.raw("</g>")
    # Lumière des fenêtres éclairées sur le sol, devant la façade.
    cv.raw('<g filter="url(#uc-flou)" style="mix-blend-mode: screen">')
    for vol, f in _fenetres_eclairees(desc):
        x0, x1 = vol["x"]
        y0, y1 = vol["y"]
        portee = 1.6 + 1.1 * (f["haut"] - f["bas"]) + 0.5 * f["bas"]
        if f["face"] == "gauche":
            cv.poly([(x0 + f["de"], y1, 0), (x0 + f["a"], y1, 0), (x0 + f["a"] + .7, y1 + portee, 0), (x0 + f["de"] - .7, y1 + portee, 0)], "url(#uc-spill)", so=0)
        else:
            cv.poly([(x1, y0 + f["de"], 0), (x1, y0 + f["a"], 0), (x1 + portee, y0 + f["a"] + .7, 0), (x1 + portee, y0 + f["de"] - .7, 0)], "url(#uc-spill)", so=0)
    cv.raw("</g>")


def _soir_apres(cv, desc):
    """Par-dessus la maison : halo des fenêtres, liserés lumineux des façades, lampes de jardin."""
    cv.raw('<g filter="url(#uc-flou)" style="mix-blend-mode: screen" opacity=".85">')
    for vol, f in _fenetres_eclairees(desc):
        face_rect(cv, vol, f["face"], f["de"], f["a"], f["bas"], f["haut"], "#FFC25A", eps=.06, so=0)
    cv.raw("</g>")
    cv.raw('<g filter="url(#uc-lueur)">')
    for x, y in desc.get("lampes", []):
        cv.line((x, y, 0), (x, y, .9), "#C9D1E0", 1.6, .9)
        cv.line((x, y, .9), (x, y, 1.15), "#FFE9B0", 2.6, 1)
    cv.raw("</g>")
    for x, y in desc.get("lampes", []):
        cx, cy = cv.P(x, y, 0.3)
        r = 2.2 * cv.scale
        cv.raw(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{r:.1f}" ry="{r * .55:.1f}" fill="url(#uc-halo)" style="mix-blend-mode: screen"></ellipse>')


def _lisere(cv, vol):
    """Liseré lumineux au pied des deux façades visibles et sur l'arête entre elles. Dessiné juste après son
    volume : un volume placé devant le recouvre."""
    x0, x1 = vol["x"]
    y0, y1 = vol["y"]
    z0, z1 = vol["z"]
    if z0 > 0:                        # un étage posé sur un autre volume : pas de liseré au pied
        return
    e = .06
    cv.raw('<g filter="url(#uc-lueur)">')
    cv.line((x0, y1 + e, .05), (x1 + e, y1 + e, .05), "#22E0F0", 1.3, .95)
    cv.line((x1 + e, y0, .05), (x1 + e, y1 + e, .05), "#22E0F0", 1.3, .95)
    cv.line((x1 + e, y1 + e, .05), (x1 + e, y1 + e, z1), "#22E0F0", 1.0, .7)
    cv.raw("</g>")


def _sapin(cv, x, y, r):
    cv.line((x, y, 0), (x, y, 1.0), "#2A2F3A", 2.4, .95)
    for k, (base, haut, larg) in enumerate(((0.8, 3.0, 1.0), (2.2, 4.4, .78), (3.6, 5.8, .52))):
        (gx, gy), (dx, dy), (tx, ty) = cv.P(x - r * larg * .7, y + r * larg * .7, base), cv.P(x + r * larg * .7, y - r * larg * .7, base), cv.P(x, y, haut)
        cv.pts.extend([(gx, gy), (dx, dy), (tx, ty)])
        cv.raw(f'<polygon points="{gx:.1f},{gy:.1f} {dx:.1f},{dy:.1f} {tx:.1f},{ty:.1f}" fill="url(#uc-tree)" stroke="#4FA08A" stroke-width=".6" stroke-opacity=".5"></polygon>')


def _pylone(cv, x, y):
    """Pylône en treillis : deux montants qui se resserrent, croisillons, deux bras."""
    h, b, t = 9.4, .95, .22
    n = 6
    niveaux = [(h * k / n, b + (t - b) * k / n) for k in range(n + 1)]
    for (za, la), (zb, lb) in zip(niveaux, niveaux[1:]):
        cv.line((x - la, y, za), (x - lb, y, zb), "#AEB9CC", 1.5, .95)
        cv.line((x + la, y, za), (x + lb, y, zb), "#AEB9CC", 1.5, .95)
        cv.line((x - la, y, za), (x + lb, y, zb), "#8794AC", .8, .8)
        cv.line((x + la, y, za), (x - lb, y, zb), "#8794AC", .8, .8)
        cv.line((x - lb, y, zb), (x + lb, y, zb), "#8794AC", .8, .8)
    for z, l in ((7.6, 1.5), (8.7, 1.1)):
        cv.line((x - l, y, z), (x + l, y, z), "#AEB9CC", 1.5, .95)
        for sx in (-l, l):
            cv.line((x + sx, y, z), (x + sx, y, z - .35), "#7FD3FF", 1.4, .9)


def render(desc: dict, style: str | None = None):
    style = style if style is not None else desc.get("style", "")
    soir = style == "soir"
    cv = Canvas(scale=desc.get("echelle", 15.0), style=style)
    sol = desc.get("sol", {"x": [-6, 24], "y": [-3, 20]})
    (sx0, sx1), (sy0, sy1) = sol["x"], sol["y"]
    if soir:
        _soir_avant(cv, desc, sol)
    else:
        cv.poly([(sx0, sy0, 0), (sx1, sy0, 0), (sx1, sy1, 0), (sx0, sy1, 0)], "url(#uc-ground)", stroke="#2A5C9A", so=.25)
    pool = desc.get("piscine")
    if pool:
        (px0, px1), (py0, py1) = pool["x"], pool["y"]
        cv.poly([(px0 - .5, py0 - .5, .02), (px1 + .5, py0 - .5, .02), (px1 + .5, py1 + .5, .02), (px0 - .5, py1 + .5, .02)], "#7C8AA6" if soir else "#B7C2D6", stroke="#D6DDEA", so=.5)
        if soir:
            cv.raw('<g filter="url(#uc-lueur)">')
        cv.poly([(px0, py0, .03), (px1, py0, .03), (px1, py1, .03), (px0, py1, .03)], "url(#uc-water)", stroke="#86D8F5", so=.5)
        if soir:
            cv.raw("</g>")
            for k in (1, 2, 3):   # reflets de l'eau
                yy = py0 + (py1 - py0) * k / 4
                cv.line((px0 + .5, yy, .04), (px1 - .5, yy + .25, .04), "#E6FDFF", .7, .45)
    for t in desc.get("arbres", []):
        x, y, r = t[:3]
        if soir and (len(t) > 3 and t[3] == "sapin"):
            _sapin(cv, x, y, r)
            continue
        cv.line((x, y, 0), (x, y, 1.7), "#3A4660", 2.2, .9)
        cv.circle((x, y, 3.4), r, "url(#uc-tree)")
        if soir:   # feuillage en relief : un second volume plus clair, décalé vers la lumière
            cv.circle((x + r * .25, y + r * .25, 3.4 + r * .3), r * .62, "url(#uc-tree)")
    for item in desc.get("volumes", []):
        if item.get("pergola"):
            draw_pergola(cv, item["pergola"])
            continue
        draw_walls(cv, item)
        if soir:
            _lisere(cv, item)
        draw_roof(cv, item)
    pole = desc.get("poteau")
    if pole:
        x, y = pole
        if soir:
            _pylone(cv, x, y)
        else:
            cv.line((x, y, 0), (x, y, 8.6), "#9AA6BE", 2.2, .85)
            cv.line((x - .8, y, 8.1), (x + .8, y, 8.1), "#9AA6BE", 1.6, .85)
            cv.line((x - .8, y, 7.5), (x + .8, y, 7.5), "#9AA6BE", 1.2, .7)
    if soir:
        _soir_apres(cv, desc)
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
    style = None
    if "--style" in argv:
        i = argv.index("--style")
        style = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) < 3:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        desc = json.load(f)
    cv = render(desc, style)
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
