# Afficher votre maison au centre du tableau de bord

La carte `ucaness-flow-card` pose les boules (solaire, réseau, batterie, maison), l'onduleur et les flux sur une image. Par défaut, c'est une maison d'exemple. Ce guide décrit l'image à préparer, trois façons de l'obtenir et le calage des boules.

## 1. L'image attendue

| Critère | Attendu | Pourquoi |
|---|---|---|
| Point de vue | Vue de trois quarts en plongée (environ 30°), depuis l'angle entre les deux façades qui montrent le mieux les panneaux | C'est la vue du portail UCANESS ; les flux restent lisibles |
| Cadrage | Maison centrée, sur 60 à 75 % de la largeur ; le haut de l'image (environ 15 %) dégagé | Les boules Solaire et Réseau se placent au-dessus du toit, Batterie et Maison en bas |
| Proportions | Environ 3 : 2 (paysage) | La carte fait 1,45 fois plus large que haute (`aspect_ratio`) |
| Fond | Transparent (PNG, WebP ou SVG), à défaut bleu nuit `#071A3A` | L'image se fond dans le fond du tableau de bord |
| Teintes | Gris-bleu, peu saturées ; panneaux en bleu | Cohérence avec le portail UCANESS et lisibilité des flux verts |
| Taille | 1 200 à 1 600 px de large, moins de 1 Mo | Netteté sur tablette sans ralentir le chargement |
| Contenu | Toits, panneaux solaires (avec leur nombre réel), garage, piscine si vous en avez | Repères utiles pour placer l'onduleur et les flux |
| À exclure | Visages, plaques d'immatriculation, numéro de rue, nom | L'image est accessible sans mot de passe (§ 4) |

## 2. Trois façons d'obtenir l'image

### a. Le générateur fourni (le plus simple)

`tools/maison_iso.py` dessine une maison isométrique dans le style UCANESS à partir d'une description en mètres. Les dimensions se relèvent sur un plan, sur le permis de construire ou en mesurant une vue aérienne (utilisée seulement comme repère : voir § 2 c).

```bash
cd dashboard/tools
cp maison-exemple.json ma-maison.json      # à modifier
python maison_iso.py ma-maison.json ma-maison.svg
```

Le script affiche ensuite les positions conseillées des boules, à recopier dans la carte (§ 3).

Repère : l'axe X va vers la façade visible à **droite**, l'axe Y vers la façade visible à **gauche**, Z vers le haut. Les volumes sont dessinés dans l'ordre de la liste, du fond vers l'avant et du bas vers le haut (un étage se décrit comme un volume posé sur le rez-de-chaussée, avec `z: [3, 6]` par exemple).

| Clé | Contenu |
|---|---|
| `volumes[]` | `x`, `y`, `z` : étendue en mètres, `[début, fin]` |
| `volumes[].toit` | `type` : `4pans`, `2pans-gauche` (pans vers la gauche et l'arrière), `2pans-droite` (pans vers la droite et l'arrière) ou `plat` ; `hauteur` (m), `debord` (m), `acrotere` (toit plat, m) |
| `volumes[].panneaux[]` | Toit en pente : `pan` (`gauche` ou `droite`), `colonnes`, `rangees`. Toit plat : `colonnes`, `rangees`, `incline_vers` (`gauche` ou `droite`) |
| `volumes[].fenetres[]` | `face` (`gauche` ou `droite`), `de` et `a` (m le long de la façade), `bas` et `haut` (m), `eclairee` (vrai ou faux) |
| `volumes[].portes_garage[]`, `parements[]` | Même principe : porte sectionnelle, parement en pierre |
| `volumes[].pergola` | À la place d'un volume : `x`, `y`, `sol`, `hauteur`, `panneaux` (nombre) |
| `piscine`, `arbres`, `poteau`, `sol` | Abords : bassin `x`/`y`, arbres `[x, y, rayon]`, poteau du réseau `[x, y]`, étendue du sol |

### b. Un modèle 3D

Un plan d'architecte en 3D, SketchUp, Blender ou Sweet Home 3D : placez une caméra orthographique (ou une focale longue) en plongée à 30° depuis l'angle des deux façades, fond transparent, puis exportez en PNG. Désaturez les murs vers le gris-bleu pour retrouver l'ambiance du portail.

### c. Une illustration à partir de vos photos

Un illustrateur, ou un outil de génération d'images à partir de vos propres photos, peut produire une vue 3D fidèle. Vérifiez que vous avez le droit d'utiliser l'image obtenue.

Les vues satellite ou 3D des services de cartographie en ligne servent de **repère** pour les proportions et la position des panneaux. Leurs conditions d'utilisation limitent la réutilisation des images elles-mêmes : ne les collez pas telles quelles dans le tableau de bord sans avoir vérifié ces conditions.

## 3. Installer et caler

1. Copier l'image dans `config/www/ucaness/` (par exemple `ma-maison.png`).
2. Dans le tableau de bord, carte `custom:ucaness-flow-card` :
   ```yaml
   - type: custom:ucaness-flow-card
     image: /local/ucaness/ma-maison.png?v=1
     calibration: true
     nodes:
       solar:    {x: 44, y: 11.5}
       inverter: {x: 44, y: 46}
       grid:     {x: 65, y: 11.5}
       battery:  {x: 20, y: 79}
       home:     {x: 60, y: 79}
   ```
3. Avec `calibration: true`, une grille rouge graduée en % s'affiche. Placez :
   - **Solaire** au-dessus du champ de panneaux principal ;
   - **l'onduleur** sur le mur ou le toit, sans cacher les panneaux ;
   - **Réseau** en haut à droite, au-dessus du poteau ou du coffret ;
   - **Batterie** et **Maison** en bas, devant la maison.
4. Si une ligne traverse un endroit gênant, imposez son tracé dans le nœud concerné : `path: [[20, 73], [20, 60], [44, 60], [44, 52]]` (points en %, toujours de la boule vers l'onduleur ; la carte inverse le sens selon le flux).
5. Ajuster si besoin `image_area` (`x`, `y`, `w` en %) pour déplacer ou agrandir l'image, et `aspect_ratio` pour la hauteur de la carte.
6. Retirer `calibration: true`. Après chaque changement d'image, augmenter le numéro `?v=` pour forcer le rechargement.

## 4. Confidentialité

- Les fichiers de `config/www` sont servis **sans authentification** à l'adresse `/local/…`. Si votre Home Assistant est accessible depuis Internet, l'image l'est aussi pour qui connaît son adresse.
- N'y mettez ni visage, ni plaque, ni numéro de rue, ni nom.
- Ne publiez pas l'image ni la description de votre maison dans un dépôt public : elles restent dans votre Home Assistant.

## 5. Liste de contrôle

| Point | Fait |
|---|---|
| Vue de trois quarts en plongée, depuis l'angle des façades aux panneaux | ☐ |
| Fond transparent ou bleu nuit, teintes gris-bleu | ☐ |
| Nombre de panneaux et emplacement conformes à la réalité | ☐ |
| Haut de l'image dégagé pour les boules | ☐ |
| 1 200 à 1 600 px de large, moins de 1 Mo | ☐ |
| Ni visage, ni plaque, ni adresse | ☐ |
| Boules calées, onduleur sans cacher les panneaux, `calibration` retiré | ☐ |
