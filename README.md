# Intégration Home Assistant « UCANESS » (UCanpower UHome)

Version 0.3.0, 21/11/2026. Testée sur un onduleur UHome 6K.

> **Non officielle.** Les mesures sont lues par l'API du portail UCANESS (oss.ucaness.com), qui n'est pas documentée. Le pilotage passe par l'API tierce documentée d'UCanpower (chemins `/api/v1`, clé d'application).
> **Lecture seule par défaut.** L'onduleur n'est piloté que si l'option « Écriture autorisée » est activée, et seulement sur deux points : le mode (autoconsommation ou arbitrage horaire) et les plages de charge. Tout autre réglage (DOD, hystérésis, courant, protections réseau, type de batterie, retour usine, commandes) est refusé par le client avant d'atteindre le réseau (§ 6 et § 8).

## 1. Ce que vous obtenez

**Un appareil « UHome 6K »** dans Home Assistant, avec 51 capteurs et 3 capteurs de surveillance, rafraîchis toutes les 60 secondes.

| Famille | Capteurs |
|---|---|
| Puissances (W) | solaire, MPPT 1, MPPT 2, batterie (charge > 0), maison, réseau estimé (soutirage > 0), onduleur |
| Batterie | SOC, SOH, tension, courant, température batterie, températures de cellule min/max, tensions de cellule min/max, nombre de modules, codes d'alarme et de défaut |
| Onduleur et réseau | tension et fréquence du réseau, tension solaire, températures (onduleur, ambiante, étage PV), courant de fuite (brut), mode et état de fonctionnement |
| Énergie (kWh, compatibles avec le tableau de bord Énergie) | production solaire, soutirage réseau, injection réseau, consommation maison, charge et décharge batterie. Chaque grandeur existe en version « aujourd'hui » et « totale » |
| Réglages de l'onduleur (lus, jamais modifiés) | DOD, hystérésis, courant de charge, puissance de décharge, puissance d'export, plage de charge 1 |
| Surveillance | connexion au cloud (en ligne et données de moins de 15 min), défaut ou alarme batterie, température batterie hors plage de charge (0–50 °C), nombre d'événements dans le journal |

## 2. Tester avant d'installer (recommandé, 5 minutes)

Depuis votre PC, avec Python 3.11 ou plus récent :

```
pip install aiohttp
python tools/ucaness_probe.py
```

Le script demande votre e-mail, votre mot de passe (saisie masquée) et votre **ID EMS**, puis affiche toutes les mesures. Votre ID EMS figure dans le portail UCANESS, encadré « Détails » de votre installation (ligne « ID EMS »).

## 3. Installation dans Home Assistant

1. Copiez le dossier `custom_components/ucaness` dans le dossier `config/custom_components/` de Home Assistant (par l'application « Samba share » ou « File editor », dans Paramètres → Applications ; les « add-ons » ont été renommés « applications » depuis Home Assistant 2026.2).

Compatibilité vérifiée : tests réussis sous Home Assistant 2026.2.3 et 2026.10.4.
2. Redémarrez Home Assistant.
3. Allez dans **Paramètres → Appareils et services → Ajouter une intégration**, puis cherchez « UCANESS ».
4. Saisissez l'e-mail, le mot de passe et l'ID EMS.
5. Facultatif : **Configurer** permet de changer la fréquence d'interrogation (60 s par défaut, 30 s minimum).

**Assistant d'installation.** Une fois la batterie connectée, l'intégration vous guide une étape à la fois vers une installation complète du pilotage : pilotage installé, capacité de la batterie, contrat d'électricité, jours ouvrés, prévision solaire, notifications.
- L'étape suivante apparaît dans **Paramètres → Système → Réparations**, avec la raison de l'étape et un lien vers l'écran où la faire. Elle disparaît d'elle-même une fois faite (à la lecture suivante de l'onduleur), et la suivante prend sa place.
- Le capteur `sensor.ucaness_installation` donne l'état (`a_configurer`, `en_simulation`, `en_service`, `a_verifier`) et, en attributs, la progression, les étapes faites et restantes, l'étape suivante.
- Deux étapes se règlent par un court dialogue, depuis la réparation elle-même (bouton **Réparer**) : « Votre batterie » (capacité proposée d'après le nombre de modules lu, à confirmer) et « Votre contrat » (prix, heures creuses ; l'assistant indique ensuite si la recharge de nuit est rentable chez vous, avant d'enregistrer).
- **Batterie sans panneaux solaires.** Si l'onduleur a déjà mesuré une production, l'assistant sait qu'il y a des panneaux. Sinon il pose la question (étape « Panneaux solaires ») ; sans panneaux, la prévision solaire n'est plus demandée. Attention : les packages de pilotage de nuit exigent encore une prévision solaire pour programmer une recharge ; leur adaptation aux batteries sans panneaux n'est pas faite.
- L'assistant n'installe aucune autre intégration et n'envoie rien à l'onduleur. Il n'enregistre un réglage que lorsque vous validez un écran de questions.

**Réglages du pilotage.** La capacité, le plancher, le rendement, la puissance de charge, la marge, la consommation par défaut et le contrat (type, prix, heures creuses, week-end) sont aussi des entités de l'intégration (`number.ucaness_capacite`, `select.ucaness_type_tarif`, `time.ucaness_hc_debut`…), visibles sur la fiche de l'appareil. Tant que les packages de pilotage lisent leurs entrées (Paramètres → Entrées), il n'y a qu'une valeur par réglage : modifier l'entité met l'entrée à jour, et inversement. Le calcul du pilotage est inchangé. Ces réglages sont masqués dans les diagnostics.
- Les entités lues par le pilotage et par le tableau de bord reçoivent d'emblée leur identifiant (`sensor.uhome_soc`, `sensor.uhome_mode`…) : sur une installation neuve, il n'y a rien à renommer. Une entité déjà enregistrée garde son identifiant.

Tableau de bord Énergie (Paramètres → Tableaux de bord → Énergie) :

| Rubrique | Capteur |
|---|---|
| Consommation du réseau | « Soutirage réseau total » |
| Retour au réseau | « Injection réseau totale » |
| Production solaire | « Production solaire totale » |
| Batterie : énergie entrante / sortante | « Charge batterie totale » / « Décharge batterie totale » |

## 4. Sécurité

- **Votre mot de passe n'est pas stocké en clair.** Home Assistant ne conserve que son empreinte MD5, celle qu'envoie le portail web. Pour ce portail, cette empreinte vaut toutefois un mot de passe : protégez vos sauvegardes Home Assistant.
- **Le jeton de session n'est jamais écrit dans les journaux.** Il est renouvelé automatiquement à son expiration.
- Si UCANESS refuse les identifiants, Home Assistant propose une reconnexion.

## 5. Limites connues

- **La puissance réseau est calculée**, pas mesurée : maison + batterie − solaire. Elle néglige les pertes de l'onduleur.
- **Codes d'alarme à interpréter.** Le pack batterie remonte un « code alarme » brut (actuellement 7), alors que le résumé batterie affiche 0. Seul ce résumé (alarme et défaut) déclenche le capteur « Défaut ou alarme batterie ». Le sens des codes est à demander à UCanpower.
- **Codes défaut 001 à 049 du manuel** : le journal d'événements du portail est vide pour l'instant, il n'a donc pas encore été possible de voir sous quelle forme ils remontent.
- **Rythme d'interrogation** : aucune limite d'appels n'est connue. Le portail web interroge toutes les 10 s ; l'intégration le fait toutes les 60 s par défaut.

## 6. Points d'accès utilisés (tous en lecture)

| Chemin | Usage | Fréquence |
|---|---|---|
| `POST /user/signin` | connexion : `{"sign": e-mail, "password": md5}` qui renvoie un jeton | à l'expiration de la session |
| `POST /device/detail/load` | mesures, compteurs, batterie, onduleur : `{"code": ID EMS, "tz": 3600}` | à chaque cycle (60 s) |
| `POST /device/config` | réglages de l'onduleur : `{"device_id": ID EMS}` | toutes les 30 min |
| `POST /oss/event/info` | journal d'événements | toutes les 5 min |

Serveur : `https://app.ucaness.com`, avec l'en-tête `Authorization: Bearer <jeton>`. Les réponses contiennent `error_code` 2000 si tout va bien, 4018 ou 4031 si la session a expiré, 5032 si les identifiants sont refusés.

Chemins d'écriture repérés sur le portail, **volontairement bloqués** : `/device/settings/update`, `/device/config/update`, `/device/ems/config/save`.

## 7. Tests

Dépendances (Python 3.13) : `pip install -r requirements_test.txt`. Les mêmes commandes tournent dans GitHub Actions à chaque envoi et à chaque demande de fusion (`.github/workflows/tests.yml`) ; le rendu dans Chrome y est facultatif.

```
pytest -p no:homeassistant -p no:socket tests/test_client_and_parser.py   # client et décodage (8 tests)
pytest -p no:homeassistant -p no:socket tests/test_pilotage.py           # signature, garde-fous, écriture et relecture (28 tests)
pytest tests/test_ha_integration.py                                       # dans Home Assistant
pytest -p no:homeassistant -p no:socket tests/test_installation.py       # assistant d'installation
pytest -p no:homeassistant -p no:socket tests/test_tarifs.py             # évaluation des offres d'électricité
pytest -p no:homeassistant tests/test_optimiseur.py                      # moteur du tarif dynamique (20 tests)
pytest tools/dimensionnement/tests -q                                     # analyse et dimensionnement (14 tests)
pytest -p no:homeassistant -p no:socket dashboard/tests -q                # tableau de bord, générateur de maison, rendu dans Chrome (14 tests)
```

Tests du pilotage : voir `pilotage/README.md` (§ Tests).

## 8. Pilotage (versions 0.2 et 0.3)

### Options de l'intégration (Paramètres → Appareils et services → UCANESS → Configurer)

| Option | Rôle |
|---|---|
| Clé et secret d'application | Fournis par UCanpower pour l'API tierce. Le secret n'est jamais réaffiché ; laisser le champ vide garde celui enregistré |
| Écriture autorisée | Interrupteur général, **éteint par défaut**. Sans lui, les actions d'écriture sont refusées |

### Actions

| Action | Effet |
|---|---|
| `ucaness.tester_api` | Lecture seule : identifiant d'appareil de l'API tierce, modèle d'onduleur, mode et plages actuels, réglages enregistrés dans le cloud |
| `ucaness.definir_plages_charge` | Jusqu'à 3 plages de charge (HHMM) ; les autres plages de charge et **toutes les plages de décharge** sont vidées |
| `ucaness.definir_mode` | `autoconsommation` ou `arbitrage_horaire`. Le mode Backup est refusé |
| `ucaness.optimiser_charge` (0.3) | Calcul seul, rien n'est envoyé : à partir des prix par créneau, de la consommation et de la prévision solaire, jusqu'à 3 plages de charge qui minimisent le coût sous un tarif dynamique (`custom_components/ucaness/optimiseur.py`, `pilotage/REGLES.md` § 8) |
| `ucaness.evaluer_offres` | Calcul seul : coût annuel estimé de plusieurs offres d'électricité sur le soutirage mesuré heure par heure, classées par coût (seul critère), avec l'écart par rapport au contrat actuel et un avis sur la puissance souscrite. Formules « base » et « heures pleines / heures creuses ». Avec la capacité utile de la batterie, la recharge de nuit est estimée pour les offres à heures creuses (estimation haute, donnée à côté du coût tel que mesuré) ; la réponse désigne la meilleure offre et dit s'il vaut mieux garder le contrat actuel. Limites dites dans la réponse : pilotage non rejoué heure par heure, Tempo et prix dynamiques non pris en charge, estimation annuelle peu fiable avec peu de jours de mesure. Chaque offre porte la source et la date de son prix ; rien n'est souscrit (`custom_components/ucaness/tarifs.py`) |
| `ucaness.plages_depuis_plan` (0.3) | Calcul seul : traduit le plan batterie d'EMHASS (ou de tout autre moteur) en 3 plages de charge au plus |

Chaque écriture est journalisée, puis relue sur l'onduleur. Si la relecture ne correspond pas, l'action échoue : un script qui enchaîne plages puis mode s'arrête avant de changer de mode.

### Garde-fous

| Garde-fou | Détail |
|---|---|
| Liste blanche | Réglage 1 (mode, valeurs 0 et 1) et réglages 44 à 55 (plages, 0000 à 2359). Tout le reste est refusé |
| Chemins | Seuls `/api/v1/device/list`, `/api/v1/device/config`, `/api/v1/device/status` et `/api/v1/device/settings/update` sont appelables par l'API tierce |
| Fréquence | 2 s au moins entre deux écritures, 20 écritures par heure au plus |
| Envoi | Comme le portail : seuls les réglages qui changent sont envoyés, deux par deux (une plage). Si l'onduleur répond « 5019 Device operation timeout », la configuration est relue pendant 2 min : un réglage relu comme demandé compte comme envoyé (le 5019 arrive aussi sur des envois appliqués) ; ce qui manque est renvoyé réglage par réglage |
| Plages de décharge | Toujours vidées : en arbitrage horaire, une plage de décharge renvoie la batterie sur le réseau |
| Modèle d'onduleur | Écriture permise seulement pour les modèles dont la table du mode et des plages est confirmée : `uhome` (documentation) et `mr` (UHome 6K, confirmé le 18/11/2026 par un enregistrement fait depuis le portail UCANESS et par la table de son formulaire) |
| Relecture | Un réglage absent de la configuration du cloud vaut 0, comme dans le portail. Si le cloud ne garde pas le mode, il est confirmé par le mode affiché par l'onduleur |

### Modes du manuel UHome (V1.9, p. 47 à 50)

| API | Manuel | À retenir |
|---|---|---|
| 0 | Autoconsommation | Mode par défaut |
| 1 | Arbitrage horaire | Charge réseau pendant les plages de charge ; hors plage, la batterie ne sert pas |
| 2 | Backup | Batterie maintenue pleine, y compris sur le réseau ; non utilisé |

## 9. Contenu du dépôt

| Dossier | Contenu |
|---|---|
| `custom_components/ucaness/` | L'intégration |
| `tests/` | Tests de l'intégration |
| `pilotage/` | Packages Home Assistant de pilotage de la batterie (nuit en heures pleines / heures creuses, tarif dynamique, secours), règles et calculs (`pilotage/REGLES.md`), guide d'installation (`pilotage/README.md`), tests. Aucune valeur propre à une installation : tout se règle dans les entrées de Home Assistant |
| `dashboard/` | Tableau de bord « UCANESS HOME ASSISTANT » dans le style du portail UCANESS : maison en direct au centre, pilotage des appareils autour, onglet Batterie (`dashboard/README.md`). Prérequis pour afficher sa propre maison : `dashboard/MAISON.md` |
| `docs/api-ucanpower.md` | Synthèse de l'API tierce UCanpower et constats sur le modèle `mr` |
| `docs/etat-de-l-art.md` | Projets existants (EMHASS, batcontrol, Predbat, PVGIS, pvlib, BREOS), ce que ce dépôt en reprend |
| `tools/` | Sonde en lecture seule à lancer hors de Home Assistant ; `tools/dimensionnement/` : analyse de l'installation et préconisation de solaire et de batterie, jusqu'à l'autonomie totale |

## 10. Licence

MIT, voir le fichier `LICENSE`. Projet indépendant, sans lien avec UCanpower.
