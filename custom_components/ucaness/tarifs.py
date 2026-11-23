"""Évaluer une offre d'électricité sur la consommation réelle de la maison (calcul seul).

Python pur, sans Home Assistant. À partir du soutirage mesuré heure par heure (l'énergie prise
sur le réseau, batterie déjà déduite) et de la grille d'une offre, `evaluer()` donne le coût
annuel estimé ; `classer()` range plusieurs offres par coût ; `analyser_puissance()` dit si la
puissance souscrite convient.

Ce que ce calcul fait :
- formules « base » (prix unique) et « hphc » (heures pleines / heures creuses, plages au choix,
  week-end et jours fériés entièrement en heures creuses si l'offre le prévoit) ;
- abonnement selon la puissance souscrite ; tous les prix sont TTC.

- recharge de nuit (si la batterie est décrite et que la maison ne recharge pas déjà la nuit) :
  pour une offre à heures creuses, estimation de ce que la batterie déplacerait des heures
  pleines vers les heures creuses, jour par jour, dans la limite de sa capacité utile et
  seulement si l'écart de prix le justifie (rendement² × HP > HC). C'est une estimation HAUTE :
  elle suppose la batterie vide en début d'heures creuses et ne retire pas la place laissée au
  solaire du lendemain. Le coût « tel que mesuré » reste donné à côté.

Ce qu'il ne fait pas (dit dans le résultat, jamais masqué) :
- il ne rejoue pas le pilotage heure par heure : si la maison recharge déjà la nuit, le soutirage
  mesuré porte la marque des heures creuses du contrat actuel ;
- il ne couvre ni Tempo (couleur du jour) ni les prix dynamiques ;
- il n'invente pas une année : avec peu de jours de mesure, l'estimation annuelle est une simple
  règle de trois, signalée comme telle (les saisons ne sont pas représentées).

Une donnée absente ne donne jamais un prix : l'offre est écartée, avec la raison.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterable

BASE, HPHC = "base", "hphc"
FORMULES = (BASE, HPHC)

# Fiabilité de l'estimation annuelle, selon le nombre de jours mesurés.
FIABLE, INDICATIF, INSUFFISANT = "fiable", "indicatif", "insuffisant"
JOURS_FIABLE, JOURS_INDICATIF = 330, 30
JOURS_GRILLE_PERIMEE = 30

# Puissances souscrites usuelles pour un particulier (kVA).
PALIERS_KVA = (3, 6, 9, 12, 15, 18, 24, 30, 36)


@dataclass(frozen=True)
class Batterie:
    capacite_utile_kwh: float      # capacité au-dessus du plancher
    rendement: float = 0.95        # dans un sens (charge ou décharge), entre 0 et 1


class OffreInvalide(ValueError):
    """La grille de l'offre ne permet pas de calculer un prix."""


@dataclass(frozen=True)
class Offre:
    nom: str
    formule: str                                   # « base » ou « hphc »
    abonnement_eur_an: dict[int, float]            # puissance souscrite (kVA) -> abonnement annuel TTC
    prix_kwh: dict[str, float]                     # base : {"base": p} ; hphc : {"hp": p, "hc": p} (TTC)
    fournisseur: str = ""
    plages_hc: tuple[tuple[str, str], ...] = ()    # (("22:30", "06:30"),) ; une plage peut passer minuit
    weekend_hc: bool = False                       # week-end et jours fériés entièrement en heures creuses
    source: str = ""                               # où le prix a été lu (adresse de la grille tarifaire)
    date_prix: date | None = None                  # date à laquelle le prix a été relevé


@dataclass
class Evaluation:
    offre: Offre
    puissance_kva: int
    jours_mesures: float
    kwh_mesures: float
    kwh_hc_mesures: float
    cout_energie_mesure_eur: float
    cout_annuel_eur: float                         # abonnement + énergie ramenée à 365 jours, soutirage tel que mesuré
    fiabilite: str
    remarques: list[str] = field(default_factory=list)
    gain_recharge_nuit_eur_an: float = 0.0         # estimation haute de ce que la recharge de nuit ferait gagner

    @property
    def cout_retenu_eur(self) -> float:
        """Coût qui sert au classement : avec la recharge de nuit quand elle a pu être estimée."""
        return self.cout_annuel_eur - self.gain_recharge_nuit_eur_an

    def resume(self) -> dict[str, Any]:
        o = self.offre
        return {
            "nom": o.nom, "fournisseur": o.fournisseur, "formule": o.formule,
            "puissance_kva": self.puissance_kva,
            "cout_annuel_eur": round(self.cout_retenu_eur, 2),
            "cout_annuel_tel_que_mesure_eur": round(self.cout_annuel_eur, 2),
            "gain_recharge_de_nuit_eur_an": round(self.gain_recharge_nuit_eur_an, 2),
            "abonnement_eur_an": round(o.abonnement_eur_an[self.puissance_kva], 2),
            "energie_eur_an": round(self.cout_annuel_eur - o.abonnement_eur_an[self.puissance_kva], 2),
            "part_heures_creuses_pct": round(100 * self.kwh_hc_mesures / self.kwh_mesures, 1) if self.kwh_mesures else None,
            "jours_mesures": round(self.jours_mesures, 1),
            "fiabilite": self.fiabilite,
            "source": o.source, "date_prix": o.date_prix.isoformat() if o.date_prix else None,
            "remarques": self.remarques,
        }


def _minutes(hhmm: str) -> int:
    h, m = (int(x) for x in str(hhmm).split(":")[:2])
    if not (0 <= h < 24 and 0 <= m < 60):
        raise OffreInvalide(f"heure illisible : {hhmm}")
    return h * 60 + m


def _recouvrement(debut_min: int, fin_min: int, plage: tuple[int, int]) -> int:
    """Minutes communes entre [debut, fin[ (dans la journée) et une plage qui peut passer minuit."""
    a, b = plage
    morceaux = [(a, b)] if a < b else [(a, 1440), (0, b)]
    return sum(max(0, min(fin_min, y) - max(debut_min, x)) for x, y in morceaux)


def part_heures_creuses(debut: datetime, offre: Offre, jours_non_ouvres: Iterable[date] = ()) -> float:
    """Part de l'heure qui commence à `debut` passée en heures creuses (0 à 1)."""
    if offre.formule != HPHC:
        return 0.0
    if offre.weekend_hc and (debut.weekday() >= 5 or debut.date() in set(jours_non_ouvres)):
        return 1.0
    d = debut.hour * 60 + debut.minute
    plages = [(_minutes(a), _minutes(b)) for a, b in offre.plages_hc]
    minutes = sum(_recouvrement(d, min(d + 60, 1440), p) for p in plages)
    if d + 60 > 1440:                                   # heure à cheval sur minuit
        minutes += sum(_recouvrement(0, d + 60 - 1440, p) for p in plages)
    return min(1.0, minutes / 60)


def verifier(offre: Offre, puissance_kva: int) -> None:
    """OffreInvalide si la grille ne permet pas de calculer un prix pour cette puissance."""
    if offre.formule not in FORMULES:
        raise OffreInvalide(f"formule non prise en charge : {offre.formule}")
    if puissance_kva not in offre.abonnement_eur_an:
        raise OffreInvalide(f"pas d'abonnement connu pour {puissance_kva} kVA")
    if not offre.abonnement_eur_an[puissance_kva] >= 0:
        raise OffreInvalide("abonnement illisible")
    attendus = ("base",) if offre.formule == BASE else ("hp", "hc")
    for periode in attendus:
        prix = offre.prix_kwh.get(periode)
        if prix is None or not prix > 0:
            raise OffreInvalide(f"prix « {periode} » manquant")
    if offre.formule == HPHC and not offre.plages_hc and not offre.weekend_hc:
        raise OffreInvalide("heures creuses non précisées")
    for a, b in offre.plages_hc:
        _minutes(a), _minutes(b)


def fiabilite(jours: float) -> str:
    return FIABLE if jours >= JOURS_FIABLE else INDICATIF if jours >= JOURS_INDICATIF else INSUFFISANT


def evaluer(
    offre: Offre,
    soutirage: Iterable[tuple[datetime, float]],
    puissance_kva: int,
    *,
    jours_non_ouvres: Iterable[date] = (),
    aujourdhui: date | None = None,
    batterie: Batterie | None = None,
    recharge_deja_active: bool = False,
) -> Evaluation:
    """Coût annuel estimé de l'offre pour ce soutirage horaire [(début de l'heure, kWh), ...].

    Le soutirage est celui mesuré (batterie déduite). Les heures sans mesure ne sont pas inventées :
    le nombre de jours couverts est déduit des heures présentes."""
    verifier(offre, puissance_kva)
    non_ouvres = set(jours_non_ouvres)
    heures, kwh_total, kwh_hc, cout = 0, 0.0, 0.0, 0.0
    hp_par_jour: dict[date, float] = {}
    for debut, kwh in soutirage:
        if kwh is None or kwh != kwh or kwh < 0:
            continue                                    # mesure absente ou incohérente : heure ignorée
        heures += 1
        kwh_total += kwh
        if offre.formule == BASE:
            cout += kwh * offre.prix_kwh["base"]
        else:
            part = part_heures_creuses(debut, offre, non_ouvres)
            kwh_hc += kwh * part
            cout += kwh * (part * offre.prix_kwh["hc"] + (1 - part) * offre.prix_kwh["hp"])
            hp_par_jour[debut.date()] = hp_par_jour.get(debut.date(), 0.0) + kwh * (1 - part)
    if heures == 0:
        raise OffreInvalide("aucune mesure de soutirage")
    jours = heures / 24
    niveau = fiabilite(jours)
    remarques = []
    if niveau == INSUFFISANT:
        remarques.append(f"Seulement {jours:.0f} jour(s) de mesure : estimation annuelle par simple règle de trois, à ne pas suivre telle quelle.")
    elif niveau == INDICATIF:
        remarques.append(f"{jours:.0f} jours de mesure : les saisons ne sont pas toutes représentées.")
    if offre.date_prix is None:
        remarques.append("Date du prix inconnue : grille à vérifier chez le fournisseur.")
    elif aujourdhui is not None and (aujourdhui - offre.date_prix) > timedelta(days=JOURS_GRILLE_PERIMEE):
        remarques.append(f"Prix relevé le {offre.date_prix.isoformat()} : à revérifier.")
    if not offre.source:
        remarques.append("Source du prix non indiquée.")
    # Recharge de nuit : énergie des heures pleines que la batterie pourrait fournir chaque jour,
    # rechargée en heures creuses (pertes comptées dans les deux sens).
    gain_mesure = 0.0
    if offre.formule == HPHC and batterie is not None and not recharge_deja_active:
        r = batterie.rendement
        if not (0 < r <= 1) or not batterie.capacite_utile_kwh > 0:
            remarques.append("Batterie mal décrite : recharge de nuit non estimée.")
        elif r * r * offre.prix_kwh["hp"] > offre.prix_kwh["hc"]:
            deplace = sum(min(hp, batterie.capacite_utile_kwh * r) for hp in hp_par_jour.values())
            gain_mesure = deplace * (offre.prix_kwh["hp"] - offre.prix_kwh["hc"] / (r * r))
            remarques.append("Recharge de nuit comprise : estimation haute (batterie supposée vide en début d'heures creuses).")
        else:
            remarques.append("Écart de prix trop faible pour que la recharge de nuit soit rentable avec cette offre.")
    return Evaluation(
        offre=offre, puissance_kva=puissance_kva, jours_mesures=jours, kwh_mesures=kwh_total,
        kwh_hc_mesures=kwh_hc, cout_energie_mesure_eur=cout,
        cout_annuel_eur=offre.abonnement_eur_an[puissance_kva] + cout * 365 / jours,
        fiabilite=niveau, remarques=remarques, gain_recharge_nuit_eur_an=gain_mesure * 365 / jours,
    )


def classer(
    offres: Iterable[Offre],
    soutirage: Iterable[tuple[datetime, float]],
    puissance_kva: int,
    *,
    contrat_actuel: Offre | None = None,
    jours_non_ouvres: Iterable[date] = (),
    aujourdhui: date | None = None,
    batterie: Batterie | None = None,
    recharge_deja_active: bool = False,
) -> dict[str, Any]:
    """Meilleure offre pour cette maison : offres rangées par coût annuel estimé (seul critère),
    écart avec le contrat actuel."""
    mesures = list(soutirage)
    communs = {"jours_non_ouvres": list(jours_non_ouvres), "aujourdhui": aujourdhui,
               "batterie": batterie, "recharge_deja_active": recharge_deja_active}
    evaluees, ecartees = [], []
    for offre in offres:
        try:
            evaluees.append(evaluer(offre, mesures, puissance_kva, **communs))
        except OffreInvalide as err:
            ecartees.append({"nom": offre.nom, "fournisseur": offre.fournisseur, "raison": str(err)})
    evaluees.sort(key=lambda e: e.cout_retenu_eur)
    actuel = None
    if contrat_actuel is not None:
        try:
            actuel = evaluer(contrat_actuel, mesures, puissance_kva, **communs)
        except OffreInvalide as err:
            ecartees.append({"nom": contrat_actuel.nom, "fournisseur": contrat_actuel.fournisseur, "raison": f"contrat actuel : {err}"})
    classement = []
    for rang, e in enumerate(evaluees, start=1):
        ligne = {"rang": rang, **e.resume()}
        if actuel is not None:
            ligne["ecart_avec_contrat_actuel_eur_an"] = round(e.cout_retenu_eur - actuel.cout_retenu_eur, 2)
        classement.append(ligne)
    meilleure = classement[0] if classement else None
    # On ne propose de changer que si l'offre fait mieux que le contrat actuel.
    if meilleure is not None and actuel is not None and meilleure["ecart_avec_contrat_actuel_eur_an"] >= 0:
        conseil = "garder_le_contrat_actuel"
    elif meilleure is None:
        conseil = "aucune_offre_evaluee"
    elif actuel is not None and meilleure["formule"] != actuel.offre.formule:
        conseil = "changer_de_formule"
    else:
        conseil = "changer_d_offre" if actuel is not None else "meilleure_offre_evaluee"
    return {
        "critere": "coût annuel estimé pour cette maison (abonnement + énergie), TTC",
        "conseil": conseil,
        "meilleure_offre": meilleure,
        "contrat_actuel": actuel.resume() if actuel else None,
        "classement": classement,
        "offres_ecartees": ecartees,
        "fiabilite": evaluees[0].fiabilite if evaluees else (actuel.fiabilite if actuel else None),
        "limites": [
            "Recharge de nuit estimée simplement, jour par jour : le pilotage n'est pas rejoué heure par heure.",
            "Tempo et prix dynamiques non pris en charge.",
            "Estimation à vérifier sur la grille du fournisseur avant toute souscription.",
        ],
    }


def analyser_puissance(
    puissances_max_kva: Iterable[float],
    souscrite_kva: int,
    *,
    marge: float = 0.10,
    mesure_fine: bool = False,
) -> dict[str, Any]:
    """La puissance souscrite convient-elle ? À partir des puissances maximales relevées (une par
    jour, en kVA).

    `mesure_fine` : vrai si les maximums viennent du compteur lui-même (prise TIC). Sinon (puissance
    estimée, relevée toutes les minutes), les pointes brèves échappent à la mesure : le conseil de
    baisse n'est jamais donné comme sûr."""
    valeurs = [float(v) for v in puissances_max_kva if v is not None and v == v and v >= 0]
    if not valeurs:
        return {"conseil": "inconnu", "raison": "Aucune puissance maximale mesurée.", "jours_mesures": 0}
    pointe = max(valeurs)
    besoin = pointe * (1 + marge)
    recommande = next((p for p in PALIERS_KVA if p >= besoin), PALIERS_KVA[-1])
    jours = len(valeurs)
    niveau = fiabilite(jours)
    if recommande > souscrite_kva:
        conseil = "augmenter"
    elif recommande < souscrite_kva:
        conseil = "baisser"
    else:
        conseil = "garder"
    remarques = []
    if conseil == "baisser":
        if niveau != FIABLE:
            remarques.append(f"{jours} jour(s) de mesure : attendre une année complète, hiver compris, avant de baisser l'abonnement.")
        if not mesure_fine:
            remarques.append("Puissance estimée, relevée par intervalles : des pointes brèves peuvent manquer. À confirmer avec les maximums du compteur (prise TIC).")
    return {
        "conseil": conseil,
        "puissance_souscrite_kva": souscrite_kva,
        "puissance_recommandee_kva": recommande,
        "pointe_mesuree_kva": round(pointe, 2),
        "marge_pct": round(marge * 100),
        "jours_mesures": jours,
        "fiabilite": niveau,
        "sur": conseil != "baisser" or (niveau == FIABLE and mesure_fine),
        "remarques": remarques,
    }
