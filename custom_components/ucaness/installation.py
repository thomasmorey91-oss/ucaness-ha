"""Assistant d'installation : où en est la configuration, et quelle est l'étape suivante.

Python pur, sans Home Assistant : `evaluer()` reçoit un instantané de l'installation (un simple
dictionnaire, construit par assistant.py) et rend un bilan. Rien n'est écrit, ni dans Home
Assistant ni sur l'onduleur : ce module constate et explique.

Une étape à la fois : le bilan désigne UNE étape suivante, la première qui manque dans l'ordre
du parcours. Les étapes obligatoires passent avant les étapes facultatives.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# États de l'installation (valeurs de sensor.ucaness_installation).
A_CONFIGURER = "a_configurer"      # une étape obligatoire manque, rien n'est en service
EN_SIMULATION = "en_simulation"    # tout est prêt, le pilotage calcule sans rien envoyer
EN_SERVICE = "en_service"          # mode réel, écriture autorisée
A_VERIFIER = "a_verifier"          # mode réel, mais quelque chose manque
ETATS = (A_CONFIGURER, EN_SIMULATION, EN_SERVICE, A_VERIFIER)

DOC_PILOTAGE = "https://github.com/thomasmorey91-oss/ucaness-ha/blob/main/pilotage/README.md"


@dataclass(frozen=True)
class Etape:
    cle: str
    titre: str
    raison: str                              # pourquoi cette étape, en une phrase
    faite: Callable[[dict[str, Any]], bool]
    obligatoire: bool = True
    lien: str | None = None                  # écran de Home Assistant (chemin interne) ou page de documentation


@dataclass
class Bilan:
    etat: str
    faites: list[str] = field(default_factory=list)
    restantes: list[str] = field(default_factory=list)
    suivante: Etape | None = None
    progression: int = 0                     # % des étapes faites
    entites_manquantes: list[str] = field(default_factory=list)

    def attributs(self) -> dict[str, Any]:
        s = self.suivante
        return {
            "progression": self.progression,
            "etapes_faites": self.faites,
            "etapes_restantes": self.restantes,
            "etape_suivante": None if s is None else {
                "cle": s.cle, "titre": s.titre, "raison": s.raison, "lien": s.lien, "obligatoire": s.obligatoire,
            },
            "entites_manquantes": self.entites_manquantes,
        }


def _positif(valeur: Any) -> bool:
    try:
        return float(valeur) > 0
    except (TypeError, ValueError):
        return False


def _contrat(ctx: dict[str, Any]) -> bool:
    """Prix renseignés : heures pleines (ou Base) toujours, heures creuses si le contrat en a."""
    if not _positif(ctx.get("prix_hp")):
        return False
    return ctx.get("type_tarif") == "Base" or _positif(ctx.get("prix_hc"))


ETAPES: tuple[Etape, ...] = (
    Etape(
        "connexion", "Connexion à la batterie",
        "Sans mesures de la batterie, rien ne peut être calculé.",
        lambda c: bool(c.get("connexion")),
        lien="/config/integrations/integration/ucaness",
    ),
    Etape(
        "packages", "Pilotage installé",
        "Les packages de pilotage décident chaque soir de la recharge de nuit.",
        lambda c: bool(c.get("packages")),
        lien=DOC_PILOTAGE,
    ),
    Etape(
        "entites", "Mesures reconnues par le pilotage",
        "Le pilotage lit la batterie sous des noms précis ; certains manquent.",
        lambda c: c.get("entites_manquantes") == [],
        lien="/config/entities",
    ),
    Etape(
        "batterie", "Votre batterie",
        "La capacité sert à savoir combien d'énergie il reste et combien il en faut.",
        lambda c: _positif(c.get("capacite_kwh")),
        lien="/config/helpers",
    ),
    Etape(
        "contrat", "Votre contrat d'électricité",
        "Recharger la nuit n'a d'intérêt que si l'écart de prix le justifie.",
        _contrat,
        lien="/config/helpers",
    ),
    Etape(
        "jours_ouvres", "Jours ouvrés",
        "Pour distinguer la semaine du week-end et des jours fériés.",
        lambda c: bool(c.get("jours_ouvres")),
        lien="/_my_redirect/config_flow_start?domain=workday",
    ),
    Etape(
        "prevision_solaire", "Prévision de production solaire",
        "Pour ne recharger que le nécessaire ; sans prévision, aucune recharge n'est programmée.",
        lambda c: bool(c.get("prevision_solaire")),
        lien="/_my_redirect/config_flow_start?domain=solcast_solar",
    ),
    Etape(
        "notifications", "Notifications",
        "Pour être prévenu d'un défaut ou d'une programmation qui a échoué.",
        lambda c: bool(c.get("notification")),
        obligatoire=False,
        lien="/config/helpers",
    ),
)
CLES = tuple(e.cle for e in ETAPES)


def evaluer(ctx: dict[str, Any]) -> Bilan:
    """Bilan de l'installation à partir de l'instantané `ctx` (voir assistant.construire_contexte).

    Une clé absente de `ctx` compte comme « non fait » : une donnée qui manque ne valide jamais
    une étape.
    """
    faites = [e.cle for e in ETAPES if e.faite(ctx)]
    restantes = [e.cle for e in ETAPES if e.cle not in faites]
    manquantes = [e for e in ETAPES if e.cle in restantes]
    suivante = next((e for e in manquantes if e.obligatoire), None) or next(iter(manquantes), None)
    pret = not any(e.obligatoire for e in manquantes)
    mode_reel = ctx.get("simulation") is False        # None = état inconnu : jamais pris pour le mode réel

    if mode_reel:
        etat = EN_SERVICE if pret and ctx.get("ecriture") else A_VERIFIER
    elif pret:
        etat = EN_SIMULATION
    else:
        etat = A_CONFIGURER
    return Bilan(
        etat=etat, faites=faites, restantes=restantes, suivante=suivante,
        progression=round(100 * len(faites) / len(ETAPES)),
        entites_manquantes=sorted(ctx.get("entites_manquantes") or []),
    )
