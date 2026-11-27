# Feuille de route

Fonctions **spécifiées, pas encore développées**, au 27/11/2026. L'ordre peut changer. Chaque étape qui touche le calcul de recharge est d'abord comparée aux nuits enregistrées (banc d'essai), puis validée sur une installation réelle.

Règle inchangée pour toutes : l'intégration n'écrit sur l'onduleur que le **mode** (autoconsommation ou arbitrage horaire) et les **plages de charge**. Jamais de plage de décharge, jamais de mode Backup, aucun réglage de fond.

## 1. Météo

| Fonction | Ce qu'elle fait | État |
|---|---|---|
| Prévision de consommation selon la météo | Correction de la prévision (7 jours pondérés) par les degrés-jours de chauffage (base 16 °C) et de climatisation (base 24 °C), bornée de −20 % à +30 % ; calcul à blanc 14 jours, puis choix « Avec la météo » | Température enregistrée depuis le 27/11 (`jarvis_meteo.yaml`) |
| Surveillance de la production solaire | Champ arrêté (un MPPT produit, l'autre non) ; écart entre les deux champs par ciel ensoleillé ; rendement par ciel clair en baisse (salissure, ombre) | Spécifiée |

## 2. Mode alerte avant une coupure

- **Déclencheur** : vigilance **rouge** Météo-France (orages, neige-verglas, vent violent ; aussi inondations), **6 h** avant le début prévu ; source du lendemain avec heures de début : intégration communautaire « Vigilance Météo France » (clé gratuite de l'API Météo-France). Sans vigilance rouge, Ucan ne pose pas de question.
- **Question d'Ucan** : « Voulez-vous passer en mode alerte ? » Sans réponse, rien ne change. Pas d'argent dans les messages : c'est une question de confort.
- **Mode alerte** : charge à 100 % (heures pleines comprises), batterie **maintenue à 100 %** pendant l'alerte ; la maison est alimentée par le solaire et le réseau ; pilotage de nuit suspendu. Moyen prévu : plage de charge continue en arbitrage horaire, **à valider par un essai** (batterie pleine, aucune décharge).
- **Coupure** : l'onduleur bascule seul sur sa sortie de secours (si elle est raccordée).
- **Fin** : bouton « Lever l'alerte » ; quand Météo-France lève la vigilance, Ucan propose de repasser en mode normal, relance, puis y revient seul au bout de 3 h.

## 3. Pilotage

| Fonction | Ce qu'elle fait |
|---|---|
| Recharge de la voiture retirée de la prévision | La consommation de la borne est soustraite de l'historique ; une recharge programmée s'ajoute au besoin à part |
| Coût d'usure de la batterie | Pas de recharge réseau si l'écart de prix ne paie pas l'usure du kWh cyclé (prix de la batterie, cycles garantis) |
| Heures creuses en plusieurs plages | Jusqu'à 3 plages par jour, été et hiver (heures creuses de l'après-midi en France, TURPE 7) ; recharge d'après-midi les jours sans soleil |
| Plan sur 48 h et au quart d'heure | Pas de recharge la veille d'un week-end ensoleillé ; prix au quart d'heure pour les offres dynamiques |

## 4. Plusieurs pays

Modèle d'offre unique : jusqu'à 4 niveaux de prix, plusieurs plages par jour, saisons, types de jour, part liée à la puissance ou au pic mensuel. Limite de puissance du compteur vérifiée avant chaque recharge réseau.

| Pays | Particularité prise en compte |
|---|---|
| France | Tarifs réglementés Base, heures creuses, Tempo ; heures creuses de l'après-midi |
| Belgique | Pic mensuel (Flandre) : pas de recharge qui crée un pic ; tarif Impact à trois niveaux (Wallonie) |
| Italie | Compteur de 3 kW (coupure au-delà de 3,3 kW) : recharge réseau refusée si elle ferait couper ; tranches F1, F2, F3 ; conseils d'Ucan pour éviter les coupures (gestes de l'utilisateur) |
| Espagne | 2.0TD : pointe, plein, vallée ; week-end en vallée ; deux puissances souscrites |
| Portugal | Options bi-, tri- et tétra-horaires, cycle quotidien ou hebdomadaire, été et hiver ; nouvelles plages en 2027 |
| Allemagne | Bridage par le gestionnaire de réseau (§ 14a) respecté ; tarifs de réseau à trois niveaux (module 3) |
| Pays-Bas | Fin de la compensation de l'injection (01/01/2027) : priorité à l'autoconsommation |
| Chine | Prix par province, vallée possible à midi |

Les règles de chaque pays sont à confirmer par un professionnel local avant leur mise en service.
