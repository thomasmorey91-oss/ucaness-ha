# Journal des changements

Versions de l'intégration (`custom_components/ucaness`) et des cartes du tableau de bord (`dashboard/www/ucaness/ucaness-cards.js`). Les packages de `pilotage/` n'ont pas de numéro : leurs changements sont datés.

## 28/11/2026

### Cartes 0.14.0 : parler à Ucan
- Option `parler` de la bulle d'Ucan : bouton qui ouvre Assist, l'assistant de Home Assistant.

### Cartes 0.13.0 : replay de la journée, trophées
- Bouton « Replay de la journée » dans les outils de la scène : la journée en 30 s depuis les statistiques sur 5 minutes.
- **`custom:ucaness-trophees-card`** : record de production et journées 100 % autonomes, calculés depuis les statistiques horaires.

### Cartes 0.12.0 : scène sur photo
- Option `photos` de la vue 3D : une photo par ambiance (jour, coucher, nuit, couvert, pluie, orage) avec fondu enchaîné.
- Option `nodes.battery.uhome.image` : image de la batterie à la place du dessin.

### Cartes 0.11.0 : outils de la scène, glissement entre vues, cadran
- Scène vivante : menu des animations (gardé sur l'appareil), tiroir d'infos du jour, visite guidée, mode cinéma ; reflet sur le sol mouillé quand il pleut.
- Glissement entre vues sur écran tactile (tablette et téléphone).
- **`custom:ucaness-gauge-card`** : cadran à aiguille.

### Cartes 0.10.0 : bilan du jour, météo des 5 jours, résumé du soir
- **`custom:ucaness-bilan-card`** : autonomie de la journée, soleil, maison, réseau et économie (estimée si aucun capteur ne la donne).
- **`custom:ucaness-forecast-card`** : météo des prochains jours (prévisions quotidiennes de Home Assistant), avec le soleil prévu par jour.
- **Résumé du soir d'Ucan** (`resume` de `custom:ucaness-ucan-card`) : la journée racontée dans la bulle à partir de 20 h.

### Cartes 0.9.1 : liste des appareils dans une page
- **`custom:ucaness-appareils-card`** : la liste automatique des appareils (lecture seule) dans une page existante, un panneau UCANESS par pièce ; refaite quand un appareil est ajouté ou retiré.

### Cartes 0.9.0 : vue « Appareils » automatique
- Stratégie de vue **`custom:ucaness-appareils`** : une carte par appareil reconnu (Appliance Électroménager Cards, facultatives), groupées par pièce ; les nouveaux appareils apparaissent seuls. Réglages : `theme`, `prix`, `exclure`, `appareils`.
- **`custom:ucaness-appareil-card`** : carte rendue inerte (aucune commande), un appui ouvre la fiche de l'appareil. Sept langues.

### Pilotage : vigilance du lendemain pour le secours
- `jarvis_secours.yaml` : « Jarvis risque de coupure » lit aussi l'intégration communautaire **« Vigilance Météo France »** (`sensor.vigilance_<département>_aujourd_hui` et `_demain`, clé gratuite de l'API Météo-France). Un créneau orange ou rouge compte s'il commence dans les 12 h et n'est pas fini ; motif avec l'heure de début ; nouvel attribut `debut`, `fin` = fin du dernier créneau retenu. Capteur trouvé d'office (zone littorale écartée), sinon l'intégration Météo-France d'origine, inchangée.

## 27/11/2026

### Cartes 0.8.0 : scène vivante
- Vue 3D de la maison en direct, option **`vivant: true`** : flux en néon avec points de lumière, modules de l'UHome qui se soulèvent et s'éteignent en veille, étiquette et carte de niveau, bandeau d'événement, Ucan dans la scène (bulle, autonomie estimée, couleur au choix), soleil et lune, oiseaux, étoile filante, arc-en-ciel, neige, fenêtres éclairées la nuit, panneaux dorés et pastille « 100 % autonome », pastille « Seuil réseau ». Rien ne change sans l'option.
- Lueur colorée des chiffres clés.

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
