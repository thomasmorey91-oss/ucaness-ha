# Pilotage de nuit d'une batterie UCanpower (packages Home Assistant)

Trois packages Home Assistant qui utilisent l'intégration `ucaness` de ce dépôt pour recharger la batterie en heures creuses, juste ce qu'il faut pour couvrir la maison jusqu'au relais du solaire ou jusqu'aux heures creuses suivantes. Les règles et le calcul sont décrits dans `REGLES.md`.

> **Avertissement.** Ces packages écrivent dans votre onduleur (mode et plages de charge seulement). Vérifiez auprès de votre installateur ou d'UCanpower que l'écriture par l'API ne remet pas en cause votre garantie. Ils démarrent en **mode simulation** : rien n'est envoyé tant que vous ne l'avez pas éteint.

| Fichier | Contenu |
|---|---|
| `packages/jarvis_batterie.yaml` | Calcul de la recharge, décision au début des heures creuses, réévaluation, retour en autoconsommation, mode simulation |
| `packages/jarvis_tarif.yaml` | Tarif paramétrable (Base ou heures pleines / heures creuses), compteurs de soutirage HP/HC |
| `packages/jarvis_alertes.yaml` | Détections de défaut (liaison cloud, défaut batterie, température, SOC figé, production basse, mode inattendu) et notifications |
| `tests/` | Tests du calcul (données inventées) et des scripts dans un vrai Home Assistant |

## Prérequis

| Élément | Remarque |
|---|---|
| Home Assistant récent (testé avec 2026.10 et 2026.11) | Actions `recorder.get_statistics`, `workday.check_date`, `ucaness.*` |
| Intégration `ucaness` (ce dépôt) | Avec la clé et le secret d'application UCanpower, et l'option « Écriture autorisée » cochée pour le mode réel |
| Intégration Workday | Jours ouvrés de votre pays : `binary_sensor.workday_sensor` |
| Prévision solaire Solcast (`BJReplay/ha-solcast-solar`) | Prévisions du jour et du lendemain, attribut `detailedHourly` |
| Application mobile Home Assistant | Pour les notifications (facultatif) |

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
   | UCANESS : puissance MPPT 1 / MPPT 2 | `sensor.uhome_puissance_mppt_1` / `_2` |
   | UCANESS : production solaire aujourd'hui | `sensor.uhome_production_solaire_aujourdhui` |
   | UCANESS : soutirage réseau total | `sensor.uhome_soutirage_reseau_total` |
   | UCANESS : mode de fonctionnement | `sensor.uhome_mode` |
   | UCANESS : code défaut / code alarme batterie | `sensor.uhome_code_defaut_batterie` / `sensor.uhome_code_alarme_batterie` |
   | UCANESS : connexion au cloud | `binary_sensor.uhome_connexion_cloud` |
   | UCANESS : défaut ou alarme batterie | `binary_sensor.uhome_defaut_batterie` |
   | UCANESS : température hors plage de charge | `binary_sensor.uhome_temperature_hors_plage` |
   | Solcast : prévision de demain / d'aujourd'hui | `sensor.solcast_pv_forecast_prevision_demain` / `..._aujourdhui` |

3. Vérifier la configuration, puis redémarrer.
4. Renseigner les entrées (Paramètres → Appareils et services → Entrées) : capacité de la batterie, plancher, puissance de charge, marge, consommation journalière par défaut, tarif (heures creuses, week-end en heures creuses, prix), service de notification. Le détail est dans `REGLES.md`, § 5.
5. Laisser tourner quelques jours en simulation : chaque soir, le journal de bord indique la recharge qui aurait été programmée et pourquoi (entité `sensor.jarvis_recharge_reseau_prevue`).
6. Mode réel : cocher « Écriture autorisée » dans les options de l'intégration UCANESS, puis éteindre « Batterie : mode simulation ». À refaire après chaque redémarrage de Home Assistant.
7. Alertes : renseigner le service de notification, puis allumer « Alertes Jarvis actives ».

## Mesurer avant de régler

| Réglage | Comment le mesurer |
|---|---|
| Puissance de charge | Puissance batterie pendant une plage de charge réseau (souvent bridée par le réglage « puissance réseau » de l'installateur) |
| Plancher | SOC le plus bas atteint une nuit sans recharge |
| Consommation journalière par défaut | Moyenne de « consommation maison aujourd'hui » sur quelques jours ; elle ne sert que pour les heures pas encore mesurées |

## Tests

```bash
# Calcul (Home Assistant, freezegun, pyyaml)
python pilotage/tests/test_calcul.py

# Scripts et automatisations (pytest-homeassistant-custom-component)
cd pilotage/tests && python -m pytest -q test_scripts_pilotage.py
```

Le test de la décision du soir se joue sur la date du jour et doit être lancé avant 23h.
