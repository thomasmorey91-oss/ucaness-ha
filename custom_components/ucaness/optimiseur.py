"""Optimisation de la recharge réseau d'une batterie sous tarif variable (tarif dynamique).

Module sans dépendance à Home Assistant (testable seul). Deux fonctions publiques :

- ``optimiser`` : à partir des prix par créneau (horaire ou quart d'heure), de la consommation
  et de la production solaire prévues, choisit pour chaque créneau entre
    * « auto »   : autoconsommation (le solaire alimente la maison, le surplus charge la batterie,
                   la batterie complète la maison) ;
    * « reseau » : plage de charge du mode arbitrage horaire (le réseau, et le solaire s'il y en a,
                   charge la batterie à la puissance de charge ; la maison est alimentée par le
                   réseau, la batterie est donc aussi « mise de côté » pendant ce créneau).
  Le choix minimise le coût d'achat moins la revente, plus la valeur du stock restant en fin
  d'horizon, sous les contraintes de l'onduleur : 3 plages de charge au plus sur les 24 h à venir
  (une plage qui passe minuit en compte deux), aucune décharge vers le réseau.
  Méthode : programmation dynamique sur le stock (discrétisé, interpolation linéaire), exacte
  pour ce modèle, sans dépendance externe.

- ``plages_depuis_plan`` : traduit un plan de charge produit par un autre moteur (EMHASS par
  exemple) en 3 plages de charge au plus.

Garde-fous : pas de plage si la charge est interdite (batterie sous 0 °C), aucun résultat si une
donnée manque (``DonneesManquantes``), aucune plage si le gain estimé est sous le seuil.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

AUTO = "auto"
RESEAU = "reseau"
MAX_PLAGES = 3
HORIZON_MAX_H = 48
PENALITE_RESERVE_EUR_KWH = 5.0      # coût fictif d'un kWh manquant sous la réserve de secours
POINTS_STOCK_MAX = 150              # finesse de la discrétisation du stock


class DonneesManquantes(ValueError):
    """Une donnée indispensable manque : aucun plan n'est produit (repli sûr)."""


@dataclass(frozen=True)
class Creneau:
    debut: datetime                 # avec fuseau horaire
    fin: datetime
    prix_achat: float               # EUR/kWh TTC
    prix_vente: float               # EUR/kWh
    conso_kwh: float
    solaire_kwh: float

    @property
    def duree_h(self) -> float:
        return (self.fin - self.debut).total_seconds() / 3600


@dataclass(frozen=True)
class Batterie:
    capacite_utile_kwh: float       # capacité au-dessus du plancher
    stock_kwh: float                # énergie utile disponible maintenant
    rendement: float = 0.95         # dans un sens (charge ou décharge)
    puissance_charge_kw: float = 3.0


@dataclass(frozen=True)
class Reserve:
    """Stock minimal souhaité entre deux instants (réserve de secours avant un risque de coupure)."""
    debut: datetime
    fin: datetime
    stock_kwh: float


@dataclass
class Plan:
    actions: list[str]
    stocks: list[float]
    cout_eur: float
    cout_autoconsommation_eur: float
    gain_eur: float
    recharge_reseau_kwh: float
    plages: list[dict[str, str]]
    fenetres: list[tuple[datetime, datetime]]
    valeur_stock_eur_kwh: float
    justification: str
    creneaux: list[Creneau] = field(default_factory=list)
    achats_kwh: list[float] = field(default_factory=list)

    def resume(self, maintenant: datetime | None = None) -> dict[str, Any]:
        """Dictionnaire sérialisable (réponse de l'action Home Assistant)."""
        maintenant = maintenant or (self.creneaux[0].debut if self.creneaux else None)
        en_cours = bool(self.actions) and self.actions[0] == RESEAU and bool(self.plages)
        prochain = next((d for d, _ in self.fenetres if maintenant is None or d >= maintenant), None)
        return {
            "plages": self.plages,
            # Fenêtres datées : le mode se décide sur elles (les plages HHMM de l'onduleur n'ont pas de date).
            "fenetres": [{"debut": d.isoformat(), "fin": f.isoformat()} for d, f in self.fenetres],
            "nombre_plages": len(self.plages),
            "charge_en_cours": en_cours,
            "prochaine_plage": prochain.isoformat() if prochain else None,
            "recharge_reseau_kwh": round(self.recharge_reseau_kwh, 2),
            "gain_estime_eur": round(self.gain_eur, 2),
            "cout_plan_eur": round(self.cout_eur, 2),
            "cout_autoconsommation_eur": round(self.cout_autoconsommation_eur, 2),
            "valeur_stock_eur_kwh": round(self.valeur_stock_eur_kwh, 4),
            "horizon_debut": self.creneaux[0].debut.isoformat() if self.creneaux else None,
            "horizon_fin": self.creneaux[-1].fin.isoformat() if self.creneaux else None,
            "creneaux": len(self.creneaux),
            "prix_min": round(min(c.prix_achat for c in self.creneaux), 4) if self.creneaux else None,
            "prix_max": round(max(c.prix_achat for c in self.creneaux), 4) if self.creneaux else None,
            "justification": self.justification,
            "detail": [
                {
                    "debut": c.debut.isoformat(),
                    "action": a,
                    "prix": round(c.prix_achat, 4),
                    "stock_kwh": round(s, 2),
                    "achat_kwh": round(g, 3),
                }
                for c, a, s, g in zip(self.creneaux, self.actions, self.stocks, self.achats_kwh)
            ],
        }


# --------------------------------------------------------------------------------------------
# Modèle d'un créneau
# --------------------------------------------------------------------------------------------
def simuler_creneau(stock: float, action: str, c: Creneau, bat: Batterie) -> tuple[float, float, float]:
    """Renvoie (stock en fin de créneau, achat réseau kWh, revente kWh)."""
    cap, eta = bat.capacite_utile_kwh, bat.rendement
    conso, pv = max(0.0, c.conso_kwh), max(0.0, c.solaire_kwh)
    if action == RESEAU:
        charge = max(0.0, min(bat.puissance_charge_kw * c.duree_h, (cap - stock) / eta))
        pv_batt = min(pv, charge)
        reste = pv - pv_batt
        achat = (charge - pv_batt) + max(0.0, conso - reste)
        return stock + charge * eta, achat, max(0.0, reste - conso)
    net = pv - conso
    if net >= 0:
        charge = min(net, max(0.0, (cap - stock) / eta))
        return stock + charge * eta, 0.0, net - charge
    fourni = min(-net, stock * eta)
    return stock - fourni / eta, -net - fourni, 0.0


def _cout(achat: float, vente: float, c: Creneau) -> float:
    return achat * c.prix_achat - vente * c.prix_vente


def _penalite(stock: float, c: Creneau, reserves: Sequence[Reserve]) -> float:
    p = 0.0
    for r in reserves:
        if r.debut <= c.debut < r.fin and stock < r.stock_kwh:
            p += (r.stock_kwh - stock) * PENALITE_RESERVE_EUR_KWH
    return p


def _hhmm(t: datetime) -> str:
    return f"{t.hour:02d}{t.minute:02d}"


def _local(t: datetime, fuseau: tzinfo) -> datetime:
    return t.astimezone(fuseau)


def _nouvelle_plage(t: int, creneaux: Sequence[Creneau], fuseau: tzinfo) -> bool:
    """Vrai si une plage en cours doit être coupée au début du créneau t (minuit local)."""
    d = _local(creneaux[t].debut, fuseau)
    return d.hour == 0 and d.minute == 0


# --------------------------------------------------------------------------------------------
# Optimisation
# --------------------------------------------------------------------------------------------
def optimiser(
    creneaux: Sequence[Creneau],
    bat: Batterie,
    *,
    fuseau: tzinfo | None = None,
    max_plages: int = MAX_PLAGES,
    horizon_plages_h: float = 24,
    charge_interdite: bool = False,
    reserves: Sequence[Reserve] = (),
    valeur_stock_eur_kwh: float | None = None,
    seuil_gain_eur: float = 0.02,
) -> Plan:
    if not creneaux:
        raise DonneesManquantes("Aucun créneau de prix exploitable")
    if bat.capacite_utile_kwh <= 0:
        raise DonneesManquantes("Capacité de la batterie non renseignée")
    if not 0 < bat.rendement <= 1:
        raise DonneesManquantes("Rendement de la batterie invalide")
    fuseau = fuseau or creneaux[0].debut.tzinfo or timezone.utc
    cap, eta = bat.capacite_utile_kwh, bat.rendement
    stock0 = min(max(0.0, bat.stock_kwh), cap)
    T = len(creneaux)
    limite = creneaux[0].debut + timedelta(hours=horizon_plages_h)
    compte = [c.debut < limite for c in creneaux]
    coupe = [_nouvelle_plage(t, creneaux, fuseau) for t in range(T)]
    actions_permises = (AUTO,) if (charge_interdite or bat.puissance_charge_kw <= 0) else (AUTO, RESEAU)

    # Valeur d'un kWh resté en batterie en fin d'horizon : ce qu'il coûterait de le recharger au
    # prix le plus bas de l'horizon (on ne charge donc jamais « pour le stock » : neutre au mieux).
    if valeur_stock_eur_kwh is None:
        valeur_stock_eur_kwh = max(0.0, min(c.prix_achat for c in creneaux)) / eta

    pas_q = max(0.05, cap / POINTS_STOCK_MAX)
    n = max(1, int(math.ceil(cap / pas_q)))
    grille = [min(i * pas_q, cap) for i in range(n + 1)]

    # Transitions précalculées : (stock final, coût du créneau) pour chaque point de stock.
    trans: list[dict[str, list[tuple[float, float]]]] = []
    for c in creneaux:
        par_action: dict[str, list[tuple[float, float]]] = {}
        for a in actions_permises:
            lignes = []
            for s in grille:
                s2, achat, vente = simuler_creneau(s, a, c, bat)
                lignes.append((s2, _cout(achat, vente, c) + _penalite(s2, c, reserves)))
            par_action[a] = lignes
        trans.append(par_action)

    def interp(v: list[float], s: float) -> float:
        x = min(max(s / pas_q, 0.0), n)
        i = min(int(x), n - 1)
        f = x - i
        return v[i] * (1 - f) + v[i + 1] * f

    etats = [(k, p) for k in range(max_plages + 1) for p in (0, 1)]
    INF = float("inf")
    terminal = [-valeur_stock_eur_kwh * s for s in grille]
    V: list[dict[tuple[int, int], list[float]]] = [dict() for _ in range(T + 1)]
    V[T] = {e: terminal for e in etats}

    def suivant(t: int, k: int, prec: int, a: str) -> tuple[int, int] | None:
        if a != RESEAU:
            return (k, 0)
        nouvelle = compte[t] and (prec == 0 or coupe[t])
        k2 = k + 1 if nouvelle else k
        return None if k2 > max_plages else (k2, 1)

    for t in range(T - 1, -1, -1):
        for (k, prec) in etats:
            ligne = []
            for i in range(n + 1):
                meilleur = INF
                for a in actions_permises:
                    e2 = suivant(t, k, prec, a)
                    if e2 is None:
                        continue
                    s2, cout = trans[t][a][i]
                    v = cout + interp(V[t + 1][e2], s2)
                    if v < meilleur:
                        meilleur = v
                ligne.append(meilleur)
            V[t][(k, prec)] = ligne

    # Passage avant avec le stock exact.
    actions, stocks, achats = [], [], []
    s, k, prec, cout_total = stock0, 0, 0, 0.0
    for t, c in enumerate(creneaux):
        choix, val_choix, e_choix = AUTO, INF, (k, 0)
        for a in actions_permises:
            e2 = suivant(t, k, prec, a)
            if e2 is None:
                continue
            s2, achat, vente = simuler_creneau(s, a, c, bat)
            v = _cout(achat, vente, c) + _penalite(s2, c, reserves) + interp(V[t + 1][e2], s2)
            if v < val_choix - 1e-9:
                choix, val_choix, e_choix = a, v, e2
        s2, achat, vente = simuler_creneau(s, choix, c, bat)
        cout_total += _cout(achat, vente, c) + _penalite(s2, c, reserves)
        actions.append(choix)
        stocks.append(s2)
        achats.append(achat)
        s, (k, prec) = s2, e_choix
    cout_total -= valeur_stock_eur_kwh * s

    cout_auto, s_auto = 0.0, stock0
    for c in creneaux:
        s2, achat, vente = simuler_creneau(s_auto, AUTO, c, bat)
        cout_auto += _cout(achat, vente, c) + _penalite(s2, c, reserves)
        s_auto = s2
    cout_auto -= valeur_stock_eur_kwh * s_auto
    gain = cout_auto - cout_total

    if RESEAU in actions and gain < seuil_gain_eur and not reserves:
        # Gain négligeable : on reste en autoconsommation (moins d'écritures, même résultat).
        return _plan_auto(creneaux, bat, stock0, cout_auto, valeur_stock_eur_kwh,
                          f"Gain estimé de {gain:.2f} € sous le seuil de {seuil_gain_eur:.2f} € : "
                          "pas de charge réseau, autoconsommation.")

    fenetres = _fenetres(creneaux, actions, limite)
    plages = _plages(fenetres, fuseau)
    recharge = 0.0
    s = stock0
    for c, a in zip(creneaux, actions):
        s2, achat, _ = simuler_creneau(s, a, c, bat)
        if a == RESEAU:
            recharge += max(0.0, (s2 - s) / eta - min(max(0.0, c.solaire_kwh), (s2 - s) / eta))
        s = s2
    plan = Plan(actions, stocks, cout_total, cout_auto, gain, recharge, plages, fenetres,
                valeur_stock_eur_kwh, "", list(creneaux), achats)
    plan.justification = _justifier(plan, bat, fuseau, charge_interdite)
    return plan


def _plan_auto(creneaux, bat, stock0, cout_auto, valeur, texte) -> Plan:
    actions, stocks, achats, s = [], [], [], stock0
    for c in creneaux:
        s, achat, _ = simuler_creneau(s, AUTO, c, bat)
        actions.append(AUTO)
        stocks.append(s)
        achats.append(achat)
    return Plan(actions, stocks, cout_auto, cout_auto, 0.0, 0.0, [], [], valeur, texte,
                list(creneaux), achats)


def _fenetres(creneaux: Sequence[Creneau], actions: Sequence[str], limite: datetime) -> list[tuple[datetime, datetime]]:
    fen: list[tuple[datetime, datetime]] = []
    debut = None
    for c, a in zip(creneaux, actions):
        if a == RESEAU and c.debut < limite:
            if debut is None:
                debut = c.debut
            fin = c.fin
        elif debut is not None:
            fen.append((debut, fin))
            debut = None
    if debut is not None:
        fen.append((debut, fin))
    return fen


def _plages(fenetres: Iterable[tuple[datetime, datetime]], fuseau: tzinfo) -> list[dict[str, str]]:
    """Fenêtres datées -> plages HHMM de l'onduleur (une fenêtre qui passe minuit en donne deux)."""
    plages: list[dict[str, str]] = []
    for d, f in fenetres:
        dl, fl = _local(d, fuseau), _local(f, fuseau)
        # Début arrondi au quart d'heure inférieur : une plage déjà commencée garde la même heure
        # d'un calcul à l'autre (pas de réécriture inutile sur l'onduleur).
        dl = dl.replace(minute=dl.minute - dl.minute % 15, second=0, microsecond=0)
        if fl.date() == dl.date() or (fl.hour == 0 and fl.minute == 0 and fl.date() == dl.date() + timedelta(days=1)):
            fin = "2359" if (fl.hour == 0 and fl.minute == 0) else _hhmm(fl)
            plages.append({"debut": _hhmm(dl), "fin": fin})
        else:
            plages.append({"debut": _hhmm(dl), "fin": "2359"})
            plages.append({"debut": "0000", "fin": _hhmm(fl)})
    return plages


def _justifier(plan: Plan, bat: Batterie, fuseau: tzinfo, charge_interdite: bool) -> str:
    if charge_interdite:
        return "Charge interdite (température de la batterie) : autoconsommation."
    if not plan.plages:
        cr = plan.creneaux
        pmin, pmax = min(c.prix_achat for c in cr), max(c.prix_achat for c in cr)
        if pmax * bat.rendement ** 2 <= pmin:
            return (f"Écart de prix insuffisant ({pmin:.3f} à {pmax:.3f} €/kWh, pertes comprises) : "
                    "pas de charge réseau, autoconsommation.")
        return "Stock et solaire prévus suffisants pour les heures chères : pas de charge réseau, autoconsommation."
    morceaux = []
    for d, f in plan.fenetres:
        prix = [c.prix_achat for c in plan.creneaux if d <= c.debut < f]
        morceaux.append(f"{_local(d, fuseau):%Hh%M}-{_local(f, fuseau):%Hh%M} "
                        f"({sum(prix) / len(prix):.3f} €/kWh en moyenne)")
    cher = max(plan.creneaux, key=lambda c: c.prix_achat)
    txt = (f"Plages de charge : {', '.join(morceaux)}. Charge réseau prévue {plan.recharge_reseau_kwh:.1f} kWh"
           f" ; pendant ces plages la maison est alimentée par le réseau et la batterie est gardée pour"
           f" les heures chères (jusqu'à {cher.prix_achat:.3f} €/kWh à {_local(cher.debut, fuseau):%Hh%M}).")
    return txt + f" Gain estimé {plan.gain_eur:.2f} € face à l'autoconsommation simple."


# --------------------------------------------------------------------------------------------
# Construction des créneaux à partir des données de Home Assistant
# --------------------------------------------------------------------------------------------
def _date(v: Any, fuseau: tzinfo) -> datetime:
    if isinstance(v, datetime):
        d = v
    else:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=fuseau)


def _champ(item: dict, *noms: str) -> Any:
    for n in noms:
        if n in item and item[n] not in (None, "", "unknown", "unavailable"):
            return item[n]
    return None


def _series(items: Iterable[dict], cles_date: tuple[str, ...], cles_val: tuple[str, ...], fuseau: tzinfo,
            pas_defaut_h: float = 1.0) -> list[tuple[datetime, datetime, float]]:
    """Liste triée de (début, fin, valeur). La fin vaut le début suivant, ou début + pas."""
    brut = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        d, v = _champ(it, *cles_date), _champ(it, *cles_val)
        if d is None or v is None:
            continue
        try:
            fin = _champ(it, "fin", "end")
            brut.append((_date(d, fuseau), _date(fin, fuseau) if fin is not None else None, float(v)))
        except (TypeError, ValueError):
            continue
    brut.sort(key=lambda x: x[0])
    sortie = []
    for i, (d, f, v) in enumerate(brut):
        if f is None:
            if i + 1 < len(brut):
                f = brut[i + 1][0]
            elif i > 0:
                f = d + (d - brut[i - 1][0])
            else:
                f = d + timedelta(hours=pas_defaut_h)
            if f - d > timedelta(hours=2):        # trou dans la série : on borne à 1 h
                f = d + timedelta(hours=pas_defaut_h)
        sortie.append((d, f, v))
    return sortie


def _energie(serie: list[tuple[datetime, datetime, float]], d: datetime, f: datetime, puissance: bool) -> float | None:
    """Énergie (kWh) de la série sur [d, f[. puissance=True : valeurs en kW moyens."""
    total, couvert = 0.0, 0.0
    for sd, sf, v in serie:
        recouvre = (min(f, sf) - max(d, sd)).total_seconds()
        if recouvre <= 0:
            continue
        duree = (sf - sd).total_seconds()
        total += v * recouvre / 3600 if puissance else v * recouvre / duree
        couvert += recouvre
    if couvert < (f - d).total_seconds() * 0.5:
        return None
    return total


def construire_creneaux(
    prix: Iterable[dict],
    conso: Any,
    solaire: Iterable[dict],
    *,
    maintenant: datetime,
    fuseau: tzinfo | str | None = None,
    prix_vente: float = 0.0,
    marge: float = 0.0,
    horizon_max_h: float = HORIZON_MAX_H,
) -> list[Creneau]:
    """Assemble les créneaux de l'horizon.

    - prix : [{debut|start|time, prix|price|value, fin|end (option)}] en EUR/kWh TTC ;
    - conso : 24 valeurs (kWh par heure de la journée, même profil chaque jour) ou
      [{debut, kwh}] heure par heure ;
    - solaire : [{debut|period_start, kwh}] (énergie de la période) ou
      [{period_start, pv_estimate}] (Solcast : puissance moyenne en kW sur la période) ;
    - l'horizon s'arrête au dernier prix connu et à la dernière prévision solaire.
    """
    if isinstance(fuseau, str):
        fuseau = ZoneInfo(fuseau)
    fuseau = fuseau or maintenant.tzinfo or timezone.utc
    maintenant = _date(maintenant, fuseau)

    sp = _series(prix, ("debut", "start", "time", "date"), ("prix", "price", "value"), fuseau)
    if not sp:
        raise DonneesManquantes("Prix indisponibles")
    sol_items = list(solaire or [])
    en_puissance = any(isinstance(i, dict) and "pv_estimate" in i for i in sol_items)
    ss = _series(sol_items, ("debut", "period_start", "start", "date"), ("kwh", "pv_estimate", "valeur"), fuseau)
    if not ss:
        raise DonneesManquantes("Prévision solaire indisponible")
    fin_horizon = min(sp[-1][1], ss[-1][1], maintenant + timedelta(hours=horizon_max_h))

    profil: list[float] | None = None
    sc: list[tuple[datetime, datetime, float]] = []
    if isinstance(conso, (list, tuple)) and len(conso) == 24 and all(isinstance(x, (int, float)) for x in conso):
        profil = [max(0.0, float(x)) for x in conso]
    else:
        sc = _series(conso or [], ("debut", "start", "date"), ("kwh", "valeur", "value"), fuseau)
        if not sc:
            raise DonneesManquantes("Consommation prévue indisponible")

    def conso_sur(d: datetime, f: datetime) -> float | None:
        if profil is not None:
            total, t = 0.0, d
            while t < f:
                h_fin = (_local(t, fuseau).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
                fin = min(f, h_fin)
                total += profil[_local(t, fuseau).hour] * (fin - t).total_seconds() / 3600
                t = fin
            return total
        return _energie(sc, d, f, puissance=False)

    creneaux = []
    for d, f, p in sp:
        if f <= maintenant or d >= fin_horizon:
            continue
        d, f = max(d, maintenant), min(f, fin_horizon)
        if (f - d).total_seconds() < 60:
            continue
        c_kwh = conso_sur(d, f)
        if c_kwh is None:
            raise DonneesManquantes(f"Consommation inconnue pour {d.isoformat()}")
        pv = _energie(ss, d, f, puissance=en_puissance)
        creneaux.append(Creneau(d, f, p, prix_vente, c_kwh * (1 + marge), pv or 0.0))
    if not creneaux:
        raise DonneesManquantes("Aucun créneau à venir (prix ou prévision solaire trop anciens)")
    return creneaux


# --------------------------------------------------------------------------------------------
# Plan d'un moteur externe (EMHASS) -> plages
# --------------------------------------------------------------------------------------------
def charge_reseau_emhass_kw(p_batt_w: float | None, p_grid_w: float | None) -> float:
    """Puissance de charge venant du réseau selon EMHASS (P_batt < 0 = charge, P_grid > 0 = soutirage)."""
    if p_batt_w is None or p_batt_w >= 0:
        return 0.0
    if p_grid_w is None:
        return -p_batt_w / 1000
    return max(0.0, min(-p_batt_w, p_grid_w)) / 1000


def plages_depuis_plan(
    plan: Iterable[dict],
    *,
    maintenant: datetime,
    fuseau: tzinfo | str | None = None,
    seuil_kw: float = 0.2,
    max_plages: int = MAX_PLAGES,
    horizon_h: float = 24,
) -> dict[str, Any]:
    """Créneaux {debut, charge_reseau_kw} (ou {date, p_batt, p_grid} d'EMHASS, en W) -> plages.

    Les créneaux de charge contigus forment une fenêtre ; s'il y en a trop, on garde celles qui
    portent le plus d'énergie (une fenêtre qui passe minuit compte pour deux plages).
    """
    if isinstance(fuseau, str):
        fuseau = ZoneInfo(fuseau)
    fuseau = fuseau or maintenant.tzinfo or timezone.utc
    maintenant = _date(maintenant, fuseau)
    items = []
    for it in plan or []:
        if not isinstance(it, dict):
            continue
        if "charge_reseau_kw" in it:
            kw = float(it["charge_reseau_kw"] or 0)
        else:
            def f(*noms):
                v = _champ(it, *noms)
                return float(v) if v is not None else None
            kw = charge_reseau_emhass_kw(f("p_batt", "p_batt_forecast"), f("p_grid", "p_grid_forecast"))
        d = _champ(it, "debut", "date", "start")
        if d is None:
            continue
        items.append({"debut": d, "valeur": kw, "fin": _champ(it, "fin", "end")})
    serie = _series(items, ("debut",), ("valeur",), fuseau)
    limite = maintenant + timedelta(hours=horizon_h)
    fen, debut, energie, fin = [], None, 0.0, None
    for d, f, kw in serie:
        actif = kw >= seuil_kw and f > maintenant and d < limite
        if actif:
            d = max(d, maintenant)
            if debut is None or d > fin:
                if debut is not None:
                    fen.append((debut, fin, energie))
                debut, energie = d, 0.0
            fin = f
            energie += kw * (f - d).total_seconds() / 3600
        elif debut is not None:
            fen.append((debut, fin, energie))
            debut = None
    if debut is not None:
        fen.append((debut, fin, energie))

    def cout(w):
        return len(_plages([(w[0], w[1])], fuseau))

    gardees, utilisees = [], 0
    for w in sorted(fen, key=lambda w: -w[2]):
        if utilisees + cout(w) <= max_plages:
            gardees.append(w)
            utilisees += cout(w)
    gardees.sort(key=lambda w: w[0])
    ecartee = sum(w[2] for w in fen) - sum(w[2] for w in gardees)
    return {
        "plages": _plages([(w[0], w[1]) for w in gardees], fuseau),
        "fenetres": [{"debut": w[0].isoformat(), "fin": w[1].isoformat()} for w in gardees],
        "charge_reseau_kwh": round(sum(w[2] for w in gardees), 2),
        "charge_ecartee_kwh": round(ecartee, 2),
        "fenetres": len(fen),
        "charge_en_cours": any(w[0] <= maintenant < w[1] for w in gardees),
        "prochaine_plage": next((w[0].isoformat() for w in gardees if w[0] >= maintenant), None),
    }
