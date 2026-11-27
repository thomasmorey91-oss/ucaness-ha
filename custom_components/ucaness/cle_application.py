"""Clé d'application UCanpower livrée avec l'intégration.

Paire « HA use » délivrée par UCanpower pour cette intégration. Diffusion publique autorisée par
écrit par UCanpower le 27/11/2026. Elle identifie l'APPLICATION, pas un propriétaire : elle ne
donne accès à aucun appareil par elle-même. Chaque propriétaire se connecte toujours avec son
propre compte UCANESS et n'accède qu'à ses propres appareils. Son usage est limité par UCanpower
aux fonctions dont l'intégration a besoin (connexion, liste, configuration, état, écriture des
réglages) ; ce que l'intégration écrit reste filtré par la liste blanche du client (api.py).

Une clé personnelle saisie dans les options (clé ET secret) passe avant celle-ci : c'est le recours
si UCanpower devait un jour révoquer la clé livrée (renouvellement manuel seulement).
"""
from __future__ import annotations

from typing import Any, Mapping

from .const import CONF_APP_KEY, CONF_APP_SECRET

# Remplies par le mainteneur du dépôt. Vides : aucune clé livrée (seule une clé personnelle sert).
CLE_LIVREE = "zmjzts24ebey7kqn"
SECRET_LIVRE = "fv74dtrg6aenvfthu4t3zj6d6b3kp9v9"

PERSONNELLE = "personnelle"
LIVREE = "livree"


def cle_effective(options: Mapping[str, Any]) -> tuple[str, str, str | None]:
    """(clé, secret, origine) à utiliser : la clé personnelle si elle est complète, sinon celle
    livrée avec l'intégration, sinon aucune (origine None)."""
    cle = (options.get(CONF_APP_KEY) or "").strip()
    secret = (options.get(CONF_APP_SECRET) or "").strip()
    if cle and secret:
        return cle, secret, PERSONNELLE
    if CLE_LIVREE.strip() and SECRET_LIVRE.strip():
        return CLE_LIVREE.strip(), SECRET_LIVRE.strip(), LIVREE
    return "", "", None
