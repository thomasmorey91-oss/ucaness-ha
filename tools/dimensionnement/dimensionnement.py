"""Analyse d'une installation solaire avec batterie et préconisation de dimensionnement.

À lancer une fois, à l'installation (ou pour un projet), depuis un PC :

    python tools/dimensionnement/dimensionnement.py installation.yaml [-o rapport.md]

Entrées (voir exemple-installation.yaml) :
  - la consommation de la maison heure par heure (export CSV de Home Assistant, de la courbe de
    charge Enedis ou de tout compteur), idéalement sur une année complète ;
  - les toitures (puissance installée, inclinaison, orientation, place disponible), la batterie et
    l'onduleur actuels ;
  - facultatif : production mesurée (pour recaler PVGIS), tarif et coûts d'investissement.

Production solaire : PVGIS (Commission européenne), heure par heure sur plusieurs années réelles,
téléchargée par pvlib et gardée en cache (aucune autre donnée n'est envoyée : seulement la
position, l'inclinaison et l'orientation des toitures).

Sorties : un rapport Markdown (installation existante, autonomie totale, autonomie élevée
réaliste, optimum économique, hypothèses) et la grille complète des simulations en CSV.
Contre-vérification facultative avec BREOS (bilan et usure de la batterie) si le module est installé.

Modèle : bilan horaire en courant alternatif, la batterie se charge avec le surplus solaire et
complète la maison (autoconsommation simple, sans charge sur le réseau), puissances bornées par
l'onduleur et la batterie, rendement dans chaque sens. Les pointes de moins d'une heure ne sont pas
vues : elles sont signalées à part.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

TOLERANCE_AUTONOMIE_KWH = 0.5           # achat annuel considéré comme nul (arrondis)


# --------------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------------
@dataclass
class Toiture:
    nom: str
    kwc: float
    inclinaison: float
    azimut: float                       # convention PVGIS : 0 = sud, -90 = est, 90 = ouest
    pertes: float = 14.0
    kwc_max: float | None = None


@dataclass
class Config:
    latitude: float
    longitude: float
    fuseau: str
    toitures: list[Toiture]
    capacite_kwh: float = 0.0
    plancher_pct: float = 10.0
    rendement: float = 0.95
    puissance_batterie_kw: float = 5.0
    module_kwh: float = 5.12
    capacite_max_kwh: float | None = None
    onduleur_kw: float = 6.0
    pv_max_onduleur_kwc: float | None = None
    secours_kw: float | None = None
    prix_achat: float | None = None
    prix_revente: float | None = None
    cout_kwc: float | None = None
    cout_kwh: float | None = None
    annees: tuple[int, int] = (2014, 2023)
    cache: pathlib.Path | None = None
    pas_pv_kwc: float = 0.5
    batterie_max_recherche_kwh: float = 200.0
    consommation: dict[str, Any] = field(default_factory=dict)
    production_mesuree: dict[str, Any] | None = None

    @property
    def capacite_utile_kwh(self) -> float:
        return self.capacite_kwh * (1 - self.plancher_pct / 100)

    @property
    def kwc_actuel(self) -> float:
        return sum(t.kwc for t in self.toitures)


def lire_config(chemin: str | pathlib.Path) -> Config:
    chemin = pathlib.Path(chemin)
    d = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    base = chemin.parent
    lieu, bat, ond = d.get("lieu", {}), d.get("batterie", {}), d.get("onduleur", {})
    tarif, couts, pvgis, rech = d.get("tarif") or {}, d.get("couts") or {}, d.get("pvgis") or {}, d.get("recherche") or {}
    conso = dict(d["consommation"])
    conso["fichier"] = str((base / conso["fichier"]).resolve())
    prod = d.get("production_mesuree")
    if prod:
        prod = dict(prod)
        prod["fichier"] = str((base / prod["fichier"]).resolve())
    annees = pvgis.get("annees", [2014, 2023])
    return Config(
        latitude=float(lieu["latitude"]), longitude=float(lieu["longitude"]), fuseau=lieu.get("fuseau", "Europe/Paris"),
        toitures=[Toiture(t.get("nom", f"Toiture {i + 1}"), float(t.get("kwc", 0)), float(t["inclinaison"]),
                          float(t["azimut"]), float(t.get("pertes", 14)),
                          float(t["kwc_max"]) if t.get("kwc_max") is not None else None)
                  for i, t in enumerate(d["toitures"])],
        capacite_kwh=float(bat.get("capacite_kwh", 0)), plancher_pct=float(bat.get("plancher_pct", 10)),
        rendement=float(bat.get("rendement_pct", 95)) / 100, puissance_batterie_kw=float(bat.get("puissance_kw", 5)),
        module_kwh=float(bat.get("module_kwh", 5.12)),
        capacite_max_kwh=float(bat["capacite_max_kwh"]) if bat.get("capacite_max_kwh") else None,
        onduleur_kw=float(ond.get("puissance_ac_kw", 6)),
        pv_max_onduleur_kwc=float(ond["pv_max_kwc"]) if ond.get("pv_max_kwc") else None,
        secours_kw=float(ond["secours_kw"]) if ond.get("secours_kw") else None,
        prix_achat=tarif.get("achat_eur_kwh"), prix_revente=tarif.get("revente_eur_kwh"),
        cout_kwc=couts.get("pv_eur_kwc"), cout_kwh=couts.get("batterie_eur_kwh"),
        annees=(int(annees[0]), int(annees[-1])),
        cache=(base / pvgis["cache"]) if pvgis.get("cache") else None,
        pas_pv_kwc=float(rech.get("pv_pas_kwc", 0.5)),
        batterie_max_recherche_kwh=float(rech.get("batterie_max_kwh", 200)),
        consommation=conso, production_mesuree=prod,
    )


# --------------------------------------------------------------------------------------------
# Lecture des séries mesurées
# --------------------------------------------------------------------------------------------
def lire_serie_horaire(fichier: str, unite: str, fuseau: str, colonne_date: str | None = None,
                       colonne_valeur: str | None = None) -> pd.Series:
    """CSV -> énergie horaire (kWh), index en heure locale.

    Reconnaît l'export de l'historique de Home Assistant (entity_id, state, last_changed), la
    courbe de charge Enedis (lignes d'en-tête puis « Horodate;Valeur ») et tout CSV « date, valeur ».
    unite : W ou kW (puissance, moyennée par heure) ; Wh ou kWh (énergie par pas, sommée par heure).
    """
    texte = pathlib.Path(fichier).read_text(encoding="utf-8-sig", errors="replace").splitlines()
    debut = next((i for i, l in enumerate(texte) if "horodate" in l.lower()), 0)
    from io import StringIO
    df = pd.read_csv(StringIO("\n".join(texte[debut:])), sep=None, engine="python")
    cols = {c.lower().strip(): c for c in df.columns}

    def cherche(noms):
        for n in noms:
            for k, c in cols.items():
                if n in k:
                    return c
        return None

    cd = colonne_date or cherche(["horodate", "last_changed", "date", "time", "start", "debut"])
    cv = colonne_valeur or cherche(["valeur", "state", "mean", "value", "kwh", "puissance", "power"])
    if cd is None or cv is None:
        raise ValueError(f"{fichier} : colonnes date et valeur introuvables ({list(df.columns)})")
    t = pd.to_datetime(df[cd], utc=True, errors="coerce", format="mixed")
    v = pd.to_numeric(df[cv].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    s = pd.Series(v.values, index=t).dropna()
    s = s[~s.index.isna()].sort_index()
    s.index = s.index.tz_convert(fuseau)
    u = unite.lower()
    if u in ("w", "kw"):
        facteur = 1 / 1000 if u == "w" else 1.0
        # Puissance : moyenne pondérée par la durée (échantillons irréguliers de Home Assistant).
        pas = s.resample("1min").ffill(limit=180)
        h = pas.resample("1h").mean() * facteur
    elif u in ("wh", "kwh"):
        h = s.resample("1h").sum(min_count=1) * (1 / 1000 if u == "wh" else 1.0)
    else:
        raise ValueError("unite : W, kW, Wh ou kWh")
    return h.dropna().clip(lower=0)


# --------------------------------------------------------------------------------------------
# Production PVGIS
# --------------------------------------------------------------------------------------------
def production_pvgis_par_kwc(cfg: Config, toit: Toiture) -> pd.Series:
    """kWh produits par kWc, heure par heure, années cfg.annees (UTC). Cache JSON."""
    cle = f"pvgis_{cfg.latitude:.2f}_{cfg.longitude:.2f}_{toit.inclinaison:g}_{toit.azimut:g}_{toit.pertes:g}_{cfg.annees[0]}_{cfg.annees[1]}.json"
    if cfg.cache:
        f = cfg.cache / cle
        if f.exists():
            d = json.loads(f.read_text())
            return pd.Series(d["kwh"], index=pd.to_datetime(d["t"], utc=True))
    try:
        import pvlib  # noqa: PLC0415
    except ImportError as err:
        raise SystemExit("pvlib est nécessaire pour télécharger PVGIS : pip install pvlib") from err
    data, _, _ = pvlib.iotools.get_pvgis_hourly(
        cfg.latitude, cfg.longitude, start=cfg.annees[0], end=cfg.annees[1],
        surface_tilt=toit.inclinaison, surface_azimuth=toit.azimut + 180,      # pvlib : 180 = sud
        pvcalculation=True, peakpower=1.0, loss=toit.pertes, components=False,
        url="https://re.jrc.ec.europa.eu/api/v5_3/",
    )
    s = (data["P"] / 1000).astype(float)
    s.index = s.index.floor("h")
    if cfg.cache:
        cfg.cache.mkdir(parents=True, exist_ok=True)
        (cfg.cache / cle).write_text(json.dumps({"t": [x.isoformat() for x in s.index], "kwh": s.round(5).tolist()}))
    return s


def caler_sur_periode(pv_utc: pd.Series, index_local: pd.DatetimeIndex, annee: int) -> np.ndarray:
    """Production d'une année PVGIS replacée sur les dates de la consommation (mois, jour, heure)."""
    a = pv_utc[pv_utc.index.year == annee]
    loc = a.copy()
    loc.index = a.index.tz_convert(index_local.tz)
    cle = pd.MultiIndex.from_arrays([loc.index.month, loc.index.day, loc.index.hour])
    table = pd.Series(loc.values, index=cle)
    table = table[~table.index.duplicated()]
    voulu = pd.MultiIndex.from_arrays([index_local.month, index_local.day, index_local.hour])
    v = table.reindex(voulu)
    # 29 février ou heure manquante (changement d'heure) : valeur de la veille à la même heure.
    if v.isna().any():
        veille = pd.MultiIndex.from_arrays([(index_local - pd.Timedelta(days=1)).month,
                                            (index_local - pd.Timedelta(days=1)).day, index_local.hour])
        v = v.fillna(pd.Series(table.reindex(veille).values, index=v.index))
    return v.fillna(0).to_numpy(dtype=float)


# --------------------------------------------------------------------------------------------
# Simulation (vectorisée : plusieurs puissances solaires × plusieurs batteries d'un coup)
# --------------------------------------------------------------------------------------------
@dataclass
class Resultat:
    achat: np.ndarray            # kWh achetés sur la période (n_pv, n_bat)
    revente: np.ndarray
    production: np.ndarray       # (n_pv,)
    conso: float
    decharge: np.ndarray         # kWh fournis par la batterie
    heures_pleine: np.ndarray
    heures_vide: np.ndarray
    ecretage: np.ndarray         # kWh solaires perdus (onduleur)
    achat_mensuel: np.ndarray | None = None   # (12, n_pv, n_bat)

    @property
    def autonomie(self) -> np.ndarray:
        return 1 - self.achat / self.conso if self.conso > 0 else np.zeros_like(self.achat)

    @property
    def autoconsommation(self) -> np.ndarray:
        prod = self.production[:, None]
        return np.where(prod > 0, 1 - self.revente / np.maximum(prod, 1e-9), 0.0)


def simuler(conso: np.ndarray, pv: np.ndarray, capacites: Iterable[float], *, rendement: float,
            p_batterie_kw: float, p_onduleur_kw: float, mois: np.ndarray | None = None,
            passes: int = 2) -> Resultat:
    """conso : (T,) kWh par heure ; pv : (n_pv, T) kWh par heure ; capacites : utiles (kWh).

    La batterie part pleine ; avec passes=2 la première année sert à atteindre le régime établi et
    seule la seconde est comptée (le stock de fin d'année repasse au début).
    """
    pv = np.atleast_2d(np.asarray(pv, dtype=float))
    cap = np.asarray(list(capacites), dtype=float)[None, :]
    n_pv, T = pv.shape
    eta = rendement
    s = np.repeat(cap, n_pv, axis=0).astype(float)
    p_ond = p_onduleur_kw
    for passe in range(passes):
        compte = passe == passes - 1
        achat = np.zeros_like(s); revente = np.zeros_like(s); dech = np.zeros_like(s)
        pleine = np.zeros_like(s); vide = np.zeros_like(s)
        ecret = np.zeros(n_pv)
        achat_m = np.zeros((12,) + s.shape) if (compte and mois is not None) else None
        for t in range(T):
            prod = np.minimum(pv[:, t], p_ond)                    # écrêtage par l'onduleur
            if compte:
                ecret += pv[:, t] - prod
            L = conso[t]
            net = (prod - L)[:, None]
            surplus = np.maximum(net, 0)
            deficit = np.maximum(-net, 0)
            charge = np.minimum(np.minimum(surplus, p_batterie_kw), np.maximum(cap - s, 0) / eta)
            # La sortie alternative de l'onduleur est bornée : solaire utilisé + batterie <= P onduleur.
            marge = np.maximum(p_ond - np.minimum(prod, L)[:, None], 0)
            fourni = np.minimum(np.minimum(deficit, np.minimum(p_batterie_kw, marge)), s * eta)
            s = s + charge * eta - fourni / eta
            if compte:
                a = deficit - fourni
                achat += a
                revente += surplus - charge
                dech += fourni
                pleine += s >= cap - 1e-6
                vide += s <= 1e-6
                if achat_m is not None:
                    achat_m[mois[t] - 1] += a
    return Resultat(achat, revente, pv.sum(axis=1), float(conso.sum()), dech, pleine, vide, ecret, achat_m)


def _achat_scalaire(L: list[float], pv: list[float], cap: float, eta: float, pb: float, pond: float,
                    tolerance: float) -> float:
    """Même modèle que simuler(), en Python pur pour une seule batterie (recherche rapide).
    Deux passes (régime établi) ; s'arrête dès que l'achat dépasse la tolérance."""
    s = cap
    achat = 0.0
    for passe in (0, 1):
        achat = 0.0
        for l, p in zip(L, pv):
            prod = p if p < pond else pond
            net = prod - l
            if net >= 0:
                room = (cap - s) / eta
                c = min(net, pb, room if room > 0 else 0.0)
                s += c * eta
            else:
                deficit = -net
                marge = pond - (prod if prod < l else l)
                f = min(deficit, pb, marge if marge > 0 else 0.0, s * eta)
                s -= f / eta
                if passe:
                    achat += deficit - f
                    if achat > tolerance:
                        return achat
    return achat


def capacite_autonomie_totale(conso: np.ndarray, pvs: list[np.ndarray], *, rendement: float, p_batterie_kw: float,
                              p_onduleur_kw: float, cap_max: float, tolerance: float = TOLERANCE_AUTONOMIE_KWH,
                              borne_haute: float | None = None) -> float | None:
    """Plus petite capacité utile (kWh) sans aucun achat, toutes années solaires confondues ; None si impossible.
    pvs : une série de production par année solaire rejouée."""
    L = [float(x) for x in conso]
    if sum(L) <= 0:
        return 0.0
    series = [[float(x) for x in pv] for pv in pvs]
    # Bilan d'énergie : sans réseau, la production (après pertes de stockage) doit couvrir la consommation.
    if any(sum(pv) < sum(L) for pv in series):
        return None
    if any(l > p_onduleur_kw + 1e-9 for l in L):
        return None
    ordre = list(range(len(series)))

    def faisable(c: float) -> bool:
        for k, i in enumerate(ordre):
            if _achat_scalaire(L, series[i], c, rendement, p_batterie_kw, p_onduleur_kw, tolerance) > tolerance:
                ordre.insert(0, ordre.pop(k))      # l'année qui échoue sera testée en premier la fois suivante
                return False
        return True

    hi = min(cap_max, borne_haute) if borne_haute is not None else cap_max
    if not faisable(hi):
        if hi < cap_max and faisable(cap_max):
            hi = cap_max
        else:
            return None
    lo = 0.0
    if faisable(lo):
        return 0.0
    while hi - lo > 0.1:
        mid = (lo + hi) / 2
        if faisable(mid):
            hi = mid
        else:
            lo = mid
    return hi


# --------------------------------------------------------------------------------------------
# Répartition d'une puissance solaire sur les toitures
# --------------------------------------------------------------------------------------------
def repartir(cfg: Config, kwc_total: float, rendements: dict[str, float]) -> tuple[dict[str, float], bool]:
    """Garde l'existant, ajoute sur les pans les plus productifs jusqu'à leur place disponible.
    Sous la puissance actuelle : réduction proportionnelle (projet neuf). Renvoie (kWc par pan, tient sur le toit)."""
    actuel = {t.nom: t.kwc for t in cfg.toitures}
    tot = sum(actuel.values())
    if kwc_total <= tot + 1e-9:
        f = kwc_total / tot if tot > 0 else 0
        return {k: v * f for k, v in actuel.items()}, True
    reste = kwc_total - tot
    out = dict(actuel)
    for t in sorted(cfg.toitures, key=lambda t: -rendements[t.nom]):
        place = (t.kwc_max if t.kwc_max is not None else math.inf) - out[t.nom]
        ajout = min(max(place, 0), reste)
        out[t.nom] += ajout
        reste -= ajout
        if reste <= 1e-9:
            break
    tient = reste <= 1e-9
    if not tient:                       # au-delà de la place : exploration seulement
        meilleur = max(cfg.toitures, key=lambda t: rendements[t.nom]).nom
        out[meilleur] += reste
    return out, tient


# --------------------------------------------------------------------------------------------
# Analyse complète
# --------------------------------------------------------------------------------------------
@dataclass
class Analyse:
    cfg: Config
    conso: pd.Series
    pv_kwc: dict[str, pd.Series]
    annees: list[int]
    grille_pv: np.ndarray
    grille_bat: np.ndarray
    achat: np.ndarray                    # (années, n_pv, n_bat)
    revente: np.ndarray
    production: np.ndarray               # (années, n_pv)
    tient: list[bool]
    existant: dict[str, Any]
    autonomie_totale: list[dict[str, Any]]
    calage: float | None
    breos: dict[str, Any] | None = None
    saisonnier: list[dict[str, Any]] = field(default_factory=list)


def analyser(cfg: Config, conso: pd.Series | None = None, pv_kwc: dict[str, pd.Series] | None = None,
             production_mesuree: pd.Series | None = None, avec_breos: bool = False) -> Analyse:
    if conso is None:
        c = cfg.consommation
        conso = lire_serie_horaire(c["fichier"], c.get("unite", "W"), cfg.fuseau, c.get("colonne_date"), c.get("colonne_valeur"))
    conso = conso.asfreq("h").fillna(conso.groupby(conso.index.hour).transform("median")).dropna()
    if pv_kwc is None:
        pv_kwc = {t.nom: production_pvgis_par_kwc(cfg, t) for t in cfg.toitures}
    annees = sorted({int(y) for y in next(iter(pv_kwc.values())).index.year})
    idx = conso.index
    mois = idx.month.to_numpy()
    L = conso.to_numpy(dtype=float)
    par_toit = {nom: {a: caler_sur_periode(s, idx, a) for a in annees} for nom, s in pv_kwc.items()}

    calage = None
    if production_mesuree is not None and len(production_mesuree) > 24 * 30:
        commun = production_mesuree.index.intersection(idx)
        if len(commun) > 24 * 30:
            pos = idx.get_indexer(commun)
            estime = np.median([sum(t.kwc * par_toit[t.nom][a][pos] for t in cfg.toitures).sum() for a in annees])
            calage = float(production_mesuree.loc[commun].sum() / estime) if estime > 0 else None
    f_cal = calage or 1.0

    rendements = {nom: np.median([v.sum() for v in par_toit[nom].values()]) for nom in par_toit}
    pv_max = cfg.pv_max_onduleur_kwc or max(cfg.kwc_actuel * 3, 12)
    place = sum((t.kwc_max if t.kwc_max is not None else t.kwc) for t in cfg.toitures)
    haut = max(pv_max, place, cfg.kwc_actuel) * 1.5
    grille_pv = np.round(np.arange(cfg.pas_pv_kwc, haut + 1e-9, cfg.pas_pv_kwc), 3)
    if cfg.kwc_actuel > 0 and not np.isclose(grille_pv, cfg.kwc_actuel).any():
        grille_pv = np.sort(np.append(grille_pv, round(cfg.kwc_actuel, 3)))
    utile = 1 - cfg.plancher_pct / 100
    grille_bat = np.round(np.arange(0, cfg.batterie_max_recherche_kwh + 1e-9, cfg.module_kwh) * utile, 3)
    if cfg.capacite_utile_kwh > 0 and not np.isclose(grille_bat, cfg.capacite_utile_kwh).any():
        grille_bat = np.sort(np.append(grille_bat, round(cfg.capacite_utile_kwh, 3)))

    reparts = [repartir(cfg, p, rendements) for p in grille_pv]
    tient = [r[1] for r in reparts]
    achats, reventes, prods = [], [], []
    res_existant = []
    for a in annees:
        pv = np.array([sum(kw[n] * par_toit[n][a] for n in kw) for kw, _ in reparts]) * f_cal
        r = simuler(L, pv, grille_bat, rendement=cfg.rendement, p_batterie_kw=cfg.puissance_batterie_kw,
                    p_onduleur_kw=cfg.onduleur_kw)
        achats.append(r.achat); reventes.append(r.revente); prods.append(r.production)
        pv_ex = sum(t.kwc * par_toit[t.nom][a] for t in cfg.toitures) * f_cal
        res_existant.append(simuler(L, pv_ex[None, :], [cfg.capacite_utile_kwh], rendement=cfg.rendement,
                                    p_batterie_kw=cfg.puissance_batterie_kw, p_onduleur_kw=cfg.onduleur_kw, mois=mois))

    # Installation existante : année médiane (par l'autonomie) et année la plus défavorable.
    aut = [float(r.autonomie[0, 0]) for r in res_existant]
    i_med = int(np.argsort(aut)[len(aut) // 2])
    i_min = int(np.argmin(aut))
    rm, rw = res_existant[i_med], res_existant[i_min]
    nuit = conso[(conso.index.hour >= 0) & (conso.index.hour < 6)]
    existant = {
        "annee_mediane": annees[i_med], "annee_defavorable": annees[i_min],
        "production_kwh": float(rm.production[0]), "conso_kwh": rm.conso,
        "achat_kwh": float(rm.achat[0, 0]), "revente_kwh": float(rm.revente[0, 0]),
        "autonomie": float(rm.autonomie[0, 0]), "autonomie_min": float(rw.autonomie[0, 0]),
        "autoconsommation": float(rm.autoconsommation[0, 0]),
        "cycles": float(rm.decharge[0, 0] / cfg.capacite_utile_kwh) if cfg.capacite_utile_kwh > 0 else 0.0,
        "heures_pleine": float(rm.heures_pleine[0, 0]), "heures_vide": float(rm.heures_vide[0, 0]),
        "ecretage_kwh": float(rm.ecretage[0]),
        "achat_mensuel": [float(x) for x in rm.achat_mensuel[:, 0, 0]],
        "achat_mensuel_defavorable": [float(x) for x in rw.achat_mensuel[:, 0, 0]],
        "heures_conso_sup_onduleur": int((conso > cfg.onduleur_kw).sum()),
        "pic_horaire_kw": float(conso.max()),
        "conso_nuit_kw": float(nuit.median()) if len(nuit) else None,
        "jours": float(len(conso) / 24),
    }

    # Autonomie totale : toutes les années solaires, capacité exacte par recherche dichotomique.
    # La capacité nécessaire baisse quand le solaire augmente : le résultat précédent sert de borne.
    # Si l'onduleur ou la batterie actuels ne peuvent pas fournir la pointe horaire, le calcul suppose
    # un matériel assez puissant (signalé dans le rapport).
    pointe = float(L.max()) * 1.05
    p_ond_tot = max(cfg.onduleur_kw, pointe)
    p_bat_tot = max(cfg.puissance_batterie_kw, pointe)
    existant["onduleur_requis_kw"] = p_ond_tot if p_ond_tot > cfg.onduleur_kw else None
    existant["batterie_puissance_requise_kw"] = p_bat_tot if p_bat_tot > cfg.puissance_batterie_kw else None
    tot = []
    cap_max = cfg.batterie_max_recherche_kwh * utile
    borne = None
    for i, p in enumerate(grille_pv):
        kw, tient_i = reparts[i]
        pvs = [sum(kw[n] * par_toit[n][a] for n in kw) * f_cal for a in annees]
        c = capacite_autonomie_totale(L, pvs, rendement=cfg.rendement, p_batterie_kw=p_bat_tot,
                                      p_onduleur_kw=p_ond_tot, cap_max=cap_max, borne_haute=borne)
        if c is not None:
            borne = c
        tot.append({"kwc": float(p), "repartition": kw, "tient_sur_le_toit": tient_i,
                    "capacite_utile_kwh": c, "capacite_nominale_kwh": (c / utile) if c is not None else None})

    # Hors de portée d'une batterie domestique : ordre de grandeur du stockage nécessaire, pour la
    # place disponible et pour le haut de la plage étudiée.
    saisonnier = []
    if all(o["capacite_utile_kwh"] is None for o in tot):
        for p in sorted({round(min(place, grille_pv[-1]), 3), float(grille_pv[-1])}):
            if p <= 0:
                continue
            kw, tient_p = repartir(cfg, p, rendements)
            pvs = [sum(kw[n] * par_toit[n][a] for n in kw) * f_cal for a in annees]
            c = capacite_autonomie_totale(L, pvs, rendement=cfg.rendement, p_batterie_kw=p_bat_tot,
                                          p_onduleur_kw=p_ond_tot, cap_max=100000.0)
            saisonnier.append({"kwc": float(p), "tient_sur_le_toit": tient_p, "capacite_utile_kwh": c,
                               "capacite_nominale_kwh": (c / utile) if c is not None else None})

    an = Analyse(cfg, conso, pv_kwc, annees, grille_pv, grille_bat, np.array(achats), np.array(reventes),
                 np.array(prods), tient, existant, tot, calage, saisonnier=saisonnier)
    if avec_breos:
        an.breos = contre_verification_breos(an)
    return an


# --------------------------------------------------------------------------------------------
# Choix des préconisations
# --------------------------------------------------------------------------------------------
def cout_investissement(cfg: Config, kwc: float, cap_utile: float) -> float | None:
    if cfg.cout_kwc is None or cfg.cout_kwh is None:
        return None
    return kwc * cfg.cout_kwc + cap_utile / (1 - cfg.plancher_pct / 100) * cfg.cout_kwh


def _score(cfg: Config, kwc: float, cap_utile: float) -> float:
    """Coût si connu, sinon un critère neutre : kWc + kWh nominaux (on cherche le plus petit système)."""
    c = cout_investissement(cfg, kwc, cap_utile)
    return c if c is not None else kwc + cap_utile / (1 - cfg.plancher_pct / 100)


def respecte_materiel(cfg: Config, kwc: float, cap_utile: float) -> list[str]:
    notes = []
    if cfg.pv_max_onduleur_kwc and kwc > cfg.pv_max_onduleur_kwc + 1e-9:
        notes.append(f"dépasse le solaire admis par l'onduleur ({cfg.pv_max_onduleur_kwc:g} kWc)")
    nominale = cap_utile / (1 - cfg.plancher_pct / 100)
    if cfg.capacite_max_kwh and nominale > cfg.capacite_max_kwh + 1e-9:
        notes.append(f"dépasse la batterie maximale du système ({cfg.capacite_max_kwh:g} kWh)")
    return notes


def options_autonomie_totale(an: Analyse) -> list[dict[str, Any]]:
    possibles = [o for o in an.autonomie_totale if o["capacite_utile_kwh"] is not None]
    for o in possibles:
        o["score"] = _score(an.cfg, o["kwc"], o["capacite_utile_kwh"])
        o["cout"] = cout_investissement(an.cfg, o["kwc"], o["capacite_utile_kwh"])
        o["limites"] = respecte_materiel(an.cfg, o["kwc"], o["capacite_utile_kwh"])
    return sorted(possibles, key=lambda o: o["score"])


def options_objectif(an: Analyse, objectif: float) -> dict[str, Any] | None:
    """Système le moins coûteux (ou le plus petit) qui atteint l'objectif d'autonomie l'année la plus défavorable."""
    aut_min = (1 - an.achat / an.existant["conso_kwh"]).min(axis=0)
    meilleur = None
    for i, p in enumerate(an.grille_pv):
        if not an.tient[i]:
            continue
        for j, b in enumerate(an.grille_bat):
            if aut_min[i, j] >= objectif:
                s = _score(an.cfg, p, b)
                if meilleur is None or s < meilleur["score"]:
                    meilleur = {"kwc": float(p), "capacite_utile_kwh": float(b), "score": s,
                                "autonomie_min": float(aut_min[i, j]),
                                "autonomie_mediane": float(np.median(1 - an.achat[:, i, j] / an.existant["conso_kwh"])),
                                "cout": cout_investissement(an.cfg, p, b),
                                "limites": respecte_materiel(an.cfg, p, b)}
                break                     # batterie la plus petite pour ce solaire
    return meilleur


def optimum_economique(an: Analyse, duree_ans: int = 20) -> list[dict[str, Any]]:
    cfg = an.cfg
    if None in (cfg.prix_achat, cfg.prix_revente, cfg.cout_kwc, cfg.cout_kwh):
        return []
    sans = an.existant["conso_kwh"] * cfg.prix_achat
    achat = np.median(an.achat, axis=0)
    revente = np.median(an.revente, axis=0)
    eco = sans - (achat * cfg.prix_achat - revente * cfg.prix_revente)
    out = []
    for i, p in enumerate(an.grille_pv):
        if not an.tient[i]:
            continue
        for j, b in enumerate(an.grille_bat):
            inv = cout_investissement(cfg, p, b)
            bilan = eco[i, j] * duree_ans - inv
            out.append({"kwc": float(p), "capacite_utile_kwh": float(b), "economie_an": float(eco[i, j]),
                        "investissement": inv, "bilan": float(bilan),
                        "retour_ans": inv / eco[i, j] if eco[i, j] > 0 else None,
                        "autonomie_mediane": float(1 - achat[i, j] / an.existant["conso_kwh"]),
                        "limites": respecte_materiel(cfg, p, b)})
    return sorted(out, key=lambda o: -o["bilan"])[:5]


# --------------------------------------------------------------------------------------------
# Contre-vérification BREOS (facultative)
# --------------------------------------------------------------------------------------------
def contre_verification_breos(an: Analyse) -> dict[str, Any] | None:
    try:
        import breos  # noqa: PLC0415
    except ImportError:
        return {"erreur": "module breos absent (pip install breos)"}
    cfg = an.cfg
    a = an.existant["annee_mediane"]
    idx = an.conso.index
    pv = sum(t.kwc * caler_sur_periode(an.pv_kwc[t.nom], idx, a) for t in cfg.toitures) * (an.calage or 1)
    try:
        bat = breos.BatteryConfig(
            nominal_energy_wh=max(cfg.capacite_kwh, 0.001) * 1000, min_soc=cfg.plancher_pct / 100, max_soc=1.0,
            charge_efficiency=cfg.rendement, discharge_efficiency=cfg.rendement, enable_replacement=False,
            inverter_ac_capacity_w=cfg.onduleur_kw * 1000, inverter_efficiency=1.0,
            max_charge_power_w=cfg.puissance_batterie_kw * 1000, max_discharge_power_w=cfg.puissance_batterie_kw * 1000,
        )
        # BREOS attend du solaire continu (W) : la production PVGIS (alternatif) est passée telle quelle,
        # rendement d'onduleur à 1 pour rester comparable.
        _, _, resume, _, _ = breos.simulate_energy_balance(
            pd.Series(pv * 1000, index=idx), pd.DataFrame({"charge": an.conso.to_numpy() * 1000}, index=idx), bat)
        r = resume.iloc[0] if isinstance(resume, pd.DataFrame) else resume
        return {"annee": a, "autonomie": float(r["Grid Independence [%]"]) / 100,
                "achat_kwh": float(r["Import [kWh]"]), "soh_fin": float(r["Final SOH [%]"])}
    except Exception as err:  # noqa: BLE001  (contre-vérification seulement)
        return {"erreur": f"BREOS : {err}"}


# --------------------------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------------------------
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def _n(x: float | None, d: int = 1, unite: str = "") -> str:
    if x is None:
        return "—"
    s = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return f"{s} {unite}".strip()


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.0f} %"


def rapport(an: Analyse) -> str:
    cfg, ex = an.cfg, an.existant
    L = []
    w = L.append
    w("# Analyse de l'installation et préconisations\n")
    w(f"Période de consommation analysée : {_n(ex['jours'], 0)} jours, {_n(ex['conso_kwh'], 0, 'kWh')}. "
      f"Production solaire : PVGIS, années {an.annees[0]} à {an.annees[-1]} rejouées sur cette période"
      + (f", recalée sur la production mesurée (facteur {_n(an.calage, 2)})" if an.calage else "") + ".\n")
    if ex["jours"] < 360:
        w("> **Période incomplète** : moins d'une année de consommation. Les conclusions sur l'autonomie totale "
          "ne valent que pour les mois couverts ; l'hiver manquant les rendrait fausses.\n")

    w("## 1. Installation existante\n")
    w("| Indicateur | Année médiane | Année la plus défavorable |\n|---|---|---|")
    w(f"| Solaire | {_n(cfg.kwc_actuel, 2, 'kWc')} | |")
    w(f"| Batterie (utile) | {_n(cfg.capacite_utile_kwh, 2, 'kWh')} ({_n(cfg.capacite_kwh, 2, 'kWh')} nominaux) | |")
    w(f"| Production estimée | {_n(ex['production_kwh'], 0, 'kWh')} ({ex['annee_mediane']}) | ({ex['annee_defavorable']}) |")
    w(f"| Autonomie (part de la consommation sans réseau) | {_pct(ex['autonomie'])} | {_pct(ex['autonomie_min'])} |")
    w(f"| Autoconsommation (part du solaire utilisée sur place) | {_pct(ex['autoconsommation'])} | |")
    w(f"| Achats au réseau | {_n(ex['achat_kwh'], 0, 'kWh')} | |")
    w(f"| Revente | {_n(ex['revente_kwh'], 0, 'kWh')} | |")
    w(f"| Cycles de la batterie | {_n(ex['cycles'], 0)} par période | |")
    w(f"| Heures batterie pleine / vide | {_n(ex['heures_pleine'], 0)} h / {_n(ex['heures_vide'], 0)} h | |")
    w(f"| Solaire perdu (onduleur saturé) | {_n(ex['ecretage_kwh'], 0, 'kWh')} | |\n")
    w("Achats au réseau par mois (kWh) :\n")
    w("| " + " | ".join(MOIS) + " |\n|" + "---|" * 12)
    w("| " + " | ".join(_n(x, 0) for x in ex["achat_mensuel"]) + " |\n")
    if ex["heures_conso_sup_onduleur"]:
        w(f"> {ex['heures_conso_sup_onduleur']} h où la consommation horaire dépasse la puissance de l'onduleur "
          f"({_n(cfg.onduleur_kw, 1, 'kW')}) : le réseau reste indispensable ces heures-là, quelle que soit la batterie.\n")
    w(f"Pointe horaire mesurée : {_n(ex['pic_horaire_kw'], 1, 'kW')} (moyenne sur une heure : les pointes plus "
      "courtes, plus fortes, ne sont pas visibles ici).\n")

    w("### Secours (sortie EPS)\n")
    nuit = ex["conso_nuit_kw"]
    phrases = []
    if nuit:
        phrases.append(f"Consommation de nuit médiane : {_n(nuit, 2, 'kW')}. Batterie pleine, la sortie de secours tiendrait "
                       f"environ {_n(cfg.capacite_utile_kwh * cfg.rendement / max(nuit, 0.05), 0, 'h')} la nuit sans solaire "
                       "(si toute la maison est raccordée à la sortie de secours).")
    if cfg.secours_kw:
        p95 = float(an.conso.quantile(0.95))
        phrases.append(f"Puissance de la sortie de secours : {_n(cfg.secours_kw, 1, 'kW')} ; 95 % des heures restent sous "
                       f"{_n(p95, 1, 'kW')} en moyenne horaire.")
    w(" ".join(phrases) + "\n")

    w("## 2. Autonomie totale (aucun achat sur le réseau, même l'année la plus défavorable)\n")
    opts = options_autonomie_totale(an)
    if ex.get("onduleur_requis_kw") or ex.get("batterie_puissance_requise_kw"):
        w("**Inatteignable avec le matériel actuel** : certaines heures, la consommation dépasse la puissance de "
          f"l'onduleur ({_n(cfg.onduleur_kw, 1, 'kW')}) ou de la batterie ({_n(cfg.puissance_batterie_kw, 1, 'kW')}). "
          f"Les combinaisons ci-dessous supposent au moins {_n(max(ex.get('onduleur_requis_kw') or 0, ex.get('batterie_puissance_requise_kw') or 0), 1, 'kW')} "
          "(moyenne horaire ; les démarrages d'appareils demandent davantage).\n")
    if not opts:
        w(f"Aucune combinaison ne l'atteint avec moins de {_n(cfg.batterie_max_recherche_kwh, 0, 'kWh')} de batterie "
          "et la plage de solaire étudiée : l'hiver demande un stockage saisonnier, hors de portée d'une batterie domestique.\n")
        for o in an.saisonnier:
            if o["capacite_nominale_kwh"] is None:
                w(f"- Avec {_n(o['kwc'], 1, 'kWc')} : impossible, même avec une batterie illimitée (production annuelle insuffisante).")
            else:
                w(f"- Avec {_n(o['kwc'], 1, 'kWc')}{'' if o['tient_sur_le_toit'] else ' (au-delà de la place disponible)'} : "
                  f"environ {_n(o['capacite_nominale_kwh'], 0, 'kWh')} de stockage, soit {_n(o['capacite_nominale_kwh'] / cfg.module_kwh, 0)} "
                  f"modules de {_n(cfg.module_kwh, 2, 'kWh')}.")
        if an.saisonnier:
            w("")
    else:
        w("| Solaire | Batterie nécessaire (nominale) | Tient sur le toit | Coût | Limites du matériel |\n|---|---|---|---|---|")
        vus = set()
        for o in sorted(opts, key=lambda o: o["kwc"]):
            cle = round(o["capacite_nominale_kwh"], 0)
            if cle in vus and o is not opts[0]:
                continue
            vus.add(cle)
            w(f"| {_n(o['kwc'], 1, 'kWc')} | {_n(o['capacite_nominale_kwh'], 1, 'kWh')} | {'oui' if o['tient_sur_le_toit'] else 'non'} "
              f"| {_n(o['cout'], 0, '€') if o['cout'] is not None else '—'} | {', '.join(o['limites']) or '—'} |")
        b = opts[0]
        w(f"\n**Combinaison la plus {'économique' if b['cout'] is not None else 'compacte'}** : {_n(b['kwc'], 1, 'kWc')} "
          f"et {_n(b['capacite_nominale_kwh'], 1, 'kWh')} de batterie"
          + (f" ({_n(b['cout'], 0, '€')})" if b["cout"] is not None else "")
          + (f" ; {', '.join(b['limites'])}" if b["limites"] else "") + ".\n")

    w("## 3. Autonomie élevée réaliste\n")
    place = sum((t.kwc_max if t.kwc_max is not None else t.kwc) for t in cfg.toitures)
    w("Le plus petit système (ou le moins coûteux si les coûts sont renseignés) qui tient l'objectif même "
      f"l'année la plus défavorable, en restant sur la place disponible ({_n(place, 1, 'kWc')}) :\n")
    w("| Objectif | Solaire | Batterie (nominale) | Autonomie (défavorable / médiane) | Coût | Limites |\n|---|---|---|---|---|---|")
    for obj in (0.7, 0.8, 0.9, 0.95):
        o = options_objectif(an, obj)
        if o is None:
            w(f"| {obj * 100:.0f} % | inatteignable | | | | |")
            continue
        w(f"| {obj * 100:.0f} % | {_n(o['kwc'], 1, 'kWc')} | {_n(o['capacite_utile_kwh'] / (1 - cfg.plancher_pct / 100), 1, 'kWh')} "
          f"| {_pct(o['autonomie_min'])} / {_pct(o['autonomie_mediane'])} | {_n(o['cout'], 0, '€') if o['cout'] is not None else '—'} "
          f"| {', '.join(o['limites']) or '—'} |")
    w("")

    eco = optimum_economique(an)
    w("## 4. Optimum économique (20 ans, sans inflation ni remplacement)\n")
    if not eco:
        w("Non calculé : renseigner `tarif` (achat, revente) et `couts` (€/kWc, €/kWh) dans le fichier de configuration.\n")
    else:
        w("| Solaire | Batterie (nominale) | Économie par an | Investissement | Bilan sur 20 ans | Retour | Autonomie médiane |\n|---|---|---|---|---|---|---|")
        for o in eco:
            w(f"| {_n(o['kwc'], 1, 'kWc')} | {_n(o['capacite_utile_kwh'] / (1 - cfg.plancher_pct / 100), 1, 'kWh')} "
              f"| {_n(o['economie_an'], 0, '€')} | {_n(o['investissement'], 0, '€')} | {_n(o['bilan'], 0, '€')} "
              f"| {_n(o['retour_ans'], 1, 'ans')} | {_pct(o['autonomie_mediane'])} |")
        w("")

    if an.breos:
        w("## 5. Contre-vérification BREOS (installation existante, année médiane)\n")
        if "erreur" in an.breos:
            w(f"Non réalisée : {an.breos['erreur']}.\n")
        else:
            w(f"Autonomie {_pct(an.breos['autonomie'])} (ce modèle : {_pct(ex['autonomie'])}), achats {_n(an.breos['achat_kwh'], 0, 'kWh')} ; "
              f"santé de la batterie après la période : {_n(an.breos['soh_fin'], 1, '%')} (modèle de vieillissement de BREOS).\n")

    w("## Hypothèses et limites\n")
    w("| Hypothèse | Valeur | Source |\n|---|---|---|")
    w(f"| Production solaire | PVGIS {an.annees[0]}-{an.annees[-1]}, pertes système par toiture | PVGIS 5.3 (Commission européenne) via pvlib |")
    w(f"| Rendement de la batterie | {_pct(cfg.rendement)} dans chaque sens | configuration |")
    w(f"| Puissance batterie / onduleur | {_n(cfg.puissance_batterie_kw, 1, 'kW')} / {_n(cfg.onduleur_kw, 1, 'kW')} | configuration (fiche technique) |")
    w(f"| Plancher de la batterie | {_n(cfg.plancher_pct, 0, '%')} | configuration |")
    w("| Pilotage | Autoconsommation simple, sans charge sur le réseau | modèle |")
    w("| Pas de temps | 1 h : pointes plus courtes non vues | modèle |")
    w("| Vieillissement | Non compté dans le dimensionnement (voir BREOS) | — |")
    w("| Solaire ajouté | Sur les pans les plus productifs, dans la limite de la place indiquée | configuration |\n")
    w("Ce rapport est une aide au dimensionnement, pas une étude d'installateur : la faisabilité (charpente, "
      "raccordement, protections, norme NF C 15-100, accord du gestionnaire de réseau) reste à valider par un professionnel.")
    return "\n".join(L) + "\n"


def grille_csv(an: Analyse) -> pd.DataFrame:
    lignes = []
    for i, p in enumerate(an.grille_pv):
        for j, b in enumerate(an.grille_bat):
            aut = 1 - an.achat[:, i, j] / an.existant["conso_kwh"]
            lignes.append({"kwc": p, "batterie_utile_kwh": b, "tient_sur_le_toit": an.tient[i],
                           "autonomie_mediane": float(np.median(aut)), "autonomie_min": float(aut.min()),
                           "achat_median_kwh": float(np.median(an.achat[:, i, j])),
                           "revente_mediane_kwh": float(np.median(an.revente[:, i, j]))})
    return pd.DataFrame(lignes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Analyse d'une installation solaire + batterie et préconisations.")
    ap.add_argument("config", help="fichier YAML (voir exemple-installation.yaml)")
    ap.add_argument("-o", "--sortie", default="rapport-installation.md")
    ap.add_argument("--breos", action="store_true", help="contre-vérification avec BREOS (pip install breos)")
    a = ap.parse_args(argv)
    cfg = lire_config(a.config)
    prod = None
    if cfg.production_mesuree:
        p = cfg.production_mesuree
        prod = lire_serie_horaire(p["fichier"], p.get("unite", "W"), cfg.fuseau, p.get("colonne_date"), p.get("colonne_valeur"))
    an = analyser(cfg, production_mesuree=prod, avec_breos=a.breos)
    sortie = pathlib.Path(a.sortie)
    sortie.write_text(rapport(an), encoding="utf-8")
    grille_csv(an).to_csv(sortie.with_suffix(".csv"), index=False)
    print(f"Rapport : {sortie}  ·  grille : {sortie.with_suffix('.csv')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
