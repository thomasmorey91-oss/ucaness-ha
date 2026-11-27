"""Véhicule électrique de la maison : catalogue, état de charge estimé, plan de recharge.

Calcul seul (« à blanc ») : rien n'est envoyé à la borne ni à l'onduleur. Le plan dit quand
recharger la voiture au moindre coût avant l'heure de départ, en commençant par le surplus solaire
puis les heures les moins chères, et signale les heures où la batterie de la maison devrait être
tenue (pour qu'elle ne se vide pas dans la voiture).

Catalogue : extrait d'OpenEV Data (CDLA-Permissive-2.0), construit par
tools/vehicules/construire_catalogue.py dans donnees/vehicules.json. Les valeurs proposées
(capacité, puissance de charge) sont à confirmer par l'utilisateur.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Iterable

CATALOGUE = Path(__file__).parent / "donnees" / "vehicules.json"
MEILLEURES_VENTES = Path(__file__).parent / "donnees" / "meilleures_ventes.json"
GABARITS = ("citadine", "compacte", "berline", "suv", "grand_suv", "utilitaire")
RENDEMENT_CHARGE = 0.90         # pertes entre la prise et la batterie de la voiture (charge AC)


# ------------------------------------------------------------------ catalogue


@dataclass(frozen=True)
class Vehicule:
    id: str
    marque: str
    modele: str
    annee: int
    version: str
    gabarit: str
    capacite_kwh: float
    ac_kw: float
    phases: int
    conso_kwh_100km: float | None = None

    @property
    def libelle(self) -> str:
        nom = " ".join(x for x in (self.marque, self.modele, self.version) if x)
        return f"{nom} ({self.annee})"


@lru_cache(maxsize=1)
def charger_catalogue(chemin: Path = CATALOGUE) -> tuple[Vehicule, ...]:
    """Lecture du fichier (à appeler hors de la boucle d'événements de Home Assistant)."""
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    return tuple(Vehicule(**v) for v in donnees["vehicules"])


def marques(catalogue: Iterable[Vehicule]) -> list[str]:
    return sorted({v.marque for v in catalogue}, key=str.casefold)


def de_la_marque(catalogue: Iterable[Vehicule], marque: str) -> list[Vehicule]:
    return sorted((v for v in catalogue if v.marque == marque),
                  key=lambda v: (v.modele.casefold(), -v.annee, v.version.casefold()))


def par_id(catalogue: Iterable[Vehicule], ident: str) -> Vehicule | None:
    return next((v for v in catalogue if v.id == ident), None)


@dataclass(frozen=True)
class MeilleureVente:
    """Modèle parmi les plus vendus du pays. `versions` : ses fiches du catalogue (vide : hors catalogue)."""
    nom: str
    gabarit: str
    versions: tuple[Vehicule, ...]


@lru_cache(maxsize=1)
def _ventes(chemin: Path = MEILLEURES_VENTES) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8"))["pays"]


def meilleures_ventes(catalogue: Iterable[Vehicule], pays: str | None) -> list[MeilleureVente]:
    """Modèles les plus vendus du pays (FR, DE, IT, ES, PT), dans l'ordre ; liste vide pour un autre pays."""
    cat = tuple(catalogue)
    out = []
    for m in (_ventes().get((pays or "").upper()) or {}).get("modeles", []):
        versions = tuple(v for v in de_la_marque(cat, m["marque"]) if v.modele == m["modele"]) if m["marque"] else ()
        out.append(MeilleureVente(m["nom"], m["gabarit"], versions))
    return out


def source_ventes(pays: str | None) -> str | None:
    p = _ventes().get((pays or "").upper())
    return f"{p['source']}, {p['periode']}" if p else None


# ------------------------------------------------------------------ énergie et état de charge


def puissance_recharge_kw(ac_vehicule_kw: float, puissance_borne_kw: float) -> float:
    """La recharge va à la vitesse du plus lent : la borne ou le chargeur de la voiture."""
    if ac_vehicule_kw <= 0 or puissance_borne_kw <= 0:
        raise ValueError("puissance nulle")
    return min(ac_vehicule_kw, puissance_borne_kw)


def energie_a_prendre_kwh(capacite_kwh: float, soc_actuel: float, soc_cible: float,
                          rendement: float = RENDEMENT_CHARGE) -> float:
    """Énergie prise à la prise (pertes de charge comprises) pour passer de soc_actuel à soc_cible."""
    if not (0 <= soc_actuel <= 100 and 0 <= soc_cible <= 100):
        raise ValueError("état de charge hors de 0-100 %")
    manque = capacite_kwh * max(0.0, soc_cible - soc_actuel) / 100
    return manque / rendement


def estimer_soc(soc_au_branchement: float, km_parcourus: float, conso_kwh_100km: float,
                capacite_kwh: float) -> float:
    """État de charge estimé quand la voiture ne le transmet pas : branchement − km × consommation."""
    perdu = km_parcourus * conso_kwh_100km / 100
    return max(0.0, min(100.0, soc_au_branchement - perdu / capacite_kwh * 100))


# ------------------------------------------------------------------ prix d'une heure


def _dans(t: time, debut: time, fin: time) -> bool:
    return debut <= t < fin if debut < fin else (t >= debut or t < fin)


def prix_heure(moment: datetime, *, prix_hp: float, prix_hc: float, hc_debut: time, hc_fin: time,
               jours_non_ouvres_hc: bool, type_tarif_base: bool = False) -> tuple[float, bool]:
    """(prix du kWh, heure creuse ?) à un instant donné. Samedi et dimanche comptent comme non ouvrés
    pour les jours à venir (les jours fériés futurs ne sont pas connus ici)."""
    if type_tarif_base:
        return prix_hp, False
    creuse = _dans(moment.time(), hc_debut, hc_fin) or (jours_non_ouvres_hc and moment.weekday() >= 5)
    return (prix_hc if creuse else prix_hp), creuse


# ------------------------------------------------------------------ plan de recharge


@dataclass(frozen=True)
class Creneau:
    debut: datetime
    fin: datetime
    prix_reseau: float             # €/kWh
    heure_creuse: bool
    surplus_solaire_kw: float = 0.0  # surplus prévu (production − consommation de la maison)


@dataclass
class Plage:
    debut: datetime
    fin: datetime
    energie_kwh: float
    solaire_kwh: float
    cout_eur: float
    tenir_batterie_maison: bool     # la batterie de la maison ne doit pas alimenter la voiture

    def en_dict(self) -> dict:
        d = asdict(self)
        d["debut"], d["fin"] = self.debut.isoformat(), self.fin.isoformat()
        d["energie_kwh"], d["solaire_kwh"], d["cout_eur"] = (round(self.energie_kwh, 2), round(self.solaire_kwh, 2),
                                                           round(self.cout_eur, 2))
        return d


@dataclass
class PlanRecharge:
    energie_kwh: float
    puissance_kw: float
    plages: list[Plage] = field(default_factory=list)
    manque_kwh: float = 0.0

    @property
    def cout_eur(self) -> float:
        return sum(p.cout_eur for p in self.plages)

    @property
    def solaire_kwh(self) -> float:
        return sum(p.solaire_kwh for p in self.plages)

    def en_dict(self) -> dict:
        return {
            "energie_kwh": round(self.energie_kwh, 2),
            "puissance_kw": self.puissance_kw,
            "cout_estime_eur": round(self.cout_eur, 2),
            "part_solaire_pct": round(100 * self.solaire_kwh / self.energie_kwh) if self.energie_kwh else 0,
            "complet": self.manque_kwh < 0.01,
            "manque_kwh": round(self.manque_kwh, 2),
            "plages": [p.en_dict() for p in self.plages],
        }


def _cout_kwh(c: Creneau, puissance_kw: float, prix_solaire: float) -> float:
    solaire = min(c.surplus_solaire_kw, puissance_kw)
    return (solaire * prix_solaire + (puissance_kw - solaire) * c.prix_reseau) / puissance_kw


def plan_recharge(energie_kwh: float, puissance_kw: float, creneaux: Iterable[Creneau], depart: datetime,
                  prix_solaire: float) -> PlanRecharge:
    """Choisit les créneaux les moins chers avant le départ jusqu'à couvrir l'énergie demandée.

    Coût d'un créneau : surplus solaire valorisé à `prix_solaire` (prix de revente perdu), le reste au
    prix du réseau. À coût égal, le créneau le plus tôt passe d'abord. Les créneaux retenus voisins
    sont regroupés en plages.
    """
    plan = PlanRecharge(energie_kwh=energie_kwh, puissance_kw=puissance_kw)
    utiles = [c for c in creneaux if c.fin <= depart and c.fin > c.debut]
    reste = energie_kwh
    choisis: list[tuple[Creneau, float, float, float]] = []
    for c in sorted(utiles, key=lambda c: (_cout_kwh(c, puissance_kw, prix_solaire), c.debut)):
        if reste <= 1e-9:
            break
        heures = (c.fin - c.debut).total_seconds() / 3600
        e = min(reste, puissance_kw * heures)
        part_solaire = min(c.surplus_solaire_kw, puissance_kw) / puissance_kw
        sol = e * part_solaire
        cout = sol * prix_solaire + (e - sol) * c.prix_reseau
        choisis.append((c, e, sol, cout))
        reste -= e
    plan.manque_kwh = max(0.0, reste)
    for c, e, sol, cout in sorted(choisis, key=lambda x: x[0].debut):
        tenir = sol < e - 1e-9            # une partie vient du réseau : la batterie de la maison ne doit pas fournir
        duree = timedelta(hours=e / puissance_kw)
        fin = min(c.fin, c.debut + duree)
        der = plan.plages[-1] if plan.plages else None
        if der and der.fin == c.debut and der.tenir_batterie_maison == tenir:
            der.fin, der.energie_kwh, der.solaire_kwh, der.cout_eur = fin, der.energie_kwh + e, der.solaire_kwh + sol, der.cout_eur + cout
        else:
            plan.plages.append(Plage(c.debut, fin, e, sol, cout, tenir))
    return plan


def creneaux_horaires(maintenant: datetime, depart: datetime, prix_de: callable,
                      surplus_de: callable) -> list[Creneau]:
    """Créneaux d'une heure (le premier commence maintenant) jusqu'au départ.

    prix_de(moment) -> (prix, heure_creuse) ; surplus_de(moment) -> kW de surplus solaire prévu."""
    out, debut = [], maintenant
    while debut < depart:
        fin = min(depart, (debut.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)))
        prix, creuse = prix_de(debut)
        out.append(Creneau(debut, fin, prix, creuse, max(0.0, surplus_de(debut))))
        debut = fin
    return out


__all__ = [
    "CATALOGUE", "GABARITS", "MEILLEURES_VENTES", "Creneau", "MeilleureVente", "Plage", "PlanRecharge", "Vehicule", "charger_catalogue", "creneaux_horaires",
    "de_la_marque", "energie_a_prendre_kwh", "estimer_soc", "marques", "meilleures_ventes", "par_id", "source_ventes", "plan_recharge", "prix_heure",
    "puissance_recharge_kw",
]
