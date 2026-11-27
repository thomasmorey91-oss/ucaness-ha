# Tableau de bord « UCANESS HOME ASSISTANT »

Un tableau de bord Home Assistant qui prolonge le portail UCANESS : même police, mêmes cartouches de panneau, mêmes couleurs, et la vue en direct de la maison au centre. Autour, le pilotage des appareils de la maison ; dans un second onglet, tout ce qui concerne la batterie.

![Aperçu avec des valeurs inventées](apercu.jpg)

| Onglet | Contenu |
|---|---|
| **Maison** | Au centre, la maison en direct : solaire, réseau, onduleur, batterie et consommation, avec des flux animés dans le sens de l'énergie. Autour, vos appareils : climatisation, eau chaude, piscine, volets, portail et garage, sécurité, caméras, prises mesurées |
| **Batterie** | Production et consommation (tableau de bord Énergie), charge de la batterie, conditions du jour (mode, heures creuses, prévision solaire), détails de l'onduleur, puissances sur 24 h, charge et décharge par jour, santé, pilotage de nuit |

Depuis la version 0.5.0 des cartes : panneaux arrondis et boutons en relief, animations discrètes (apparition en cascade, chiffres qui défilent, anneau de charge avec halo, graphiques qui se tracent), ambiance de jour et de nuit qui suit le soleil, ciel en fond selon la météo, et une vue 3D de la maison en direct sans pastilles (§ 4 et `MAISON.md`). Les cartes de l'écran de téléphone (en-tête compact, navigation en bas, chiffres clés, décision de la nuit, graphique heure par heure) sont aussi fournies (§ 4).

## 1. Contenu du dossier

| Fichier | Rôle |
|---|---|
| `www/ucaness/ucaness-cards.js` | Cartes personnalisées, en un seul fichier, sans dépendance ni compilation |
| `www/ucaness/maison-exemple.svg` | Maison d'exemple affichée tant que vous n'avez pas mis la vôtre |
| `www/ucaness/ciel/` | Huit ciels en fond (jour, nuages, pluie, orage, coucher, nuit claire, nuit couverte, nuit d'orage), images originales calculées, sans photo d'origine |
| `www/ucaness/fonts/` | Police Tinos (métriquement identique à Times New Roman), servie localement |
| `themes/ucaness.yaml` | Thème « UCANESS » pour les cartes standard de Home Assistant |
| `dashboards/ucaness-home-assistant.yaml` | Le tableau de bord (deux onglets), en mode YAML |
| `tools/maison_iso.py`, `tools/maison-exemple.json` | Générateur de maison isométrique (voir `MAISON.md`) |
| `MAISON.md` | Prérequis et méthode pour afficher **votre** maison au centre |
| `tests/` | Aperçu hors Home Assistant et tests |

## 2. Prérequis

| Élément | Remarque |
|---|---|
| Home Assistant 2026.x | Cartes standard utilisées : `tile` (avec fonctions), `entities`, `history-graph`, `statistics-graph`, cartes Énergie, `weather-forecast`, `picture-entity` |
| Intégration `ucaness` (ce dépôt) | Entités renommées en `sensor.uhome_*` (§ 3, étape 5) |
| Tableau de bord Énergie configuré | Pour les panneaux Production et Consommation de l'onglet Batterie (voir le README principal, § 3) |
| Packages de pilotage (`pilotage/`) | Facultatifs : panneau « Pilotage de nuit », plancher et capacité de l'anneau de charge, heures creuses et prix |
| Prévision Solcast, intégration météo | Facultatives : lignes « Solaire prévu » et carte météo |

## 3. Installation

1. **Fichiers.** Copier `www/ucaness/` dans `config/www/ucaness/` (application « Samba share » ou « File editor »). Le dossier `www` est servi à l'adresse `/local/`.
2. **Ressource.** Paramètres → Tableaux de bord → ⋮ → Ressources → Ajouter une ressource :
   - URL : `/local/ucaness/ucaness-cards.js?v=0.5.5`
   - Type : module JavaScript

   Changer le numéro après `?v=` à chaque mise à jour du fichier, pour forcer les navigateurs à le recharger.
3. **Thème.** Copier `themes/ucaness.yaml` dans `config/themes/`, avec dans `configuration.yaml` :
   ```yaml
   frontend:
     themes: !include_dir_merge_named themes/
   ```
   Le tableau de bord applique le thème à ses deux onglets (`theme: UCANESS`) sans changer celui du reste de Home Assistant.
4. **Tableau de bord.** Copier `dashboards/ucaness-home-assistant.yaml` dans `config/dashboards/`, puis dans `configuration.yaml` :
   ```yaml
   lovelace:
     dashboards:
       ucaness-maison:
         mode: yaml
         title: UCANESS
         icon: mdi:home-lightning-bolt
         show_in_sidebar: true
         filename: dashboards/ucaness-home-assistant.yaml
   ```
   Le nom `ucaness-maison` donne l'adresse des onglets (`/ucaness-maison/maison`, `/ucaness-maison/batterie`). Si vous en choisissez un autre, changez aussi les `path` des onglets dans l'en-tête.
5. **Entités.** Sur une installation neuve de l'intégration, les entités portent déjà l'identifiant attendu. Sur une installation plus ancienne, les renommer (Paramètres → Entités, champ « ID de l'entité ») : celles du tableau `pilotage/README.md` (étape 2), plus :

   | Entité d'origine | ID attendu |
   |---|---|
   | UCANESS : puissance solaire | `sensor.uhome_puissance_solaire` |
   | UCANESS : tension solaire | `sensor.uhome_tension_solaire` |
   | UCANESS : tension réseau | `sensor.uhome_tension_reseau` |
   | UCANESS : fréquence réseau | `sensor.uhome_frequence_reseau` |
   | UCANESS : tension batterie | `sensor.uhome_tension_batterie` |
   | UCANESS : courant batterie | `sensor.uhome_courant_batterie` |
   | UCANESS : santé batterie (SOH) | `sensor.uhome_sante_batterie` |
   | UCANESS : température onduleur | `sensor.uhome_temperature_onduleur` |
   | UCANESS : charge batterie totale | `sensor.uhome_charge_batterie_totale` |
   | UCANESS : décharge batterie totale | `sensor.uhome_decharge_batterie_totale` |

   Une entité absente n'empêche pas l'affichage : la valeur est remplacée par « — ».
6. **Vos appareils.** Les entités marquées `# EXEMPLE` dans le fichier YAML (climatisation, ballon, piscine, volets, portail, alarme, caméra, prises) sont à remplacer par les vôtres. Supprimez les cartes des appareils que vous n'avez pas.
7. **Votre maison.** Voir `MAISON.md`.
8. Vérifier la configuration, redémarrer Home Assistant, puis ouvrir « UCANESS » dans la barre latérale.

## 4. Cartes

### `custom:ucaness-layout-card`

| Option | Défaut | Rôle |
|---|---|---|
| `header` | — | Options de l'en-tête (ci-dessous) |
| `columns` | obligatoire | Liste de colonnes : `width` (`300px`, `1fr`…) et `cards` |
| `gap` | `12px` | Espace entre les colonnes |
| `mobile_breakpoint` | `900` | Largeur (px) sous laquelle tout passe sur une colonne |
| `mobile_first_column` | colonne du milieu | Colonne affichée en premier sur téléphone |
| `sky` | `true` | Ciel en fond et ambiance jour / nuit (§ « Ambiance »). `false` : fond bleu uni |
| `sun_entity` | `sun.sun` | Soleil : la nuit commence quand il passe sous l'horizon |
| `weather_entity` | `weather.maison`, sinon la première entité météo | Temps qu'il fait, pour le ciel |

### `custom:ucaness-header-card`

| Option | Rôle |
|---|---|
| `title`, `site` | Titre du bandeau, nom affiché à gauche |
| `tabs` | Onglets : `title`, `path`, et `entity` facultative dont la valeur s'affiche dans l'onglet |
| `connectivity_entity` | Capteur binaire de liaison (icône verte ou rouge) |
| `alert_entities` | Capteurs binaires comptés dans la pastille d'alertes quand ils sont à « on » |
| `subtitle` ou `subtitle_entity` | Texte sous l'heure |
| `weather_entity`, `weather` | Pictogramme et température à côté de l'heure (`weather: false` pour les masquer) |

### `custom:ucaness-panel-card`

| Option | Rôle |
|---|---|
| `title`, `cards` | Titre du cartouche et cartes contenues |
| `slides`, `interval` | Carrousel : liste de `{title, cards}` qui défilent toutes les `interval` secondes (8 par défaut, 0 pour arrêter). Après un choix manuel, le défilement reprend à zéro |
| `tabs` | `true` : les `slides` deviennent des onglets nommés en haut du panneau (`tab` pour le nom, `icon` facultative, `cards`), le titre `title` reste fixe et rien ne défile seul |
| `status_entity` | Valeur affichée à droite du cartouche |

### `custom:ucaness-flow-card`

| Option | Défaut | Rôle |
|---|---|---|
| `image` | `maison-exemple.svg` | Image de la maison (voir `MAISON.md`) |
| `aspect_ratio` | `1.45` | Largeur / hauteur de la carte |
| `image_area` | `{x: 0, y: 6.5, w: 100}` | Position et largeur de l'image, en % de la carte |
| `min_power` | `30` | En dessous (W), un flux est considéré au repos (pointillés gris) |
| `calibration` | `false` | Grille de calage graduée en % |
| `nodes` | voir ci-dessous | `solar`, `grid`, `inverter`, `battery`, `home` |

Chaque nœud accepte `entity`, `x` et `y` (en % de la carte), `label`, `details` (entités affichées à côté, par exemple tension et courant), `details_side` (`left` ou `right`), `invert` (inverse le signe de la puissance) et `path` (tracé imposé, liste de points `[x, y]` en %). Le nœud `battery` prend aussi `soc_entity`.

Conventions de signe de l'intégration : batterie positive en charge, réseau positif en soutirage. Un appui sur une boule ouvre la fiche de l'entité.

**Vue 3D (`scene: 3d`, cartes 0.5.0).** Plus aucune pastille : chaque élément est l'objet dessiné, avec ses chiffres écrits à côté. Les panneaux du toit s'illuminent quand ils produisent ; une colonne UHome (onduleur et trois modules de batterie, jauge de charge sur le flanc) change de couleur selon l'état (cyan en charge, orange en décharge) ; une ampoule représente la maison, le poteau le réseau, une borne facultative la recharge du véhicule. Les flux n'ont pas de flèches : le défilement des tirets montre le sens, et ils sont plus serrés et plus rapides quand la puissance augmente. Trajets colorés : soleil orange, recharge bleue, maison verte, réseau orange ; pointillés gris au repos. Toutes les positions sont en % de la carte (calage : `MAISON.md`, § 3 b).

| Option | Rôle |
|---|---|
| `scene` | `3d` pour la vue 3D ; absente, la vue à pastilles |
| `nodes.solar` | `x`, `y` (chiffres), `align` (`right` par défaut), `routes` (un ou plusieurs trajets des panneaux vers l'UHome), `glow` (`[cx, cy, rx, ry, angle]` : lueur sur chaque champ de panneaux, `rx` et `ry` en % de la largeur), `leader` (pointillé des chiffres vers les panneaux) |
| `nodes.grid` | `x`, `y`, `align` (`left`), `route` (du haut du poteau vers l'UHome ; une onde part du poteau quand le courant passe) |
| `nodes.battery` | `x`, `y`, `align` (`right`) pour les chiffres, `uhome: {x, y, w}` (coin haut gauche et largeur de la colonne) |
| `nodes.home` | `x`, `y`, `align` (`right`), `route` (de l'UHome vers l'ampoule), `bulb: {x, y, w}` |
| `ev` | Facultatif : `entity` (puissance de charge), `state_entity`, `name`, `x`, `y`, `align`, `route`, `borne: {x, y, w}`, `state_names` (traductions des états) |
| `mode_entity` | Mode de l'onduleur, écrit en clair sous l'UHome (`sensor.uhome_mode`) |
| `battery_path` | Page ouverte par un appui sur l'UHome (sinon, la fiche de la charge) |
| `label_scale` | Taille des chiffres (1 par défaut) |
| `details` | `false` : sans tensions ni fréquence. Sous 520 px de large, seuls les noms et les puissances restent |

### Cartes de l'écran de téléphone

| Carte | Rôle et options principales |
|---|---|
| `custom:ucaness-app-card` | Écran complet dans une vue `panel: true` : en-tête compact (lieu, météo, titre, alertes, heure), cartes en une colonne, navigation collée en bas. `site`, `alert_entities` (entité, ou `{entity, alert_state, name}`), `nav` (`title`, `icon`, `path`, `badge_entities`), `cards`, `wide_redirect: {min_width, path}` (sur grand écran, ouvre plutôt le tableau complet ; `?mobile` dans l'adresse l'empêche), `sky`, `sun_entity`, `weather_entity` |
| `custom:ucaness-status-card` | « Tout va bien » en vert, ou les alertes en cours en rouge (`alert_entities`) ou en orange (`notice_entities`) ; `ok_text`, `info_template` (texte à droite) |
| `custom:ucaness-stats-card` | Deux à quatre chiffres côte à côte : `items` (`name`, `entity`, `attribute`, `unit`, `digits`, `color`, `sub` ou `sub_template`, `value_template`, `navigation_path`) |
| `custom:ucaness-info-card` | Une phrase calculée (`template`, `title` ou `title_template`, `icon`), lien facultatif (`navigation_path` ou `entity`) |
| `custom:ucaness-shortcuts-card` | Raccourcis icône et nom (`items` : `name`, `icon`, `color`, `navigation_path` ou `entity`) ; un raccourci dont l'entité n'existe pas est masqué ; la tuile se remplit de cyan quand l'appareil est allumé |
| `custom:ucaness-detail-card` | Une décision en clair : `title` ou `title_template`, `aside_template`, `headline` ou `headline_template`, `template` ; `details` (petit markdown) affiché par « Pourquoi ? » ; `buttons` (`name`, `icon`, `entity`, `navigation_path`, ou `logbook` pour déplier le journal écrit sous ce nom, avec `logbook_entities`, `days`, `limit`). La carte se retourne quand la décision change |
| `custom:ucaness-hours-card` | Graphique de la journée heure par heure, avec un choix en haut : `tabs` (`name`, `statistic`, `stat_type`, `kind: line`, `unit`, `color`, `digits`, `min`, `max`, `hours: auto`, `total_label`, `forecast_entity` et `forecast_attribute`, `forecast_key`, `forecast_label`, `floor_entity`). Les barres poussent en cascade, la courbe se trace avec un dégradé dessous ; un appui sur une heure affiche sa valeur dans une bulle |

`custom:ucaness-soc-card` accepte aussi `compact: true` (petit anneau, réserve et énergie utilisable à droite), avec `title`, `mode_entity` et `simulation_entity`.

### `custom:ucaness-ucan-card` (0.5.1)

Ucan, la batterie UHome avec un visage, et son conseil du moment (package `pilotage/packages/ucan_conseils.yaml`). L'écran du module du haut change d'expression : orange « à surveiller » si une alerte de `alert_entities` est en cours, « un conseil » si `sensor.ucan_conseil` en propose un, yeux fermés quand le soleil est couché (`sun.sun`), sourire sinon. Les barres des trois modules s'allument avec la charge (`soc`, `sensor.uhome_soc` par défaut : au-dessus de 0, 33 et 66 %). Le conseil s'affiche dans une bulle (constat, geste, gain, avertissement) avec trois boutons : « Je le fais », « Pas maintenant », « Ne plus proposer », envoyés à `script.ucan_conseil_reponse`. Options : `conseil`, `soc`, `script`, `alert_entities`, `compact: true` (petit avatar, pour une colonne de 300 px ou le téléphone). Dans une colonne étroite, la bulle passe sous l'avatar (0.5.2). `floating: true` (0.5.3) : Ucan devient un bouton rond en bas à droite de l'écran, devant les cartes, comme une fenêtre de discussion ; un appui ouvre le conseil, la croix ou Échap le referme ; une pastille et un léger battement signalent un conseil ou une alerte (sans animation en mode allégé ou si l'appareil demande moins de mouvement). `offset_bottom` et `offset_right` (px, 20 par défaut) le décalent, par exemple au-dessus de la barre de navigation du téléphone. Placée n'importe où dans la page, la carte n'y prend aucune place. Depuis la 0.5.4, la bulle se déplace en la faisant glisser (souris ou doigt) si elle cache quelque chose ; la position est gardée sur cet appareil, et « Replacer » dans la fenêtre la remet à sa place d'origine. Depuis la 0.5.5, l'option `simulateur` (`puissance_actuelle_kva`, `abonnement_actuel_eur_an`, `jours`, 30 par défaut) ajoute dans la fenêtre deux questions « Et si… je changeais de contrat ? » et « … de puissance ? » : l'action `ucaness.simuler` calcule sur les mesures de la maison, sans rien appliquer, et Ucan répond dans la fenêtre.

### `custom:ucaness-note-card`

Texte replié sur quelques lignes et terminé par « … » : le module garde la taille des autres. Un appui sur le texte ou sur « … » le déplie en entier, « Réduire » le replie. Un texte assez court pour tenir s'affiche normalement, sans « … ». Un lien dans le texte s'ouvre sans le déplier.

Pour l'utiliser, remplacer `type: markdown` par `type: custom:ucaness-note-card` en gardant `content:`.

| Option | Défaut | Rôle |
|---|---|---|
| `content` | — | Texte markdown (modèles acceptés, comme dans une carte markdown) |
| `card` | — | À la place de `content` : n'importe quelle autre carte à replier |
| `lines` | `4` | Nombre de lignes visibles, texte replié |
| `mobile_lines` | `lines` | Nombre de lignes visibles sous 900 px de large |

```yaml
- type: custom:ucaness-note-card
  lines: 4
  content: |-
    #### Une journée de la batterie
    ...
```

### `custom:ucaness-soc-card`

Options : `soc_entity`, `power_entity`, `floor_entity` ou `floor` (%), `capacity_entity` ou `capacity` (kWh). Par défaut, les entrées des packages de pilotage. L'anneau est en dégradé : cyan en charge, orange en décharge, vert au repos, avec un halo qui bat d'autant plus vite que la puissance est forte.

### Ambiance : jour, nuit et ciel

- **Jour et nuit.** L'interface passe en tons plus sombres (panneaux plus foncés, filets des cartouches ambrés) quand le soleil (`sun.sun`) passe sous l'horizon, en fondu de 1,4 s. Autour du coucher (soleil entre −4° et 6°, beau temps ou nuageux), le ciel est doré.
- **Ciel.** Une image derrière tous les panneaux, sous un voile bleu nuit, selon l'entité météo : `sunny`, `clear-night` → beau ; `partlycloudy`, `cloudy`, `fog` → nuageux ; `rainy`, `pouring`, `snowy-rainy` → pluie (avec pluie animée) ; `lightning`, `lightning-rainy` → orage (avec une lueur d'éclair).
- **Aperçu** sans rien changer dans Home Assistant : `?ambiance=nuit` (ou `jour`), `?meteo=beau|nuageux|pluie|orage`, `?coucher=1` à la fin de l'adresse. Affichage seulement, sur cet appareil.

### Animations

Apparition des cartes en cascade et vague cyan à l'ouverture d'un écran ; chiffres qui défilent jusqu'à la nouvelle valeur ; boutons en relief qui s'enfoncent au clic avec une onde cyan (le survol n'existe qu'avec une souris). Seules la position et l'opacité sont animées. Tout est coupé si l'appareil demande moins de mouvement (réglage d'accessibilité du système).

### Mode allégé

Sur une tablette peu puissante, ajouter `?leger=1` à l'adresse du tableau de bord (par exemple `/ucaness-maison/maison?leger=1`) : ni flou, ni vague, ni retournement (fondu à la place), ciel figé, aucune animation continue sauf les flux de la maison en direct. Le choix est mémorisé sur l'appareil ; `?leger=0` le retire. Les cartes ne se redessinent que lorsque leurs propres entités changent ; la vue 3D ne redessine ses flux que si leur état ou leur allure change.

## 5. Sécurité

- **Confirmations.** Le portail, la porte de garage et le mode de pilotage de la batterie s'actionnent par un appui avec confirmation. N'ajoutez pas de boutons rapides (`features`) sur ces cartes : ils agissent sans confirmation.
- **Fichiers publics.** Tout ce qui est dans `config/www` est lisible sans mot de passe à l'adresse `/local/…` par quiconque atteint votre Home Assistant. N'y mettez rien de confidentiel (voir `MAISON.md`, § 4).
- **Caméras.** Respectez la vie privée des voisins et des personnes filmées.

## 6. Aperçu sans Home Assistant

```bash
cd dashboard
python -m http.server 8765
# puis ouvrir http://localhost:8765/tests/apercu.html
```

L'aperçu utilise des valeurs inventées et remplace les cartes standard par des lignes simples. `tests/cartes.html` montre de la même façon le texte repliable et le panneau à onglets, `tests/scene.html` la vue 3D, le ciel et les cartes du téléphone (`?ambiance=nuit`, `?meteo=orage`, `?leger=1` pour essayer).

## 7. Tests

```bash
pip install -r requirements_test.txt playwright==1.63.0   # depuis la racine du dépôt
python -m playwright install chromium
pytest -p no:homeassistant -p no:socket dashboard/tests -q
```

Les tests vérifient le fichier YAML, la cohérence entre le tableau de bord, les cartes et la liste des entités, le générateur de maison, l'absence de données personnelles dans le dossier, la version annoncée de la ressource, et le rendu des cartes dans Chrome : flux, carrousel, onglets, texte repliable (ordinateur et téléphone), redessin limité, mode allégé, vue 3D (flux selon l'état, sens du réseau, chiffres, appui sur l'UHome), ciel et ambiance jour / nuit, réduction des animations, cartes du téléphone (ignoré si Playwright n'est pas installé).

## 8. Licences et marques

Code et ciels de `www/ucaness/ciel/` : MIT (fichier `LICENSE` du dépôt). Police Tinos : SIL Open Font License 1.1 (`www/ucaness/fonts/OFL-Tinos.txt`). UCANESS est le nom du portail d'UCanpower ; ce tableau de bord en reprend la présentation pour s'y intégrer.
