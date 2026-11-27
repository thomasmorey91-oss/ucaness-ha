# Intégration Home Assistant « UCANESS » (UCanpower UHome)

Version 0.5.4, 27/11/2026. Testée sur un onduleur UHome 6K.

> **Non officielle.** Les mesures sont lues par l'API du portail UCANESS (oss.ucaness.com), qui n'est pas documentée. Le pilotage passe par l'API tierce documentée d'UCanpower (chemins `/api/v1`, clé d'application).
> **Lecture seule par défaut.** L'onduleur n'est piloté que si l'option « Écriture autorisée » est activée, et seulement sur deux points : le mode (autoconsommation ou arbitrage horaire) et les plages de charge. Tout autre réglage (DOD, hystérésis, courant, protections réseau, type de batterie, retour usine, commandes) est refusé par le client avant d'atteindre le réseau (§ 6 et § 8).

## 1. Ce que vous obtenez

**Un appareil « UHome 6K »** dans Home Assistant, avec 51 capteurs et 3 capteurs de surveillance, rafraîchis toutes les 60 secondes, auxquels s'ajoutent le capteur de l'assistant d'installation et 14 réglages du pilotage (§ 3).

| Famille | Capteurs |
|---|---|
| Puissances (W) | solaire, MPPT 1, MPPT 2, batterie (charge > 0), maison, réseau estimé (soutirage > 0), onduleur |
| Batterie | SOC, SOH, tension, courant, température batterie, températures de cellule min/max, tensions de cellule min/max, nombre de modules, codes d'alarme et de défaut |
| Onduleur et réseau | tension et fréquence du réseau, tension solaire, températures (onduleur, ambiante, étage PV), courant de fuite (brut), mode et état de fonctionnement |
| Énergie (kWh, compatibles avec le tableau de bord Énergie) | production solaire, soutirage réseau, injection réseau, consommation maison, charge et décharge batterie. Chaque grandeur existe en version « aujourd'hui » et « totale » |
| Réglages de l'onduleur (lus, jamais modifiés) | DOD, hystérésis, courant de charge, puissance de décharge, puissance d'export, plage de charge 1 |
| Surveillance | connexion au cloud (en ligne et données de moins de 15 min), défaut ou alarme batterie, température batterie hors plage de charge (0–50 °C), nombre d'événements dans le journal |
| Assistant d'installation (0.4) | état de l'installation et étape suivante (`sensor.ucaness_installation`) |
| Réglages du pilotage (0.4) | 9 nombres, 2 heures, 2 interrupteurs et 1 liste (capacité, plancher, contrat, panneaux solaires…) |

**Langues (0.5.0 à 0.5.4).** Les écrans de l'intégration (connexion, options, assistant d'installation, actions), les noms des entités et les messages d'erreur suivent la langue de votre profil Home Assistant : français, anglais, chinois simplifié (0.5.1), allemand (0.5.2 ; tutoiement depuis la 0.5.3, comme le reste de Home Assistant), italien, espagnol ou portugais du Portugal (0.5.4). Toute autre langue s'affiche en anglais. Les cartes du tableau de bord sont traduites dans les mêmes langues (0.6.0, puis 0.6.1 pour l'italien, l'espagnol et le portugais) (`dashboard/README.md`). Restent en français pour l'instant : les textes calculés par le moteur (explications, conseils, résultats des actions `evaluer_offres` et `simuler`) et le pilotage (packages YAML).
- Le français est la langue de référence (`translations/fr.json`) ; `tests/test_traductions.py` vérifie que chaque langue a les mêmes clés et les mêmes paramètres.
- Identifiants : en français, les entités gardent les identifiants d'avant (`sensor.uhome_production_solaire_totale`…). Dans une autre langue, les entités qui n'ont pas d'identifiant fixe prennent un identifiant tiré de leur nom dans cette langue (allemand, anglais…) ou, pour le chinois, du nom anglais (règle de Home Assistant). Les entités lues par le pilotage et le tableau de bord ont un identifiant fixe, quelle que soit la langue.
- `select.ucaness_type_tarif` a désormais pour état `hphc` ou `base` (affichés « Heures pleines / heures creuses » et « Base ») ; l'entrée du package `input_select.jarvis_type_tarif` garde ses textes.

## 2. Tester avant d'installer (recommandé, 5 minutes)

Depuis votre PC, avec Python 3.11 ou plus récent :

```
pip install aiohttp
python tools/ucaness_probe.py
```

Le script demande votre e-mail, votre mot de passe (saisie masquée) et votre **ID EMS**, puis affiche toutes les mesures. Votre ID EMS figure dans le portail UCANESS, encadré « Détails » de votre installation (ligne « ID EMS »).

## 3. Installation dans Home Assistant

1. Copiez le dossier `custom_components/ucaness` dans le dossier `config/custom_components/` de Home Assistant (par l'application « Samba share » ou « File editor », dans Paramètres → Applications ; les « add-ons » ont été renommés « applications » depuis Home Assistant 2026.2).
2. Redémarrez Home Assistant.
3. Allez dans **Paramètres → Appareils et services → Ajouter une intégration**, puis cherchez « UCANESS ».
4. Saisissez l'e-mail, le mot de passe et l'ID EMS.
5. Facultatif : **Configurer** permet de changer la fréquence d'interrogation (60 s par défaut, 30 s minimum).

Compatibilité : tests automatiques sous Home Assistant 2026.2.3 (§ 7), tests réussis aussi sous 2026.10.4 ; version 0.3.0 en service sous Home Assistant 2026.11. La version 0.4.0 n'a pas encore été essayée sur une installation réelle (§ 5).

**Assistant d'installation.** Une fois la batterie connectée, l'intégration vous guide une étape à la fois vers une installation complète du pilotage, en 9 étapes : connexion, pilotage installé, mesures reconnues par le pilotage, capacité de la batterie, panneaux solaires, contrat d'électricité, jours ouvrés, prévision solaire (s'il y a des panneaux), notifications (facultative).
- L'étape suivante apparaît dans **Paramètres → Système → Réparations**, avec la raison de l'étape et un lien vers l'écran où la faire. Elle disparaît d'elle-même une fois faite (à la lecture suivante de l'onduleur), et la suivante prend sa place.
- Le capteur `sensor.ucaness_installation` donne l'état (`a_configurer`, `en_simulation`, `en_service`, `a_verifier`) et, en attributs, la progression, les étapes faites et restantes, l'étape suivante.
- Trois étapes se règlent par un court dialogue, depuis la réparation elle-même (bouton **Réparer**) : « Votre batterie » (capacité proposée d'après le nombre de modules lu, à confirmer), « Panneaux solaires » (posée seulement si l'onduleur n'a encore mesuré aucune production) et « Votre contrat » (prix, heures creuses ; l'assistant indique ensuite si la recharge de nuit est rentable chez vous, avant d'enregistrer).
- **Batterie sans panneaux solaires.** Si l'onduleur a déjà mesuré une production, l'assistant sait qu'il y a des panneaux. Sinon il pose la question (étape « Panneaux solaires ») ; sans panneaux, la prévision solaire n'est plus demandée. Le pilotage en est prévenu (« Batterie : panneaux solaires ») et calcule alors la recharge en heures creuses avec une production nulle.
- L'assistant n'installe aucune autre intégration et n'envoie rien à l'onduleur. Il n'enregistre un réglage que lorsque vous validez un écran de questions.

**Réglages du pilotage.** La capacité, le plancher, le rendement, la puissance de charge, la marge, la consommation par défaut, le contrat (type, prix, heures creuses, week-end) et la présence de panneaux solaires (`switch.ucaness_solaire`) sont aussi des entités de l'intégration (`number.ucaness_capacite`, `select.ucaness_type_tarif`, `time.ucaness_hc_debut`…), visibles sur la fiche de l'appareil. Tant que les packages de pilotage lisent leurs entrées (Paramètres → Entrées), il n'y a qu'une valeur par réglage : modifier l'entité met l'entrée à jour, et inversement. Le calcul du pilotage est inchangé. Ces réglages sont masqués dans les diagnostics.
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
- **Codes d'alarme à interpréter.** Le pack batterie peut remonter un « code alarme » brut non nul alors que le résumé batterie affiche 0. Seul ce résumé (alarme et défaut) déclenche le capteur « Défaut ou alarme batterie ». Le sens des codes est à demander à UCanpower.
- **Codes défaut 001 à 049 du manuel** : le journal d'événements du portail est vide pour l'instant, il n'a donc pas encore été possible de voir sous quelle forme ils remontent.
- **Assistant d'installation (0.4.0)** : les liens et les écrans de questions des réparations sont testés dans un Home Assistant de test, pas encore sur une installation réelle.
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
pytest -p no:homeassistant -p no:socket tests/test_client_and_parser.py   # client et décodage (9 tests)
pytest -p no:homeassistant -p no:socket tests/test_pilotage.py           # signature, garde-fous, écriture et relecture (29 tests)
pytest tests/test_ha_integration.py                                       # dans Home Assistant (37 tests)
pytest -p no:homeassistant -p no:socket tests/test_installation.py       # assistant d'installation (28 tests)
pytest -p no:homeassistant -p no:socket tests/test_tarifs.py             # évaluation des offres d'électricité (38 tests)
pytest -p no:homeassistant tests/test_optimiseur.py                      # moteur du tarif dynamique (20 tests)
pytest tools/dimensionnement/tests -q                                     # analyse et dimensionnement (14 tests, dont 1 qui demande le paquet breos)
pytest -p no:homeassistant -p no:socket dashboard/tests -q                # tableau de bord et générateur de maison (10 tests), rendu dans Chrome (15 tests, ignorés sans Chrome)
```

Tests du pilotage : voir `pilotage/README.md` (§ Tests). Un contrôle refuse aussi tout fichier qui contient encore un marqueur de conflit de fusion.

## 8. Pilotage (versions 0.2 à 0.4)

### Options de l'intégration (Paramètres → Appareils et services → UCANESS → Configurer)

| Option | Rôle |
|---|---|
| Clé et secret d'application | **Facultatifs depuis la 0.4.1** : l'intégration est livrée avec une clé d'application fournie par UCanpower (voir ci-dessous). Une clé personnelle complète (clé et secret), si UCanpower vous en a fourni une, passe avant ; vider le champ de la clé revient à la clé livrée. Le secret n'est jamais réaffiché ; laisser son champ vide garde celui enregistré |
| Écriture autorisée | Interrupteur général, **éteint par défaut**. Sans lui, les actions d'écriture sont refusées |

**Clé d'application livrée (0.4.1).** UCanpower a délivré pour cette intégration une paire clé et secret d'application dédiée à Home Assistant, et en a autorisé par écrit la diffusion publique le 27/11/2026 (`custom_components/ucaness/cle_application.py`). Elle identifie l'application, pas un propriétaire : elle ne donne accès à aucun appareil par elle-même. Chaque propriétaire se connecte avec son propre compte UCANESS et n'accède qu'à ses propres appareils. UCanpower limite cette clé aux fonctions dont l'intégration a besoin (connexion, liste des appareils, configuration, état, écriture des réglages) ; ce que l'intégration écrit reste filtré par la liste blanche ci-dessous, UCanpower ne filtrant pas encore les réglages de son côté. Aucune limite d'appels n'est fixée. Le renouvellement de la clé est manuel : si elle devait être révoquée, une nouvelle version de l'intégration la remplacerait, et une clé personnelle saisie dans les options permet de continuer en attendant.

### Actions

| Action | Effet |
|---|---|
| `ucaness.tester_api` | Lecture seule : identifiant d'appareil de l'API tierce, modèle d'onduleur, mode et plages actuels, réglages enregistrés dans le cloud |
| `ucaness.definir_plages_charge` | Jusqu'à 3 plages de charge (HHMM) ; les autres plages de charge et **toutes les plages de décharge** sont vidées |
| `ucaness.definir_mode` | `autoconsommation` ou `arbitrage_horaire`. Le mode Backup est refusé |
| `ucaness.optimiser_charge` (0.3) | Calcul seul, rien n'est envoyé : à partir des prix par créneau, de la consommation et de la prévision solaire, jusqu'à 3 plages de charge qui minimisent le coût sous un tarif dynamique (`custom_components/ucaness/optimiseur.py`, `pilotage/REGLES.md` § 8) |
| `ucaness.evaluer_offres` (0.4) | Calcul seul : coût annuel estimé de plusieurs offres d'électricité sur le soutirage mesuré heure par heure, classées par coût (seul critère), avec l'écart par rapport au contrat actuel et un avis sur la puissance souscrite. Formules « base », « heures pleines / heures creuses » et « tempo » (six prix ; année reconstituée avec 300 jours bleus, 43 blancs et 22 rouges et la consommation moyenne mesurée d'un jour de chaque couleur ; couleurs des jours mesurés facultatives, `couleurs_tempo`). Avec la capacité utile de la batterie, la recharge de nuit est estimée pour les offres à heures creuses et pour Tempo, couleur par couleur (estimation haute, donnée à côté du coût tel que mesuré) ; la réponse désigne la meilleure offre et dit s'il vaut mieux garder le contrat actuel. Limites dites dans la réponse : pilotage non rejoué heure par heure, consommation des jours rouges non déplacée, prix dynamiques non pris en charge, estimation annuelle peu fiable avec peu de jours de mesure. Chaque offre porte la source et la date de son prix ; rien n'est souscrit (`custom_components/ucaness/tarifs.py`) |
| `ucaness.simuler` (0.4.2) | Simulateur « et si », calcul seul sur les mesures de la maison (statistiques de l'enregistreur) : `question: contrat` compare le contrat actuel (réglages du tarif, puissance et abonnement passés) aux offres de référence (`catalogue.py` : tarifs réglementés heures creuses et Tempo, avec source et date du prix) ou aux offres passées ; `question: puissance` dit si la puissance souscrite convient, d'après la pointe prise au réseau chaque jour. Utilisée par la bulle Ucan (« Et si… ») |
| `ucaness.plages_depuis_plan` (0.3) | Calcul seul : traduit le plan batterie d'EMHASS (ou de tout autre moteur) en 3 plages de charge au plus. Réponse : `plages`, `fenetres` (fenêtres datées retenues), `nombre_fenetres` (fenêtres trouvées, depuis la 0.3.1), énergie retenue et écartée |

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

### Modes (manuel UHome V1.9, p. 47 à 50, et constats)

| API | Manuel | À retenir |
|---|---|---|
| 0 | Autoconsommation | Mode par défaut |
| 1 | Arbitrage horaire | Charge réseau pendant les plages de charge. Selon le manuel, hors plage, la batterie ne sert pas. **Constaté sur un UHome 6K (modèle `mr`) : hors plage, la batterie continue d'alimenter la maison** ; le calcul de nuit en tient compte (`pilotage/REGLES.md`) |
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
