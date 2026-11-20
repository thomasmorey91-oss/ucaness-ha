# Pilotage de nuit d'une batterie UCanpower : règles et calculs

Ce document décrit ce que font les packages de `pilotage/packages/`. Ils s'appuient sur l'intégration `ucaness` de ce dépôt et conviennent à tout onduleur UCanpower UHome dont la table de réglages est confirmée (`uhome`, `mr`).

## 1. Objectifs

1. Consommer sur place, en priorité, la production solaire.
2. Alimenter la maison avec de l'électricité d'heures creuses jusqu'à ce que le solaire prenne le relais, même tard dans la journée si le soleil n'arrive que l'après-midi.
3. Compter la production solaire prévue, puis compléter avec l'électricité des heures creuses de la nuit précédente pour tenir jusqu'aux heures creuses suivantes.
4. Ne recharger sur le réseau que si c'est rentable, et ne jamais réinjecter sur le réseau l'énergie qui en vient.
5. Journaliser chaque décision avec sa justification.

## 2. Règles de sécurité

| Règle | Mise en œuvre |
|---|---|
| Seuls le mode et les plages de charge sont écrits | Liste blanche du client (`api.py`) : réglage 1 (valeurs 0 et 1) et réglages 44 à 55. Tout autre réglage est refusé avant d'atteindre le réseau |
| Aucun réglage de fond | DOD, hystérésis, courant, puissance réseau, protections réseau, type de batterie, norme, firmware, retour usine : jamais envoyés |
| Pas de mode Backup | Valeur 2 du mode refusée |
| Pas de plage de décharge | Les plages 46/47, 50/51, 54/55 sont toujours remises à 0 : une plage de décharge renverrait la batterie sur le réseau |
| Écriture autorisée explicitement | Option « Écriture autorisée » de l'intégration, éteinte par défaut |
| Modèle confirmé | Écriture permise seulement pour les modèles `uhome` et `mr` |
| Relecture | Chaque envoi est relu sur l'onduleur. Un réglage absent de la configuration du cloud vaut 0 ; le mode est aussi confirmé par le mode affiché |
| Fréquence | 2 s entre envois, 20 envois par heure au plus, seuls les réglages modifiés, deux par deux |
| Simulation | « Batterie : mode simulation » revient à « allumé » à chaque redémarrage de Home Assistant : rien n'est envoyé tant qu'il n'est pas éteint |
| Température | Aucune charge si la batterie est sous 0 °C |
| Retour sûr | Retour en autoconsommation 2 min avant la fin des heures creuses, contrôle de secours 15 min après, puis alerte |
| Données manquantes | Prix, capacité, SOC ou consommation inconnus : aucune recharge (repli sûr) |
| Nouveaux essais | Programmation de la nuit : jusqu'à 3 essais (début des heures creuses, +10 min, +30 min). Le script est rejouable : les réglages déjà en place ne sont pas renvoyés |
| Alertes | Échec de programmation (après le dernier essai), de réévaluation ou de retour : notification sur le téléphone |

## 3. Déroulement d'une nuit

| Moment | Action |
|---|---|
| 22h30 | Calcul d'aperçu (journal) |
| Début des heures creuses | Recalcul avec le SOC du moment. Si le stock restant après la nuit couvre le besoin, rien n'est envoyé. Sinon : plage de charge en fin de nuit, puis passage en arbitrage horaire |
| 1 h avant le début de la charge | Réévaluation avec le SOC et la prévision du moment : plage raccourcie, allongée ou supprimée. Si une donnée manque, la plage déjà programmée est conservée |
| 15 min avant la fin des heures creuses | Fin de la plage de charge |
| 2 min avant la fin des heures creuses | Retour en autoconsommation |
| 15 min après la fin des heures creuses | Contrôle de secours |

La recharge est placée en fin d'heures creuses : elle ne se cumule pas avec les appareils lancés au début des heures creuses (ballon d'eau chaude, électroménager), et l'énergie chargée sert le matin.

## 4. Calcul de la recharge

Pour le jour préparé (le lendemain le soir, le jour même après minuit) :

1. **Consommation heure par heure** : moyenne mesurée des 7 derniers jours (`recorder.get_statistics`, moyenne horaire de `sensor.uhome_puissance_maison`), même type de jour (ouvré ou repos) en priorité. Pour une heure sans mesure : « consommation journalière par défaut » × profil type.
2. **Solaire heure par heure** : prévision Solcast (attribut `detailedHourly`).
3. **Bilan cumulé** de la fin des heures creuses à leur retour : il baisse de déficit ÷ rendement quand la maison consomme plus que le solaire, il monte de surplus × rendement sinon.
4. **Besoin** : le point le plus bas de ce bilan, c'est-à-dire l'énergie à avoir en stock en fin de nuit pour tenir jusqu'au relais du solaire, ou jusqu'aux heures creuses suivantes si le solaire ne suffit pas. On y ajoute le quart d'heure entre la fin de la plage et la fin des heures creuses, puis la marge de sécurité.
5. **Place pour le solaire** : capacité utile − pic de remplissage atteint avant le point le plus bas. Un stock consommé avant le surplus solaire ne prend pas sa place.
6. **Cible** : min(besoin ; place ; capacité utile).
7. **Stock restant** : (SOC − plancher) × capacité − consommation d'ici la fin des heures creuses ÷ rendement. En arbitrage horaire, hors plage, la batterie continue d'alimenter la maison.
8. **Recharge réseau** : (cible − stock restant) ÷ rendement, si rendement² × prix HP > prix HC.
9. **Plage** : fin 15 min avant la fin des heures creuses, durée = recharge ÷ puissance de charge × 1,1, début jamais avant le début des heures creuses. Une plage qui passe minuit est coupée en deux.

Pas de recharge si le jour préparé n'est pas ouvré et que les week-ends et jours fériés sont en heures creuses, si la batterie est sous 0 °C, ou si une donnée manque.

## 5. Réglages (Paramètres > Entrées)

| Entrée | Rôle | Valeur de départ |
|---|---|---|
| Batterie : capacité | Capacité nominale (kWh), par exemple 5,12 kWh par module ULB-5120MT | 0 : à renseigner, rien n'est programmé avant |
| Batterie : SOC plancher | SOC sous lequel l'onduleur ne décharge plus. Avec un DOD de 90 %, observer le SOC le plus bas atteint | 20 % |
| Batterie : rendement | Rendement dans un sens (charge ou décharge) | 95 % |
| Batterie : puissance de charge | Puissance réellement observée pendant une plage de charge réseau | 3 kW |
| Batterie : marge de sécurité | Majoration du besoin | 10 % |
| Batterie : consommation journalière par défaut | Pour les heures sans mesure (les premiers jours) | 0 : à renseigner |
| Tarif : type, heures creuses, week-end en heures creuses, prix HP, HC et revente | Contrat de fourniture | Heures creuses 22h30-6h30, prix à 0 : à renseigner |
| Alertes : service de notification | Par exemple `mobile_app_mon_telephone` | Vide : pas de notification |

## 6. Constats sur un onduleur UHome 6K (modèle `mr`)

| Constat |
|---|
| La table du mode et des plages est la même que celle documentée pour `uhome` (confirmée par une requête du portail UCANESS). Les réglages de fond sont stockés à l'échelle ×10 |
| Le cloud omet les valeurs nulles dans la configuration (mode 0, plages vides) |
| Un envoi de 12 réglages d'un coup reçoit « 5019 Device operation timeout » ; un ou deux réglages passent |
| Un « 5019 » peut aussi répondre à un envoi que l'onduleur a bien appliqué : l'intégration relit la configuration pendant 2 min avant de conclure à un échec |
| Mode affiché : « Match Load Mode » en autoconsommation, « Peak Fill Mode » en arbitrage horaire |
| En arbitrage horaire, hors plage, la batterie continue d'alimenter la maison (le manuel indique le contraire) |
| La puissance de charge réseau est bridée par le réglage « puissance réseau » de l'installateur (par exemple 3,6 kW pour 60 % de 6 kW) |
| Sous le plancher, l'onduleur se recharge seul de quelques pourcents sur le réseau, y compris en heures pleines |
| L'application mobile UCANESS affiche « Arbitrage horaire » par défaut quand le mode n'est pas stocké : ne jamais valider ce formulaire sans vérifier le mode |

## 7. Historique

| Version | Changement |
|---|---|
| v1 | Calcul de la recharge de nuit, simulation seulement |
| v3 | Besoin = point le plus bas du bilan horaire (jusqu'au relais du solaire ou aux heures creuses) |
| v4 | Recharge en fin d'heures creuses, décision au début des heures creuses, réévaluation 1 h avant, jour préparé correct après minuit |
| v5 | Consommation mesurée, nuit toujours déduite, marge de sécurité |
| v6 | Réglages propres à chaque installation dans des entrées (aucune valeur d'installation dans le code), service de notification paramétrable, place pour le solaire comptée avant le point le plus bas |
