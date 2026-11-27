"""Offres de référence du simulateur « et si » (ucaness.simuler) : tarifs réglementés d'EDF.

Prix TTC relevés à la date indiquée, avec leur source. Ils vieillissent : au-delà de 30 jours, le
moteur le signale dans chaque résultat (« à revérifier »). Toute offre peut être remplacée ou
complétée par les offres passées à l'action (champ « offres »), comme pour ucaness.evaluer_offres.
"""
from __future__ import annotations

from datetime import date

from .tarifs import HPHC, TEMPO, Offre

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
