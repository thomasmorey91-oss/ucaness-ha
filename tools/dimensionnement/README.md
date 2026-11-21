# Analyse de l'installation et préconisation de dimensionnement

Outil à lancer une fois, à l'installation ou pour un projet, depuis un PC. Il répond à trois questions :

1. **Que donne l'installation actuelle ?** Autonomie (part de la consommation couverte sans réseau), autoconsommation, achats et revente par mois, cycles de la batterie, heures où elle est pleine ou vide, solaire perdu quand l'onduleur sature, autonomie de la sortie de secours.
2. **Que faudrait-il pour l'autonomie totale ?** Pour chaque puissance solaire, la plus petite batterie qui supprime tout achat au réseau, **même l'année la plus défavorable** parmi les années PVGIS rejouées. Si c'est hors de portée d'une batterie domestique (cas courant en France à cause de l'hiver), l'outil chiffre le stockage saisonnier qu'il faudrait.
3. **Quelle installation viser raisonnablement ?** Le plus petit système (ou le moins coûteux si les coûts sont renseignés) qui atteint 70, 80, 90 ou 95 % d'autonomie l'année la plus défavorable, sur la place disponible, puis l'optimum économique sur 20 ans si le tarif et les coûts sont renseignés.

Le rapport signale les limites du matériel : solaire admis par l'onduleur, capacité maximale de la batterie, heures où la consommation dépasse la puissance de l'onduleur.

## Installation

```bash
pip install numpy pandas pyyaml pvlib      # pvlib : téléchargement PVGIS
pip install breos                          # facultatif : contre-vérification et usure de la batterie
```

## Utilisation

1. Exporter la consommation de la maison heure par heure (au moins un an, hiver compris) :
   - **Home Assistant** : Historique → choisir le capteur de puissance de la maison (par exemple `sensor.uhome_puissance_maison`) sur la période → Télécharger les données (CSV `entity_id, state, last_changed`, unité W) ;
   - **Enedis** : espace client → Mes mesures → Courbe de charge → Télécharger (CSV « Horodate;Valeur », unité W) ;
   - ou tout CSV « date, valeur » en W, kW, Wh ou kWh.
2. Copier `exemple-installation.yaml`, le remplir (toitures, batterie, onduleur, place disponible ; tarif et coûts facultatifs).
3. Lancer :
   ```bash
   python tools/dimensionnement/dimensionnement.py mon-installation.yaml -o rapport.md [--breos]
   ```
   Le rapport Markdown et la grille de toutes les simulations (`rapport.csv`) sont écrits à côté.

Pour un onduleur UHome, les puissances se trouvent dans la fiche technique du manuel (§ 3.3) : puissance de sortie, puissance solaire maximale, puissance de la sortie de secours, puissance de charge selon le nombre de modules de 5,12 kWh, extension jusqu'à 40,96 kWh.

## Données envoyées

Seulement à PVGIS (Commission européenne) : la position, l'inclinaison et l'orientation de chaque toiture. Les réponses sont gardées dans le dossier de cache. La consommation ne quitte pas le PC. Le fichier de configuration et le rapport contiennent des données de votre maison : ne les publiez pas.

## Méthode

| Étape | Détail |
|---|---|
| Production | PVGIS 5.3 (`seriescalc`, via `pvlib.iotools.get_pvgis_hourly`), 1 kWc par toiture, heure par heure sur les années choisies ; chaque année est replacée sur les dates de la consommation (mois, jour, heure) |
| Recalage | Facultatif : rapport entre la production mesurée et la production PVGIS sur la même période |
| Ajout de solaire | Sur les pans les plus productifs, jusqu'à la place indiquée (`kwc_max`) |
| Bilan horaire | La batterie se charge avec le surplus et complète la maison ; puissances bornées par l'onduleur et la batterie ; rendement dans chaque sens ; plancher de décharge |
| Régime établi | Chaque année est simulée deux fois : seule la seconde compte (le stock de fin d'année repasse au début) |
| Autonomie totale | Recherche dichotomique de la plus petite capacité sans aucun achat (tolérance 0,5 kWh par an), toutes années confondues |
| Contre-vérification | BREOS (`simulate_energy_balance`) sur l'installation existante : autonomie et santé de la batterie en fin de période |

Limites : pas de temps d'une heure (les pointes plus courtes ne sont pas vues), pas de pilotage réseau (la recharge en heures creuses ou en tarif dynamique améliore l'économie, pas l'autonomie), vieillissement non compté dans le dimensionnement. Le rapport est une aide au dimensionnement, pas une étude d'installateur.

## Tests

```bash
python -m pytest -q tools/dimensionnement/tests      # données inventées, sans accès réseau
```
