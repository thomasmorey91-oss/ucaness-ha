# Pilotage d'une batterie UCanpower : règles et calculs

Ce document décrit ce que font les packages de `pilotage/packages/` : pilotage de nuit en heures pleines / heures creuses (§ 1 à 7), tarif dynamique (§ 8), secours (§ 9). Ils s'appuient sur l'intégration `ucaness` de ce dépôt et conviennent à tout onduleur UCanpower UHome dont la table de réglages est confirmée (`uhome`, `mr`).

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
| Simulation | « Batterie : mode simulation » revient à « allumé » à chaque redémarrage de Home Assistant (rien n'est envoyé tant qu'il n'est pas éteint), sauf si « Batterie : garder le mode réel après un redémarrage » est allumé : le mode d'avant le redémarrage est alors conservé |
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

1. **Consommation heure par heure** : moyenne mesurée des 7 derniers jours (`recorder.get_statistics`, moyenne horaire de `sensor.uhome_puissance_maison`), même type de jour (ouvré ou repos) en priorité, **pondérée par l'ancienneté** : le jour retenu le plus récent compte 1, le précédent 1/2, puis 1/4, etc. Pour une heure sans mesure : « consommation journalière par défaut » × profil type.
2. **Solaire heure par heure** : prévision Solcast (attribut `detailedHourly`), valeurs datées du jour préparé seulement. Sans prévision pour ce jour : aucune recharge (repli sûr) ; en réévaluation, la plage déjà programmée est conservée.
3. **Bilan cumulé** de la fin des heures creuses à leur retour : il baisse de déficit ÷ rendement quand la maison consomme plus que le solaire, il monte de surplus × rendement sinon.
4. **Besoin** : le point le plus bas de ce bilan, c'est-à-dire l'énergie à avoir en stock en fin de nuit pour tenir jusqu'au relais du solaire, ou jusqu'aux heures creuses suivantes si le solaire ne suffit pas. On y ajoute le quart d'heure entre la fin de la plage et la fin des heures creuses, puis la marge de sécurité.
5. **Place pour le solaire** : capacité utile − pic de remplissage atteint avant le point le plus bas. Un stock consommé avant le surplus solaire ne prend pas sa place.
6. **Cible** : min(besoin ; place ; capacité utile).
7. **Stock restant** : (SOC − plancher) × capacité − consommation d'ici la fin des heures creuses ÷ rendement. En arbitrage horaire, hors plage, la batterie continue d'alimenter la maison.
8. **Recharge réseau** : (cible − stock restant) ÷ rendement, si rendement² × prix HP > prix HC.
9. **Plage** : fin 15 min avant la fin des heures creuses, durée = recharge ÷ puissance de charge × 1,1, début jamais avant le début des heures creuses. Une plage qui passe minuit est coupée en deux.

Pas de recharge si le jour préparé n'est pas ouvré et que les week-ends et jours fériés sont en heures creuses, si la batterie est sous 0 °C, ou si une donnée manque.

## 5. Journal et gain réel

| Élément | Contenu |
|---|---|
| Journal de chaque décision | Justification, fourchette solaire P10-P90 (cas défavorable et favorable de Solcast), heure de la prévision, heures de consommation mesurées, besoin supérieur à la capacité (batterie remplie quelle que soit la prévision) |
| Programmation au début des heures creuses | Jusqu'à 3 essais (au début des heures creuses, puis 10 et 30 min après) ; alerte seulement après le dernier |
| Gain réel du jour (`sensor.jarvis_gain_reel_du_jour`) | 25 min après le début des heures creuses : coût réel des 24 dernières heures (soutirage mesuré × prix de l'heure − injection × prix de revente) comparé à l'autoconsommation simple simulée heure par heure avec la consommation et la production mesurées, à partir du même stock. L'écart de stock final est valorisé au prix des heures creuses × rendement. Sans recharge (week-end), le gain doit rester proche de 0 |
| Cumuls | `sensor.jarvis_gain_reel_du_mois` et `sensor.jarvis_gain_reel_de_l_annee` ; un jour n'est compté qu'une fois |
| Mises à jour Solcast pilotées (optionnel) | Interrupteur « Solcast : mises à jour pilotées par Jarvis », éteint par défaut. À utiliser avec la mise à jour automatique de l'intégration coupée : 3 mises à jour de jour (lever + 15 min, 13h, coucher − 45 min) et une 20 min avant la réévaluation de nuit, dans la limite du quota (2 appels par jour restent pour les valeurs réelles estimées de l'amortissement automatique) |

## 6. Réglages (Paramètres > Entrées)

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

## 7. Constats sur un onduleur UHome 6K (modèle `mr`)

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

## 8. Tarif dynamique (`jarvis_dynamique.yaml`, facultatif)

Pour un contrat dont le prix change chaque heure ou chaque quart d'heure et est publié la veille (prix de marché « day-ahead »). L'état de l'art et les choix sont dans `docs/etat-de-l-art.md`.

### 8.1 Stratégies

| « Pilotage : stratégie de recharge » | Effet |
|---|---|
| Heures pleines / heures creuses (calcul v7) | Valeur par défaut. Le pilotage de nuit (§ 3 et 4) fonctionne seul ; le tarif dynamique ne fait rien |
| Tarif dynamique (moteur intégré) | Le pilotage de nuit ne programme plus rien. Toutes les 15 min, l'action `ucaness.optimiser_charge` calcule les plages des 24 h à venir |
| Tarif dynamique (EMHASS) | Idem, mais le plan vient d'EMHASS, installé et lancé à part ; l'action `ucaness.plages_depuis_plan` le traduit en plages |

### 8.2 Prix payé

prix TTC = (prix de marché + coûts ajoutés de l'heure) × (1 + TVA). Les coûts ajoutés (frais du fournisseur, acheminement, taxes, en EUR/kWh HT) peuvent différer entre les heures pleines et les heures creuses d'Enedis (plages « Tarif : début / fin des heures creuses », chaque jour). Source du prix de marché : Nord Pool (intégration officielle, zone FR) ou tout capteur qui publie un attribut `prix` (ou `prices`) : liste de `{debut, prix}` en EUR/kWh.

### 8.3 Calcul (moteur intégré)

| Étape | Détail |
|---|---|
| Horizon | De maintenant au dernier prix connu et à la dernière prévision solaire (48 h au plus) ; le premier créneau est raccourci à l'instant présent |
| Consommation | Mesurée sur 7 jours, moyenne pondérée par l'ancienneté, profils séparés jours ouvrés / jours de repos (comme le § 4), majorée de la marge |
| Solaire | Prévision Solcast d'aujourd'hui et de demain (`detailedHourly`, médiane) |
| Deux actions par créneau | Autoconsommation, ou plage de charge (le réseau, et le solaire s'il y en a, charge la batterie à la puissance de charge ; la maison est alimentée par le réseau, la batterie est donc gardée) |
| Contraintes | 3 plages au plus dans les 24 h à venir, une plage qui passe minuit en compte deux ; aucune décharge vers le réseau ; capacité utile au-dessus du plancher ; rendement dans chaque sens |
| Objectif | Coût d'achat − revente, moins la valeur du stock restant en fin d'horizon (prix le plus bas ÷ rendement : on ne charge jamais pour le seul stock) |
| Méthode | Programmation dynamique sur le stock, exacte pour ce modèle |
| Seuil | Aucune plage si le gain estimé face à l'autoconsommation simple est sous le « gain minimal » (0,05 € par défaut) |
| Réserve de secours | Si le package secours l'autorise (§ 9), stock minimal à tenir jusqu'à la fin du risque de coupure |

### 8.4 Application

| Règle | Détail |
|---|---|
| Plages | Écrites seulement quand elles changent, à l'avance (en autoconsommation, l'onduleur ne les applique pas) |
| Mode | Arbitrage horaire pendant une fenêtre datée du plan et 3 min avant son début, autoconsommation en dehors. Les plages de l'onduleur n'ont pas de date et se répètent chaque jour : une plage prévue demain à l'heure qu'il est n'a pas d'effet tant que l'onduleur reste en autoconsommation |
| Stabilité | Début des plages arrondi au quart d'heure : une plage déjà commencée n'est pas réécrite à chaque calcul |
| Repli sûr | Plan non valide ou de plus de 40 min, prix, prévision solaire, SOC, température ou capacité manquants, batterie hors plage de température : aucune plage, retour en autoconsommation. Une donnée « inconnue », « indisponible » ou absente compte comme manquante : elle interdit la charge dans le calcul et la bascule en arbitrage horaire |
| Âge du plan EMHASS | Compté depuis la dernière publication du capteur batterie par EMHASS (attribut `publie_le`), et non depuis sa relecture toutes les 5 min. Au-delà de « EMHASS : âge maximal du plan publié » (40 min si l'entrée vaut 0 ; à allonger si EMHASS n'est lancé qu'une fois par jour), le plan n'est plus valide |
| Simulation | Même interrupteur que le pilotage de nuit : en simulation, chaque nouveau plan est journalisé (« [simulation] »), rien n'est envoyé ; au passage en réel, les plages en cours sont écrites aussitôt |
| Retour à la stratégie de nuit | Retour en autoconsommation et oubli des plages du tarif dynamique |
| Alertes | Plages ou mode non confirmés : à surveiller ; retour en autoconsommation non confirmé : intervention (les plages se répètent chaque jour) |

## 9. Secours (`jarvis_secours.yaml`, facultatif)

Rien n'est écrit sur l'onduleur : en cas de coupure, il bascule seul sur sa sortie de secours (EPS) si elle est activée et raccordée. En autoconsommation, réseau coupé, le solaire puis la batterie alimentent la sortie de secours (manuel V1.9, p. 48).

| Fonction | Détail |
|---|---|
| Détection d'une coupure | Tension réseau sous le seuil (100 V par défaut) pendant 20 s alors que l'onduleur répond, ou état « hors réseau » de l'onduleur (libellé à confirmer à la première coupure) |
| Alerte de début | Intervention : heure, SOC, énergie utile, autonomie à la consommation du moment, puissance maximale de la sortie de secours |
| Suivi | Autonomie sous 1 h, batterie à moins de 5 points du plancher, puissance demandée au-delà de 90 % de la sortie de secours pendant 30 s |
| Bilan de fin | Durée, énergie fournie par la batterie, SOC au début, au plus bas et à la fin, puissance la plus haute ; cumuls de l'année (`sensor.jarvis_derniere_coupure`) |
| Risque de coupure | Vigilance Météo-France **rouge** par défaut, ou orange et rouge selon « Secours : niveau de vigilance » (vent violent, orages, neige-verglas, pluie-inondation, inondation, vagues-submersion), ou coupure programmée annoncée par Enedis (12 h avant son début). Capteur de vigilance : celui saisi, sinon le premier `sensor.…_weather_alert` de l'intégration Météo-France. Alerte à surveiller ; avec la stratégie « moteur intégré » et l'interrupteur « garder une réserve », stock minimal (80 % par défaut) jusqu'à la fin du risque |
| Arrêt de Home Assistant | Au redémarrage, si le dernier signe de vie date de plus de 15 min : coupure de courant ou d'Internet probable |
| Mode Backup | Signalé s'il est activé hors de Jarvis (Jarvis ne l'écrit jamais) |
| Autonomie de secours | `sensor.jarvis_autonomie_de_secours` : énergie utile × rendement ÷ consommation du moment (au moins 0,2 kW), sans le solaire |

Pour être alerté pendant une coupure, Home Assistant, la box Internet et le module Wi-Fi de l'onduleur doivent rester alimentés (circuits sur la sortie de secours ou petit onduleur UPS).

Puissance continue de la sortie de secours (manuel V1.9, § 3.3) : 3 000 VA (3K0L), 3 680 VA (3K6L), 4 000 VA (4K0L), 4 600 VA (4K6L), 5 000 VA (5K0L), 6 000 VA (6K0L), 8 000 VA (8K0L) ; au-delà de 6 000 W, deux modules de batterie au moins.

## 10. Analyse de l'installation et dimensionnement

Outil hors de Home Assistant, à lancer une fois depuis un PC : `tools/dimensionnement/README.md`. Il chiffre l'installation existante, la batterie et le solaire nécessaires à l'autonomie totale, et le système le plus petit pour 70 à 95 % d'autonomie.

## 11. Historique

| Version | Changement |
|---|---|
| v1 | Calcul de la recharge de nuit, simulation seulement |
| v3 | Besoin = point le plus bas du bilan horaire (jusqu'au relais du solaire ou aux heures creuses) |
| v4 | Recharge en fin d'heures creuses, décision au début des heures creuses, réévaluation 1 h avant, jour préparé correct après minuit |
| v5 | Consommation mesurée, nuit toujours déduite, marge de sécurité |
| v6 | Réglages propres à chaque installation dans des entrées (aucune valeur d'installation dans le code), service de notification paramétrable, place pour le solaire comptée avant le point le plus bas |
| v7 | Moyenne de consommation pondérée par l'ancienneté, aucune recharge sans prévision solaire datée du jour préparé, journal enrichi (fourchette P10-P90, heure de la prévision), gain réel du jour face à l'autoconsommation et cumuls, 3 essais de programmation, mises à jour Solcast pilotées (optionnel) |
| v7.1 | Correctifs du journal : cumul du gain de l'année (et bilan annuel des coupures) qui repartait de zéro chaque jour, Home Assistant relisant l'attribut « annee » comme un nombre ; aperçu de 22h30 journalisé ; confirmation de la plage ajustée journalisée après la réévaluation. Interrupteur « Batterie : garder le mode réel après un redémarrage » (éteint par défaut : simulation à chaque démarrage, comme avant). Aucun changement du calcul ni des commandes envoyées |
| Tarif dynamique 1 | Stratégie au choix (nuit, moteur intégré, EMHASS) ; moteur intégré par programmation dynamique ; adaptateur EMHASS ; le pilotage de nuit ne programme rien quand une stratégie dynamique est choisie |
| Tarif dynamique 1.1 | Repli sûr renforcé : température ou SOC « inconnu » ou « indisponible » = aucune charge pilotée (moteur intégré, plan EMHASS, application du plan) ; âge du plan EMHASS compté depuis sa publication ; plan EMHASS enfin appliqué (les fenêtres datées étaient remplacées par leur nombre : intégration 0.3.1, clé `nombre_fenetres`). Aucun changement du pilotage de nuit |
| v7.2 | Batterie sans panneaux solaires : entrée « Batterie : panneaux solaires » (détection automatique, avec, sans) et `binary_sensor.jarvis_sans_solaire`. Sans panneaux, la recharge en heures creuses est calculée avec une production nulle, sans prévision solaire ; le tarif dynamique reçoit une production nulle sur 48 h. Avec panneaux, et dans le doute, rien ne change : aucune recharge sans prévision solaire datée |
| Secours 1 | Détection et suivi des coupures, bilan, risque de coupure (vigilance, coupure programmée), réserve de secours pour le tarif dynamique, bilan au redémarrage ; rien n'est écrit sur l'onduleur |
