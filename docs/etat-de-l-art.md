# État de l'art : pilotage d'une batterie et dimensionnement

Relevé de novembre 2026. Ce document dit ce qui existe déjà, ce que ce dépôt en reprend et pourquoi il garde son propre moteur.

## 1. Pilotage d'une batterie sous tarif variable

| Projet | Licence | Méthode | Onduleurs | Ce que ce dépôt en reprend |
|---|---|---|---|---|
| **EMHASS** (`davidusb-geek/emhass`) | MIT | Programmation linéaire sur un horizon (prix, prévision solaire, charges différables), module complémentaire de Home Assistant ; publie le plan dans des capteurs (`sensor.p_batt_forecast`, `sensor.soc_batt_forecast`). Convention : P_batt > 0 = décharge, < 0 = charge | Aucun en direct : Home Assistant exécute le plan | **Adaptateur** : stratégie « Tarif dynamique (EMHASS) », l'action `ucaness.plages_depuis_plan` traduit le plan en 3 plages de charge |
| **batcontrol** (`MaStr/batcontrol`) | MIT | Boucle de 3 min : décharge permise, décharge évitée, charge forcée sur le réseau, charge solaire limitée ; prix, prévision solaire, consommation | Fronius Gen24, tout onduleur par un pont MQTT | L'idée de **« mettre la batterie de côté »** aux heures bon marché : chez UCanpower, une plage de charge alimente la maison par le réseau et garde la batterie |
| **Predbat** (`springfall2008/batpred`) | Conditions d'usage restrictives (usage personnel) | Prévision de la batterie sur 48 h par créneaux de 30 min, plages de charge et de décharge | GivEnergy, Solis, Huawei, SolarEdge, Fox, Sofar… | Rien du code. Confirme l'approche « horizon 24 à 48 h, plages de charge » |
| PowerSync, sunSale | Variable | Intégrations récentes, plusieurs fabricants | Tesla, SolarEdge, Sungrow… | Rien (non vérifiées sur du matériel, selon leurs auteurs) |

### Pourquoi un moteur intégré en plus d'EMHASS

| Contrainte de l'UHome | Conséquence |
|---|---|
| 3 plages de charge par jour, en heures HHMM sans date ; une plage qui passe minuit en prend deux | Le plan doit tenir dans 3 plages : contrainte native du moteur (`optimiseur.py`), approximée pour EMHASS (on garde les fenêtres qui portent le plus d'énergie) |
| Pas de consigne de puissance ni de SOC cible, seulement le mode et les plages | Un plan « continu » (EMHASS) est arrondi en fenêtres ; le moteur intégré raisonne directement en fenêtres |
| Pendant une plage, le réseau charge la batterie et alimente la maison | Une plage sert aussi à garder la batterie pour les heures chères : décision prise en compte par le moteur |
| Écriture par le cloud, lente (8 à 80 s), 20 écritures par heure au plus | Plages écrites à l'avance et seulement quand elles changent ; mode basculé au début et à la fin des plages |
| Pas de décharge vers le réseau (règle de ce dépôt) | Aucune action de décharge dans le modèle |

Le moteur intégré : **programmation dynamique** sur le stock (discrétisé, interpolation linéaire), deux actions par créneau (autoconsommation ou plage de charge), nombre de plages dans l'état. Exact pour ce modèle, sans dépendance, quelques dixièmes de seconde pour 48 h au quart d'heure. Valeur du stock restant en fin d'horizon : prix le plus bas de l'horizon ÷ rendement (on ne charge jamais « pour le stock »).

## 2. Prix dynamiques en France

| Élément | État en novembre 2026 |
|---|---|
| Offres au prix horaire pour les particuliers | Sobry (SoFlex, variante plafonnée SoCap) et Frank Énergie (Contrat dynamique, sans plafond) |
| Fournisseurs obligés (plus de 200 000 clients) | Régime transitoire de la CRE prolongé jusqu'au 30 juin 2027 (délibération n° 2026-128) : les offres à effacement comptent encore comme « tarification dynamique » |
| Source des prix de marché dans Home Assistant | Intégration officielle **Nord Pool** (zone FR, action `nordpool.get_prices_for_date`, prix du lendemain vers 13h, pas de 15 min géré) ; ENTSO-E (intégration communautaire, clé gratuite) |
| Prix payé | Prix de marché + frais du fournisseur + acheminement + taxes, puis TVA : à paramétrer dans les entrées du package (`jarvis_dynamique.yaml`) selon la grille du fournisseur |

## 3. Dimensionnement solaire et batterie

| Outil | Licence | Apport | Usage dans ce dépôt |
|---|---|---|---|
| **PVGIS** (Commission européenne, JRC) | Données libres | Production heure par heure sur des années réelles (`seriescalc`), outil hors réseau (`SHScalc`) | Source de production de `tools/dimensionnement/` |
| **pvlib** | BSD-3 | `pvlib.iotools.get_pvgis_hourly` : appel PVGIS et mise en forme | Téléchargement PVGIS |
| **BREOS** | BSD-3 | Simulation PV + batterie, vieillissement (SOH), économie, dimensionnement multi-objectif (NSGA-II) | Contre-vérification facultative du bilan et de l'usure de la batterie |
| Travaux universitaires (autoconsommation et autosuffisance) | — | Relation entre taille du solaire, de la batterie et taux d'autonomie ; effet de la limite d'injection | Méthode : courbe d'autonomie par combinaison, année la plus défavorable |

Choix de `tools/dimensionnement/` : moteur propre (numpy) vectorisé sur toute la grille « solaire × batterie », plusieurs années PVGIS rejouées sur la consommation réelle, recherche exacte de la batterie qui supprime tout achat, contraintes du matériel UHome (solaire admis, extension de 5,12 à 40,96 kWh, puissance de la sortie de secours).

## Sources

- EMHASS : https://github.com/davidusb-geek/emhass et https://emhass.readthedocs.io/en/latest/plan_output_schema.html
- batcontrol : https://github.com/MaStr/batcontrol
- Predbat : https://springfall2008.github.io/batpred/what-does-predbat-do
- Nord Pool (Home Assistant) : https://www.home-assistant.io/integrations/nordpool et https://www.home-assistant.io/actions/nordpool.get_prices_for_date/
- CRE, délibération n° 2026-128 du 17 juin 2026 : https://www.cre.fr/fileadmin/Documents/Deliberations/2026/260617_2026-128_Mise_a_jour_regime_transitoire_OTD.pdf
- Offres dynamiques (novembre 2026) : https://www.fournisseurs-electricite.com/contrat-electricite/abonnement/tarification-dynamique
- PVGIS, service non interactif : https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/api-non-interactive-service_en
- pvlib : https://pvlib-python.readthedocs.io/en/stable/_modules/pvlib/iotools/pvgis.html
- BREOS : https://pypi.org/project/breos/
