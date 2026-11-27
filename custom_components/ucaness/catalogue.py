"""Offres de référence et grilles horaires par pays (simulateur « et si », ucaness.simuler ;
évaluation d'offres, ucaness.evaluer_offres).

Le pays vient du réglage général de Home Assistant (`hass.config.country`), jamais d'une adresse IP.

- France : tarifs réglementés d'EDF (Tempo, heures creuses), prix TTC.
- Portugal : tarifs réglementés transitoires de l'ERSE (BTN de 3,45 à 20,7 kVA), cycle quotidien,
  prix hors TVA et taxes (le dire dans le résultat).
- Espagne : grille 2.0TD (pointe, plein, vallée) ; pas de prix fixe de référence (le prix réglementé
  PVPC change chaque heure) : l'utilisateur passe ses offres avec `structure: es_2.0td`.
- Italie : tranches F1, F2, F3 (ou F1, F23) définies par l'ARERA ; pas d'offre réglementée commune :
  l'utilisateur passe ses offres avec `structure: it_f1f2f3` ou `it_f1f23`.

Les prix vieillissent : au-delà de 30 jours après la date de relevé, le moteur le signale dans chaque
résultat (« à revérifier »). Une grille horaire datée (`valable_jusqu_au`) est signalée une fois la
date passée. Toute offre peut être remplacée ou complétée par les offres passées à l'action.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .tarifs import (
    BASE, DIMANCHE_FERIE, ETE, HIVER, HPHC, OUVRE, PALIERS_KVA, PLAGES, SAMEDI, TEMPO, Offre, Regle,
)

# ------------------------------------------------------------------ grilles horaires (formule « plages »)


@dataclass(frozen=True)
class Structure:
    pays: str
    nom: str
    regles: tuple[Regle, ...]
    niveau_defaut: str
    source: str
    valable_jusqu_au: date | None = None

    @property
    def niveaux(self) -> tuple[str, ...]:
        vus: list[str] = []
        for n in [r.niveau for r in self.regles] + [self.niveau_defaut]:
            if n not in vus:
                vus.append(n)
        return tuple(vus)


OUVRES = (OUVRE,)
TOUS = (OUVRE, SAMEDI, DIMANCHE_FERIE)

STRUCTURES: dict[str, Structure] = {
    # Espagne, péninsule, Baléares et Canaries : 2.0TD. Samedi, dimanche et fériés nationaux en vallée.
    "es_2.0td": Structure(
        "ES", "2.0TD (punta, llano, valle)",
        (Regle("punta", "10:00", "14:00", OUVRES), Regle("punta", "18:00", "22:00", OUVRES),
         Regle("llano", "08:00", "10:00", OUVRES), Regle("llano", "14:00", "18:00", OUVRES),
         Regle("llano", "22:00", "00:00", OUVRES)),
        "valle",
        "Péages 2.0TD (CNMC), périodes publiées par REE : https://www.ree.es/en/operation/electricity-system/pvpc",
    ),
    # Italie : tranches de l'ARERA ; fériés nationaux en F3.
    "it_f1f2f3": Structure(
        "IT", "F1, F2, F3",
        (Regle("f1", "08:00", "19:00", OUVRES),
         Regle("f2", "07:00", "08:00", OUVRES), Regle("f2", "19:00", "23:00", OUVRES),
         Regle("f2", "07:00", "23:00", (SAMEDI,))),
        "f3",
        "ARERA, fasce orarie : https://www.arera.it/bolletta/glossario-dei-termini/dettaglio/fasce-orarie",
    ),
    "it_f1f23": Structure(
        "IT", "F1, F23 (bioraria)",
        (Regle("f1", "08:00", "19:00", OUVRES),),
        "f23",
        "ARERA, fasce orarie : https://www.arera.it/bolletta/glossario-dei-termini/dettaglio/fasce-orarie",
    ),
    # Portugal continental, BTN, cycle quotidien : identique tous les jours de l'année.
    # Nouvelles plages progressivement entre le 01/07/2027 et le 31/12/2027 (ERSE).
    "pt_bi_diario": Structure(
        "PT", "Bi-horária, ciclo diário (vazio, fora de vazio)",
        (Regle("vazio", "22:00", "08:00", TOUS),),
        "fora_vazio",
        "ERSE, períodos horários (BTN, ciclo diário) : https://www.erse.pt/media/s0wh5zf0/periodoshorariosele.pdf",
        valable_jusqu_au=date(2027, 6, 30),
    ),
    "pt_tri_diario": Structure(
        "PT", "Tri-horária, ciclo diário (ponta, cheias, vazio)",
        (Regle("vazio", "22:00", "08:00", TOUS),
         Regle("ponta", "09:00", "10:30", TOUS, HIVER), Regle("ponta", "18:00", "20:30", TOUS, HIVER),
         Regle("ponta", "10:30", "13:00", TOUS, ETE), Regle("ponta", "19:30", "21:00", TOUS, ETE)),
        "cheias",
        "ERSE, períodos horários (BTN, ciclo diário) : https://www.erse.pt/media/s0wh5zf0/periodoshorariosele.pdf",
        valable_jusqu_au=date(2027, 6, 30),
    ),
}


def offre_plages(nom: str, structure: str, abonnement_eur_an: dict[float, float], prix_kwh: dict[str, float],
                 **autres) -> Offre:
    """Offre « plages » construite sur une grille du catalogue."""
    s = STRUCTURES[structure]
    return Offre(nom, PLAGES, abonnement_eur_an, prix_kwh, regles=s.regles, niveau_defaut=s.niveau_defaut,
                 structure=structure, valable_jusqu_au=autres.pop("valable_jusqu_au", s.valable_jusqu_au), **autres)


# ------------------------------------------------------------------ France

SOURCE_TEMPO = "https://www.fournisseurs-electricite.com/fournisseurs/edf/tarifs/tempo/prix"
SOURCE_HPHC = "Tarif réglementé (option heures creuses) au 01/08/2026, relevé le 16/11/2026"

OFFRES_REFERENCE: tuple[Offre, ...] = (
    Offre(
        "Tempo (tarif réglementé)", TEMPO, {6: 189.60, 9: 236.40, 12: 282.00, 15: 324.12},
        {"bleu_hp": 0.1654, "bleu_hc": 0.1356, "blanc_hp": 0.1921, "blanc_hc": 0.1536,
         "rouge_hp": 0.7295, "rouge_hc": 0.1615},
        fournisseur="EDF", source=SOURCE_TEMPO, date_prix=date(2026, 8, 1),
    ),
    Offre(
        "Heures creuses (tarif réglementé)", HPHC, {9: 238.56},
        {"hp": 0.2142, "hc": 0.1589}, fournisseur="EDF", plages_hc=(("22:30", "06:30"),),
        source=SOURCE_HPHC, date_prix=date(2026, 8, 1),
    ),
)

# ------------------------------------------------------------------ Portugal

# Tarifs transitoires de vente aux clients finals, BTN (> 2,3 kVA et ≤ 20,7 kVA), en vigueur depuis le
# 01/10/2026 (ERSE, mise à jour trimestrielle de la composante énergie, quadro 5-6). Puissance en EUR
# par jour, identique pour les trois options ; abonnement annuel = 365 jours. Prix publiés hors TVA.
SOURCE_PT = ("ERSE, tarifas transitórias de venda a clientes finais BTN, em vigor a partir de 01/10/2026 : "
             "https://www.erse.pt/media/pfojkwzr/atualiza%C3%A7%C3%A3o-tenergia-se-2026-t4.pdf")
_PUISSANCE_PT_EUR_JOUR = {3.45: 0.1917, 4.6: 0.2499, 5.75: 0.3079, 6.9: 0.3659,
                          10.35: 0.5397, 13.8: 0.7136, 17.25: 0.8875, 20.7: 1.0614}
_ABONNEMENT_PT = {kva: round(e * 365, 2) for kva, e in _PUISSANCE_PT_EUR_JOUR.items()}
_COMMUN_PT = {"fournisseur": "Tarif réglementé (ERSE)", "source": SOURCE_PT, "date_prix": date(2026, 11, 27),
              "taxes_comprises": False}

OFFRES_PT: tuple[Offre, ...] = (
    Offre("Simples (tarifa regulada)", BASE, _ABONNEMENT_PT, {"base": 0.1711}, **_COMMUN_PT),
    offre_plages("Bi-horária, ciclo diário (tarifa regulada)", "pt_bi_diario", _ABONNEMENT_PT,
                 {"vazio": 0.1143, "fora_vazio": 0.2045}, **_COMMUN_PT),
    offre_plages("Tri-horária, ciclo diário (tarifa regulada)", "pt_tri_diario", _ABONNEMENT_PT,
                 {"vazio": 0.1143, "cheias": 0.1747, "ponta": 0.2553}, **_COMMUN_PT),
)

# ------------------------------------------------------------------ par pays

OFFRES_PAR_PAYS: dict[str, tuple[Offre, ...]] = {"FR": OFFRES_REFERENCE, "PT": OFFRES_PT, "ES": (), "IT": ()}

# Puissances souscrites possibles (kVA) ; None : paliers non connus (recommandation arrondie au dixième).
PALIERS_PAR_PAYS: dict[str, tuple[float, ...] | None] = {
    "FR": PALIERS_KVA,
    "PT": (1.15, 2.3, 3.45, 4.6, 5.75, 6.9, 10.35, 13.8, 17.25, 20.7),
}

# Puissance prise par défaut quand l'utilisateur n'en indique pas.
PUISSANCE_DEFAUT_PAR_PAYS: dict[str, float] = {"FR": 9, "PT": 6.9, "ES": 4.6, "IT": 3}

POURQUOI_SANS_OFFRE: dict[str, str] = {
    "ES": "Espagne : pas de prix fixe de référence (le PVPC change chaque heure). Passez vos offres avec "
          "« structure: es_2.0td » et les prix punta, llano, valle.",
    "IT": "Italie : pas d'offre réglementée commune. Passez vos offres avec « structure: it_f1f2f3 » "
          "(prix f1, f2, f3) ou « it_f1f23 » (prix f1, f23).",
}


def offres_reference(pays: str | None) -> tuple[Offre, ...]:
    """Offres de référence du pays (France si le pays n'est pas réglé, comme avant la 0.6)."""
    return OFFRES_PAR_PAYS.get((pays or "FR").upper(), ())


def paliers(pays: str | None) -> tuple[float, ...] | None:
    return PALIERS_PAR_PAYS.get((pays or "FR").upper())


def puissance_defaut(pays: str | None) -> float:
    return PUISSANCE_DEFAUT_PAR_PAYS.get((pays or "FR").upper(), 6)


def pays_pris_en_charge() -> tuple[str, ...]:
    return tuple(OFFRES_PAR_PAYS)


__all__ = ["OFFRES_PAR_PAYS", "OFFRES_PT", "OFFRES_REFERENCE", "PALIERS_PAR_PAYS", "POURQUOI_SANS_OFFRE",
           "STRUCTURES", "Structure", "offre_plages", "offres_reference", "paliers", "pays_pris_en_charge",
           "puissance_defaut"]
