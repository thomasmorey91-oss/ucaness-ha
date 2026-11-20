# API UCanpower (UCANESS) : synthèse de la documentation officielle

Source : « App与业务平台接口-第三方 » (interface App ↔ plateforme, pour tiers), PDF de 49 pages en chinois daté du 15/03/2025, fourni par UCanpower. Synthèse du 18/11/2026, complétée le 19/11/2026 par des constats faits sur un onduleur UHome 6K.

## Ce que le document confirme

| Sujet | Contenu |
|---|---|
| Objet | Interface pour applications tierces : lire l'état, les données de l'onduleur et de la batterie, l'historique, et **envoyer des paramètres de fonctionnement à l'onduleur** |
| Serveur | `https://app.ucaness.com`, chemins en `/api/v1/…`, requêtes POST en JSON |
| Authentification | Jeton `Bearer` obtenu par `/api/v1/user/signin`, **plus** une signature par requête : `url=<chemin>&app_key=<clé>&timestamp=<s>` signé en HMAC-SHA256 avec l'AppSecret, valable 3 min, placé dans les en-têtes avec `app_key` et `timestamp` |
| Clés d'application | AppKey et AppSecret délivrés **hors ligne uniquement** par UCanpower. Le document fournit une clé de test (non recopiée ici) |
| Limites d'appel | Seul le code HTTP 429 « Too Many Requests » est cité, **sans aucun chiffre** |

## Écriture des réglages de l'UHome

Point d'accès : `/api/v1/device/settings/update`, corps `{"device_id", "inverter_model": "uhome", "pcs": [{"set_id", "set_data"}]}`. Les réglages peuvent être envoyés un par un. Modèles cités par la documentation : `uhome`, `uhc`, `ufox`.

| set_id | Réglage | Plage | Utile au projet |
|---|---|---|---|
| 1 | Mode de fonctionnement | 0 autoconsommation (Self Consume), 1 arbitrage horaire (Peak Shift), 2 priorité batterie (Bat Priority) | Oui |
| 2 | DOD raccordé au réseau | 10 à 90 % | Non (réglage de fond) |
| 3 | Courant de charge | 1 à 170 A selon le type de batterie | Non (réglage de fond) |
| 4 | Puissance d'export (Grid Power) | 0 à 100 % | Non (réglage de fond) |
| 5 | Puissance de décharge | 0 à 100 % | Non (réglage de fond) |
| 14 | Anti-reflux (zéro export) | 0 / 1 | Non |
| 22 | Backup | 0 / 1 | Non |
| 25 | Hystérésis (Bat EodHyst) | 10 à 90 % | Non (réglage de fond) |
| 44 à 55 | 3 plages de charge et 3 de décharge (début, fin) | 0 à 2359 (HHMM) | Oui (plages de charge seulement) |

**À ne jamais envoyer** (réservé à l'installateur, ou destructif) : 8 à 11 (protections tension et fréquence du réseau), 12 (communication batterie), 16 (type de batterie), 17 et 19 (tensions de charge), 20 (norme réseau), 21 (fonction réseau), 23 (retour usine), 24 et 30 (effacement des historiques), 32 (détection d'arc), ainsi que `/api/v1/device/command` (redémarrage, remise à zéro, retour usine) et `/api/v1/device/config/update`. Le même point d'accès accepte ces réglages : la liste blanche est appliquée dans le client.

## Lectures utiles absentes de l'intégration actuelle

| Point d'accès | Apport |
|---|---|
| `/api/v1/device/status` | Puissance réseau **mesurée** (`grid_power`) alors que l'intégration la calcule ; `work_state` (0 normal, 1 alarme, 2 défaut, 3 perte de communication) ; `alarm_status` ; `bat_status` |
| `/api/v1/device/pcs/detail` | Détail onduleur, MPPT, packs batterie |
| `/api/v1/report/event` et `/api/v1/report/event/desc` | Événements (source EMS, PCS ou BMS, niveau) avec **cause et conseil** fournis par UCanpower |
| `/api/v1/report/errorcode` | Table des codes d'erreur de la plateforme |

Les mesures de l'intégration passent par les chemins du portail web (`/device/detail/load`…), absents de ce document ; seul le pilotage utilise l'API tierce signée.

## Modes de fonctionnement

| Valeur API | Mode du manuel (V1.9, p. 47 à 50) | Mode affiché par l'onduleur `mr` | Comportement observé |
|---|---|---|---|
| 0 | Autoconsommation | « Match Load Mode » | Le solaire alimente la maison, le surplus charge la batterie puis part au réseau ; la batterie complète la maison |
| 1 | Arbitrage horaire | « Peak Fill Mode » | Pendant les plages de charge, le réseau recharge la batterie (3,6 kW mesurés). **Hors plage, la batterie continue d'alimenter la maison** (le manuel indique le contraire). Une plage de décharge injecterait la batterie sur le réseau |
| 2 | Backup | — | Non utilisé (recharge complète sans contrôle de la quantité) |

## Modèle `mr` (constaté sur un UHome 6K)

| Constat (18-19/11/2026) | Détail |
|---|---|
| Modèle déclaré | `mr`, absent de la documentation |
| Table confirmée | Par une requête du portail (`{"inverter_model": "mr", "pcs": [{"set_id": 1, "set_data": 0}]}`) et par la table de son formulaire : mode 1 ; charges 44/45, 48/49, 52/53 ; décharges 46/47, 50/51, 54/55 ; heures en nombre HHMM (01:00 → 100) |
| Échelle des réglages de fond | ×10 par rapport à la documentation `uhome` (DOD 900 pour 90 %, hystérésis 100 pour 10 %, courant 1000 pour 100 A, puissance réseau 600 pour 60 %) |
| Configuration du cloud | Omet les valeurs nulles (mode 0, plages vides) ; le portail lit un réglage absent comme 0 |
| Envoi groupé | 12 réglages d'un coup : « 5019 Device operation timeout ». Un ou deux réglages : accepté, confirmé en 8 à 80 s |
| 5019 sur un envoi appliqué | Un seul réglage (début de plage) a reçu « 5019 Device operation timeout » alors que l'onduleur l'avait enregistré (relu quelques minutes plus tard). Le client relit la configuration avant de conclure à un échec |
| Plancher | Avec un DOD de 90 % et une hystérésis de 10 %, l'onduleur ne descend pas sous 13 % et se recharge seul jusqu'à 16 %, y compris en heures pleines |
| Application du téléphone | Affiche « Arbitrage horaire » par défaut quand le mode n'est pas stocké : ne pas valider ce formulaire sans corriger le mode |

## Points encore ouverts

| Point | Nature |
|---|---|
| Recharges automatiques sous le plancher, y compris en heures pleines (DOD et hystérésis, réglages de l'installateur) | Réglage de fond |
| Clé d'application de production : à demander à UCanpower (la documentation fournit une clé de test) | Accès à l'API |
| Limites d'appel de l'API (aucun chiffre publié) | Accès à l'API |
