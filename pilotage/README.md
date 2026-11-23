# Pilotage d'une batterie UCanpower (packages Home Assistant)

Packages Home Assistant qui utilisent l'intégration `ucaness` de ce dépôt :
- **pilotage de nuit** (heures pleines / heures creuses) : recharger la batterie en heures creuses, juste ce qu'il faut pour couvrir la maison jusqu'au relais du solaire ou jusqu'aux heures creuses suivantes ;
- **tarif dynamique** (facultatif) : prix qui change chaque heure ou chaque quart d'heure, plages de charge calculées par le moteur intégré ou par EMHASS ;
- **secours** (facultatif) : alertes et analyse des coupures du réseau, sortie de secours (EPS), risque de coupure.

Les règles et les calculs sont décrits dans `REGLES.md`. Pour analyser l'installation et dimensionner le solaire et la batterie : `../tools/dimensionnement/README.md`.

> **Avertissement.** Ces packages écrivent dans votre onduleur (mode et plages de charge seulement). Vérifiez auprès de votre installateur ou d'UCanpower que l'écriture par l'API ne remet pas en cause votre garantie. Ils démarrent en **mode simulation** : rien n'est envoyé tant que vous ne l'avez pas éteint.

| Fichier | Contenu |
|---|---|
| `packages/jarvis_batterie.yaml` | Calcul de la recharge, décision au début des heures creuses, réévaluation, retour en autoconsommation, mode simulation |
| `packages/jarvis_tarif.yaml` | Tarif paramétrable (Base ou heures pleines / heures creuses), compteurs de soutirage HP/HC |
| `packages/jarvis_alertes.yaml` | Détections de défaut (liaison cloud, défaut batterie, température, SOC figé, production basse, mode inattendu) et notifications |
| `packages/jarvis_dynamique.yaml` | Facultatif. Tarif dynamique : choix de la stratégie, prix TTC (Nord Pool ou capteur personnalisé), plan du moteur intégré ou d'EMHASS, application des plages et du mode (`REGLES.md`, § 8) |
| `packages/jarvis_secours.yaml` | Facultatif. Coupures du réseau : détection, alertes, suivi, bilan, risque de coupure, réserve de secours, bilan au redémarrage ; rien n'est écrit sur l'onduleur (`REGLES.md`, § 9) |
| `tests/` | Tests du calcul (données inventées) et des scripts dans un vrai Home Assistant |

## Prérequis

| Élément | Remarque |
|---|---|
| Home Assistant récent (testé avec 2026.10 et 2026.11) | Actions `recorder.get_statistics`, `workday.check_date`, `ucaness.*` |
| Intégration `ucaness` (ce dépôt) | Avec la clé et le secret d'application UCanpower, et l'option « Écriture autorisée » cochée pour le mode réel |
| Intégration Workday | Jours ouvrés de votre pays : `binary_sensor.workday_sensor` |
| Prévision solaire Solcast (`BJReplay/ha-solcast-solar`) | Prévisions du jour et du lendemain, attribut `detailedHourly` |
| Application mobile Home Assistant | Pour les notifications (facultatif) |
| Tarif dynamique : intégration Nord Pool (officielle) | Ou tout capteur qui publie la liste des prix ; EMHASS pour la stratégie EMHASS |
| Secours : intégration Météo-France | Facultatif, pour la vigilance (`sensor.<département>_weather_alert`) |

## Installation

1. Copier `packages/` dans le dossier `config/` de Home Assistant, puis ajouter dans `configuration.yaml` :
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
2. Renommer les entités (Paramètres → Entités, champ « ID de l'entité ») pour obtenir :

   | Entité d'origine | ID attendu |
   |---|---|
   | UCANESS : charge batterie (SOC) | `sensor.uhome_soc` |
   | UCANESS : température batterie | `sensor.uhome_temperature_batterie` |
   | UCANESS : puissance batterie | `sensor.uhome_puissance_batterie` |
   | UCANESS : puissance maison | `sensor.uhome_puissance_maison` |
   | UCANESS : puissance réseau estimée | `sensor.uhome_puissance_reseau` |
   | UCANESS : puissance MPPT 1 / MPPT 2 | `sensor.uhome_puissance_mppt_1` / `sensor.uhome_puissance_mppt_2` |
   | UCANESS : production solaire aujourd'hui | `sensor.uhome_production_solaire_aujourdhui` |
   | UCANESS : soutirage réseau total | `sensor.uhome_soutirage_reseau_total` |
   | UCANESS : mode de fonctionnement | `sensor.uhome_mode` |
   | UCANESS : code défaut / code alarme batterie | `sensor.uhome_code_defaut_batterie` / `sensor.uhome_code_alarme_batterie` |
   | UCANESS : connexion au cloud | `binary_sensor.uhome_connexion_cloud` |
   | UCANESS : défaut ou alarme batterie | `binary_sensor.uhome_defaut_batterie` |
   | UCANESS : température hors plage de charge | `binary_sensor.uhome_temperature_hors_plage` |
   | UCANESS : tension réseau (secours) | `sensor.uhome_tension_reseau` |
   | UCANESS : état de fonctionnement (secours) | `sensor.uhome_etat` |
   | Solcast : prévision de demain / d'aujourd'hui | `sensor.solcast_pv_forecast_prevision_demain` / `..._aujourdhui` |
   | Solcast : dernière interrogation de l'API, limite, appels utilisés (journal, mises à jour pilotées) | `sensor.solcast_pv_forecast_derniere_interrogation_de_l_api`, `sensor.solcast_pv_forecast_limite_api`, `sensor.solcast_pv_forecast_api_utilisee` (noms créés par Home Assistant en français) |

3. Vérifier la configuration, puis redémarrer.
4. Renseigner les entrées (Paramètres → Appareils et services → Entrées) : capacité de la batterie, plancher, puissance de charge, marge, consommation journalière par défaut, tarif (heures creuses, week-end en heures creuses, prix), service de notification. Le détail est dans `REGLES.md`, § 6.
5. Gain réel : chaque soir, `sensor.jarvis_gain_reel_du_jour` compare le coût réel des 24 dernières heures à l'autoconsommation simple simulée avec les mêmes mesures ; cumuls dans `sensor.jarvis_gain_reel_du_mois` et `sensor.jarvis_gain_reel_de_l_annee`. Les jours sans recharge, il doit rester proche de 0 : l'écart mesure la précision de la simulation.
6. Laisser tourner quelques jours en simulation : chaque soir, le journal de bord indique la recharge qui aurait été programmée et pourquoi (entité `sensor.jarvis_recharge_reseau_prevue`).
7. Mode réel : cocher « Écriture autorisée » dans les options de l'intégration UCANESS, puis éteindre « Batterie : mode simulation ». Par défaut, la simulation revient à chaque redémarrage de Home Assistant ; pour garder le mode réel, allumer « Batterie : garder le mode réel après un redémarrage ».
8. Alertes : renseigner le service de notification, puis allumer « Alertes Jarvis actives ».

## Tarif dynamique (facultatif)

1. Copier aussi `packages/jarvis_dynamique.yaml`. Version de l'intégration `ucaness` : 0.3.0 ou plus (actions `optimiser_charge` et `plages_depuis_plan`).
2. Source des prix : installer l'intégration **Nord Pool** (zone FR) et copier l'identifiant de son entrée (Outils de développement → Actions → « Nord Pool : Get prices for date », choisir l'entrée puis passer en mode YAML : valeur de `config_entry`) dans « Tarif dynamique : identifiant de l'entrée Nord Pool » ; ou choisir « Capteur personnalisé » et indiquer un capteur dont l'attribut `prix` (ou `prices`) est une liste de `{debut, prix}` en EUR/kWh.
3. Renseigner, d'après la grille du fournisseur : « coûts ajoutés au prix de marché » en heures pleines et en heures creuses (EUR/kWh HT : frais du fournisseur, acheminement, taxes) et la TVA. Vérifier `sensor.jarvis_prix_dynamiques` sur une facture.
4. Choisir « Tarif dynamique (moteur intégré) » dans « Pilotage : stratégie de recharge ». Le pilotage de nuit ne programme alors plus rien.
5. Laisser quelques jours en simulation : `sensor.jarvis_plan_tarif_dynamique` (plages, gain estimé, justification) et le journal montrent ce qui aurait été programmé.
6. Stratégie EMHASS : installer EMHASS à part, publier son plan, vérifier les noms des capteurs et des attributs (« EMHASS : … » dans les entrées), puis choisir « Tarif dynamique (EMHASS) ».

Les listes de prix et de plans sont longues : pour alléger la base de données, on peut exclure `sensor.jarvis_prix_marche_nordpool`, `sensor.jarvis_prix_dynamiques`, `sensor.jarvis_plan_tarif_dynamique` et `sensor.jarvis_plan_emhass` de l'enregistreur (`recorder:` → `exclude:`).

## Secours (facultatif)

1. Copier `packages/jarvis_secours.yaml` et renommer `sensor.uhome_tension_reseau` et `sensor.uhome_etat`.
2. Renseigner : « sortie de secours raccordée » (selon le câblage de l'installateur), puissance continue de la sortie de secours (fiche technique, `REGLES.md` § 9), capteur de vigilance Météo-France, et, si Enedis annonce une coupure, ses dates.
3. Facultatif : « garder une réserve avant un risque de coupure » (avec la stratégie « moteur intégré ») et le SOC à garder (80 % par défaut).
4. Pour être alerté pendant une coupure, Home Assistant, la box et le module Wi-Fi de l'onduleur doivent rester alimentés (sortie de secours ou UPS).

## Mesurer avant de régler

| Réglage | Comment le mesurer |
|---|---|
| Puissance de charge | Puissance batterie pendant une plage de charge réseau (souvent bridée par le réglage « puissance réseau » de l'installateur) |
| Plancher | SOC le plus bas atteint une nuit sans recharge |
| Consommation journalière par défaut | Moyenne de « consommation maison aujourd'hui » sur quelques jours ; elle ne sert que pour les heures pas encore mesurées |

## Tests

```bash
# Dépendances, depuis la racine du dépôt (Python 3.13)
pip install -r requirements_test.txt

# Calcul (Home Assistant, freezegun, pyyaml)
python pilotage/tests/test_calcul.py
# Ajouts v7 : repli sans prévision solaire, moyenne pondérée, fourchette P10-P90, gain réel
python pilotage/tests/test_v7.py

# Scripts et automatisations (pytest-homeassistant-custom-component)
cd pilotage/tests && python -m pytest -q test_scripts_pilotage.py test_v7_config.py
# Tarif dynamique et secours
cd pilotage/tests && python -m pytest -q test_dynamique.py test_secours.py
```

Le test de la décision du soir se joue sur la date du jour et doit être lancé avant 23h.
