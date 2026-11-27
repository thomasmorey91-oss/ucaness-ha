# Journal des changements

Versions de l'intégration (`custom_components/ucaness`) et des cartes du tableau de bord (`dashboard/www/ucaness/ucaness-cards.js`). Les packages de `pilotage/` n'ont pas de numéro : leurs changements sont datés.

## 27/11/2026

### Intégration 0.7.0 et cartes 0.7.0 : véhicule électrique
- **Options « Configurer votre véhicule »** : marque, modèle et version choisis dans le catalogue OpenEV Data (CDLA-Permissive-2.0, `donnees/vehicules.json`, 1 157 versions depuis 2018, `tools/vehicules/construire_catalogue.py`), caractéristiques proposées puis confirmées ou corrigées ; les dix modèles les plus vendus du pays (FR, DE, IT, ES, PT) en tête de liste ; silhouette, couleur, charge visée, puissance de la borne, entité de charge transmise par la voiture. Capteur `sensor.ucaness_vehicule`.
- **`ucaness.planifier_recharge_vehicule`** (calcul seul) : énergie à prendre, puissance la plus faible de la borne et du véhicule, surplus solaire d'abord puis heures les moins chères avant le départ ; plages à réseau marquées pour tenir la batterie de la maison (`vehicules.py`).
- **`ucaness.definir_image_vehicule`** : image de la voiture (adresses servies par Home Assistant seulement).
- **Carte `custom:ucaness-vehicle-card`** : silhouette dessinée (six gabarits : citadine, compacte, berline, SUV, grand SUV, utilitaire) ou photo détourée, bouton photo mis en avant dans le navigateur (modèle u2netp facultatif, `tools/vehicules/installer_detourage.sh` ; sinon fond uni), charge et objectif, plan de recharge. Sept langues.

### Intégration 0.6.0 : offres par pays
- **Formule « plages »** dans le moteur d'offres (`tarifs.py`) : plusieurs niveaux de prix, plages horaires par type de jour (ouvré, samedi, dimanche et férié) et par heure légale (été, hiver) ; recharge réseau estimée dans le niveau le moins cher ; prix hors taxes signalés ; grille datée signalée une fois périmée ; puissances non entières (3,45 kVA).
- **Catalogue par pays** (`catalogue.py`), choisi d'après le pays réglé dans Home Assistant :
  - Espagne : grille 2.0TD (pointe 10h-14h et 18h-22h, plein 8h-10h, 14h-18h et 22h-24h, vallée 0h-8h ; week-end et fériés en vallée) ;
  - Italie : tranches F1, F2, F3 et F1, F23 de l'ARERA ;
  - Portugal : cycle quotidien bi- et tri-horaire (été et hiver), valable jusqu'au 30/06/2027, et tarifs réglementés transitoires de l'ERSE en vigueur depuis le 01/10/2026 (simple, bi-horaire, tri-horaire, 3,45 à 20,7 kVA, hors TVA).
- `ucaness.simuler` : offres de référence, puissance par défaut et paliers de puissance du pays ; réponse avec `pays`.

### Intégration 0.4.1 → 0.5.4
- **0.4.1** : clé d'application livrée avec l'intégration (fournie par UCanpower) ; une clé personnelle, si vous en avez une, passe avant (#14, #16). Texte de l'action `evaluer_offres` lisible par Home Assistant (#17).
- **Offres** : formule **Tempo** dans le moteur d'offres (`tarifs.py`), jours de 6h à 6h, couleurs du jour passées à `evaluer_offres` (`couleurs_tempo`) ou année type 300 bleus, 43 blancs, 22 rouges (#19).
- **0.4.2** : action **`ucaness.simuler`**, simulateur « et si » en calcul seul sur les statistiques de l'enregistreur : `question: contrat` (contrat actuel comparé aux tarifs réglementés heures creuses et Tempo de `catalogue.py`, ramenés à la puissance demandée) et `question: puissance` (pointe prise au réseau chaque jour) (#25).
- **0.5.0 à 0.5.4** : traductions de l'intégration. Français de référence, puis anglais, chinois simplifié, allemand (tutoiement), italien, espagnol, portugais ; test de complétude des clés (#26, #27, #28, #30, #31).

### Cartes 0.5.1 → 0.6.1
- **0.5.1** : carte **Ucan** (`custom:ucaness-ucan-card`) : avatar « pile avec un visage », humeur et niveau de charge, conseil du moment avec boutons de réponse (#20).
- **0.5.2** : carte Ucan lisible dans une colonne de 300 px (#21).
- **0.5.3** : option `floating: true` : Ucan en **bulle de discussion** en bas à droite, devant les cartes, sur toutes les vues (#22).
- **0.5.4** : bulle **déplaçable** (glisser, position gardée par le navigateur, bouton « Replacer ») (#23).
- **0.5.5** : option `simulateur` : questions **« Et si… je changeais de contrat / de puissance ? »** dans la fenêtre d'Ucan, réponse calculée par `ucaness.simuler` (#25).
- **0.6.0 et 0.6.1** : traductions des cartes dans les sept langues (#30, #31).

### Pilotage (`pilotage/packages`)
- `jarvis_batterie.yaml` :
  - **gain réel** : injection lue au compteur de l'onduleur (`sensor.uhome_injection_reseau_totale`), avec repli sur l'estimation ; attribut `injection_source` (#15) ;
  - **Solcast de nuit** : mise à jour seulement après minuit UTC (quota), journal fidèle (#15) ;
  - **jours exceptionnels** écartés de la prévision de consommation (`input_text.jarvis_jours_exceptionnels`), nettoyés au bout de 7 jours (#18) ;
  - **calibration de la durée de charge** : mesure de chaque nuit (charge réelle ÷ charge calculée), médiane des 5 dernières nuits ; facteur appliqué seulement en mode « Automatique » (borné de 0,9 à 1,3) (#18).
- `ucan_conseils.yaml` (nouveau) : conseils d'Ucan tirés des mesures, un seul à la fois, chaque matin, avec mesure de l'effet et pause de 30 jours après deux refus :
  - **machines** (achats en heures pleines la veille) (#20) ;
  - **lavage** (cycle du lave-linge plus gourmand que d'habitude, cycles détectés par une prise mesurée) (#24) ;
  - **veilles** (talon de nuit en hausse, le plus bas des 7 nuits pour écarter le chauffage) (#24).
- `jarvis_secours.yaml` : capteur de vigilance Météo-France trouvé d'office ; choix « niveau de vigilance » (**rouge** par défaut, ou orange et rouge) ; attribut `capteur_vigilance` (#29).
- `jarvis_meteo.yaml` (nouveau, facultatif) : **température extérieure** enregistrée (`sensor.jarvis_temperature_exterieure`), pour la future prévision selon la météo (#29).

### Documentation
- `docs/feuille-de-route.md` : fonctions spécifiées, pas encore développées.
- `docs/ucan-conversation.md` : conversation avec Ucan par un assistant relié à Home Assistant (ha-mcp), en lecture seule.
