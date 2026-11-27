/*
 * UCANESS HOME ASSISTANT : cartes Lovelace dans le style du portail UCANESS.
 * Un seul fichier, sans dépendance ni compilation. Licence MIT (voir LICENSE du dépôt).
 *
 * Cartes fournies :
 *   custom:ucaness-layout-card  en-tête + colonnes (300 px | reste | 300 px), une seule colonne sur téléphone
 *   custom:ucaness-header-card  bandeau titre, onglets, heure, liaison, alertes
 *   custom:ucaness-panel-card   panneau titré (losange, barres orange et cyan), carrousel ou onglets facultatifs,
 *                               réduit ou déplié d'un appui sur son titre (0.4.2 ; collapsible: false pour l'empêcher)
 *   custom:ucaness-flow-card    vue en direct de la maison : image, boules, onduleur, flux animés
 *   custom:ucaness-soc-card     anneau de charge de la batterie (compact: true pour le téléphone)
 *   custom:ucaness-note-card    texte replié sur quelques lignes, terminé par « … », déplié d'un appui
 *   custom:ucaness-app-card     écran de téléphone : en-tête compact, une colonne, navigation en bas
 *   custom:ucaness-status-card  bandeau d'état : « Tout va bien » ou les alertes en cours
 *   custom:ucaness-stats-card   deux à quatre chiffres clés côte à côte
 *   custom:ucaness-info-card    une ligne de texte (modèle Jinja), avec lien facultatif
 *   custom:ucaness-shortcuts-card  raccourcis (icône + nom) vers une page ou une fiche
 *   custom:ucaness-detail-card  une décision en clair, l'explication (« Pourquoi ? ») sur demande
 *   custom:ucaness-hours-card   graphique de la journée heure par heure, avec un choix en haut
 *   custom:ucaness-ucan-card    Ucan, la batterie UHome avec un visage, et son conseil du moment (0.5.1)
 *
 * Conventions de signe de l'intégration ucaness : batterie > 0 = charge, réseau > 0 = soutirage.
 *
 * 0.5.5 (27/11/2026) : « Et si… » dans la bulle Ucan (option simulateur, action ucaness.simuler).
 *
 * 0.5.4 (27/11/2026) : bulle Ucan déplaçable (glisser, position gardée sur l'appareil, « Replacer »).
 *
 * 0.5.3 (27/11/2026) : Ucan en bulle de discussion en bas à droite (floating: true).
 *
 * 0.5.2 (27/11/2026) : carte Ucan dans une colonne étroite (300 px) : la bulle passe sous l'avatar.
 *
 * 0.5.1 (27/11/2026) : carte Ucan (custom:ucaness-ucan-card), avatar et conseil du moment.
 *
 * 0.5.0 (27/11/2026) : style et animations.
 *   Encadrés arrondis à bordure fine, boutons en relief (survol à la souris seulement, enfoncement et onde au clic) ;
 *   cartes en cascade et vague cyan à l'ouverture d'un écran ; chiffres qui défilent ; anneau de charge en dégradé
 *   avec halo ; barres heure par heure en cascade et courbe tracée avec un dégradé dessous ; carte de décision qui se
 *   retourne quand la décision change ; bascule jour / nuit sur sun.sun (fondu 1,4 s) et fond de ciel selon
 *   weather.maison, sous un voile bleu ; « Maison en direct » en vue 3D (scene: 3d) : colonne UHome, borne,
 *   ampoule, poteau, chiffres écrits à côté des objets, flux sans flèches sur des trajets séparés.
 *   Seulement transform et opacité ; tout est coupé si l'appareil demande moins de mouvement ; mode allégé ?leger=1 :
 *   ni flou, ni vague, ni retournement, fond figé, aucune animation continue sauf les flux de la maison en direct.
 *   Aperçu sans rien changer dans Home Assistant : « ?ambiance=nuit » ou « jour », « ?meteo=beau|nuageux|pluie|orage »,
 *   « ?coucher=1 » dans l'adresse (affichage seulement, cet appareil, cette page).
 */

const UC_VERSION = '0.6.0';

/* Traductions des cartes : français (référence), anglais, chinois simplifié, allemand.
 * Entre les marqueurs I18N : JSON strict, vérifié par dashboard/tests/test_traductions_cartes.py
 * (mêmes clés et mêmes paramètres {…} dans chaque langue, toute clé utilisée existe). */
const UC_I18N = /* I18N-DEBUT */{
 "fr": {
  "meteo": "Météo : {etat}",
  "vues": "Vues",
  "alertes_en_cours": "{n} alerte(s) en cours",
  "aucune_alerte": "Aucune alerte",
  "cloud_en_ligne": "Liaison au cloud en ligne",
  "cloud_perdu": "Liaison au cloud perdue",
  "deplier": "Déplier",
  "reduire": "Réduire",
  "afficher": "Afficher {titre}",
  "lire_la_suite": "Lire la suite",
  "navigation": "Navigation",
  "fermer": "Fermer",
  "replacer": "Replacer",
  "flux_direct": "Flux d'énergie en direct",
  "solaire": "Solaire",
  "reseau": "Réseau",
  "batterie": "Batterie",
  "maison": "Maison",
  "onduleur": "Onduleur",
  "panneaux_solaires": "Panneaux solaires",
  "recharge": "Recharge",
  "borne": "Borne",
  "injection": "injection",
  "bat_chargement": "Chargement",
  "bat_decharge": "Décharge",
  "bat_veille": "Veille",
  "en_charge": "en charge",
  "en_decharge": "en décharge",
  "au_repos": "au repos",
  "batterie_a": "Batterie à {soc} %, {etat}",
  "uhome_batterie_a": "UHome : batterie à {soc} %, {etat}",
  "ouvrir_page_batterie": "Ouvrir la page de la batterie",
  "en_attente_mesures": "en attente des mesures",
  "en_direct": "en direct · relevé il y a {age}",
  "batterie_deux_points": "Batterie : ",
  "onduleur_mode": "Onduleur : {mode}",
  "scene_soleil": "Le soleil produit {kw} kW.",
  "scene_batterie": "La batterie est {etat}.",
  "scene_batterie_soc": "La batterie est {etat} à {soc} %.",
  "scene_maison": "La maison consomme {kw} kW.",
  "scene_achat": "Achat au réseau.",
  "scene_injection": "Injection sur le réseau.",
  "scene_voiture": "Voiture en charge.",
  "scene_mode_autoconsommation": "autoconsommation",
  "scene_mode_arbitrage": "arbitrage horaire",
  "scene_mode_secours": "secours",
  "mode_autoconsommation": "Autoconsommation",
  "mode_arbitrage": "Arbitrage horaire",
  "mode_secours": "Secours",
  "borne_en_charge": "en charge",
  "borne_libre": "libre",
  "borne_en_pause": "en pause",
  "borne_programmee": "programmée",
  "borne_branchee": "branchée",
  "borne_hors_ligne": "hors ligne",
  "borne_en_defaut": "en défaut",
  "borne_indisponible": "indisponible",
  "borne_inconnue": "inconnue",
  "charge_de_la_batterie": "Charge de la batterie : {v}",
  "indisponible": "indisponible",
  "charge_majuscules": "CHARGE",
  "stockee": "Stockée",
  "avant_plancher": "Avant plancher",
  "batterie_etat": "Batterie : {v}",
  "charge_indisponible": "charge indisponible",
  "simulation": "Simulation",
  "en_reserve": "En réserve",
  "utilisable_avant_plancher": "Utilisable avant le plancher",
  "plancher": "Plancher {v} %",
  "tout_va_bien": "Tout va bien",
  "n_alertes": "{n} alertes : ",
  "pourquoi": "Pourquoi ?",
  "chargement": "Chargement…",
  "journal_indisponible": "Journal indisponible.",
  "journal_vide": "Aucune entrée sur la période.",
  "journal_simulation": "simulation",
  "historique_indisponible": "Historique indisponible",
  "pas_de_mesure": "Pas encore de mesure aujourd’hui",
  "prevu": "prévu",
  "de_a": "{nom} : de {min} à {max}",
  "heure_en_cours": "barre estompée : heure en cours",
  "pointilles_prevision": "pointillés : prévision",
  "graphique_heures": "Graphique heure par heure",
  "nom_heures": "{nom} heure par heure",
  "un_conseil": "Un conseil",
  "je_le_fais": "Je le fais",
  "pas_maintenant": "Pas maintenant",
  "ne_plus_proposer": "Ne plus proposer",
  "alerte_conseils_attendront": "Une alerte est en cours : {noms}. Les conseils attendront.",
  "ucan_tout_va_bien": "Tout va bien. Je vous ferai signe quand un geste en vaudra la peine.",
  "calcul_en_cours": "Je calcule avec vos mesures…",
  "calcul_impossible": "Calcul impossible : {erreur}",
  "sur_vos_jours": "Sur vos {jours} derniers jours de mesures (estimation {fiabilite}) :",
  "fiab_fiable": "fiable",
  "fiab_indicatif": "indicative",
  "fiab_insuffisant": "insuffisante",
  "contrat_actuel_par_an": "Contrat actuel : {montant} par an.",
  "offre_par_an": "{nom} : {montant} par an",
  "prix_a_verifier": "Prix à vérifier chez le fournisseur avant de changer.",
  "puissance_garder": "Pointe prise au réseau : {pointe} kVA sur {jours} jours. Votre puissance de {actuelle} kVA convient : {reco} kVA suffiraient avec {marge} % de marge.",
  "puissance_baisser": "Pointe prise au réseau : {pointe} kVA sur {jours} jours. Votre puissance de {actuelle} kVA pourrait baisser : {reco} kVA suffiraient avec {marge} % de marge.",
  "puissance_augmenter": "Pointe prise au réseau : {pointe} kVA sur {jours} jours. Votre puissance de {actuelle} kVA est trop juste : {reco} kVA suffiraient avec {marge} % de marge.",
  "et_si": "Et si…",
  "q_contrat": "je changeais de contrat ?",
  "q_puissance": "je changeais de puissance ?",
  "erreur_inconnue": "erreur inconnue",
  "ucan_conseil_attend": "Ucan : un conseil vous attend",
  "ucan_alerte": "Ucan : une alerte est en cours",
  "err_layout": "ucaness-layout-card : « columns » est obligatoire (liste de colonnes avec « cards »).",
  "err_panel": "ucaness-panel-card : indiquez « cards » ou « slides ».",
  "err_note": "ucaness-note-card : indiquez « content » (texte markdown) ou « card ».",
  "err_app": "ucaness-app-card : « cards » est obligatoire.",
  "err_stats": "ucaness-stats-card : « items » est obligatoire.",
  "err_info": "ucaness-info-card : indiquez « template » ou « text ».",
  "err_shortcuts": "ucaness-shortcuts-card : « items » est obligatoire.",
  "err_detail": "ucaness-detail-card : indiquez « headline » ou « headline_template ».",
  "err_hours_tabs": "ucaness-hours-card : « tabs » est obligatoire.",
  "err_hours_stat": "ucaness-hours-card : chaque onglet demande « statistic ».",
  "carte_layout_nom": "UCANESS : mise en page",
  "carte_layout_desc": "En-tête et colonnes du tableau de bord UCANESS HOME ASSISTANT.",
  "carte_header_nom": "UCANESS : en-tête",
  "carte_header_desc": "Bandeau titre, onglets, heure, liaison et alertes.",
  "carte_panel_nom": "UCANESS : panneau",
  "carte_panel_desc": "Panneau titré dans le style UCANESS, avec carrousel ou onglets facultatifs.",
  "carte_flow_nom": "UCANESS : maison en direct",
  "carte_flow_desc": "Flux solaire, réseau, batterie et maison sur l’image de votre maison.",
  "carte_note_nom": "UCANESS : texte repliable",
  "carte_note_desc": "Texte replié sur quelques lignes, déplié d’un appui.",
  "carte_soc_nom": "UCANESS : charge batterie",
  "carte_soc_desc": "Anneau de charge, énergie stockée et réserve avant le plancher.",
  "carte_app_nom": "UCANESS : écran de téléphone",
  "carte_app_desc": "En-tête compact, cartes en une colonne, navigation en bas.",
  "carte_status_nom": "UCANESS : bandeau d’état",
  "carte_status_desc": "« Tout va bien » ou les alertes en cours.",
  "carte_stats_nom": "UCANESS : chiffres clés",
  "carte_stats_desc": "Deux à quatre chiffres côte à côte.",
  "carte_info_nom": "UCANESS : ligne d’information",
  "carte_info_desc": "Une phrase calculée par un modèle, avec lien facultatif.",
  "carte_shortcuts_nom": "UCANESS : raccourcis",
  "carte_shortcuts_desc": "Tuiles icône et nom vers une page ou une fiche.",
  "carte_detail_nom": "UCANESS : décision expliquée",
  "carte_detail_desc": "Une décision en clair, l’explication sur demande.",
  "carte_ucan_nom": "UCANESS : Ucan",
  "carte_ucan_desc": "Ucan, la batterie qui conseille : son expression et le conseil du moment.",
  "carte_hours_nom": "UCANESS : heure par heure",
  "carte_hours_desc": "Graphique de la journée heure par heure, avec un choix en haut."
 },
 "en": {
  "meteo": "Weather: {etat}",
  "vues": "Views",
  "alertes_en_cours": "{n} active alert(s)",
  "aucune_alerte": "No alerts",
  "cloud_en_ligne": "Cloud link online",
  "cloud_perdu": "Cloud link lost",
  "deplier": "Expand",
  "reduire": "Collapse",
  "afficher": "Show {titre}",
  "lire_la_suite": "Read more",
  "navigation": "Navigation",
  "fermer": "Close",
  "replacer": "Reset position",
  "flux_direct": "Live energy flow",
  "solaire": "Solar",
  "reseau": "Grid",
  "batterie": "Battery",
  "maison": "Home",
  "onduleur": "Inverter",
  "panneaux_solaires": "Solar panels",
  "recharge": "Charging",
  "borne": "Charger",
  "injection": "export",
  "bat_chargement": "Charging",
  "bat_decharge": "Discharging",
  "bat_veille": "Standby",
  "en_charge": "charging",
  "en_decharge": "discharging",
  "au_repos": "idle",
  "batterie_a": "Battery at {soc} %, {etat}",
  "uhome_batterie_a": "UHome: battery at {soc} %, {etat}",
  "ouvrir_page_batterie": "Open the battery page",
  "en_attente_mesures": "waiting for readings",
  "en_direct": "live · read {age} ago",
  "batterie_deux_points": "Battery: ",
  "onduleur_mode": "Inverter: {mode}",
  "scene_soleil": "The sun is producing {kw} kW.",
  "scene_batterie": "The battery is {etat}.",
  "scene_batterie_soc": "The battery is {etat} at {soc} %.",
  "scene_maison": "The house is using {kw} kW.",
  "scene_achat": "Buying from the grid.",
  "scene_injection": "Exporting to the grid.",
  "scene_voiture": "Car charging.",
  "scene_mode_autoconsommation": "self-consumption",
  "scene_mode_arbitrage": "time arbitrage",
  "scene_mode_secours": "backup",
  "mode_autoconsommation": "Self-consumption",
  "mode_arbitrage": "Time arbitrage",
  "mode_secours": "Backup",
  "borne_en_charge": "charging",
  "borne_libre": "available",
  "borne_en_pause": "paused",
  "borne_programmee": "scheduled",
  "borne_branchee": "plugged in",
  "borne_hors_ligne": "offline",
  "borne_en_defaut": "fault",
  "borne_indisponible": "unavailable",
  "borne_inconnue": "unknown",
  "charge_de_la_batterie": "Battery charge: {v}",
  "indisponible": "unavailable",
  "charge_majuscules": "CHARGE",
  "stockee": "Stored",
  "avant_plancher": "Above floor",
  "batterie_etat": "Battery: {v}",
  "charge_indisponible": "charge unavailable",
  "simulation": "Simulation",
  "en_reserve": "In reserve",
  "utilisable_avant_plancher": "Usable above the floor",
  "plancher": "Floor {v} %",
  "tout_va_bien": "All good",
  "n_alertes": "{n} alerts: ",
  "pourquoi": "Why?",
  "chargement": "Loading…",
  "journal_indisponible": "Logbook unavailable.",
  "journal_vide": "No entries for this period.",
  "journal_simulation": "simulation",
  "historique_indisponible": "History unavailable",
  "pas_de_mesure": "No readings yet today",
  "prevu": "forecast",
  "de_a": "{nom}: from {min} to {max}",
  "heure_en_cours": "faded bar: current hour",
  "pointilles_prevision": "dotted: forecast",
  "graphique_heures": "Hour-by-hour chart",
  "nom_heures": "{nom} hour by hour",
  "un_conseil": "A tip",
  "je_le_fais": "I'll do it",
  "pas_maintenant": "Not now",
  "ne_plus_proposer": "Don't suggest again",
  "alerte_conseils_attendront": "An alert is active: {noms}. Tips will wait.",
  "ucan_tout_va_bien": "All good. I'll let you know when something is worth doing.",
  "calcul_en_cours": "Calculating with your readings…",
  "calcul_impossible": "Calculation failed: {erreur}",
  "sur_vos_jours": "Over your last {jours} days of readings ({fiabilite} estimate):",
  "fiab_fiable": "reliable",
  "fiab_indicatif": "indicative",
  "fiab_insuffisant": "insufficient",
  "contrat_actuel_par_an": "Current contract: {montant} per year.",
  "offre_par_an": "{nom}: {montant} per year",
  "prix_a_verifier": "Check prices with the supplier before switching.",
  "puissance_garder": "Peak drawn from the grid: {pointe} kVA over {jours} days. Your {actuelle} kVA is right: {reco} kVA would be enough with a {marge} % margin.",
  "puissance_baisser": "Peak drawn from the grid: {pointe} kVA over {jours} days. Your {actuelle} kVA could be lowered: {reco} kVA would be enough with a {marge} % margin.",
  "puissance_augmenter": "Peak drawn from the grid: {pointe} kVA over {jours} days. Your {actuelle} kVA is too tight: {reco} kVA would be enough with a {marge} % margin.",
  "et_si": "What if…",
  "q_contrat": "I changed my contract?",
  "q_puissance": "I changed my power rating?",
  "erreur_inconnue": "unknown error",
  "ucan_conseil_attend": "Ucan: a tip is waiting for you",
  "ucan_alerte": "Ucan: an alert is active",
  "err_layout": "ucaness-layout-card: 'columns' is required (list of columns with 'cards').",
  "err_panel": "ucaness-panel-card: provide 'cards' or 'slides'.",
  "err_note": "ucaness-note-card: provide 'content' (markdown text) or 'card'.",
  "err_app": "ucaness-app-card: 'cards' is required.",
  "err_stats": "ucaness-stats-card: 'items' is required.",
  "err_info": "ucaness-info-card: provide 'template' or 'text'.",
  "err_shortcuts": "ucaness-shortcuts-card: 'items' is required.",
  "err_detail": "ucaness-detail-card: provide 'headline' or 'headline_template'.",
  "err_hours_tabs": "ucaness-hours-card: 'tabs' is required.",
  "err_hours_stat": "ucaness-hours-card: each tab needs 'statistic'.",
  "carte_layout_nom": "UCANESS: layout",
  "carte_layout_desc": "Header and columns of the UCANESS HOME ASSISTANT dashboard.",
  "carte_header_nom": "UCANESS: header",
  "carte_header_desc": "Title bar, tabs, time, link and alerts.",
  "carte_panel_nom": "UCANESS: panel",
  "carte_panel_desc": "Titled panel in the UCANESS style, with optional carousel or tabs.",
  "carte_flow_nom": "UCANESS: live home",
  "carte_flow_desc": "Solar, grid, battery and home flows on a picture of your home.",
  "carte_note_nom": "UCANESS: collapsible text",
  "carte_note_desc": "Text folded to a few lines, expanded with a tap.",
  "carte_soc_nom": "UCANESS: battery charge",
  "carte_soc_desc": "Charge ring, stored energy and reserve above the floor.",
  "carte_app_nom": "UCANESS: phone screen",
  "carte_app_desc": "Compact header, single-column cards, bottom navigation.",
  "carte_status_nom": "UCANESS: status bar",
  "carte_status_desc": "\"All good\" or the active alerts.",
  "carte_stats_nom": "UCANESS: key figures",
  "carte_stats_desc": "Two to four figures side by side.",
  "carte_info_nom": "UCANESS: info line",
  "carte_info_desc": "A sentence computed by a template, with an optional link.",
  "carte_shortcuts_nom": "UCANESS: shortcuts",
  "carte_shortcuts_desc": "Icon and name tiles linking to a page or a card.",
  "carte_detail_nom": "UCANESS: explained decision",
  "carte_detail_desc": "A decision in plain words, the explanation on request.",
  "carte_ucan_nom": "UCANESS: Ucan",
  "carte_ucan_desc": "Ucan, the battery that gives advice: its mood and the current tip.",
  "carte_hours_nom": "UCANESS: hour by hour",
  "carte_hours_desc": "Hour-by-hour chart of the day, with a selector at the top."
 },
 "zh-Hans": {
  "meteo": "天气：{etat}",
  "vues": "视图",
  "alertes_en_cours": "{n} 条告警进行中",
  "aucune_alerte": "无告警",
  "cloud_en_ligne": "云连接在线",
  "cloud_perdu": "云连接已断开",
  "deplier": "展开",
  "reduire": "收起",
  "afficher": "显示 {titre}",
  "lire_la_suite": "阅读更多",
  "navigation": "导航",
  "fermer": "关闭",
  "replacer": "复位",
  "flux_direct": "实时能量流",
  "solaire": "光伏",
  "reseau": "电网",
  "batterie": "电池",
  "maison": "家庭",
  "onduleur": "逆变器",
  "panneaux_solaires": "光伏板",
  "recharge": "充电",
  "borne": "充电桩",
  "injection": "上网",
  "bat_chargement": "充电中",
  "bat_decharge": "放电中",
  "bat_veille": "待机",
  "en_charge": "充电中",
  "en_decharge": "放电中",
  "au_repos": "静置",
  "batterie_a": "电池 {soc}%，{etat}",
  "uhome_batterie_a": "UHome：电池 {soc}%，{etat}",
  "ouvrir_page_batterie": "打开电池页面",
  "en_attente_mesures": "等待测量数据",
  "en_direct": "实时 · {age}前读取",
  "batterie_deux_points": "电池：",
  "onduleur_mode": "逆变器：{mode}",
  "scene_soleil": "太阳正在发电 {kw} kW。",
  "scene_batterie": "电池{etat}。",
  "scene_batterie_soc": "电池{etat}，电量 {soc}%。",
  "scene_maison": "家庭正在用电 {kw} kW。",
  "scene_achat": "正在从电网购电。",
  "scene_injection": "正在向电网送电。",
  "scene_voiture": "汽车充电中。",
  "scene_mode_autoconsommation": "自发自用",
  "scene_mode_arbitrage": "峰谷套利",
  "scene_mode_secours": "备用",
  "mode_autoconsommation": "自发自用",
  "mode_arbitrage": "峰谷套利",
  "mode_secours": "备用",
  "borne_en_charge": "充电中",
  "borne_libre": "空闲",
  "borne_en_pause": "已暂停",
  "borne_programmee": "已预约",
  "borne_branchee": "已连接",
  "borne_hors_ligne": "离线",
  "borne_en_defaut": "故障",
  "borne_indisponible": "不可用",
  "borne_inconnue": "未知",
  "charge_de_la_batterie": "电池电量：{v}",
  "indisponible": "不可用",
  "charge_majuscules": "电量",
  "stockee": "已储存",
  "avant_plancher": "下限以上",
  "batterie_etat": "电池：{v}",
  "charge_indisponible": "电量不可用",
  "simulation": "模拟",
  "en_reserve": "储备电量",
  "utilisable_avant_plancher": "下限以上可用",
  "plancher": "下限 {v}%",
  "tout_va_bien": "一切正常",
  "n_alertes": "{n} 条告警：",
  "pourquoi": "为什么？",
  "chargement": "加载中…",
  "journal_indisponible": "日志不可用。",
  "journal_vide": "此期间没有记录。",
  "journal_simulation": "模拟",
  "historique_indisponible": "历史数据不可用",
  "pas_de_mesure": "今天还没有测量数据",
  "prevu": "预计",
  "de_a": "{nom}：从 {min} 到 {max}",
  "heure_en_cours": "浅色柱：当前小时",
  "pointilles_prevision": "虚线：预测",
  "graphique_heures": "逐小时图表",
  "nom_heures": "{nom} 逐小时",
  "un_conseil": "一条建议",
  "je_le_fais": "我来做",
  "pas_maintenant": "以后再说",
  "ne_plus_proposer": "不再提示",
  "alerte_conseils_attendront": "有告警进行中：{noms}。建议稍后再说。",
  "ucan_tout_va_bien": "一切正常。有值得做的事情时我会通知您。",
  "calcul_en_cours": "正在根据您的测量数据计算…",
  "calcul_impossible": "无法计算：{erreur}",
  "sur_vos_jours": "根据您最近 {jours} 天的测量数据（{fiabilite}估算）：",
  "fiab_fiable": "可靠",
  "fiab_indicatif": "参考性",
  "fiab_insuffisant": "数据不足",
  "contrat_actuel_par_an": "当前合同：每年 {montant}。",
  "offre_par_an": "{nom}：每年 {montant}",
  "prix_a_verifier": "更换前请向供应商核实价格。",
  "puissance_garder": "电网取电峰值：{jours} 天内 {pointe} kVA。您的 {actuelle} kVA 合适：留 {marge}% 余量时 {reco} kVA 即可。",
  "puissance_baisser": "电网取电峰值：{jours} 天内 {pointe} kVA。您的 {actuelle} kVA 可以降低：留 {marge}% 余量时 {reco} kVA 即可。",
  "puissance_augmenter": "电网取电峰值：{jours} 天内 {pointe} kVA。您的 {actuelle} kVA 偏小：留 {marge}% 余量时需要 {reco} kVA。",
  "et_si": "如果……",
  "q_contrat": "我更换合同？",
  "q_puissance": "我更改签约功率？",
  "erreur_inconnue": "未知错误",
  "ucan_conseil_attend": "Ucan：有一条建议等着您",
  "ucan_alerte": "Ucan：有告警进行中",
  "err_layout": "ucaness-layout-card：必须提供“columns”（包含“cards”的列列表）。",
  "err_panel": "ucaness-panel-card：请提供“cards”或“slides”。",
  "err_note": "ucaness-note-card：请提供“content”（markdown 文本）或“card”。",
  "err_app": "ucaness-app-card：必须提供“cards”。",
  "err_stats": "ucaness-stats-card：必须提供“items”。",
  "err_info": "ucaness-info-card：请提供“template”或“text”。",
  "err_shortcuts": "ucaness-shortcuts-card：必须提供“items”。",
  "err_detail": "ucaness-detail-card：请提供“headline”或“headline_template”。",
  "err_hours_tabs": "ucaness-hours-card：必须提供“tabs”。",
  "err_hours_stat": "ucaness-hours-card：每个标签页都需要“statistic”。",
  "carte_layout_nom": "UCANESS：布局",
  "carte_layout_desc": "UCANESS HOME ASSISTANT 仪表板的页眉和列。",
  "carte_header_nom": "UCANESS：页眉",
  "carte_header_desc": "标题栏、标签页、时间、连接和告警。",
  "carte_panel_nom": "UCANESS：面板",
  "carte_panel_desc": "UCANESS 风格的带标题面板，可选轮播或标签页。",
  "carte_flow_nom": "UCANESS：实时家庭",
  "carte_flow_desc": "在您的房屋图片上显示光伏、电网、电池和家庭能量流。",
  "carte_note_nom": "UCANESS：可折叠文本",
  "carte_note_desc": "文本折叠为几行，轻点即可展开。",
  "carte_soc_nom": "UCANESS：电池电量",
  "carte_soc_desc": "电量环、已储存电量和下限以上的储备。",
  "carte_app_nom": "UCANESS：手机界面",
  "carte_app_desc": "紧凑页眉、单列卡片、底部导航。",
  "carte_status_nom": "UCANESS：状态栏",
  "carte_status_desc": "“一切正常”或进行中的告警。",
  "carte_stats_nom": "UCANESS：关键数据",
  "carte_stats_desc": "并排显示两到四个数字。",
  "carte_info_nom": "UCANESS：信息行",
  "carte_info_desc": "由模板计算的一句话，可附链接。",
  "carte_shortcuts_nom": "UCANESS：快捷方式",
  "carte_shortcuts_desc": "带图标和名称的磁贴，链接到页面或详情。",
  "carte_detail_nom": "UCANESS：决策说明",
  "carte_detail_desc": "用平实语言说明决策，按需查看原因。",
  "carte_ucan_nom": "UCANESS：Ucan",
  "carte_ucan_desc": "Ucan，会提建议的电池：它的表情和当前建议。",
  "carte_hours_nom": "UCANESS：逐小时",
  "carte_hours_desc": "当天逐小时图表，顶部可切换。"
 },
 "de": {
  "meteo": "Wetter: {etat}",
  "vues": "Ansichten",
  "alertes_en_cours": "{n} aktive Warnung(en)",
  "aucune_alerte": "Keine Warnungen",
  "cloud_en_ligne": "Cloud-Verbindung online",
  "cloud_perdu": "Cloud-Verbindung verloren",
  "deplier": "Aufklappen",
  "reduire": "Einklappen",
  "afficher": "{titre} anzeigen",
  "lire_la_suite": "Weiterlesen",
  "navigation": "Navigation",
  "fermer": "Schließen",
  "replacer": "Zurücksetzen",
  "flux_direct": "Energiefluss live",
  "solaire": "Solar",
  "reseau": "Netz",
  "batterie": "Batterie",
  "maison": "Haus",
  "onduleur": "Wechselrichter",
  "panneaux_solaires": "Solarmodule",
  "recharge": "Laden",
  "borne": "Wallbox",
  "injection": "Einspeisung",
  "bat_chargement": "Lädt",
  "bat_decharge": "Entlädt",
  "bat_veille": "Standby",
  "en_charge": "lädt",
  "en_decharge": "entlädt",
  "au_repos": "im Ruhezustand",
  "batterie_a": "Batterie bei {soc} %, {etat}",
  "uhome_batterie_a": "UHome: Batterie bei {soc} %, {etat}",
  "ouvrir_page_batterie": "Batterieseite öffnen",
  "en_attente_mesures": "warte auf Messwerte",
  "en_direct": "live · vor {age} gelesen",
  "batterie_deux_points": "Batterie: ",
  "onduleur_mode": "Wechselrichter: {mode}",
  "scene_soleil": "Die Sonne erzeugt {kw} kW.",
  "scene_batterie": "Die Batterie {etat}.",
  "scene_batterie_soc": "Die Batterie {etat}, Ladestand {soc} %.",
  "scene_maison": "Das Haus verbraucht {kw} kW.",
  "scene_achat": "Bezug aus dem Netz.",
  "scene_injection": "Einspeisung ins Netz.",
  "scene_voiture": "Auto wird geladen.",
  "scene_mode_autoconsommation": "Eigenverbrauch",
  "scene_mode_arbitrage": "Zeitarbitrage",
  "scene_mode_secours": "Notstrom",
  "mode_autoconsommation": "Eigenverbrauch",
  "mode_arbitrage": "Zeitarbitrage",
  "mode_secours": "Notstrom",
  "borne_en_charge": "lädt",
  "borne_libre": "frei",
  "borne_en_pause": "pausiert",
  "borne_programmee": "geplant",
  "borne_branchee": "angesteckt",
  "borne_hors_ligne": "offline",
  "borne_en_defaut": "Fehler",
  "borne_indisponible": "nicht verfügbar",
  "borne_inconnue": "unbekannt",
  "charge_de_la_batterie": "Batterieladestand: {v}",
  "indisponible": "nicht verfügbar",
  "charge_majuscules": "LADUNG",
  "stockee": "Gespeichert",
  "avant_plancher": "Über Untergrenze",
  "batterie_etat": "Batterie: {v}",
  "charge_indisponible": "Ladestand nicht verfügbar",
  "simulation": "Simulation",
  "en_reserve": "In Reserve",
  "utilisable_avant_plancher": "Nutzbar über der Untergrenze",
  "plancher": "Untergrenze {v} %",
  "tout_va_bien": "Alles in Ordnung",
  "n_alertes": "{n} Warnungen: ",
  "pourquoi": "Warum?",
  "chargement": "Wird geladen…",
  "journal_indisponible": "Logbuch nicht verfügbar.",
  "journal_vide": "Keine Einträge in diesem Zeitraum.",
  "journal_simulation": "Simulation",
  "historique_indisponible": "Verlauf nicht verfügbar",
  "pas_de_mesure": "Heute noch keine Messwerte",
  "prevu": "Prognose",
  "de_a": "{nom}: von {min} bis {max}",
  "heure_en_cours": "blasser Balken: aktuelle Stunde",
  "pointilles_prevision": "gepunktet: Prognose",
  "graphique_heures": "Stundendiagramm",
  "nom_heures": "{nom} Stunde für Stunde",
  "un_conseil": "Ein Tipp",
  "je_le_fais": "Mache ich",
  "pas_maintenant": "Nicht jetzt",
  "ne_plus_proposer": "Nicht mehr vorschlagen",
  "alerte_conseils_attendront": "Eine Warnung ist aktiv: {noms}. Die Tipps warten.",
  "ucan_tout_va_bien": "Alles in Ordnung. Ich melde mich, wenn sich etwas lohnt.",
  "calcul_en_cours": "Ich rechne mit deinen Messwerten…",
  "calcul_impossible": "Berechnung nicht möglich: {erreur}",
  "sur_vos_jours": "Über deine letzten {jours} Messtage (Schätzung {fiabilite}):",
  "fiab_fiable": "zuverlässig",
  "fiab_indicatif": "Richtwert",
  "fiab_insuffisant": "unzureichend",
  "contrat_actuel_par_an": "Aktueller Vertrag: {montant} pro Jahr.",
  "offre_par_an": "{nom}: {montant} pro Jahr",
  "prix_a_verifier": "Preise vor einem Wechsel beim Anbieter prüfen.",
  "puissance_garder": "Spitzenbezug aus dem Netz: {pointe} kVA in {jours} Tagen. Deine {actuelle} kVA passen: {reco} kVA würden mit {marge} % Reserve reichen.",
  "puissance_baisser": "Spitzenbezug aus dem Netz: {pointe} kVA in {jours} Tagen. Deine {actuelle} kVA könnten sinken: {reco} kVA würden mit {marge} % Reserve reichen.",
  "puissance_augmenter": "Spitzenbezug aus dem Netz: {pointe} kVA in {jours} Tagen. Deine {actuelle} kVA sind zu knapp: {reco} kVA würden mit {marge} % Reserve reichen.",
  "et_si": "Was wäre, wenn…",
  "q_contrat": "ich den Vertrag wechsle?",
  "q_puissance": "ich die Leistung ändere?",
  "erreur_inconnue": "unbekannter Fehler",
  "ucan_conseil_attend": "Ucan: Ein Tipp wartet auf dich",
  "ucan_alerte": "Ucan: Eine Warnung ist aktiv",
  "err_layout": "ucaness-layout-card: „columns“ ist erforderlich (Liste von Spalten mit „cards“).",
  "err_panel": "ucaness-panel-card: „cards“ oder „slides“ angeben.",
  "err_note": "ucaness-note-card: „content“ (Markdown-Text) oder „card“ angeben.",
  "err_app": "ucaness-app-card: „cards“ ist erforderlich.",
  "err_stats": "ucaness-stats-card: „items“ ist erforderlich.",
  "err_info": "ucaness-info-card: „template“ oder „text“ angeben.",
  "err_shortcuts": "ucaness-shortcuts-card: „items“ ist erforderlich.",
  "err_detail": "ucaness-detail-card: „headline“ oder „headline_template“ angeben.",
  "err_hours_tabs": "ucaness-hours-card: „tabs“ ist erforderlich.",
  "err_hours_stat": "ucaness-hours-card: Jeder Tab braucht „statistic“.",
  "carte_layout_nom": "UCANESS: Layout",
  "carte_layout_desc": "Kopfzeile und Spalten des Dashboards UCANESS HOME ASSISTANT.",
  "carte_header_nom": "UCANESS: Kopfzeile",
  "carte_header_desc": "Titelleiste, Tabs, Uhrzeit, Verbindung und Warnungen.",
  "carte_panel_nom": "UCANESS: Panel",
  "carte_panel_desc": "Panel mit Titel im UCANESS-Stil, optional mit Karussell oder Tabs.",
  "carte_flow_nom": "UCANESS: Haus live",
  "carte_flow_desc": "Solar-, Netz-, Batterie- und Hausflüsse auf dem Bild deines Hauses.",
  "carte_note_nom": "UCANESS: einklappbarer Text",
  "carte_note_desc": "Auf wenige Zeilen gekürzter Text, per Antippen aufklappbar.",
  "carte_soc_nom": "UCANESS: Batterieladestand",
  "carte_soc_desc": "Ladering, gespeicherte Energie und Reserve über der Untergrenze.",
  "carte_app_nom": "UCANESS: Handybildschirm",
  "carte_app_desc": "Kompakte Kopfzeile, Karten in einer Spalte, Navigation unten.",
  "carte_status_nom": "UCANESS: Statusleiste",
  "carte_status_desc": "„Alles in Ordnung“ oder die aktiven Warnungen.",
  "carte_stats_nom": "UCANESS: Kennzahlen",
  "carte_stats_desc": "Zwei bis vier Zahlen nebeneinander.",
  "carte_info_nom": "UCANESS: Infozeile",
  "carte_info_desc": "Ein von einer Vorlage berechneter Satz, optional mit Link.",
  "carte_shortcuts_nom": "UCANESS: Verknüpfungen",
  "carte_shortcuts_desc": "Kacheln mit Symbol und Name zu einer Seite oder Detailansicht.",
  "carte_detail_nom": "UCANESS: erklärte Entscheidung",
  "carte_detail_desc": "Eine Entscheidung in klaren Worten, die Erklärung auf Wunsch.",
  "carte_ucan_nom": "UCANESS: Ucan",
  "carte_ucan_desc": "Ucan, die Batterie, die berät: ihr Ausdruck und der aktuelle Tipp.",
  "carte_hours_nom": "UCANESS: Stunde für Stunde",
  "carte_hours_desc": "Stundendiagramm des Tages, mit Auswahl oben."
 }
}/* I18N-FIN */;
let UC_LANG_VUE = null;   // dernière langue vue, pour les appels sans hass (configuration, sélecteur de cartes)

/** Langue des cartes : celle du profil Home Assistant ; chinois → zh-Hans ; langue inconnue → anglais. */
function ucLang(hass) {
  const brute = (hass && ((hass.locale && hass.locale.language) || hass.language)) || UC_LANG_VUE
    || (typeof document !== 'undefined' && document.documentElement.lang) || 'fr';
  if (hass) UC_LANG_VUE = brute;
  if (UC_I18N[brute]) return brute;
  const base = String(brute).split('-')[0];
  if (base === 'zh') return 'zh-Hans';
  return UC_I18N[base] ? base : 'en';
}

/** Texte traduit ; {nom} est remplacé par params.nom. */
function ucT(hass, cle, params) {
  const l = ucLang(hass);
  let t = (UC_I18N[l] && UC_I18N[l][cle]) || UC_I18N.en[cle] || UC_I18N.fr[cle] || cle;
  if (params) t = t.replace(/\{(\w+)\}/g, (m, k) => (params[k] !== undefined && params[k] !== null ? String(params[k]) : m));
  return t;
}

/* Dossier où se trouve ce fichier (en général /local/ucaness/). */
const UC_BASE = (() => {
  try { return new URL('.', import.meta.url).href; } catch (e) { return '/local/ucaness/'; }
})();

/* ------------------------------------------------------------------ outils */

const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const UC_FONT = "'Times New Roman', Tinos, 'Liberation Serif', serif";
/* Le titre UCANESS garde toujours la police du portail, même quand le thème choisit une autre police. */
const UC_BRAND_FONT = UC_FONT;

/* Mode allégé, pour les tablettes peu puissantes : animations coupées.
 * « ?leger=1 » dans l'adresse l'active sur cet appareil (mémorisé), « ?leger=0 » le retire. */
const UC_LIGHT = (() => {
  try {
    const q = new URLSearchParams(window.location.search).get('leger');
    if (q === '1') window.localStorage.setItem('ucaness-leger', '1');
    if (q === '0') window.localStorage.removeItem('ucaness-leger');
    return window.localStorage.getItem('ucaness-leger') === '1';
  } catch (e) { return false; }
})();

/* Moins de mouvement demandé par l'appareil : toutes les animations coupées. */
const UC_REDUCED = (() => {
  try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; }
})();

/** Apparition d'une carte (cascade) : fondu et montée, flou → net ; fondu seul en mode allégé. */
function ucRise(el, delay) {
  if (UC_REDUCED || !el || !el.animate) return;
  const kf = UC_LIGHT
    ? [{ opacity: 0 }, { opacity: 1 }]
    : [{ opacity: 0, transform: 'translateY(14px)', filter: 'blur(6px)' }, { opacity: 1, transform: 'none', filter: 'blur(0)' }];
  try { el.animate(kf, { duration: UC_LIGHT ? 300 : 550, delay: delay || 0, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'backwards' }); } catch (e) { /* navigateur ancien : sans animation */ }
}

/** Chiffres qui défilent : chaque élément [data-n] (clé) [data-v] (valeur) [data-d] (décimales) [data-s] (signe −)
 *  part de la valeur précédente (0 à la première apparition) et rejoint la nouvelle en 0,8 s. */
function ucCount(card, root, hass) {
  card._ucPrev = card._ucPrev || {};
  root.querySelectorAll('[data-n]').forEach((el) => {
    const key = el.dataset.n;
    const to = Number(el.dataset.v);
    const d = Number(el.dataset.d || 0);
    const signed = el.dataset.s === '1';
    const from = card._ucPrev[key];
    card._ucPrev[key] = to;
    if (!Number.isFinite(to)) return;
    const fmt = (v) => (signed && v < -0.0001 ? '−' : '') + ucNumber(hass, signed ? Math.abs(v) : v, d);
    const start = from === undefined ? 0 : from;
    if (UC_REDUCED || UC_LIGHT || start === to || !window.requestAnimationFrame) { el.textContent = fmt(to); return; }
    const t0 = performance.now();
    const dur = 800;
    el.textContent = fmt(start);
    const step = (now) => {
      if (!el.isConnected || card._ucPrev[key] !== to) return;
      const k = Math.min(1, (now - t0) / dur);
      el.textContent = fmt(start + (to - start) * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
    // Sécurité : si l'écran ne dessine plus (onglet caché, tablette en veille), la valeur finale s'écrit quand même.
    setTimeout(() => { if (el.isConnected && card._ucPrev[key] === to) el.textContent = fmt(to); }, dur + 150);
  });
}

/* ------------------------------------------------------------------ jour / nuit et ciel */

/* Météo-France → ciel : 0 beau, 1 nuageux, 2 pluie, 3 orage. */
const UC_METEO = {
  sunny: 0, 'clear-night': 0,
  partlycloudy: 1, cloudy: 1, fog: 1, windy: 1, 'windy-variant': 1, snowy: 1, hail: 1, exceptional: 1,
  rainy: 2, pouring: 2, 'snowy-rainy': 2,
  lightning: 3, 'lightning-rainy': 3,
};
const UC_METEO_NOMS = ['beau', 'nuageux', 'pluie', 'orage'];
const UC_METEO_ICONES = {
  sunny: 'mdi:weather-sunny', 'clear-night': 'mdi:weather-night', partlycloudy: 'mdi:weather-partly-cloudy',
  cloudy: 'mdi:weather-cloudy', fog: 'mdi:weather-fog', rainy: 'mdi:weather-rainy', pouring: 'mdi:weather-pouring',
  lightning: 'mdi:weather-lightning', 'lightning-rainy': 'mdi:weather-lightning-rainy', snowy: 'mdi:weather-snowy',
  'snowy-rainy': 'mdi:weather-snowy-rainy', windy: 'mdi:weather-windy', 'windy-variant': 'mdi:weather-windy-variant',
  hail: 'mdi:weather-hail', exceptional: 'mdi:alert-circle-outline',
};

/* Aperçu d'ambiance par l'adresse (affichage seulement, rien n'est écrit dans Home Assistant). */
function ucApercu() {
  try {
    const q = new URLSearchParams(window.location.search);
    return { ambiance: q.get('ambiance'), meteo: q.get('meteo'), coucher: q.get('coucher') === '1' };
  } catch (e) { return {}; }
}

/** Entité météo : celle de la configuration, sinon weather.maison, sinon la première entité météo. */
function ucWeatherId(hass, wanted) {
  if (!hass || !hass.states) return null;
  if (wanted && hass.states[wanted]) return wanted;
  if (hass.states['weather.maison']) return 'weather.maison';
  return Object.keys(hass.states).find((k) => k.startsWith('weather.')) || null;
}

/** Ambiance du moment : nuit (sun.sun sous l'horizon), météo, coucher du soleil, image du ciel. */
function ucAmbiance(hass, cfg) {
  const c = cfg || {};
  const ap = ucApercu();
  const sun = hass && hass.states ? hass.states[c.sun_entity || 'sun.sun'] : null;
  const wid = ucWeatherId(hass, c.weather_entity);
  const w = wid ? hass.states[wid] : null;
  const h = new Date().getHours();
  let night = sun ? sun.state === 'below_horizon' : (h < 7 || h >= 19);
  let meteo = w && UC_METEO[w.state] !== undefined ? UC_METEO[w.state] : (w ? 1 : 0);
  const a = (sun && sun.attributes) || {};
  let dusk = !!sun && a.rising === false && Number(a.elevation) <= 6 && Number(a.elevation) >= -4;
  if (ap.ambiance === 'nuit') { night = true; dusk = false; }
  if (ap.ambiance === 'jour') { night = false; dusk = false; }
  if (ap.coucher) { night = false; dusk = true; }
  if (ap.meteo && UC_METEO_NOMS.includes(ap.meteo)) meteo = UC_METEO_NOMS.indexOf(ap.meteo);
  const img = dusk && meteo <= 1 ? 'coucher'
    : night ? ['nuit-claire', 'nuit-couverte', 'nuit-couverte', 'nuit-orage'][meteo]
      : ['jour-beau', 'jour-nuageux', 'jour-pluie', 'jour-orage'][meteo];
  return { night, meteo, dusk, img, weather: w, sunId: c.sun_entity || 'sun.sun', weatherId: wid };
}

/* Calque du ciel (derrière tout le contenu) et vague d'ouverture, pour la mise en page et l'écran de téléphone. */
const UC_SKY_CSS = `
  .uc-sky { position: fixed; inset: 0; z-index: -1; pointer-events: none; overflow: hidden; background: #030B20; }
  .uc-sl { position: absolute; inset: -1%; background: #030B20 center / cover no-repeat; opacity: 0; transition: opacity 1.4s ease; transform-origin: 30% 20%; }
  .uc-sl.on { opacity: 1; }
  .uc-sl.drift { animation: ucDrift 90s ease-in-out infinite alternate; }
  @keyframes ucDrift { from { transform: scale(1); } to { transform: scale(1.08) translate(-1.5%, -1%); } }
  .uc-rain, .uc-flash { position: absolute; display: none; }
  .uc-rain { left: -10%; right: -10%; top: -100%; height: 200%; background: repeating-linear-gradient(105deg, rgba(160,210,255,0) 0 14px, rgba(160,210,255,.16) 14px 15px); animation: ucRain .9s linear infinite; }
  @keyframes ucRain { from { transform: translateY(0); } to { transform: translateY(50%); } }
  .uc-flash { inset: 0; background: radial-gradient(ellipse at 62% 20%, rgba(230,240,255,0.55) 0%, rgba(230,240,255,0) 60%); opacity: 0; animation: ucFlash 7s linear infinite; }
  @keyframes ucFlash { 0%, 86%, 100% { opacity: 0; } 87% { opacity: .9; } 88% { opacity: .1; } 89.5% { opacity: .7; } 92% { opacity: 0; } }
  ${UC_LIGHT || UC_REDUCED ? '' : '.uc-sky[data-meteo="2"] .uc-rain { display: block; } .uc-sky[data-meteo="3"] .uc-flash { display: block; }'}
  .uc-veil, .uc-veil-n { position: absolute; inset: 0; transition: opacity 1.4s ease; }
  .uc-veil { background: linear-gradient(180deg, rgba(6,26,62,0.42) 0%, rgba(5,20,50,0.58) 55%, rgba(3,11,32,0.76) 100%); opacity: calc(1 - var(--uc-night, 0)); }
  .uc-veil-n { background: linear-gradient(180deg, rgba(2,6,18,0.35) 0%, rgba(2,8,22,0.6) 55%, rgba(1,4,11,0.8) 100%); opacity: var(--uc-night, 0); }
  .uc-vague { position: fixed; top: 0; bottom: 0; left: -70%; width: 70%; z-index: 30; pointer-events: none; background: linear-gradient(90deg, rgba(0,209,214,0) 0%, rgba(0,209,214,.14) 36%, rgba(127,243,245,.5) 50%, rgba(26,111,190,.22) 62%, rgba(0,209,214,0) 100%); transform: skewX(-14deg); }
`;
const UC_SKY_HTML = `<div class="uc-sky" aria-hidden="true"><div class="uc-sl"></div><div class="uc-sl"></div><div class="uc-rain"></div><div class="uc-flash"></div><div class="uc-veil"></div><div class="uc-veil-n"></div></div><div class="uc-vague" aria-hidden="true"></div>`;

/** Met à jour l'ambiance d'un écran : variable --uc-night (héritée par toutes les cartes), image du ciel en fondu. */
function ucSkyUpdate(host, hass, cfg) {
  const root = host.shadowRoot;
  const sky = root && root.querySelector('.uc-sky');
  if (!sky || !hass) return;
  const amb = ucAmbiance(hass, cfg);
  host.style.setProperty('--uc-night', amb.night ? '1' : '0');
  host.toggleAttribute('nuit', amb.night);
  sky.dataset.meteo = String(amb.meteo);
  if (host._ucImg === amb.img) return;
  host._ucImg = amb.img;
  const layers = sky.querySelectorAll('.uc-sl');
  const cur = Array.from(layers).find((l) => l.classList.contains('on'));
  const next = cur === layers[0] ? layers[1] : layers[0];
  const url = `${UC_BASE}ciel/ciel-${amb.img}.jpg`;
  next.style.backgroundImage = `url(${url})`;
  next.classList.toggle('drift', !UC_LIGHT && !UC_REDUCED);
  // L'image s'affiche une fois chargée, pour un vrai fondu.
  const img = new Image();
  const show = () => { next.classList.add('on'); if (cur) cur.classList.remove('on'); };
  img.onload = show;
  img.onerror = show;
  img.src = url;
}

/** Vague cyan qui traverse l'écran à son ouverture (pas en mode allégé). */
function ucVague(host) {
  if (UC_LIGHT || UC_REDUCED) return;
  const v = host.shadowRoot && host.shadowRoot.querySelector('.uc-vague');
  if (!v || !v.animate) return;
  try {
    v.animate([{ transform: 'translateX(0) skewX(-14deg)' }, { transform: 'translateX(250%) skewX(-14deg)' }],
      { duration: 1300, delay: 150, easing: 'cubic-bezier(.45,0,.2,1)' });
  } catch (e) { /* sans animation */ }
}

/** Pictogramme et température de la météo, pour l'en-tête. */
function ucMeteoHtml(hass, cfg) {
  const wid = ucWeatherId(hass, cfg && cfg.weather_entity);
  if (!wid || (cfg && cfg.weather === false)) return '';
  const w = hass.states[wid];
  const t = Number((w.attributes || {}).temperature);
  const unit = (w.attributes || {}).temperature_unit || '°C';
  return `<span class="meteo" role="img" aria-label="${esc(ucT(hass, 'meteo', { etat: hass.formatEntityState ? hass.formatEntityState(w) : w.state }))}${Number.isFinite(t) ? ', ' + esc(ucNumber(hass, t, 0)) + ' ' + esc(unit) : ''}"><ha-icon icon="${esc(UC_METEO_ICONES[w.state] || 'mdi:weather-partly-cloudy')}"></ha-icon>${Number.isFinite(t) ? `<span>${esc(ucNumber(hass, t, 0))}${esc(unit === '°C' ? '°' : ' ' + unit)}</span>` : ''}</span>`;
}

/** Vrai si l'état d'une des entités a changé depuis le dernier appel pour cette carte.
 *  Home Assistant transmet `hass` à chaque changement d'état de la maison : on ne redessine
 *  la carte que pour ses propres entités. */
function ucChanged(card, hass, ids) {
  if (hass) ucLang(hass);
  const next = ids.map((id) => (hass && hass.states ? hass.states[id] : undefined));
  const prev = card._ucSeen;
  card._ucSeen = next;
  if (!prev || prev.length !== next.length) return true;
  return next.some((st, i) => st !== prev[i]);
}

function ucNumber(hass, value, digits) {
  const lang = (hass && hass.locale && hass.locale.language) || (hass && hass.language) || 'fr';
  try {
    return new Intl.NumberFormat(lang, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
  } catch (e) {
    return Number(value).toFixed(digits);
  }
}

/** État numérique d'une entité, ou null si absente ou indisponible. */
function ucNum(hass, entityId) {
  const st = entityId && hass && hass.states ? hass.states[entityId] : undefined;
  if (!st) return null;
  const v = parseFloat(st.state);
  return Number.isFinite(v) ? v : null;
}

/** Puissance en W (convertit kW si l'unité l'indique). */
function ucWatts(hass, entityId) {
  const v = ucNum(hass, entityId);
  if (v === null) return null;
  const unit = (hass.states[entityId].attributes || {}).unit_of_measurement;
  return unit === 'kW' ? v * 1000 : v;
}

/** Valeur affichée d'une entité avec son unité (« 51,8 V »). */
function ucDisplay(hass, entityId) {
  const st = entityId && hass && hass.states ? hass.states[entityId] : undefined;
  if (!st || st.state === 'unavailable' || st.state === 'unknown') return '—';
  const unit = (st.attributes || {}).unit_of_measurement || '';
  const v = parseFloat(st.state);
  if (!Number.isFinite(v)) return st.state;
  let digits = Math.abs(v) >= 10 ? 1 : 2;
  if (unit === 'Hz') digits = 2;
  if (unit === '%' || unit === 'W') digits = 0;
  return `${ucNumber(hass, v, digits)}${unit ? ' ' + unit : ''}`;
}

function ucMoreInfo(node, entityId) {
  if (!entityId) return;
  node.dispatchEvent(new CustomEvent('hass-more-info', { bubbles: true, composed: true, detail: { entityId } }));
}

function ucNavigate(path) {
  window.history.pushState(null, '', path);
  window.dispatchEvent(new CustomEvent('location-changed', { detail: { replace: false } }));
}

/** Rend un modèle Jinja côté Home Assistant (même mécanisme que la carte markdown) et
 *  rappelle `onChange` à chaque nouveau résultat. Un seul abonnement par clé et par carte. */
function ucTemplate(card, key, template, hass, onChange) {
  card._ucTpl = card._ucTpl || {};
  const slot = card._ucTpl[key] || (card._ucTpl[key] = {});
  if (!template || !hass || !hass.connection) return slot.value;
  if (slot.template === template && slot.conn === hass.connection && slot.unsub) return slot.value;
  if (slot.unsub) slot.unsub.then((u) => u && u()).catch(() => {});
  slot.template = template;
  slot.conn = hass.connection;
  slot.unsub = hass.connection.subscribeMessage((msg) => {
    if (msg && Object.prototype.hasOwnProperty.call(msg, 'result')) {
      slot.value = String(msg.result);
      onChange();
    }
  }, { type: 'render_template', template, strict: false }).catch(() => null);
  return slot.value;
}

function ucTemplatesOff(card) {
  for (const slot of Object.values(card._ucTpl || {})) {
    if (slot.unsub) slot.unsub.then((u) => u && u()).catch(() => {});
  }
  card._ucTpl = {};
}

/** Pose l'attribut `narrow` sur la carte quand SA largeur passe sous `limit` px :
 *  la mise en page suit la place réellement disponible (barre latérale comprise), pas l'écran. */
function ucWatchWidth(card, limit, onChange) {
  if (card._ucRo || typeof ResizeObserver === 'undefined') return;
  card._ucRo = new ResizeObserver(() => {
    const w = card.getBoundingClientRect().width;
    if (!w) return;
    const narrow = w < limit;
    if (narrow !== card.hasAttribute('narrow')) {
      card.toggleAttribute('narrow', narrow);
      if (onChange) onChange(narrow);
    }
  });
  card._ucRo.observe(card);
}

function ucUnwatchWidth(card) {
  if (card._ucRo) card._ucRo.disconnect();
  card._ucRo = null;
}

/** Nombre formaté avec son unité (€ pour EUR). */
function ucFormat(hass, value, digits, unit) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—';
  const u = unit === 'EUR' ? '€' : (unit || '');
  return `${ucNumber(hass, Number(value), digits)}${u ? '\u202f' + u : ''}`;
}

/** Crée les cartes enfants avec les outils de Home Assistant. */
async function ucCreateCards(configs, hass, host) {
  const helpers = window.loadCardHelpers ? await window.loadCardHelpers() : null;
  return (configs || []).map((conf) => {
    const make = () => {
      const el = helpers ? helpers.createCardElement(conf) : document.createElement('div');
      el.hass = host._hass || hass;
      return el;
    };
    let el = make();
    el.addEventListener('ll-rebuild', (ev) => {
      ev.stopPropagation();
      const fresh = make();
      fresh.hass = host._hass;
      el.replaceWith(fresh);
      el = fresh;
    });
    return el;
  });
}

/* Polices locales (Tinos, métriquement identique à Times New Roman), chargées une seule fois. */
(function ucInjectFonts() {
  if (typeof document === 'undefined' || document.getElementById('ucaness-fonts')) return;
  const base = UC_BASE;
  const style = document.createElement('style');
  style.id = 'ucaness-fonts';
  style.textContent = [400, 700].map((w) => `@font-face{font-family:Tinos;font-style:normal;font-weight:${w};font-display:swap;src:url(${base}fonts/tinos-latin-${w}-normal.woff2) format('woff2')}`).join('');
  document.head.appendChild(style);
})();

/* Styles communs (variables surchargeables par le thème). */
const UC_BASE_CSS = `
  :host {
    --uc-font: var(--ucaness-font, ${UC_FONT});
    --uc-text: var(--ucaness-text, #FFFFFF);
    --uc-muted: var(--ucaness-muted, #7DABCD);
    --uc-label: var(--ucaness-label, #02E8EA);
    --uc-value: var(--ucaness-value, #00FFFF);
    --uc-accent: var(--ucaness-accent, #2AB7E2);
    --uc-tab: var(--ucaness-tab, #00D1D6);
    --uc-tab-border: var(--ucaness-tab-border, #446E74);
    --uc-orange: var(--ucaness-orange, #F39C12);
    --uc-green: var(--ucaness-green, #2ECC71);
    --uc-panel-bg: var(--ucaness-panel-bg, linear-gradient(180deg, rgba(10,27,54,0.92) 0%, rgba(8,20,42,0.92) 100%));
    --uc-panel-border: var(--ucaness-panel-border, #12345E);
    --uc-title-bg: var(--ucaness-title-bg, linear-gradient(180deg, #154B84 0%, #0B2C55 100%));
    /* 0.5.0 : cartes intérieures arrondies, bordure fine cyan transparente, ombre douce */
    --uc-card-border: var(--ucaness-card-border, rgba(42,183,226,0.22));
    --uc-card-bg: var(--ucaness-card-bg, linear-gradient(180deg, rgba(20,52,94,0.88) 0%, rgba(12,32,62,0.88) 100%));
    --uc-card-shadow: 0 4px 12px rgba(0,0,0,0.28);
    font-family: var(--uc-font);
    color: var(--uc-text);
  }
  /* Boutons cliquables en relief : liseré clair en haut, bord sombre en bas, ombre portée.
     Clic : le bouton s'enfonce, puis une onde cyan part du centre au relâchement. */
  .uc-key { position: relative; overflow: hidden; box-shadow: inset 0 1px 0 rgba(255,255,255,.18), inset 0 -2px 0 rgba(0,0,0,.35), 0 3px 8px rgba(0,0,0,.4); transition: transform .18s cubic-bezier(.2,.8,.2,1), box-shadow .2s ease, filter .2s ease; -webkit-tap-highlight-color: transparent; }
  .uc-key::after { content: ""; position: absolute; left: 50%; top: 50%; width: 12px; height: 12px; margin: -6px 0 0 -6px; border-radius: 50%; background: radial-gradient(circle, rgba(127,243,245,.7) 0%, rgba(0,209,214,0) 70%); transform: scale(16); opacity: 0; pointer-events: none; transition: transform .55s ease-out, opacity .6s ease-out; }
  .uc-key:active { transform: translateY(1px) scale(.96); filter: brightness(1.05); box-shadow: inset 0 2px 6px rgba(0,0,0,.55), 0 1px 2px rgba(0,0,0,.4); transition-duration: .06s; }
  .uc-key:active::after { transform: scale(0); opacity: 1; transition: 0s; }
  .uc-tile { transition: transform .18s cubic-bezier(.2,.8,.2,1), box-shadow .2s ease, filter .2s ease; -webkit-tap-highlight-color: transparent; }
  .uc-tile:active { transform: scale(.97); }
  .uc-tap { transition: transform .15s ease, filter .2s ease; -webkit-tap-highlight-color: transparent; }
  .uc-tap:active { transform: scale(.94); }
  /* Survol : écrans avec souris seulement. */
  @media (hover: hover) {
    .uc-key:hover { transform: translateY(-2px); filter: brightness(1.15); box-shadow: inset 0 1px 0 rgba(255,255,255,.22), inset 0 -2px 0 rgba(0,0,0,.3), 0 8px 18px rgba(0,0,0,.45), 0 0 16px rgba(0,209,214,.45); }
    .uc-key:hover:active { transform: translateY(1px) scale(.96); }
    .uc-tile:hover { transform: translateY(-2px); filter: brightness(1.1); box-shadow: 0 8px 18px rgba(0,0,0,.4), 0 0 14px rgba(0,209,214,.35); }
    .uc-tap:hover { filter: brightness(1.25); }
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
    .uc-key, .uc-key:active, .uc-tile, .uc-tile:active, .uc-tap, .uc-tap:active { transform: none !important; }
  }
  ${UC_LIGHT ? '*:not(.uc-flow) { animation: none !important; }' : ''}
`;

const UC_DIAMOND = `<span class="diamond" aria-hidden="true"><span><i></i></span></span>`;
const UC_BARS = `<span class="bars" aria-hidden="true"><i class="o"></i><i></i><i></i></span>`;
const UC_TITLE_CSS = `
  .titlebar { position: relative; height: 40px; display: flex; align-items: center; }
  .titlebar .tab { height: 36px; display: flex; align-items: center; gap: 10px; padding: 0 30px 0 6px; background: var(--uc-title-bg); border-top-left-radius: 12px; clip-path: polygon(0 0, calc(100% - 16px) 0, 100% 100%, 0 100%); }
  .titlebar h2 { margin: 0; font: 400 19px var(--uc-font); color: var(--uc-text); white-space: nowrap; }
  .titlebar .line { position: absolute; left: 0; right: 0; bottom: 1px; height: 2px; background: linear-gradient(90deg, var(--uc-accent) 0%, rgba(42,183,226,0.35) 60%, rgba(42,183,226,0) 100%); }
  /* Nuit : filet ambré, en fondu de 1,4 s. */
  .titlebar .line::after { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, #F39C12 0%, rgba(243,156,18,0.35) 60%, rgba(243,156,18,0) 100%); opacity: var(--uc-night, 0); transition: opacity 1.4s ease; }
  .titlebar .status { margin-left: auto; padding-right: 6px; font-size: 13px; color: var(--uc-muted); }
  .diamond { width: 26px; height: 26px; box-sizing: border-box; border: 1px solid rgba(58,134,200,0.7); border-radius: 7px; background: #0A2546; display: flex; align-items: center; justify-content: center; flex: 0 0 26px; }
  .diamond > span { width: 11px; height: 11px; box-sizing: border-box; border: 1.5px solid #6FD6F5; border-radius: 2px; transform: rotate(45deg); display: flex; align-items: center; justify-content: center; }
  .diamond i { width: 3px; height: 3px; background: #BFF2FF; }
  .bars { display: flex; gap: 3px; margin: 0 0 16px 2px; }
  .bars i { width: 8px; height: 6px; background: var(--uc-accent); transform: skewX(-40deg); }
  .bars i.o { background: var(--uc-orange); }
`;

/* ------------------------------------------------------------------ en-tête */

class UcanessHeaderCard extends HTMLElement {
  setConfig(config) {
    this._config = Object.assign({ title: 'UCANESS HOME ASSISTANT', site: 'Maison', tabs: [], alert_entities: [] }, config || {});
    this._ucSeen = null;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const c = this._config || {};
    const ids = [c.connectivity_entity, c.subtitle_entity, ...(c.alert_entities || []), ...(c.tabs || []).map((t) => t.entity), ucWeatherId(hass, c.weather_entity)].filter(Boolean);
    if (ucChanged(this, hass, ids)) this._render();
  }

  connectedCallback() {
    this._timer = setInterval(() => this._render(), 30000);
    this._onLoc = () => this._render();
    window.addEventListener('location-changed', this._onLoc);
    ucWatchWidth(this, (this._config && this._config.mobile_breakpoint) || 900);
    // 0.4.3 : onglets sous le titre quand ils le chevaucheraient (écran moyen, nombreux onglets).
    if (!this._ucFit && typeof ResizeObserver !== 'undefined') {
      this._ucFit = new ResizeObserver(() => this._fitRows());
      this._ucFit.observe(this);
    }
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    window.removeEventListener('location-changed', this._onLoc);
    ucUnwatchWidth(this);
    if (this._ucFit) this._ucFit.disconnect();
    this._ucFit = null;
  }

  getCardSize() { return 1; }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const c = this._config;
    const hass = this._hass;
    const lang = (hass && hass.locale && hass.locale.language) || 'fr';
    const now = new Date();
    const time = now.toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit' });
    const date = now.toLocaleDateString(lang, { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' });
    const path = window.location.pathname;
    const alerts = (c.alert_entities || []).filter((e) => hass && hass.states[e] && hass.states[e].state === 'on').length;
    const conn = c.connectivity_entity && hass ? hass.states[c.connectivity_entity] : null;
    const online = conn ? conn.state === 'on' : null;
    const subtitle = c.subtitle_entity && hass && hass.states[c.subtitle_entity] ? hass.states[c.subtitle_entity].state : (c.subtitle || '');
    const tabs = (c.tabs || []).map((t, i) => {
      const active = path.endsWith('/' + String(t.path).replace(/^\/+/, '').split('/').pop());
      const extra = t.entity && hass && hass.states[t.entity] ? ` <b>${esc(ucDisplay(hass, t.entity))}</b>` : '';
      return `<button type="button" class="tab${active ? ' on' : ''}" data-i="${i}" ${active ? 'aria-current="page"' : ''}><span class="uc-key">${esc(t.title)}${extra}</span></button>`;
    }).join('');
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        header { position: relative; height: 62px; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; background: linear-gradient(180deg, #0B2F5C 0%, #061B3D 100%); border-bottom: 1px solid #1C5C9E; box-shadow: 0 2px 14px rgba(0,0,0,0.55); overflow: hidden; }
        header::before { content: ''; position: absolute; inset: 0; background: linear-gradient(180deg, #081A36 0%, #040D1F 100%); opacity: var(--uc-night, 0); transition: opacity 1.4s ease; pointer-events: none; }
        .meteo { display: flex; align-items: center; gap: 4px; font: 400 17px var(--uc-font); color: #E6ECF5; --mdc-icon-size: 24px; }
        .meteo ha-icon { color: #FFD27A; }
        :host([narrow]) .meteo { font-size: 15px; --mdc-icon-size: 20px; }
        .plate { position: absolute; left: 50%; top: 0; width: min(620px, 52%); height: 58px; transform: translateX(-50%); clip-path: polygon(0 0, 100% 0, 95% 100%, 5% 100%); background: linear-gradient(180deg, #1A6FBE 0%, #0E4382 62%, #0A2F5E 100%); overflow: hidden; }
        .sweep { position: absolute; top: 0; left: 0; width: 140px; height: 58px; background: linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(160,220,255,0.22) 50%, rgba(255,255,255,0) 100%); animation: sweep 7s ease-in-out infinite; }
        @keyframes sweep { 0% { transform: translateX(-120%); } 60%, 100% { transform: translateX(520%); } }
        h1 { position: relative; margin: 0; height: 58px; display: flex; align-items: center; justify-content: center; font: 700 clamp(18px, 2.4vw, 31px) ${UC_BRAND_FONT}; background: linear-gradient(180deg, #FFFFFF 78%, #7DABCD 100%); -webkit-background-clip: text; background-clip: text; color: transparent; white-space: nowrap; }
        .left, .right { display: flex; align-items: center; gap: 14px; z-index: 1; }
        .site { display: flex; align-items: center; gap: 8px; font: 500 19px var(--uc-font); color: #C9CACA; }
        .tab { height: 44px; padding: 0 2px; border: 0; background: transparent; cursor: pointer; font: inherit; }
        .tab span { display: block; padding: 5px 14px; border: 1px solid var(--uc-tab-border); border-radius: 18px; background: linear-gradient(180deg, rgba(26,111,190,0.35) 0%, rgba(10,37,70,0.6) 100%); color: var(--uc-text); font: 400 16px var(--uc-font); }
        .tab.on span { background: linear-gradient(180deg, #33E4E8 0%, var(--uc-tab) 55%, #00A9AE 100%); border-color: #7FF3F5; }
        .tab b { font-weight: 400; color: var(--uc-green); }
        .tab.on b { color: var(--uc-text); }
        .bell { position: relative; display: flex; }
        .badge { position: absolute; right: -9px; top: -7px; min-width: 18px; height: 16px; padding: 0 4px; box-sizing: border-box; border-radius: 8px; background: #E5484D; font: 700 11px var(--uc-font); display: flex; align-items: center; justify-content: center; }
        .clock { display: flex; flex-direction: column; align-items: flex-end; line-height: 1.1; }
        .clock b { font: 700 22px var(--uc-font); }
        .clock span { font-size: 12px; color: var(--uc-muted); }
        :host([rows]) header { height: auto; flex-wrap: wrap; padding: 0 16px 8px; }
        :host([rows]) .plate { position: relative; left: auto; transform: none; flex: 0 0 min(620px, 60%); margin: 0 auto; }
        :host([rows]) .right { position: absolute; top: 0; right: 16px; height: 58px; }
        :host([rows]) .left { flex: 0 0 100%; margin-top: 4px; }
        :host([narrow]) header { height: auto; min-height: 56px; flex-wrap: wrap; gap: 6px 12px; padding: 6px 10px; }
        :host([narrow]) .plate { display: none; }
        :host([narrow]) .site span { display: none; }
        :host([narrow]) .left, :host([narrow]) .right { gap: 8px; }
        :host([narrow]) .clock b { font-size: 18px; }
      </style>
      <header>
        <div class="plate"><div class="sweep" aria-hidden="true"></div><h1>${esc(c.title)}</h1></div>
        <div class="left">
          <span class="site"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#F0883E" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M3 11.5L12 4l9 7.5"/><path d="M6 10v10h12V10"/></svg><span>${esc(c.site)}</span></span>
          <nav aria-label="${esc(ucT(hass, 'vues'))}">${tabs}</nav>
        </div>
        <div class="right">
          ${(c.alert_entities || []).length ? `<span class="bell" role="img" aria-label="${esc(ucT(hass, 'alertes_en_cours', { n: alerts }))}"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#7DABCD" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20a2 2 0 0 0 4 0"/></svg>${alerts ? `<span class="badge">${alerts}</span>` : ''}</span>` : ''}
          ${online === null ? '' : `<svg role="img" aria-label="${esc(ucT(hass, online ? 'cloud_en_ligne' : 'cloud_perdu'))}" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="${online ? '#2ED198' : '#E5484D'}" stroke-width="2" stroke-linecap="round"><path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19.5" r="1" fill="currentColor"/></svg>`}
          ${hass ? ucMeteoHtml(hass, c) : ''}
          <span class="clock"><b>${esc(time)}</b><span>${esc(date)}${subtitle ? ' · ' + esc(subtitle) : ''}</span></span>
        </div>
      </header>`;
    this.shadowRoot.querySelectorAll('.tab').forEach((b) => b.addEventListener('click', () => {
      const t = c.tabs[Number(b.dataset.i)];
      if (t && t.path) ucNavigate(t.path);
    }));
    this._fitRows();
  }

  /** Passe les onglets sur une 2e ligne si le bloc de gauche ou de droite empiète sur le titre. */
  _fitRows() {
    const r = this.shadowRoot;
    if (!r) return;
    if (this.hasAttribute('narrow')) { this.removeAttribute('rows'); return; }
    const plate = r.querySelector('.plate');
    const left = r.querySelector('.left');
    const right = r.querySelector('.right');
    if (!plate || !left || !right) return;
    this.removeAttribute('rows');
    const p = plate.getBoundingClientRect();
    if (!p.width) return;
    const inset = p.width * 0.05;
    const clash = left.getBoundingClientRect().right > p.left + inset - 6
      || right.getBoundingClientRect().left < p.right - inset + 6;
    this.toggleAttribute('rows', clash);
  }
}

/* ------------------------------------------------------------------ mise en page */

class UcanessLayoutCard extends HTMLElement {
  setConfig(config) {
    if (!config || !Array.isArray(config.columns) || !config.columns.length) {
      throw new Error(ucT(null, 'err_layout'));
    }
    this._config = config;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    (this._children || []).forEach((el) => { el.hass = hass; });
    if (this._header) this._header.hass = hass;
    // 0.5.0 : ambiance jour / nuit et ciel, recalculés quand le soleil ou la météo changent.
    const c = this._config || {};
    if (c.sky !== false && ucChanged(this, hass, [c.sun_entity || 'sun.sun', ucWeatherId(hass, c.weather_entity)].filter(Boolean))) ucSkyUpdate(this, hass, c);
  }

  getCardSize() { return 12; }

  connectedCallback() {
    ucWatchWidth(this, (this._config && this._config.mobile_breakpoint) || 1000);
    if (this._children && this._children.length) this._entree();
  }

  disconnectedCallback() { ucUnwatchWidth(this); }

  /** Ouverture de l'écran : vague cyan, puis les cartes en cascade. */
  _entree() {
    ucVague(this);
    (this._children || []).forEach((el, i) => ucRise(el, Math.min(80 + i * 70, 700)));
  }

  async _build() {
    const c = this._config;
    const widths = c.columns.map((col) => col.width || '1fr').join(' ');
    const main = Number.isInteger(c.mobile_first_column) ? c.mobile_first_column : Math.floor(c.columns.length / 2);
    const sky = c.sky !== false;
    this._ucSeen = null;
    this._ucImg = null;
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}${sky ? UC_SKY_CSS : ''}
        :host { display: block; min-height: 100%; position: relative; isolation: isolate; background: ${sky ? 'transparent' : 'var(--ucaness-page-bg, radial-gradient(ellipse at 50% 42%, #0D2A58 0%, #071A3A 48%, #030B20 100%))'}; }
        .wrap { display: flex; flex-direction: column; gap: 10px; padding-bottom: 14px; }
        .grid { display: grid; grid-template-columns: ${widths}; gap: ${c.gap || '12px'}; padding: 0 16px; align-items: start; }
        .col { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
        :host([narrow]) .grid { grid-template-columns: minmax(0, 1fr); padding: 0 8px; }
        :host([narrow]) .col[data-i="${main}"] { order: -1; }
      </style>
      ${sky ? UC_SKY_HTML : ''}<div class="wrap"><div class="head"></div><div class="grid"></div></div>`;
    if (sky && this._hass) ucSkyUpdate(this, this._hass, c);
    const grid = this.shadowRoot.querySelector('.grid');
    if (c.header) {
      this._header = document.createElement('ucaness-header-card');
      this._header.setConfig(c.header);
      if (this._hass) this._header.hass = this._hass;
      this.shadowRoot.querySelector('.head').appendChild(this._header);
    }
    this._children = [];
    for (let i = 0; i < c.columns.length; i++) {
      const colEl = document.createElement('div');
      colEl.className = 'col';
      colEl.dataset.i = String(i);
      grid.appendChild(colEl);
      const cards = await ucCreateCards(c.columns[i].cards, this._hass, this);
      cards.forEach((el) => { colEl.appendChild(el); this._children.push(el); });
    }
    this._entree();
  }
}

/* ------------------------------------------------------------------ panneau */

class UcanessPanelCard extends HTMLElement {
  setConfig(config) {
    if (!config || (!config.cards && !config.slides)) {
      throw new Error(ucT(null, 'err_panel'));
    }
    this._config = config;
    this._slide = 0;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    (this._children || []).flat().forEach((el) => { el.hass = hass; });
    this._status();
  }

  connectedCallback() { this._startTimer(); }

  /** Défilement automatique du carrousel ; relancé après un choix manuel pour laisser le temps de lire. */
  _startTimer() {
    clearInterval(this._timer);
    const c = this._config || {};
    if (this.isConnected && c.slides && c.slides.length > 1 && c.interval !== 0 && !c.tabs) {
      this._timer = setInterval(() => this._show((this._slide + 1) % c.slides.length), (c.interval || 8) * 1000);
    }
  }

  disconnectedCallback() { clearInterval(this._timer); }

  getCardSize() { return 4; }

  async _build() {
    const c = this._config;
    const slides = c.slides || [{ title: c.title, cards: c.cards }];
    // tabs: true → titre fixe, onglets nommés en haut du panneau, pas de défilement automatique.
    const tabs = !!(c.tabs && c.slides && c.slides.length > 1);
    const title = tabs ? (c.title || '') : (slides[0].title || '');
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}${UC_TITLE_CSS}
        :host { display: block; }
        .body { position: relative; isolation: isolate; box-sizing: border-box; padding: 8px; display: flex; flex-direction: column; gap: 8px; background: var(--uc-panel-bg); border: 1px solid var(--uc-card-border); border-top: 0; border-radius: 0 0 12px 12px; box-shadow: 0 6px 18px rgba(0,0,0,0.28); --ha-card-border-radius: 12px; --ha-card-border-color: var(--uc-card-border); }
        /* Nuit : panneau plus foncé, en fondu de 1,4 s. */
        .body::before { content: ''; position: absolute; inset: 0; z-index: -1; border-radius: inherit; background: linear-gradient(180deg, rgba(10,18,36,0.93) 0%, rgba(5,10,22,0.93) 100%); opacity: var(--uc-night, 0); transition: opacity 1.4s ease; pointer-events: none; }
        .body.dots-on { padding-bottom: 24px; }
        .slide { display: flex; flex-direction: column; gap: 8px; animation: ucIn .45s ease-out both; }
        .slide[hidden] { display: none; }
        @keyframes ucIn { from { opacity: 0; transform: translateY(-12px); } to { opacity: 1; transform: none; } }
        .dots { position: absolute; left: 0; right: 0; bottom: 0; display: flex; justify-content: center; }
        .dots button { width: 44px; height: 22px; border: 0; background: transparent; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .dots i { display: block; width: 14px; height: 3px; background: #4E6C93; }
        .dots button.on i { width: 24px; background: #FFFFFF; }
        .tabs { display: flex; gap: 6px; }
        .tabs button { flex: 1 1 0; min-width: 0; min-height: 48px; box-sizing: border-box; padding: 4px 2px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; border: 1px solid #1E4E85; border-radius: 12px; background: linear-gradient(180deg, rgba(26,111,190,0.32) 0%, rgba(10,30,60,0.7) 100%); color: var(--uc-text); font: 400 12px var(--uc-font); cursor: pointer; --mdc-icon-size: 18px; }
        .tabs button ha-icon { color: #9CC9F5; }
        .tabs button[aria-selected="true"] { border-color: #22E0F0; background: rgba(18,80,150,0.55); box-shadow: 0 0 10px rgba(34,224,240,0.55); }
        .titlebar.toggle { cursor: pointer; -webkit-tap-highlight-color: transparent; }
        .titlebar.toggle:focus-visible { outline: 2px solid #22E0F0; outline-offset: 2px; }
        .chev { width: 12px; height: 12px; margin: 0 4px 0 2px; color: #00D1D6; transition: transform .2s ease; flex: 0 0 12px; }
        section.reduit .chev { transform: rotate(-90deg); }
        section.reduit .body { display: none; }
      </style>
      <section aria-label="${esc(title)}">
        <div class="titlebar"><div class="tab">${UC_DIAMOND}<h2>${esc(title)}</h2>${c.collapsible === false ? '' : '<svg class="chev" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>'}</div>${c.slides && !tabs ? '' : UC_BARS}<span class="status"></span><div class="line" aria-hidden="true"></div></div>
        <div class="body${slides.length > 1 && !tabs ? ' dots-on' : ''}"></div>
      </section>`;
    const body = this.shadowRoot.querySelector('.body');
    this._setupCollapse(title);
    this._children = [];
    if (tabs) {
      const bar = document.createElement('div');
      bar.className = 'tabs';
      bar.setAttribute('role', 'tablist');
      bar.setAttribute('aria-label', title);
      bar.innerHTML = slides.map((s, i) => `<button type="button" class="uc-key" role="tab" aria-selected="${i ? 'false' : 'true'}" data-i="${i}">${s.icon ? `<ha-icon icon="${esc(s.icon)}"></ha-icon>` : ''}<span>${esc(s.tab || s.title || i + 1)}</span></button>`).join('');
      bar.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => this._show(Number(b.dataset.i))));
      body.appendChild(bar);
    }
    for (let i = 0; i < slides.length; i++) {
      const s = document.createElement('div');
      s.className = 'slide';
      if (i) s.hidden = true;
      body.appendChild(s);
      const cards = await ucCreateCards(slides[i].cards || (slides[i].card ? [slides[i].card] : []), this._hass, this);
      cards.forEach((el) => s.appendChild(el));
      this._children.push(cards);
    }
    if (slides.length > 1 && !tabs) {
      const dots = document.createElement('div');
      dots.className = 'dots';
      dots.innerHTML = slides.map((s, i) => `<button type="button" aria-label="${esc(ucT(null, 'afficher', { titre: s.title || i + 1 }))}" class="${i ? '' : 'on'}" data-i="${i}"><i></i></button>`).join('');
      dots.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => { this._show(Number(b.dataset.i)); this._startTimer(); }));
      body.appendChild(dots);
    }
    this._status();
  }

  /** Réduire ou déplier le panneau d'un appui sur son titre ; état gardé sur l'appareil (page + titre). */
  _setupCollapse(title) {
    const c = this._config;
    if (c.collapsible === false) return;
    const section = this.shadowRoot.querySelector('section');
    const bar = this.shadowRoot.querySelector('.titlebar');
    const key = 'ucaness-reduit:' + location.pathname + ':' + (c.collapse_id || title);
    let reduit = false;
    try { reduit = localStorage.getItem(key) === '1'; } catch (e) { /* stockage indisponible : panneau déplié */ }
    if (c.collapsed_default && !(() => { try { return localStorage.getItem(key) !== null; } catch (e) { return false; } })()) reduit = true;
    const apply = () => {
      section.classList.toggle('reduit', reduit);
      bar.setAttribute('aria-expanded', String(!reduit));
      bar.title = ucT(null, reduit ? 'deplier' : 'reduire');
    };
    bar.classList.add('toggle');
    bar.setAttribute('role', 'button');
    bar.tabIndex = 0;
    const toggle = () => {
      reduit = !reduit;
      try { localStorage.setItem(key, reduit ? '1' : '0'); } catch (e) { /* sans mémoire : état perdu au rechargement */ }
      apply();
      this.dispatchEvent(new Event('iron-resize', { bubbles: true, composed: true }));
    };
    bar.addEventListener('click', toggle);
    bar.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggle(); } });
    apply();
  }

  _show(i) {
    const slides = this._config.slides || [];
    if (!this.shadowRoot || !slides[i]) return;
    this._slide = i;
    this.shadowRoot.querySelectorAll('.slide').forEach((s, k) => { s.hidden = k !== i; });
    this.shadowRoot.querySelectorAll('.dots button').forEach((b, k) => b.classList.toggle('on', k === i));
    this.shadowRoot.querySelectorAll('.tabs button').forEach((b, k) => b.setAttribute('aria-selected', String(k === i)));
    if (this._config.tabs) return;  // onglets : le titre du panneau ne change pas
    this.shadowRoot.querySelector('.titlebar h2').textContent = slides[i].title || '';
    this.shadowRoot.querySelector('section').setAttribute('aria-label', slides[i].title || '');
  }

  _status() {
    const c = this._config;
    const el = this.shadowRoot && this.shadowRoot.querySelector('.status');
    if (!el || !c.status_entity || !this._hass) return;
    el.textContent = ucDisplay(this._hass, c.status_entity);
  }
}

/* ------------------------------------------------------------------ vue en direct */

const UC_FLOW_DEFAULTS = {
  image: UC_BASE + 'maison-exemple.svg',
  aspect_ratio: 1.45,
  image_area: { x: 0, y: 6.5, w: 100 },
  min_power: 30,
  calibration: false,
  nodes: {
    solar: { entity: 'sensor.uhome_puissance_solaire', x: 44, y: 11.5, details: ['sensor.uhome_tension_solaire'], details_side: 'left' },
    grid: { entity: 'sensor.uhome_puissance_reseau', x: 65, y: 11.5, details: ['sensor.uhome_tension_reseau', 'sensor.uhome_frequence_reseau'], details_side: 'right' },
    inverter: { x: 44, y: 46 },
    battery: { entity: 'sensor.uhome_puissance_batterie', soc_entity: 'sensor.uhome_soc', x: 20, y: 79, details: ['sensor.uhome_tension_batterie', 'sensor.uhome_courant_batterie'], details_side: 'right' },
    home: { entity: 'sensor.uhome_puissance_maison', x: 60, y: 79, details: [], details_side: 'right' },
  },
};

class UcanessFlowCard extends HTMLElement {
  static getStubConfig() { return {}; }

  setConfig(config) {
    const c = Object.assign({}, UC_FLOW_DEFAULTS, config || {});
    c.nodes = {};
    for (const k of Object.keys(UC_FLOW_DEFAULTS.nodes)) {
      c.nodes[k] = Object.assign({}, UC_FLOW_DEFAULTS.nodes[k], ((config || {}).nodes || {})[k] || {});
    }
    c.image_area = Object.assign({}, UC_FLOW_DEFAULTS.image_area, (config || {}).image_area || {});
    this._config = c;
    this._ucSeen = null;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this.shadowRoot.innerHTML = '';
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (ucChanged(this, hass, this._ids())) this._render();
  }

  /** Entités affichées par la carte (puissances, charge, détails). */
  _ids() {
    const ids = [];
    const c = this._config;
    for (const n of Object.values(c.nodes)) {
      if (n.entity) ids.push(n.entity);
      if (n.soc_entity) ids.push(n.soc_entity);
      (n.details || []).forEach((d) => ids.push(d));
    }
    if (c.ev) [c.ev.entity, c.ev.state_entity].forEach((e) => e && ids.push(e));
    if (c.mode_entity) ids.push(c.mode_entity);
    return ids;
  }

  /* L'âge du relevé (« il y a 20 s ») avance même sans nouvelle mesure. */
  connectedCallback() { this._timer = setInterval(() => this._render(), 30000); }

  disconnectedCallback() { clearInterval(this._timer); }

  getCardSize() { return 8; }

  /** Sens et intensité d'un flux : 'in' = vers l'onduleur, 'out' = depuis l'onduleur, null = au repos. */
  _flow(key) {
    const n = this._config.nodes[key];
    const w = ucWatts(this._hass, n.entity);
    if (w === null) return { w: null, dir: null };
    const v = n.invert ? -w : w;
    if (Math.abs(v) < this._config.min_power) return { w: v, dir: null };
    if (key === 'solar') return { w: v, dir: v > 0 ? 'in' : null };
    if (key === 'home') return { w: v, dir: v > 0 ? 'out' : null };
    if (key === 'battery') return { w: v, dir: v > 0 ? 'out' : 'in' };  // charge > 0 : de l'onduleur vers la batterie
    if (key === 'grid') return { w: v, dir: v > 0 ? 'in' : 'out' };     // soutirage > 0 : du réseau vers l'onduleur
    return { w: v, dir: null };
  }

  /** Tracé orthogonal de la boule vers l'onduleur (coordonnées en unités du SVG). */
  _route(key, W, H) {
    const c = this._config;
    const n = c.nodes[key];
    const inv = c.nodes.inverter;
    const P = (p) => [p[0] * W / 100, p[1] * H / 100];
    if (Array.isArray(n.path) && n.path.length >= 2) return n.path.map(P);
    const r = (key === 'solar' ? 6.75 : key === 'grid' ? 6.1 : 5.8) * W / 100;  // rayon des boules
    const iw = 7.7 * W / 100, ih = 4.5 * W / 100;                             // demi-onduleur
    const [nx, ny] = P([n.x, n.y]);
    const [ix, iy] = P([inv.x, inv.y]);
    if (ny < iy) {  // boule au-dessus de l'onduleur
      if (Math.abs(nx - ix) < iw * 0.6) return [[nx, ny + r], [nx, iy - ih]];
      const side = nx > ix ? ix + iw : ix - iw;
      return [[nx, ny + r], [nx, iy], [side, iy]];
    }
    // boule sous l'onduleur
    const sx = Math.max(ix - iw * 0.75, Math.min(ix + iw * 0.75, nx));
    if (Math.abs(nx - sx) < 1) return [[nx, ny - r], [sx, iy + ih]];
    const midY = iy + ih + Math.max(12, (ny - r - iy - ih) * 0.35);
    const endX = nx < ix ? ix - iw * 0.45 : ix + iw * 0.45;
    return [[nx, ny - r], [nx, midY], [endX, midY], [endX, iy + ih]];
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    if (this._config.scene === '3d' || this._config.scene === 'maison-3d') return this._renderScene();
    const c = this._config;
    const hass = this._hass || { states: {} };
    const W = 1000, H = Math.round(1000 / c.aspect_ratio);
    const kw = (w) => (w === null ? '—' : ucNumber(hass, Math.abs(w) / 1000, 2));
    let paths = '';
    const flows = {};
    for (const key of ['solar', 'grid', 'battery', 'home']) {
      const f = this._flow(key);
      flows[key] = f;
      let pts = this._route(key, W, H);
      const active = f.dir !== null;
      if (active && f.dir === 'out') pts = pts.slice().reverse();
      const d = 'M' + pts.map((p) => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L');
      if (active) {
        const [ex, ey] = pts[pts.length - 1];
        const [px, py] = pts[pts.length - 2];
        const ang = Math.atan2(ey - py, ex - px);
        const a = 13, s = 0.6;
        const p1 = [ex - a * Math.cos(ang - s), ey - a * Math.sin(ang - s)];
        const p2 = [ex - a * Math.cos(ang + s), ey - a * Math.sin(ang + s)];
        paths += `<path class="flow" d="${d}"/><path class="pulse" d="${d}"/><path class="arrow" d="M${p1[0].toFixed(1)} ${p1[1].toFixed(1)} L${ex.toFixed(1)} ${ey.toFixed(1)} L${p2[0].toFixed(1)} ${p2[1].toFixed(1)}"/>`;
      } else {
        paths += `<path class="idle" d="${d}"/>`;
      }
    }
    const names = { solar: ucT(hass, 'solaire'), grid: ucT(hass, 'reseau'), battery: ucT(hass, 'batterie'), home: ucT(hass, 'maison') };
    const nodeHtml = (key, cls, label) => {
      const n = c.nodes[key];
      const f = flows[key];
      const on = f.dir !== null;
      const det = c.details === false ? '' : (n.details || []).map((e) => esc(ucDisplay(hass, e))).join('<br>');
      const side = n.details_side === 'left' ? 'left' : 'right';
      return `
        <button type="button" class="ball ${cls}${on ? ' on' : ''}${f.w === null ? ' na' : ''}" style="left:${n.x}%;top:${n.y}%" data-entity="${esc(n.entity || '')}" aria-label="${esc((label || names[key]) + ' : ' + kw(f.w) + ' kW')}">
          ${label ? `<span class="lbl">${esc(label)}</span>` : ''}<span class="val">${key === 'battery' && f.w !== null && f.w < 0 ? '−' : ''}${esc(kw(f.w))}</span><span class="unit">kW</span>
        </button>
        ${det ? `<div class="det ${side} ${cls}" style="left:${n.x}%;top:${n.y}%">${det}</div>` : ''}`;
    };
    const inv = c.nodes.inverter;
    const bat = c.nodes.battery;
    const soc = ucNum(hass, bat.soc_entity);
    const bf = flows.battery;
    const batState = ucT(hass, bf.dir === 'out' ? 'bat_chargement' : bf.dir === 'in' ? 'bat_decharge' : 'bat_veille');
    const home = c.nodes.home;
    let grid = '';
    if (c.calibration) {
      for (let i = 10; i < 100; i += 10) {
        grid += `<div class="cal v" style="left:${i}%"><span>${i}</span></div><div class="cal h" style="top:${i}%"><span>${i}</span></div>`;
      }
    }
    const ages = Object.values(c.nodes).map((n) => n.entity && hass.states[n.entity] && Date.parse(hass.states[n.entity].last_updated)).filter((t) => Number.isFinite(t));
    const age = ages.length ? Math.max(0, Math.round((Date.now() - Math.max(...ages)) / 1000)) : null;
    const ia = c.image_area;
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        .stage { position: relative; width: 100%; aspect-ratio: ${c.aspect_ratio}; container-type: inline-size; --bs: ${Number(c.ball_scale) || 1}; }
        .house { position: absolute; left: ${ia.x}%; top: ${ia.y}%; width: ${ia.w}%; height: auto; pointer-events: none; user-select: none; }
        svg.lines { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none; }
        .flow, .pulse, .idle, .arrow { fill: none; vector-effect: non-scaling-stroke; stroke-linejoin: round; stroke-linecap: round; }
        .flow { stroke: var(--uc-green); stroke-width: 3; }
        .arrow { stroke: var(--uc-green); stroke-width: 3; }
        .pulse { stroke: #D9FFE9; stroke-width: 3; stroke-dasharray: 2 16; animation: flow 1.2s linear infinite; }
        .idle { stroke: #C9CED6; stroke-width: 3; stroke-dasharray: 10 8; opacity: .8; }
        @keyframes flow { to { stroke-dashoffset: -36; } }
        .ball { position: absolute; transform: translate(-50%, -50%); width: calc(11.6cqw * var(--bs)); height: calc(11.6cqw * var(--bs)); box-sizing: border-box; border-radius: 50%; border: .65cqw solid #B9C2CC; padding: 0; background: radial-gradient(circle at 38% 30%, #FFFFFF 0%, #DDE2E8 55%, #A9B3BE 100%); box-shadow: inset 0 -4px 8px rgba(0,0,0,0.18); display: flex; flex-direction: column; align-items: center; justify-content: center; color: #133960; font: 800 max(${c.ball_scale ? 11 : 9}px, calc(2.1cqw * var(--bs))) var(--uc-font); line-height: 1.05; cursor: pointer; }
        .ball.solar { width: calc(13.5cqw * var(--bs)); height: calc(13.5cqw * var(--bs)); }
        .ball.grid { width: calc(12.2cqw * var(--bs)); height: calc(12.2cqw * var(--bs)); }
        .ball.on { border-color: var(--uc-green); box-shadow: 0 0 2.6cqw rgba(46,204,113,0.6), inset 0 -4px 8px rgba(0,0,0,0.18); }
        .ball.na { opacity: .6; }
        .ball .val { font-size: max(${c.ball_scale ? 16 : 11}px, calc(3cqw * var(--bs))); }
        .det { position: absolute; transform: translateY(-50%); font-size: max(10px, 2.2cqw); line-height: 1.35; white-space: nowrap; text-shadow: 0 1px 3px #000; }
        .det.right { margin-left: 7.5cqw; }
        .det.left { transform: translate(-100%, -50%); margin-left: -8.2cqw; text-align: right; }
        .inv { position: absolute; left: ${inv.x}%; top: ${inv.y}%; transform: translate(-50%, -50%); width: 15.4cqw; height: 9cqw; box-sizing: border-box; border: 2px solid #2F80ED; border-radius: 4px; background: linear-gradient(180deg, #0F3470 0%, #0A2450 100%); box-shadow: 0 0 3.5cqw rgba(47,128,237,0.6); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: .3cqw; color: #CFE6FF; font-size: 1.8cqw; letter-spacing: 1px; }
        .inv svg { width: 7cqw; height: auto; }
        .bat { position: absolute; left: ${bat.x}%; top: ${bat.y}%; transform: translate(-2.6cqw, 7.6cqw); display: flex; align-items: flex-end; gap: 1.6cqw; color: var(--uc-text); background: none; border: 0; padding: 0; font: inherit; cursor: pointer; }
        .bat .cell { position: relative; width: 5.1cqw; height: 6.4cqw; box-sizing: border-box; border: 2px solid #3A8EEA; border-radius: 3px; background: rgba(10,36,80,0.7); box-shadow: 0 0 1.6cqw rgba(58,142,234,0.5); }
        .bat .cell::before { content: ''; position: absolute; left: 30%; top: -.9cqw; width: 40%; height: .6cqw; background: #3A8EEA; }
        .bat .fill { position: absolute; left: 3px; right: 3px; bottom: 3px; background: var(--uc-green); }
        .bat .txt { display: flex; flex-direction: column; align-items: center; font-size: max(${c.ball_scale ? 13 : 10}px, calc(2.4cqw * var(--bs))); line-height: 1.2; text-shadow: 0 1px 3px #000; }
        .bulb { position: absolute; left: ${home.x}%; top: ${home.y}%; transform: translate(-50%, 6.6cqw); width: 6.4cqw; height: auto; filter: drop-shadow(0 0 1.3cqw rgba(255,196,64,${flows.home.dir ? '0.8' : '0.15'})); opacity: ${flows.home.dir ? 1 : 0.5}; }
        .live { position: absolute; left: .6%; top: .4%; display: flex; align-items: center; gap: 6px; font-size: max(11px, 1.8cqw); color: var(--uc-value); }
        .live i { width: 7px; height: 7px; border-radius: 50%; background: #2ED198; animation: pulse 1.6s ease-in-out infinite; }
        @keyframes pulse { 50% { opacity: .3; } }
        .glow { position: absolute; left: 37%; bottom: -7px; width: 26%; height: 4px; border-radius: 2px; background: #22E0F0; box-shadow: 0 0 14px #22E0F0, 0 0 4px #FFFFFF; animation: bar 2.4s ease-in-out infinite; }
        @keyframes bar { 50% { opacity: .55; } }
        .cal { position: absolute; background: rgba(255,80,80,.45); pointer-events: none; }
        .cal.v { top: 0; bottom: 0; width: 1px; }
        .cal.h { left: 0; right: 0; height: 1px; }
        .cal span { position: absolute; font: 11px monospace; color: #FF8080; left: 2px; top: 2px; }
      </style>
      <div class="stage" role="group" aria-label="${esc(ucT(hass, 'flux_direct'))}">
        <img class="house" src="${esc(c.image)}" alt="">
        <svg class="lines" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${paths}</svg>
        <div class="inv" aria-hidden="true"><svg viewBox="0 0 44 26" fill="none" stroke="#8FD3FF" stroke-width="2" stroke-linecap="round"><rect x="2" y="2" width="40" height="22" rx="3"/><path d="M9 13c2-5 4-5 6 0s4 5 6 0 4-5 6 0 4 5 6 0"/></svg><span>${esc(inv.label || ucT(hass, 'onduleur'))}</span></div>
        ${nodeHtml('solar', 'solar', c.nodes.solar.label || names.solar)}
        ${nodeHtml('grid', 'grid', c.nodes.grid.label || names.grid)}
        ${nodeHtml('battery', 'battery', c.nodes.battery.label || '')}
        ${nodeHtml('home', 'home', c.nodes.home.label || '')}
        <button type="button" class="bat" data-entity="${esc(bat.soc_entity || '')}" aria-label="${esc(ucT(hass, 'batterie_a', { soc: soc === null ? '—' : Math.round(soc), etat: batState }))}">
          <span class="cell"><span class="fill" style="height:${soc === null ? 0 : Math.max(6, Math.min(100, soc)) * 0.86}%"></span></span>
          <span class="txt">${soc === null ? '—' : esc(ucNumber(hass, Math.round(soc), 0))} %<span>${batState}</span></span>
        </button>
        <svg class="bulb" viewBox="0 0 24 26" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4a6 6 0 0 0-4 10.5c.8.8 1 1.6 1 2.5h6c0-.9.2-1.7 1-2.5A6 6 0 0 0 12 4z" fill="#FFC440" stroke="#FFB020" stroke-width="1"/><path d="M9.5 19h5M10 21.5h4" stroke="#9AA6BE" stroke-width="1.6"/><path d="M3 5l2 1.5M21 5l-2 1.5M1.5 11.5h2.5M20 11.5h2.5M5 18l1.6-1.2M19 18l-1.6-1.2" stroke="#FFC440" stroke-width="1.4"/></svg>
        <div class="live"><i></i>${esc(age === null ? ucT(hass, 'en_attente_mesures') : ucT(hass, 'en_direct', { age: age < 120 ? age + ' s' : Math.round(age / 60) + ' min' }))}</div>
        <div class="glow" aria-hidden="true"></div>
        ${grid}
      </div>`;
    this.shadowRoot.querySelectorAll('[data-entity]').forEach((el) => el.addEventListener('click', () => ucMoreInfo(this, el.dataset.entity)));
  }

  /* ---------------------------------------------------------------- Maison en direct, vue 3D (0.5.0)
   * scene: 3d : plus aucune pastille. Chaque élément est l'objet dessiné, avec ses chiffres écrits à côté :
   *   panneaux du toit (s'illuminent quand ils produisent), colonne UHome (onduleur + 3 modules, sans logo),
   *   ampoule (maison), borne de recharge (facultative), poteau (réseau).
   * Flux sans flèches : le défilement des tirets montre le sens. Trajets séparés et colorés : soleil orange,
   * recharge bleue, maison verte, réseau orange ; pointillés gris au repos. Plus la puissance est forte,
   * plus les tirets sont serrés et rapides.
   * Toutes les positions sont en % de la carte (comme « nodes » de la vue à pastilles), à caler sur votre
   * image avec « calibration: true » (voir dashboard/MAISON.md) :
   *   nodes.solar   : x, y (point d'accroche des chiffres), align (left | right), routes (un ou plusieurs
   *                   trajets, des panneaux vers l'UHome), glow ([cx, cy, rx, ry, angle] : lueur sur les panneaux,
   *                   rx et ry en % de la largeur), leader (pointillé des chiffres vers les panneaux)
   *   nodes.grid    : x, y, align, route (du haut du poteau vers l'UHome)
   *   nodes.battery : x, y, align (chiffres de l'UHome), uhome: {x, y, w} (coin haut gauche et largeur)
   *   nodes.home    : x, y, align, route (de l'UHome vers l'ampoule), bulb: {x, y, w}
   *   ev            : entity, state_entity, name, x, y, align, route, borne: {x, y, w}   (facultatif)
   * Autres options : mode_entity (mode de l'onduleur en clair), battery_path (un appui sur l'UHome ouvre
   * cette page), label_scale, details: false (sans tensions ni fréquence).
   * Le rendu complet n'est refait que si un flux change d'état ou d'allure ; sinon seuls les chiffres changent,
   * pour ne pas relancer les animations à chaque mesure. */
  _renderScene() {
    const c = this._config;
    const hass = this._hass || { states: {} };
    const min = Number(c.min_power) || 30;
    const N = c.nodes;
    const E = c.ev || null;
    const W = 1000;
    const H = W / (Number(c.aspect_ratio) || 1.45);
    const P = (p) => `${(p[0] * W / 100).toFixed(1)} ${(p[1] * H / 100).toFixed(1)}`;
    const D = (pts) => (Array.isArray(pts) && pts.length >= 2 ? 'M' + pts.map(P).join(' L') : '');
    const pv = ucWatts(hass, N.solar.entity);
    const grid = ucWatts(hass, N.grid.entity);
    const bat = ucWatts(hass, N.battery.entity);
    const home = ucWatts(hass, N.home.entity);
    const soc = ucNum(hass, N.battery.soc_entity);
    const ev = E && E.entity ? ucWatts(hass, E.entity) : null;
    const evRaw = E && E.state_entity && hass.states[E.state_entity] ? String(hass.states[E.state_entity].state) : '';
    const on = (w) => w !== null && Math.abs(w) >= min;
    const sunOn = on(pv) && pv > 0;
    const charging = on(bat) && bat > 0;
    const discharging = on(bat) && bat < 0;
    const etatBat = ucT(hass, charging ? 'en_charge' : discharging ? 'en_decharge' : 'au_repos');
    const homeOn = on(home) && home > 0;
    const gridIn = on(grid) && grid > 0;
    const gridOut = on(grid) && grid < 0;
    const evOn = ev !== null && ev >= 50;
    const uhColor = charging ? '#00D1D6' : discharging ? '#F39C12' : '#7DABCD';
    // Allure d'un flux : tirets plus serrés et plus rapides avec la puissance (motif de 10, 15 ou 20 pour boucler sur 60).
    const pace = (w) => {
      const p = Math.abs(w || 0);
      return { gap: p > 2400 ? 7 : p > 1000 ? 12 : 17, dur: Math.max(0.35, Math.round(600 / (30 + p * 0.04)) / 10) };
    };
    const halo = Math.max(0.6, (charging ? 2.6 : 2.2) - Math.min(1.6, Math.abs(bat || 0) / 2600));
    const sig = JSON.stringify([sunOn && pace(pv), charging, discharging, homeOn && pace(home), (gridIn || gridOut) && [gridIn, pace(grid)], evOn && pace(ev), soc === null ? null : Math.round(soc / 5), uhColor, Math.round(halo * 5)]);
    const glow = UC_LIGHT ? '' : 'filter: drop-shadow(0 0 4px VAR);';
    const flow = (pts, base, dash, glowColor, w, reverse) => {
      const d = D(pts);
      if (!d) return '';
      const p = pace(w);
      return `<path d="${d}" fill="none" stroke="${base}" stroke-width="4.5" stroke-opacity="0.75" stroke-linejoin="round"/>`
        + `<path class="uc-flow" d="${d}" fill="none" stroke="${dash}" stroke-width="4.8" stroke-linecap="round" stroke-linejoin="round" style="stroke-dasharray: 4.5 ${p.gap * 1.5}; animation-duration: ${p.dur}s;${reverse ? ' animation-direction: reverse;' : ''} ${glow.replace('VAR', glowColor)}"/>`;
    };
    const idle = (pts) => { const d = D(pts); return d ? `<path d="${d}" fill="none" stroke="#9AA7B5" stroke-width="3.8" stroke-dasharray="9 9" stroke-opacity="0.7" stroke-linejoin="round"/>` : ''; };
    const many = (list, fn) => (Array.isArray(list) && Array.isArray(list[0]) && Array.isArray(list[0][0]) ? list : (list ? [list] : [])).map(fn).join('');
    const solarRoutes = N.solar.routes || (N.solar.route ? [N.solar.route] : []);
    const uh = Object.assign({ x: 33, y: 61, w: 9 }, N.battery.uhome || {});
    const uhH = uh.w * (126 / 60) * (W / H);                 // hauteur de la colonne en % de la carte
    const bulb = Object.assign({ x: 75, y: 73, w: 6 }, N.home.bulb || {});
    const borne = E ? Object.assign({ x: 73, y: 56, w: 3 }, E.borne || {}) : null;
    const pole = Array.isArray(N.grid.route) && N.grid.route[0];
    const evLed = evOn ? '#2ED198' : '#6FD6F5';
    const art = () => `
      <svg class="ov" viewBox="0 0 ${W} ${H.toFixed(1)}" preserveAspectRatio="none" aria-hidden="true">
        ${sunOn && Array.isArray(N.solar.glow) ? `<g class="uc-live" style="mix-blend-mode: screen">${N.solar.glow.map((g) => `<ellipse cx="${(g[0] * W / 100).toFixed(1)}" cy="${(g[1] * H / 100).toFixed(1)}" rx="${(g[2] * W / 100).toFixed(1)}" ry="${(g[3] * W / 100).toFixed(1)}" transform="rotate(${Number(g[4]) || 0} ${(g[0] * W / 100).toFixed(1)} ${(g[1] * H / 100).toFixed(1)})" fill="rgba(255,210,122,0.22)"/>`).join('')}</g>` : ''}
        ${solarRoutes.map((r) => (sunOn ? flow(r, '#F39C12', '#FFE7B0', 'rgba(243,156,18,0.9)', pv) : idle(r))).join('')}
        ${gridIn || gridOut ? `${UC_LIGHT || !pole ? '' : `<circle class="uc-wave" cx="${(pole[0] * W / 100).toFixed(1)}" cy="${(pole[1] * H / 100).toFixed(1)}" r="11" fill="none" stroke="#F7B248" stroke-width="3" style="animation-duration: 1.6s"/>`}${flow(N.grid.route, '#F39C12', '#FFE7B0', 'rgba(243,156,18,0.9)', grid, gridOut)}` : idle(N.grid.route)}
        ${homeOn ? flow(N.home.route, '#2ED198', '#D9FFE9', 'rgba(46,209,152,0.9)', home) : idle(N.home.route)}
        ${E ? (evOn ? flow(E.route, '#2AB7E2', '#D6F6FF', 'rgba(42,183,226,0.9)', ev) : idle(E.route)) : ''}
        ${(charging || discharging) && !UC_LIGHT ? `<circle class="uc-wave" cx="${((uh.x + uh.w / 2) * W / 100).toFixed(1)}" cy="${((uh.y + uhH / 2) * H / 100).toFixed(1)}" r="${(uh.w * 0.72 * W / 100).toFixed(1)}" fill="none" stroke="${uhColor}" stroke-width="3.8" style="animation-duration: ${halo.toFixed(1)}s"/>` : ''}
        ${N.solar.leader ? `<path d="${D(N.solar.leader)}" fill="none" stroke="#F7B248" stroke-width="1.5" stroke-dasharray="3 4.5" stroke-opacity="0.8"/>` : ''}
      </svg>
      ${borne ? `<svg class="borne" style="left:${borne.x}%;top:${borne.y}%;width:${borne.w}%" viewBox="0 0 19 33" aria-hidden="true"><polygon points="0,8.5 16,0 16,24.5 0,33" fill="#1B2130" stroke="#6FD6F5" stroke-width="1.3" stroke-linejoin="round"/><polygon points="16,0 19,1.5 19,26 16,24.5" fill="#11151F" stroke="#6FD6F5" stroke-width="0.8"/><circle cx="8" cy="15" r="4" fill="none" stroke="${evLed}" stroke-width="1.8"/>${evOn && !UC_LIGHT ? `<circle class="uc-wave" cx="8" cy="15" r="4" fill="none" stroke="${evLed}" stroke-width="1.8" style="animation-duration: 1.6s"/>` : ''}</svg>` : ''}
      <button type="button" class="uh" style="left:${uh.x}%;top:${uh.y}%;width:${uh.w}%" aria-label="${esc(ucT(hass, 'uhome_batterie_a', { soc: soc === null ? '—' : Math.round(soc), etat: etatBat }) + (c.battery_path ? '. ' + ucT(hass, 'ouvrir_page_batterie') : ''))}">
        <svg viewBox="0 0 60 126" aria-hidden="true">
          <defs><linearGradient id="uhm" x1="0" x2="1"><stop offset="0" stop-color="#2B2E34"/><stop offset=".55" stop-color="#34373E"/><stop offset="1" stop-color="#24262B"/></linearGradient>
          <linearGradient id="uht" x1="0" x2="1"><stop offset="0" stop-color="#30333A"/><stop offset=".55" stop-color="#3A3D45"/><stop offset="1" stop-color="#2A2D33"/></linearGradient></defs>
          <rect x="4" y="4" width="56" height="120" rx="7" fill="#1A1C20"/>
          <rect x="0.5" y="0.5" width="56" height="120" rx="7" fill="#2A2D33" stroke="#50555F"/>
          <path d="M2 2.5 H55" stroke="#D5DAE2" stroke-width="2" stroke-linecap="round"/>
          <path d="M1 42 V8 a7 7 0 0 1 7 -7 H49 a7 7 0 0 1 7 7 V42 Z" fill="url(#uht)"/>
          <path d="M13 4 V20 a14 14 0 0 0 28 0 V4" fill="none" stroke="#50555F"/>
          <rect x="20" y="13" width="16" height="13" rx="5" fill="#15171B" stroke="${uhColor}" stroke-width="2"/>
          ${[42, 68, 94].map((y, i) => `<rect x="1" y="${y}" width="55" height="25" fill="url(#uhm)"/><path d="M1 ${y} H56" stroke="#15171B"/><rect class="uc-slit" x="17" y="${y + 11}" width="22" height="2.5" rx="1.2" fill="${uhColor}" style="animation-delay: ${i * 250}ms"/>`).join('')}
          <rect x="50" y="44" width="3" height="72" rx="1.5" fill="#15171B"/>
          <rect x="50" y="${(116 - 72 * Math.max(0.03, Math.min(1, (soc || 0) / 100))).toFixed(1)}" width="3" height="${(72 * Math.max(0.03, Math.min(1, (soc || 0) / 100))).toFixed(1)}" rx="1.5" fill="${uhColor}"/>
          <rect x="4" y="120" width="12" height="5" rx="1.5" fill="#15171B"/><rect x="41" y="120" width="12" height="5" rx="1.5" fill="#15171B"/>
        </svg>
      </button>
      <svg class="bulb${homeOn ? ' lit' : ''}" style="left:${bulb.x}%;top:${bulb.y}%;width:${bulb.w}%" viewBox="0 0 24 26" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4a6 6 0 0 0-4 10.5c.8.8 1 1.6 1 2.5h6c0-.9.2-1.7 1-2.5A6 6 0 0 0 12 4z" fill="#FFC440" stroke="#FFB020" stroke-width="1"/><path d="M9.5 19h5M10 21.5h4" stroke="#9AA6BE" stroke-width="1.6"/><path d="M3 5l2 1.5M21 5l-2 1.5M1.5 11.5h2.5M20 11.5h2.5M5 18l1.6-1.2M19 18l-1.6-1.2" stroke="#FFC440" stroke-width="1.4"/></svg>`;
    // Chiffres écrits à côté des objets.
    const det = (n) => (c.details === false ? '' : (n.details || []).map((e) => esc(ucDisplay(hass, e))).join(' · '));
    const kwv = (key, w) => (w === null ? '<b>—</b>' : `<b><span data-n="${key}" data-v="${Math.abs(w) / 1000}" data-d="2">${esc(ucNumber(hass, Math.abs(w) / 1000, 2))}</span> kW</b>`);
    const modeRaw = c.mode_entity && hass.states[c.mode_entity] ? hass.states[c.mode_entity].state : null;
    const modeNames = Object.assign({ 'Match Load Mode': ucT(hass, 'scene_mode_autoconsommation'), 'Peak Fill Mode': ucT(hass, 'scene_mode_arbitrage'), 'Backup Mode': ucT(hass, 'scene_mode_secours') }, c.mode_names || {});
    const mode = modeRaw && !['unknown', 'unavailable'].includes(modeRaw) ? (modeNames[modeRaw] || modeRaw) : null;
    const B = (k) => ucT(hass, 'borne_' + k);
    const evNames = Object.assign({ charging: B('en_charge'), ready: B('libre'), paused: B('en_pause'), scheduled: B('programmee'), 'waiting for car demand': B('branchee'), 'connected: waiting car demand': B('branchee'), 'waiting for next schedule': B('programmee'), disconnected: B('hors_ligne'), error: B('en_defaut'), unavailable: B('indisponible'), unknown: B('inconnue') }, (E && E.state_names) || {});
    const evState = evOn ? B('en_charge') : (evNames[evRaw.toLowerCase()] || evNames[evRaw] || (evRaw ? evRaw.toLowerCase() : B('libre')));
    const ages = Object.values(N).map((n) => n.entity && hass.states[n.entity] && Date.parse(hass.states[n.entity].last_updated)).filter((t) => Number.isFinite(t));
    const age = ages.length ? Math.max(0, Math.round((Date.now() - Math.max(...ages)) / 1000)) : null;
    const L = (n, defAlign, ent, html, cls) => {
      const al = n.align || defAlign;
      const x = Number(n.x), y = Number(n.y);
      return `<div class="lb ${al === 'right' ? 'r' : 'l'}${cls ? ' ' + cls : ''}" style="${al === 'right' ? `right:${(100 - x).toFixed(2)}%` : `left:${x.toFixed(2)}%`};top:${y.toFixed(2)}%"${ent ? ` data-entity="${esc(ent)}" role="button" tabindex="0"` : ''}>${html}</div>`;
    };
    const sd = det(N.solar);
    const gd = det(N.grid);
    const hd = det(N.home);
    const labels = `
      <div class="live"><i></i>${esc(age === null ? ucT(hass, 'en_attente_mesures') : ucT(hass, 'en_direct', { age: age < 120 ? age + ' s' : Math.round(age / 60) + ' min' }))}</div>
      ${L(N.solar, 'right', N.solar.entity, `<span class="t" style="color:#F7B248">${esc(N.solar.label && N.solar.label !== 'Solaire' ? N.solar.label : ucT(hass, 'panneaux_solaires'))}</span><br>${kwv('pv', pv)}${sd ? `<br><span class="o">${sd}</span>` : ''}`)}
      ${L(N.battery, 'right', N.battery.soc_entity, `<span class="t" style="color:${uhColor}">${esc(N.battery.label || 'UHome')}</span><br><b>${soc === null ? '—' : `<span data-n="soc" data-v="${Math.round(soc)}" data-d="0">${esc(ucNumber(hass, Math.round(soc), 0))}</span>`} % · ${bat === null ? '—' : `<span data-n="bat" data-v="${Math.abs(bat) / 1000}" data-d="2">${esc(ucNumber(hass, Math.abs(bat) / 1000, 2))}</span>`} kW</b><br><span class="o">${esc(ucT(hass, 'batterie_deux_points'))}</span>${esc(etatBat)}${mode ? `<br><span class="o">${esc(ucT(hass, 'onduleur_mode', { mode }))}</span>` : ''}`)}
      ${E ? L(E, 'left', E.entity, `<span class="t" style="color:${evOn ? '#2ED198' : '#9CC9F5'}">${esc(ucT(hass, 'recharge'))}</span><br>${kwv('ev', ev)}<br><span class="o">${esc(E.name || ucT(hass, 'borne'))} · </span>${esc(evState)}`) : ''}
      ${L(N.home, 'right', N.home.entity, `<span class="t" style="color:#FFC440">${esc(N.home.label || ucT(hass, 'maison'))}</span><br>${kwv('home', home)}${hd ? `<br><span class="o">${hd}</span>` : ''}`)}
      ${L(N.grid, 'left', N.grid.entity, `<span class="t" style="color:#F7B248">${esc(N.grid.label || ucT(hass, 'reseau'))}</span><br>${kwv('grid', grid)}${gridOut ? '<br>' + esc(ucT(hass, 'injection')) : ''}${gd ? `<br><span class="o">${gd.replace(' · ', '<br>')}</span>` : ''}`, 'g')}`;
    const label = [
      sunOn ? ucT(hass, 'scene_soleil', { kw: ucNumber(hass, pv / 1000, 2) }) : '',
      soc === null ? ucT(hass, 'scene_batterie', { etat: etatBat }) : ucT(hass, 'scene_batterie_soc', { etat: etatBat, soc: Math.round(soc) }),
      ucT(hass, 'scene_maison', { kw: home === null ? '—' : ucNumber(hass, Math.max(0, home) / 1000, 2) }),
      gridIn ? ucT(hass, 'scene_achat') : gridOut ? ucT(hass, 'scene_injection') : '',
      evOn ? ucT(hass, 'scene_voiture') : '',
    ].filter(Boolean).join(' ');
    const root = this.shadowRoot;
    if (!root.querySelector('.stage.scene')) {
      const ia = c.image_area;
      let cal = '';
      if (c.calibration) {
        for (let i = 5; i < 100; i += 5) cal += `<div class="cal v${i % 10 ? ' f' : ''}" style="left:${i}%"><span>${i % 10 ? '' : i}</span></div><div class="cal h${i % 10 ? ' f' : ''}" style="top:${i}%"><span>${i % 10 ? '' : i}</span></div>`;
      }
      root.innerHTML = `
        <style>${UC_BASE_CSS}
          :host { display: block; }
          .stage { position: relative; width: 100%; aspect-ratio: ${Number(c.aspect_ratio) || 1.45}; container-type: inline-size; --ls: ${Number(c.label_scale) || 1}; }
          .house { position: absolute; left: ${ia.x}%; top: ${ia.y}%; width: ${ia.w}%; height: auto; pointer-events: none; user-select: none; }
          .art, .lbls { position: absolute; inset: 0; }
          .lbls { pointer-events: none; }
          .ov { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none; }
          @keyframes ucFlow { to { stroke-dashoffset: -90; } }
          .uc-flow { animation-name: ucFlow; animation-timing-function: linear; animation-iteration-count: infinite; }
          @keyframes ucWave { 0% { transform: scale(1); opacity: .9; } 100% { transform: scale(1.9); opacity: 0; } }
          .uc-wave { transform-box: fill-box; transform-origin: center; animation-name: ucWave; animation-timing-function: ease-out; animation-iteration-count: infinite; }
          @keyframes ucPulse { 50% { opacity: .3; } }
          .uc-live { animation: ucPulse 1.6s ease-in-out infinite; }
          @keyframes ucSlit { 0%, 100% { opacity: .45; } 50% { opacity: 1; } }
          .uc-slit { animation: ucSlit 1.6s ease-in-out infinite; }
          .uh { position: absolute; padding: 0; border: 0; background: none; cursor: pointer; filter: drop-shadow(0 8px 10px rgba(0,0,0,0.5)); }
          .uh svg { display: block; width: 100%; height: auto; }
          .borne { position: absolute; height: auto; overflow: visible; }
          .bulb { position: absolute; height: auto; opacity: .45; }
          .bulb.lit { opacity: 1; filter: drop-shadow(0 0 1.3cqw rgba(255,196,64,0.85)); }
          .lb { position: absolute; pointer-events: auto; cursor: pointer; white-space: nowrap; font: 400 max(10px, calc(1.92cqw * var(--ls))) / 1.3 var(--uc-font); color: #E6ECF5; text-shadow: 0 1px 3px #000, 0 0 6px rgba(0,0,0,0.6); }
          .lb.r { text-align: right; }
          .lb b { font-size: max(12px, calc(2.56cqw * var(--ls))); font-weight: 700; color: #FFFFFF; }
          .lb:focus-visible { outline: 2px solid #22E0F0; outline-offset: 2px; }
          .live { position: absolute; left: .6%; top: .4%; display: flex; align-items: center; gap: 6px; font-size: max(11px, 1.8cqw); color: var(--uc-value); text-shadow: 0 1px 3px #000; }
          .live i { width: 7px; height: 7px; border-radius: 50%; background: #2ED198; animation: ucPulse 1.6s ease-in-out infinite; }
          .cal { position: absolute; background: rgba(255,80,80,.45); pointer-events: none; }
          .cal.f { background: rgba(255,80,80,.18); }
          .cal.v { top: 0; bottom: 0; width: 1px; }
          .cal.h { left: 0; right: 0; height: 1px; }
          .cal span { position: absolute; font: 11px monospace; color: #FF8080; left: 2px; top: 2px; }
          /* Petite largeur (téléphone) : seulement le nom et les chiffres principaux. */
          @container (max-width: 520px) { .lb .o { display: none; } .lb.g { left: auto !important; right: 0; text-align: right; } }
        </style>
        <div class="stage scene" role="img">
          <img class="house" src="${esc(c.image)}" alt="">
          <div class="art"></div>
          <div class="lbls"></div>
          ${cal}
        </div>`;
      root.querySelector('.art').addEventListener('click', (ev) => {
        if (!ev.composedPath().some((el) => el.classList && el.classList.contains('uh'))) return;
        if (c.battery_path) ucNavigate(c.battery_path); else ucMoreInfo(this, N.battery.soc_entity);
      });
      root.querySelector('.lbls').addEventListener('click', (ev) => {
        const el = ev.composedPath().find((x) => x.dataset && x.dataset.entity);
        if (el) ucMoreInfo(this, el.dataset.entity);
      });
      root.querySelector('.lbls').addEventListener('keydown', (ev) => {
        if (ev.key !== 'Enter' && ev.key !== ' ') return;
        const el = ev.composedPath().find((x) => x.dataset && x.dataset.entity);
        if (el) { ev.preventDefault(); ucMoreInfo(this, el.dataset.entity); }
      });
      this._sceneSig = null;
    }
    root.querySelector('.stage').setAttribute('aria-label', label);
    if (this._sceneSig !== sig) {
      this._sceneSig = sig;
      root.querySelector('.art').innerHTML = art();
    }
    root.querySelector('.lbls').innerHTML = labels;
    ucCount(this, root.querySelector('.lbls'), hass);
  }
}

/* ------------------------------------------------------------------ anneau de charge */

class UcanessSocCard extends HTMLElement {
  setConfig(config) {
    this._config = Object.assign({
      soc_entity: 'sensor.uhome_soc',
      power_entity: 'sensor.uhome_puissance_batterie',
      floor_entity: 'input_number.jarvis_batterie_plancher',
      capacity_entity: 'input_number.jarvis_batterie_capacite',
    }, config || {});
    this._ucSeen = null;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const c = this._config;
    if (ucChanged(this, hass, [c.soc_entity, c.power_entity, c.floor_entity, c.capacity_entity, c.mode_entity, c.simulation_entity].filter(Boolean))) this._render();
  }

  getCardSize() { return this._config && this._config.compact ? 3 : 6; }

  /** 0.5.0 : dégradé de l'anneau et halo selon l'état (cyan en charge, orange en décharge, vert au repos). */
  _look(p) {
    const moving = p !== null && Math.abs(p) >= 30;
    const g = !moving ? ['#2ED198', '#8FF0C8'] : p > 0 ? ['#00D1D6', '#7FF3F5'] : ['#F39C12', '#FFD27A'];
    const dur = Math.max(0.6, (p > 0 ? 2.6 : 2.2) - Math.min(1.6, Math.abs(p || 0) / 2600));
    return { moving, g, dur };
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    if (this._config.compact) return this._renderCompact();
    const c = this._config;
    const hass = this._hass || { states: {} };
    const soc = ucNum(hass, c.soc_entity);
    const p = ucWatts(hass, c.power_entity);
    const floor = c.floor !== undefined ? c.floor : ucNum(hass, c.floor_entity);
    const cap = c.capacity !== undefined ? c.capacity : ucNum(hass, c.capacity_entity);
    const R = 88, C = 2 * Math.PI * R;
    const dash = soc === null ? 0 : C * Math.max(0, Math.min(100, soc)) / 100;
    const state = ucT(hass, p === null || Math.abs(p) < 30 ? 'bat_veille' : p > 0 ? 'bat_chargement' : 'bat_decharge');
    const stored = soc !== null && cap ? ucNumber(hass, cap * soc / 100, 2) + ' kWh' : '—';
    const avail = soc !== null && cap && floor !== null ? ucNumber(hass, Math.max(0, cap * (soc - floor) / 100), 2) + ' kWh' : '—';
    const lk = this._look(p);
    const first = !this._drawn;
    this._drawn = true;
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        .wrap { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 8px 0; }
        .ring { position: relative; width: min(250px, 100%); aspect-ratio: 1; }
        .ring svg { width: 100%; height: 100%; overflow: visible; }
        .arc { filter: drop-shadow(0 0 6px ${lk.g[0]}99); }
        .arc.draw { animation: draw 1.2s ease-out both; }
        @keyframes draw { from { stroke-dasharray: 0 ${C.toFixed(1)}; } }
        .halo { transform-box: fill-box; transform-origin: center; animation: ucHalo ${lk.dur.toFixed(1)}s ease-out infinite; }
        @keyframes ucHalo { 0% { transform: scale(.92); opacity: .85; } 100% { transform: scale(1.18); opacity: 0; } }
        .mid { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; text-align: center; }
        .mid small { font-size: 13px; color: var(--uc-muted); letter-spacing: 2px; }
        .mid b { font: 700 clamp(36px, 10vw, 62px) var(--uc-font); line-height: 1; }
        .mid > span { font-size: 15px; color: ${lk.g[0]}; }
        .mid em { font-style: normal; font-size: 13px; color: var(--uc-muted); }
        .row { display: flex; gap: 22px; font-size: 13px; }
        .row span span { color: var(--uc-value); }
        .row span.warn span { color: var(--uc-orange); }
      </style>
      <div class="wrap">
        <div class="ring">
          <svg viewBox="0 0 250 250" role="img" aria-label="${esc(ucT(hass, 'charge_de_la_batterie', { v: soc === null ? ucT(hass, 'indisponible') : Math.round(soc) + ' %' }))}">
            <defs><linearGradient id="ucg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${lk.g[1]}"/><stop offset="1" stop-color="${lk.g[0]}"/></linearGradient></defs>
            ${lk.moving && !UC_LIGHT ? `<circle class="halo" cx="125" cy="125" r="${R}" fill="none" stroke="${lk.g[0]}" stroke-width="6"/>` : ''}
            <circle cx="125" cy="125" r="104" fill="none" stroke="#12345E" stroke-width="2" stroke-dasharray="3 6"/>
            <circle cx="125" cy="125" r="${R}" fill="none" stroke="#16365F" stroke-width="20"/>
            <circle class="arc${first ? ' draw' : ''}" cx="125" cy="125" r="${R}" fill="none" stroke="url(#ucg)" stroke-width="20" stroke-linecap="round" stroke-dasharray="${dash.toFixed(1)} ${C.toFixed(1)}" transform="rotate(-90 125 125)"/>
          </svg>
          <div class="mid"><small>${esc(ucT(hass, 'charge_majuscules'))}</small><b>${soc === null ? '—' : `<span data-n="soc" data-v="${Math.round(soc)}" data-d="0">${esc(ucNumber(hass, Math.round(soc), 0))}</span>`} %</b><span>${state}${p !== null && Math.abs(p) >= 30 ? ' · ' + esc(ucNumber(hass, Math.abs(p) / 1000, 2)) + ' kW' : ''}</span>${floor !== null ? `<em>plancher ${esc(ucNumber(hass, floor, 0))} %${cap ? ' · ' + esc(ucNumber(hass, cap, 1)) + ' kWh' : ''}</em>` : ''}</div>
        </div>
        <div class="row"><span>${esc(ucT(hass, 'stockee'))} <span>${esc(stored)}</span></span><span class="warn">${esc(ucT(hass, 'avant_plancher'))} <span>${esc(avail)}</span></span></div>
      </div>`;
    ucCount(this, this.shadowRoot, hass);
  }

  /** Version téléphone (compact: true) : petit anneau à gauche, réserve et énergie utilisable à droite.
   *  Options : title (Batterie), mode_entity (mode de l'onduleur, affiché en clair),
   *  simulation_entity (pastille orange « Simulation » quand elle est à « on »). */
  _renderCompact() {
    const c = this._config;
    const hass = this._hass || { states: {} };
    const soc = ucNum(hass, c.soc_entity);
    const p = ucWatts(hass, c.power_entity);
    const floor = c.floor !== undefined ? c.floor : ucNum(hass, c.floor_entity);
    const cap = c.capacity !== undefined ? c.capacity : ucNum(hass, c.capacity_entity);
    const R = 52, C = 2 * Math.PI * R;
    const dash = soc === null ? 0 : C * Math.max(0, Math.min(100, soc)) / 100;
    const low = soc !== null && floor !== null && soc <= floor + 2;
    const moving = p !== null && Math.abs(p) >= 30;
    const state = p === null ? '' : ucT(hass, !moving ? 'au_repos' : p > 0 ? 'en_charge' : 'en_decharge');
    const stateColor = !moving ? 'var(--uc-muted)' : p > 0 ? '#2ECC71' : '#7FD3FF';
    const kwh = (v) => esc(ucFormat(hass, v, v < 10 ? 1 : 0, 'kWh'));
    const stored = soc !== null && cap ? kwh(cap * soc / 100) : '—';
    const avail = soc !== null && cap && floor !== null ? kwh(Math.max(0, cap * (soc - floor) / 100)) : '—';
    const modeRaw = c.mode_entity && hass.states[c.mode_entity] ? hass.states[c.mode_entity].state : null;
    const modeNames = Object.assign({ 'Match Load Mode': ucT(hass, 'mode_autoconsommation'), 'Peak Fill Mode': ucT(hass, 'mode_arbitrage'), 'Backup Mode': ucT(hass, 'mode_secours') }, c.mode_names || {});
    const mode = modeRaw && !['unknown', 'unavailable'].includes(modeRaw) ? (modeNames[modeRaw] || modeRaw) : null;
    const sim = c.simulation_entity && hass.states[c.simulation_entity] && hass.states[c.simulation_entity].state === 'on';
    const lk = this._look(p);
    const g = low ? ['#F39C12', '#FFD27A'] : lk.g;
    const first = !this._drawn;
    this._drawn = true;
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        button.box { width: 100%; box-sizing: border-box; padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; border: 1px solid var(--uc-card-border); border-radius: 14px; background: var(--uc-card-bg); box-shadow: var(--uc-card-shadow); color: var(--uc-text); font: inherit; text-align: left; cursor: pointer; }
        .ring svg { overflow: visible; }
        .arc.draw { animation: draw 1.2s ease-out both; }
        @keyframes draw { from { stroke-dasharray: 0 ${C.toFixed(1)}; } }
        .halo { transform-box: fill-box; transform-origin: center; animation: ucHalo ${lk.dur.toFixed(1)}s ease-out infinite; }
        @keyframes ucHalo { 0% { transform: scale(.92); opacity: .85; } 100% { transform: scale(1.18); opacity: 0; } }
        .head { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 26px; }
        .t { font-size: 15px; color: var(--uc-label); }
        .chips { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
        .chip { padding: 3px 10px; border: 1px solid var(--uc-tab-border); border-radius: 12px; font-size: 13px; color: #CFE6FF; white-space: nowrap; }
        .chip.sim { border-color: #8A5A12; background: rgba(243,156,18,0.14); color: #FFD08A; }
        .body { display: flex; align-items: center; gap: 14px; }
        .ring { position: relative; width: 124px; height: 124px; flex: 0 0 124px; }
        .ring svg { position: absolute; inset: 0; width: 100%; height: 100%; }
        .mid { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; line-height: 1.1; text-align: center; }
        .mid b { font: 700 32px var(--uc-font); }
        .mid > span { font-size: 13px; }
        .figs { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
        .figs .f { display: flex; flex-direction: column; }
        .n { font-size: 12px; color: #9CC9F5; text-transform: uppercase; letter-spacing: .4px; }
        .v { font: 700 22px var(--uc-font); color: var(--uc-value); }
        .v.warn { color: var(--uc-orange); }
        .s { font-size: 13px; color: #9CC9F5; }
      </style>
      <button type="button" class="box" aria-label="${esc(ucT(hass, 'batterie_etat', { v: soc === null ? ucT(hass, 'charge_indisponible') : Math.round(soc) + ' %' }))}">
        <span class="head"><span class="t">${esc(c.title || ucT(hass, 'batterie'))}</span><span class="chips">${mode ? `<span class="chip">${esc(mode)}</span>` : ''}${sim ? `<span class="chip sim">${esc(ucT(hass, 'simulation'))}</span>` : ''}</span></span>
        <span class="body">
          <span class="ring">
            <svg viewBox="0 0 124 124" aria-hidden="true">
              <defs><linearGradient id="ucgc" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${g[1]}"/><stop offset="1" stop-color="${g[0]}"/></linearGradient></defs>
              ${lk.moving && !UC_LIGHT ? `<circle class="halo" cx="62" cy="62" r="${R}" fill="none" stroke="${g[0]}" stroke-width="4"/>` : ''}
              <circle cx="62" cy="62" r="${R}" fill="none" stroke="#173A66" stroke-width="10"/>
              <circle class="arc${first ? ' draw' : ''}" cx="62" cy="62" r="${R}" fill="none" stroke="url(#ucgc)" stroke-width="10" stroke-linecap="round" stroke-dasharray="${dash.toFixed(1)} ${C.toFixed(1)}" transform="rotate(-90 62 62)" style="filter: drop-shadow(0 0 4px ${g[0]}99)"/>
            </svg>
            <span class="mid"><b>${soc === null ? '—' : `<span data-n="soc" data-v="${Math.round(soc)}" data-d="0">${esc(ucNumber(hass, Math.round(soc), 0))}</span> %`}</b>${state ? `<span style="color:${stateColor}">${esc(state)}</span>` : ''}${moving ? `<span style="color:#CFE6FF">${esc(ucFormat(hass, Math.abs(p) / 1000, 2, 'kW'))}</span>` : ''}</span>
          </span>
          <span class="figs">
            <span class="f"><span class="n">${esc(ucT(hass, 'en_reserve'))}</span><span class="v">${stored}</span></span>
            <span class="f"><span class="n">${esc(ucT(hass, 'utilisable_avant_plancher'))}</span><span class="v warn">${avail}</span></span>
            ${floor !== null ? `<span class="s">${esc(ucT(hass, 'plancher', { v: ucNumber(hass, floor, 0) }))}${cap ? ' · ' + esc(ucFormat(hass, cap, 1, 'kWh')) : ''}</span>` : ''}
          </span>
        </span>
      </button>`;
    this.shadowRoot.querySelector('button').addEventListener('click', () => ucMoreInfo(this, c.soc_entity));
    ucCount(this, this.shadowRoot, hass);
  }
}

/* ------------------------------------------------------------------ texte repliable */

/*
 * custom:ucaness-note-card : un texte (carte markdown) replié sur quelques lignes, terminé par « … ».
 * Un appui sur le texte ou sur « … » le déplie en entier ; un nouvel appui le replie.
 * Remplace directement une carte markdown : changer « type: markdown » en
 * « type: custom:ucaness-note-card » et garder « content: ». Option « lines » (4 par défaut),
 * « mobile_lines » sous 900 px de large (par défaut la même valeur), ou « card » pour une autre carte.
 */
class UcanessNoteCard extends HTMLElement {
  setConfig(config) {
    if (!config || (!config.content && !config.card)) {
      throw new Error(ucT(null, 'err_note'));
    }
    this._config = Object.assign({ lines: 4 }, config);
    this._open = false;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._child) this._child.hass = hass;
  }

  getCardSize() { return Math.ceil((this._lines() * 21 + 16) / 50); }

  disconnectedCallback() {
    if (this._ro) this._ro.disconnect();
    if (this._onResize) window.removeEventListener('resize', this._onResize);
  }

  connectedCallback() {
    const slot = this.shadowRoot && this.shadowRoot.querySelector('.slot');
    if (this._ro && slot) this._ro.observe(slot);
    if (this._onResize) window.addEventListener('resize', this._onResize);
  }

  _lines() {
    const c = this._config || {};
    const mobile = typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(max-width: 900px)').matches;
    return Math.max(1, Number(mobile && c.mobile_lines ? c.mobile_lines : c.lines) || 4);
  }

  async _build() {
    // Home Assistant peut rappeler setConfig avant la fin de la construction précédente :
    // seule la dernière construction est gardée, et l'ancienne surveillance de taille est arrêtée.
    const build = (this._buildId = (this._buildId || 0) + 1);
    if (this._ro) { this._ro.disconnect(); this._ro = null; }
    if (this._onResize) { window.removeEventListener('resize', this._onResize); this._onResize = null; }
    const c = this._config;
    const childConf = c.card || Object.assign({ type: 'markdown' }, c.content !== undefined ? { content: c.content } : {});
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        .clip { position: relative; overflow: hidden; cursor: pointer; border-radius: 0; }
        .slot { display: flow-root; }
        .clip.open { cursor: auto; }
        .fade { position: absolute; left: 0; right: 0; bottom: 0; height: 2.4em; background: linear-gradient(180deg, rgba(22,40,72,0) 0%, rgba(22,40,72,0.96) 78%); pointer-events: none; }
        .more { position: absolute; right: 6px; bottom: 2px; min-width: 44px; height: 32px; padding: 0 12px; border: 1px solid var(--uc-tab-border); border-radius: 16px; background: linear-gradient(180deg, #123A68 0%, #0A2546 100%); color: var(--uc-tab); font: 700 16px var(--uc-font); letter-spacing: 1px; cursor: pointer; }
        .less { display: block; margin: 2px 6px 6px auto; min-width: 44px; height: 32px; padding: 0 12px; border: 1px solid var(--uc-tab-border); border-radius: 16px; background: linear-gradient(180deg, #123A68 0%, #0A2546 100%); color: var(--uc-tab); font: 400 14px var(--uc-font); cursor: pointer; }
        .clip:not(.cut) .fade, .clip:not(.cut) .more, .clip.open .fade, .clip.open .more { display: none; }
        .less[hidden] { display: none; }
      </style>
      <div class="clip" part="clip"><div class="slot"></div><div class="fade" aria-hidden="true"></div><button type="button" class="more uc-key" aria-expanded="false" aria-label="${esc(ucT(null, 'lire_la_suite'))}">…</button></div>
      <button type="button" class="less uc-key" aria-expanded="true" hidden>${esc(ucT(null, 'reduire'))}</button>`;
    const clip = this.shadowRoot.querySelector('.clip');
    const more = this.shadowRoot.querySelector('.more');
    const less = this.shadowRoot.querySelector('.less');
    const [child] = await ucCreateCards([childConf], this._hass, this);
    if (build !== this._buildId) return;
    this._child = child;
    child.style.display = 'block';
    this.shadowRoot.querySelector('.slot').appendChild(child);
    const toggle = (open) => {
      this._open = open;
      clip.classList.toggle('open', open);
      clip.style.maxHeight = open ? 'none' : `${this._lines() * 21 + 16}px`;
      more.setAttribute('aria-expanded', String(open));
      less.hidden = !open || !clip.classList.contains('cut');
    };
    const slot = this.shadowRoot.querySelector('.slot');
    // La hauteur se mesure sur le conteneur : une carte de Home Assistant est un élément « en ligne »
    // dont la hauteur propre vaut 0.
    const measure = () => {
      const limit = this._lines() * 21 + 16;
      clip.classList.toggle('cut', slot.scrollHeight > limit + 4);
      toggle(this._open);
    };
    clip.addEventListener('click', (ev) => {
      if (!clip.classList.contains('cut') || this._open) return;
      // Un lien reste un lien. Il est dans le shadow DOM de la carte markdown : on suit le chemin complet de l'appui.
      if (ev.composedPath().some((el) => el.tagName === 'A')) return;
      toggle(true);
    });
    more.addEventListener('click', (ev) => { ev.stopPropagation(); toggle(true); });
    less.addEventListener('click', () => toggle(false));
    if (typeof ResizeObserver !== 'undefined') {
      this._ro = new ResizeObserver(measure);
      this._ro.observe(slot);
    }
    this._onResize = measure;
    window.addEventListener('resize', this._onResize);
    measure();
  }
}

/* ------------------------------------------------------------------ écran de téléphone */

/*
 * custom:ucaness-app-card : un écran de téléphone complet, dans une vue `panel: true`.
 * En-tête compact sur une ligne (lieu, titre UCANESS, alertes, heure), cartes en une colonne,
 * barre de navigation en bas, toujours visible (collée au bas de l'écran pendant le défilement).
 *
 *   type: custom:ucaness-app-card
 *   site: Maison
 *   alert_entities: [binary_sensor.x, {entity: binary_sensor.y, alert_state: 'off'}]
 *   nav:
 *     - {title: Accueil, icon: mdi:home, path: /mon-tableau/accueil}
 *     - {title: Sécurité, icon: mdi:shield-outline, path: /mon-tableau/securite, badge_entities: [...]}
 *   wide_redirect: {min_width: 900, path: /mon-tableau-complet/accueil}   (facultatif)
 *   cards: [...]
 *
 * wide_redirect : sur un écran plus large que min_width (ordinateur, tablette), ouvre plutôt `path`.
 * Utile quand ce tableau est le tableau par défaut du compte (réglage commun à tous ses appareils).
 * « ?mobile » à la fin de l'adresse garde l'écran de téléphone (pour le voir ou le vérifier sur ordinateur).
 */
const UC_APP_CSS = `
  :host { display: block; }
  :host { position: relative; isolation: isolate; }
  .app { box-sizing: border-box; min-height: var(--ucaness-app-height, 100dvh); display: flex; flex-direction: column; background: transparent; overflow-x: hidden; }
  :host([no-sky]) .app { background: var(--ucaness-page-bg, radial-gradient(ellipse at 50% 30%, #0D2A58 0%, #071A3A 52%, #030B20 100%)); }
  header { position: relative; height: 52px; flex: 0 0 52px; box-sizing: border-box; display: flex; align-items: center; justify-content: space-between; padding: 0 6px 0 12px; background: linear-gradient(180deg, #0B2F5C 0%, #061B3D 100%); border-bottom: 1px solid #1C5C9E; }
  header::before, nav::before { content: ''; position: absolute; inset: 0; background: linear-gradient(180deg, #081A36 0%, #040D1F 100%); opacity: var(--uc-night, 0); transition: opacity 1.4s ease; pointer-events: none; }
  .site { position: relative; display: flex; align-items: center; gap: 6px; font-size: 16px; color: #E6ECF5; min-width: 0; }
  .site .meteo { display: flex; align-items: center; gap: 2px; font-size: 15px; --mdc-icon-size: 20px; }
  .site .meteo ha-icon { color: #FFD27A; }
  .site .nom { display: none; }
  .site.sans-meteo .nom { display: inline; }
  @media (min-width: 440px) { .site .nom { display: inline; } }
  .plate { position: absolute; left: 50%; top: 0; width: 150px; height: 44px; margin-left: -75px; clip-path: polygon(0 0, 100% 0, 92% 100%, 8% 100%); background: linear-gradient(180deg, #1A6FBE 0%, #0E4382 62%, #0A2F5E 100%); display: flex; align-items: center; justify-content: center; pointer-events: none; }
  .plate span { font: 700 19px ${UC_BRAND_FONT}; letter-spacing: .5px; background: linear-gradient(180deg, #FFFFFF 78%, #7DABCD 100%); -webkit-background-clip: text; background-clip: text; color: transparent; }
  .right { position: relative; display: flex; align-items: center; gap: 2px; }
  .bell { position: relative; width: 44px; height: 44px; border: 0; padding: 0; background: transparent; display: flex; align-items: center; justify-content: center; cursor: pointer; }
  .badge { position: absolute; right: 4px; top: 6px; min-width: 18px; height: 18px; padding: 0 4px; box-sizing: border-box; border-radius: 9px; background: #E5484D; color: #FFFFFF; font: 700 12px var(--uc-font); display: flex; align-items: center; justify-content: center; }
  .clock { display: flex; flex-direction: column; align-items: flex-end; line-height: 1.05; padding-right: 6px; }
  .clock b { font: 700 18px var(--uc-font); }
  .clock span { font-size: 12px; color: #9CC9F5; }
  main { flex: 1 1 auto; box-sizing: border-box; padding: 10px 8px 12px; display: flex; flex-direction: column; gap: 8px; min-width: 0; --ha-card-border-radius: 12px; }
  nav { position: sticky; bottom: 0; z-index: 5; flex: 0 0 auto; box-sizing: border-box; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); padding-bottom: env(safe-area-inset-bottom, 0px); background: #061B3D; border-top: 1px solid #1C5C9E; box-shadow: 0 -4px 14px rgba(0,0,0,0.45); }
  nav button { position: relative; z-index: 1; height: 64px; border: 0; padding: 0; background: transparent; color: #9CC9F5; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; font: 400 12px var(--uc-font); cursor: pointer; --mdc-icon-size: 24px; }
  nav button[aria-current="page"] { color: var(--uc-tab); }
  nav button[aria-current="page"]::before { content: ''; position: absolute; top: 0; left: 22%; right: 22%; height: 3px; background: var(--uc-tab); }
  nav .badge { right: calc(50% - 22px); top: 6px; }
`;

class UcanessAppCard extends HTMLElement {
  setConfig(config) {
    if (!config || !Array.isArray(config.cards)) throw new Error(ucT(null, 'err_app'));
    this._config = Object.assign({ site: 'Maison', title: 'UCANESS', nav: [], alert_entities: [] }, config);
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    (this._children || []).forEach((el) => { el.hass = hass; });
    const c = this._config || {};
    const ids = [...ucAlertList(c.alert_entities).map((a) => a.entity), ...(c.nav || []).flatMap((n) => n.badge_entities || []), c.sun_entity || 'sun.sun', ucWeatherId(hass, c.weather_entity)].filter(Boolean);
    if (ucChanged(this, hass, ids)) {
      this._chrome();
      if (c.sky !== false) ucSkyUpdate(this, hass, c);
    }
  }

  connectedCallback() {
    this._timer = setInterval(() => this._chrome(), 30000);
    if (this._children && this._children.length) this._entree();
    this._onLoc = () => this._chrome();
    window.addEventListener('location-changed', this._onLoc);
    window.addEventListener('popstate', this._onLoc);
    this._wide();
  }

  /** Écran large : ouvre le tableau complet à la place (sauf « ?mobile » dans l'adresse). */
  _wide() {
    const w = this._config && this._config.wide_redirect;
    if (!w || !w.path) return;
    const q = new URLSearchParams(window.location.search);
    if (q.has('mobile') || q.has('edit')) return;
    if (window.innerWidth < (w.min_width || 900) || window.location.pathname === w.path) return;
    window.history.replaceState(null, '', w.path);
    window.dispatchEvent(new CustomEvent('location-changed', { detail: { replace: true } }));
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    window.removeEventListener('location-changed', this._onLoc);
    window.removeEventListener('popstate', this._onLoc);
  }

  getCardSize() { return 12; }

  /** Ouverture de l'écran : vague cyan, puis les cartes en cascade. */
  _entree() {
    ucVague(this);
    (this._children || []).forEach((el, i) => ucRise(el, Math.min(80 + i * 70, 700)));
  }

  async _build() {
    const c = this._config;
    const build = (this._buildId = (this._buildId || 0) + 1);
    const sky = c.sky !== false;
    this.toggleAttribute('no-sky', !sky);
    this._ucSeen = null;
    this._ucImg = null;
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}${UC_APP_CSS}${sky ? UC_SKY_CSS : ''}</style>
      ${sky ? UC_SKY_HTML : ''}
      <div class="app">
        <header>
          <span class="site"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#F0883E" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M3 11.5L12 4l9 7.5"/><path d="M6 10v10h12V10"/></svg><span class="nom">${esc(c.site)}</span><span class="meteo-slot"></span></span>
          <div class="plate" aria-hidden="true"><span>${esc(c.title)}</span></div>
          <div class="right"><span class="alerts"></span><span class="clock"></span></div>
        </header>
        <main></main>
        <nav aria-label="${esc(ucT(null, 'navigation'))}"></nav>
      </div>`;
    const cards = await ucCreateCards(c.cards, this._hass, this);
    if (build !== this._buildId) return;
    const main = this.shadowRoot.querySelector('main');
    cards.forEach((el) => main.appendChild(el));
    this._children = cards;
    this._chrome();
    if (sky && this._hass) ucSkyUpdate(this, this._hass, c);
    this._entree();
  }

  /** En-tête (alertes, heure) et navigation : redessinés sans toucher aux cartes. */
  _chrome() {
    if (!this.shadowRoot || !this._config) return;
    const c = this._config;
    const hass = this._hass;
    const lang = (hass && hass.locale && hass.locale.language) || 'fr';
    const now = new Date();
    const clock = this.shadowRoot.querySelector('.clock');
    if (!clock) return;
    clock.innerHTML = `<b>${esc(now.toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit' }))}</b><span>${esc(now.toLocaleDateString(lang, { weekday: 'short', day: '2-digit', month: '2-digit' }))}</span>`;
    const slot = this.shadowRoot.querySelector('.meteo-slot');
    if (slot) {
      const m = hass ? ucMeteoHtml(hass, c) : '';
      slot.innerHTML = m;
      slot.parentElement.classList.toggle('sans-meteo', !m);
    }
    const active = ucActiveAlerts(hass, c.alert_entities);
    const alerts = this.shadowRoot.querySelector('.alerts');
    alerts.innerHTML = ucAlertList(c.alert_entities).length ? `<button type="button" class="bell" aria-label="${esc(active.length ? ucT(hass, 'alertes_en_cours', { n: active.length }) : ucT(hass, 'aucune_alerte'))}"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="${active.length ? '#FFB4B6' : '#7DABCD'}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20a2 2 0 0 0 4 0"/></svg>${active.length ? `<span class="badge">${active.length}</span>` : ''}</button>` : '';
    const bell = alerts.querySelector('button');
    if (bell && active.length) bell.addEventListener('click', () => ucMoreInfo(this, active[0].entity));
    const path = window.location.pathname;
    const nav = this.shadowRoot.querySelector('nav');
    nav.innerHTML = (c.nav || []).map((n, i) => {
      const on = n.path && (path === n.path || path.startsWith(n.path + '/'));
      const count = (n.badge_entities || []).filter((e) => hass && hass.states[e] && hass.states[e].state === 'on').length;
      return `<button type="button" class="uc-tap" data-i="${i}"${on ? ' aria-current="page"' : ''}><ha-icon icon="${esc(n.icon || 'mdi:circle-outline')}"></ha-icon><span>${esc(n.title)}</span>${count ? `<span class="badge">${count}</span>` : ''}</button>`;
    }).join('');
    nav.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => {
      const n = c.nav[Number(b.dataset.i)];
      if (n && n.path) ucNavigate(n.path);
    }));
  }
}

/** Liste d'alertes : une entité seule = alerte quand elle est à « on » ; sinon {entity, alert_state, name}. */
function ucAlertList(list) {
  return (list || []).map((a) => (typeof a === 'string' ? { entity: a, alert_state: 'on' } : Object.assign({ alert_state: 'on' }, a))).filter((a) => a.entity);
}

function ucActiveAlerts(hass, list) {
  if (!hass) return [];
  return ucAlertList(list).filter((a) => hass.states[a.entity] && hass.states[a.entity].state === a.alert_state).map((a) => {
    const st = hass.states[a.entity];
    return Object.assign({}, a, { name: a.name || (st.attributes && st.attributes.friendly_name) || a.entity });
  });
}

/* ------------------------------------------------------------------ bandeau d'état */

/*
 * custom:ucaness-status-card : « Tout va bien » en vert, ou les alertes en cours en rouge,
 * avec à droite une information courte (modèle Jinja facultatif, par exemple le tarif).
 *   alert_entities: [...] (comme ucaness-app-card) ; notice_entities: [...] (orange, pour information)
 *   ok_text: Tout va bien ; info_template: "{{ ... }}"
 */
class UcanessStatusCard extends HTMLElement {
  setConfig(config) {
    this._config = Object.assign({ alert_entities: [], notice_entities: [] }, config || {});
    this._ucSeen = null;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const c = this._config;
    if (c.info_template) ucTemplate(this, 'info', c.info_template, hass, () => this._render());
    const ids = [...ucAlertList(c.alert_entities), ...ucAlertList(c.notice_entities)].map((a) => a.entity);
    if (ucChanged(this, hass, ids)) this._render();
  }

  disconnectedCallback() { ucTemplatesOff(this); }

  connectedCallback() { if (this._hass) this.hass = this._hass; }

  getCardSize() { return 1; }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const c = this._config;
    const alerts = ucActiveAlerts(this._hass, c.alert_entities);
    const notices = ucActiveAlerts(this._hass, c.notice_entities);
    const info = (this._ucTpl && this._ucTpl.info && this._ucTpl.info.value) || '';
    const kind = alerts.length ? 'alert' : notices.length ? 'notice' : 'ok';
    const list = alerts.length ? alerts : notices;
    const text = kind === 'ok' ? esc(c.ok_text || ucT(this._hass, 'tout_va_bien')) : `${alerts.length > 1 ? esc(ucT(this._hass, 'n_alertes', { n: alerts.length })) : ''}${list.map((a) => esc(a.name)).join(' · ')}`;
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        button { width: 100%; min-height: 44px; box-sizing: border-box; padding: 6px 12px; display: flex; align-items: center; justify-content: space-between; gap: 10px; border: 1px solid rgba(46,204,113,0.45); border-radius: 12px; background: linear-gradient(180deg, rgba(46,204,113,0.16) 0%, rgba(46,204,113,0.07) 100%); box-shadow: var(--uc-card-shadow); color: var(--uc-text); font: 400 16px var(--uc-font); text-align: left; cursor: default; }
        button.alert { border-color: #8E2C30; background: rgba(229,72,77,0.16); cursor: pointer; }
        button.notice { border-color: #8A5A12; background: rgba(243,156,18,0.14); cursor: pointer; }
        .l { display: flex; align-items: center; gap: 8px; min-width: 0; }
        .dot { flex: 0 0 10px; width: 10px; height: 10px; border-radius: 5px; background: #2ECC71; }
        .alert .dot { background: #E5484D; }
        .notice .dot { background: #F39C12; }
        .r { flex: 0 1 auto; font-size: 14px; color: #9CC9F5; text-align: right; }
      </style>
      <button type="button" class="${kind}${kind === 'ok' ? '' : ' uc-tile'}"><span class="l"><span class="dot" aria-hidden="true"></span><span>${text}</span></span>${info ? `<span class="r">${esc(info)}</span>` : ''}</button>`;
    if (kind !== 'ok') this.shadowRoot.querySelector('button').addEventListener('click', () => ucMoreInfo(this, list[0].entity));
  }
}

/* ------------------------------------------------------------------ chiffres clés */

/*
 * custom:ucaness-stats-card : deux à quatre chiffres côte à côte (libellé, valeur, précision).
 *   items:
 *     - {name: Réseau, entity: sensor.cout_du_jour, digits: 2, sub: aujourd'hui}
 *     - {name: Soleil, entity: sensor.production_du_jour, digits: 1, sub_template: "sur {{ ... }} prévus"}
 *     - {name: Dehors, entity: weather.maison, attribute: temperature, unit: °C, digits: 1}
 *   Un appui ouvre la fiche de l'entité.
 */
class UcanessStatsCard extends HTMLElement {
  setConfig(config) {
    if (!config || !Array.isArray(config.items) || !config.items.length) throw new Error(ucT(null, 'err_stats'));
    this._config = config;
    this._ucSeen = null;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const c = this._config;
    c.items.forEach((it, i) => {
      if (it.value_template) ucTemplate(this, 'v' + i, it.value_template, hass, () => this._render());
      if (it.sub_template) ucTemplate(this, 's' + i, it.sub_template, hass, () => this._render());
    });
    if (ucChanged(this, hass, c.items.map((it) => it.entity).filter(Boolean))) this._render();
  }

  disconnectedCallback() { ucTemplatesOff(this); }

  connectedCallback() { if (this._hass) this.hass = this._hass; }

  getCardSize() { return 2; }

  _value(it, i) {
    const hass = this._hass;
    const tpl = this._ucTpl || {};
    if (it.value_template) return tpl['v' + i] && tpl['v' + i].value !== undefined ? tpl['v' + i].value : '…';
    const st = it.entity && hass ? hass.states[it.entity] : undefined;
    if (!st) return '—';
    const raw = it.attribute ? (st.attributes || {})[it.attribute] : st.state;
    const unit = it.unit !== undefined ? it.unit : (it.attribute ? '' : (st.attributes || {}).unit_of_measurement);
    const v = parseFloat(raw);
    if (!Number.isFinite(v)) return raw === undefined || raw === 'unavailable' || raw === 'unknown' ? '—' : String(raw);
    return ucFormat(hass, v, it.digits !== undefined ? it.digits : (Math.abs(v) >= 10 ? 0 : 1), unit);
  }

  /** Valeur affichée ; un nombre lu sur une entité défile jusqu'à sa nouvelle valeur (0.5.0). */
  _countHtml(it, i) {
    const text = esc(this._value(it, i));
    const hass = this._hass;
    const st = !it.value_template && it.entity && hass ? hass.states[it.entity] : undefined;
    if (!st) return text;
    const v = parseFloat(it.attribute ? (st.attributes || {})[it.attribute] : st.state);
    if (!Number.isFinite(v)) return text;
    const d = it.digits !== undefined ? it.digits : (Math.abs(v) >= 10 ? 0 : 1);
    const shown = ucNumber(hass, v, d);
    const at = text.indexOf(esc(shown));
    if (at < 0) return text;
    return `${text.slice(0, at)}<span data-n="i${i}" data-v="${v}" data-d="${d}">${esc(shown)}</span>${text.slice(at + esc(shown).length)}`;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const c = this._config;
    const tpl = this._ucTpl || {};
    const cols = c.columns || Math.min(4, c.items.length);
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        .grid { display: grid; grid-template-columns: repeat(${cols}, minmax(0, 1fr)); gap: 8px; }
        button { min-height: 76px; box-sizing: border-box; padding: 8px 10px; display: flex; flex-direction: column; align-items: flex-start; justify-content: center; gap: 2px; border: 1px solid var(--uc-card-border); border-radius: 12px; background: var(--uc-card-bg); box-shadow: var(--uc-card-shadow); color: var(--uc-text); font: inherit; text-align: left; cursor: pointer; min-width: 0; }
        .n { font-size: 12px; color: #9CC9F5; text-transform: uppercase; letter-spacing: .4px; }
        .v { font: 700 21px var(--uc-font); color: var(--uc-value); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
        .s { font-size: 12px; color: #9CC9F5; }
      </style>
      <div class="grid">${c.items.map((it, i) => {
        const sub = it.sub_template ? (tpl['s' + i] && tpl['s' + i].value) || '' : (it.sub || '');
        return `<button type="button" class="uc-tile" data-i="${i}"><span class="n">${esc(it.name || '')}</span><span class="v"${it.color ? ` style="color:${esc(it.color)}"` : ''}>${this._countHtml(it, i)}</span>${sub ? `<span class="s">${esc(sub)}</span>` : ''}</button>`;
      }).join('')}</div>`;
    this.shadowRoot.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => {
      const it = c.items[Number(b.dataset.i)];
      if (it.navigation_path) ucNavigate(it.navigation_path);
      else ucMoreInfo(this, it.entity);
    }));
    ucCount(this, this.shadowRoot, this._hass);
  }
}

/* ------------------------------------------------------------------ ligne d'information */

/*
 * custom:ucaness-info-card : une ou deux lignes de texte, calculées par un modèle Jinja
 * (même syntaxe que la carte markdown, sans mise en forme), précédées d'un titre en couleur.
 *   title: Cette nuit ; icon: mdi:weather-night ; template: "{{ ... }}"
 *   title_template: "{{ ... }}" (facultatif : titre calculé, à la place de title)
 *   navigation_path: /tableau/energie (facultatif : la ligne devient un lien)
 */
class UcanessInfoCard extends HTMLElement {
  setConfig(config) {
    if (!config || (!config.template && !config.text)) throw new Error(ucT(null, 'err_info'));
    this._config = config;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._config.template) ucTemplate(this, 't', this._config.template, hass, () => this._render());
    if (this._config.title_template) ucTemplate(this, 'h', this._config.title_template, hass, () => this._render());
  }

  disconnectedCallback() { ucTemplatesOff(this); }

  connectedCallback() { if (this._hass) this.hass = this._hass; }

  getCardSize() { return 1; }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const c = this._config;
    const text = c.template ? ((this._ucTpl && this._ucTpl.t && this._ucTpl.t.value) || '…') : c.text;
    const title = c.title_template ? ((this._ucTpl && this._ucTpl.h && this._ucTpl.h.value) || '') : c.title;
    const link = !!(c.navigation_path || c.entity);
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        .row { width: 100%; min-height: 48px; box-sizing: border-box; padding: 9px 12px; display: flex; align-items: center; gap: 10px; border: 1px solid var(--uc-card-border); border-radius: 12px; background: var(--uc-card-bg); box-shadow: var(--uc-card-shadow); color: var(--uc-text); font: 400 16px/1.35 var(--uc-font); text-align: left; --mdc-icon-size: 22px; }
        button.row { cursor: pointer; }
        ha-icon { flex: 0 0 auto; color: #9CC9F5; }
        .txt { flex: 1 1 auto; min-width: 0; white-space: pre-line; }
        .t { color: var(--uc-label); }
        .chev { flex: 0 0 auto; color: var(--uc-tab); }
      </style>
      <${link ? 'button type="button"' : 'div'} class="row${link ? ' uc-tile' : ''}">${c.icon ? `<ha-icon icon="${esc(c.icon)}"></ha-icon>` : ''}<span class="txt">${title ? `<span class="t">${esc(title)}</span> : ` : ''}${esc(text)}</span>${link ? '<svg class="chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>' : ''}</${link ? 'button' : 'div'}>`;
    if (link) this.shadowRoot.querySelector('.row').addEventListener('click', () => (c.navigation_path ? ucNavigate(c.navigation_path) : ucMoreInfo(this, c.entity)));
  }
}

/* ------------------------------------------------------------------ raccourcis */

/*
 * custom:ucaness-shortcuts-card : tuiles icône + nom, quatre par ligne.
 *   items: [{name, icon, color, navigation_path | entity}]
 *   Un élément dont l'entité n'existe pas n'est pas affiché (appareil pas encore relié).
 */
class UcanessShortcutsCard extends HTMLElement {
  setConfig(config) {
    if (!config || !Array.isArray(config.items)) throw new Error(ucT(null, 'err_shortcuts'));
    this._config = config;
    this._ucSeen = null;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const ids = this._config.items.map((it) => it.entity).filter(Boolean);
    if (ucChanged(this, hass, ids)) this._render();
  }

  getCardSize() { return 2; }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const c = this._config;
    const hass = this._hass;
    const items = c.items.map((it, i) => Object.assign({ i }, it)).filter((it) => !it.entity || !hass || hass.states[it.entity]);
    const cols = c.columns || 4;
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        .grid { display: grid; grid-template-columns: repeat(${cols}, minmax(0, 1fr)); gap: 8px; }
        button { position: relative; overflow: hidden; height: 72px; box-sizing: border-box; padding: 4px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; border: 1px solid var(--uc-card-border); border-radius: 12px; background: var(--uc-card-bg); box-shadow: var(--uc-card-shadow); color: var(--uc-text); font: 400 13px var(--uc-font); cursor: pointer; --mdc-icon-size: 24px; min-width: 0; }
        button span { max-width: 100%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        button.on ha-icon { filter: drop-shadow(0 0 6px currentColor); }
        /* Appareil allumé : la tuile se remplit de cyan. */
        button::before { content: ''; position: absolute; inset: 0; background: linear-gradient(0deg, rgba(0,209,214,0.28) 0%, rgba(0,209,214,0.08) 100%); transform: scaleY(0); transform-origin: 50% 100%; transition: transform .5s cubic-bezier(.2,.8,.2,1); pointer-events: none; }
        button.on::before { transform: scaleY(1); }
        button > * { position: relative; }
      </style>
      <div class="grid">${items.map((it) => {
        const st = it.entity && hass ? hass.states[it.entity] : null;
        const on = st && ['on', 'heat', 'open', 'playing'].includes(st.state);
        return `<button type="button" data-i="${it.i}" class="uc-tile${on ? ' on' : ''}"><ha-icon icon="${esc(it.icon || 'mdi:circle-outline')}" style="color:${esc(it.color || 'var(--uc-tab)')}"></ha-icon><span>${esc(it.name || '')}</span></button>`;
      }).join('')}</div>`;
    this.shadowRoot.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => {
      const it = c.items[Number(b.dataset.i)];
      if (it.navigation_path) ucNavigate(it.navigation_path);
      else ucMoreInfo(this, it.entity);
    }));
  }
}

/* ------------------------------------------------------------------ décision expliquée */

/** Petit sous-ensemble de markdown, pour les explications : titres « #### », listes « - » et « 1. »,
 *  gras « **…** », paragraphes séparés par une ligne vide. Le texte est échappé avant mise en forme. */
function ucMiniMarkdown(text) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  const out = [];
  let list = null;
  const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
  String(text || '').split('\n').forEach((raw) => {
    const line = raw.trim();
    let m;
    if (!line) { close(); return; }
    if ((m = line.match(/^#{1,6}\s+(.*)$/))) { close(); out.push(`<h4>${inline(m[1])}</h4>`); return; }
    if ((m = line.match(/^[-*]\s+(.*)$/))) { if (list !== 'ul') { close(); list = 'ul'; out.push('<ul>'); } out.push(`<li>${inline(m[1])}</li>`); return; }
    if ((m = line.match(/^\d+\.\s+(.*)$/))) { if (list !== 'ol') { close(); list = 'ol'; out.push('<ol>'); } out.push(`<li>${inline(m[1])}</li>`); return; }
    close();
    out.push(`<p>${inline(line)}</p>`);
  });
  close();
  return out.join('');
}

/*
 * custom:ucaness-detail-card : une décision en clair, l'explication sur demande.
 *   title | title_template ; aside_template (à droite du titre) ;
 *   headline | headline_template (la décision, en gros) ; template (une phrase) ;
 *   details (modèle Jinja, petit markdown) affiché par le bouton details_label (« Pourquoi ? ») ;
 *   buttons: [{name, icon, entity | navigation_path | logbook}] : un appui ouvre la fiche ou la page ;
 *     avec « logbook: <nom> », il déplie dans la carte les dernières entrées du journal de Home Assistant
 *     écrites sous ce nom (action logbook.log), sur « days » jours (3 par défaut), « limit » au plus (8).
 *     « logbook_entities: [automation.…] » (conseillé) : seules les entrées écrites par ces automatismes
 *     sont cherchées, sans télécharger tout le journal de la maison.
 */
class UcanessDetailCard extends HTMLElement {
  setConfig(config) {
    if (!config || (!config.headline && !config.headline_template)) throw new Error(ucT(null, 'err_detail'));
    this._config = config;
    this._panel = null;
    this._journal = null;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const c = this._config;
    [['h', c.title_template], ['a', c.aside_template], ['l', c.headline_template], ['t', c.template], ['d', c.details]]
      .forEach(([k, t]) => { if (t) ucTemplate(this, k, t, hass, () => this._render()); });
  }

  disconnectedCallback() { ucTemplatesOff(this); }

  connectedCallback() { if (this._hass) this.hass = this._hass; }

  getCardSize() { return this._panel ? 6 : 3; }

  /** Dernières entrées du journal écrites sous le nom `b.logbook` (les plus récentes d'abord). */
  async _loadJournal(b) {
    const hass = this._hass;
    if (!hass || !hass.callWS) return;
    this._journal = { loading: true, entries: [] };
    this._render();
    try {
      const start = new Date(Date.now() - (Number(b.days) || 3) * 86400e3).toISOString();
      let events;
      if (Array.isArray(b.logbook_entities) && b.logbook_entities.length) {
        // Léger : les exécutions des automatismes indiqués, puis les entrées écrites pendant chacune
        // (même contexte). Le journal complet de la maison n'est pas téléchargé.
        const runs = (await hass.callWS({ type: 'logbook/get_events', start_time: start, entity_ids: b.logbook_entities }))
          .filter((e) => e.context_id && e.domain === 'automation' && typeof e.when === 'number')
          .slice(-(Number(b.limit) || 8) * 2);
        const parts = await Promise.all(runs.map((e) => hass.callWS({
          type: 'logbook/get_events', context_id: e.context_id,
          start_time: new Date(e.when * 1000 - 1000).toISOString(), end_time: new Date(e.when * 1000 + 15 * 60e3).toISOString(),
        }).catch(() => [])));
        events = parts.flat();
      } else {
        events = await hass.callWS({ type: 'logbook/get_events', start_time: start });
      }
      const seen = new Set();
      const entries = (events || []).filter((e) => e.name === b.logbook && e.message && !seen.has(e.when + e.message) && seen.add(e.when + e.message))
        .map((e) => ({ when: new Date(typeof e.when === 'number' ? e.when * 1000 : e.when), text: String(e.message).replace(/\s+/g, ' ').trim() }))
        .sort((x, y) => y.when - x.when).slice(0, Number(b.limit) || 8);
      this._journal = { entries };
    } catch (err) {
      this._journal = { error: true, entries: [] };
    }
    if (this._panel === 'journal') this._render();
  }

  _journalHtml() {
    const j = this._journal;
    if (!j || j.loading) return `<p class="m">${esc(ucT(this._hass, 'chargement'))}</p>`;
    if (j.error) return `<p class="m">${esc(ucT(this._hass, 'journal_indisponible'))}</p>`;
    if (!j.entries.length) return `<p class="m">${esc(ucT(this._hass, 'journal_vide'))}</p>`;
    const lang = (this._hass && this._hass.locale && this._hass.locale.language) || 'fr';
    return `<ul class="jl">${j.entries.map((e, i) => {
      const date = e.when.toLocaleDateString(lang, { weekday: 'short', day: '2-digit', month: '2-digit' }) + ' ' + e.when.toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit' });
      const sim = /^\[simulation\]/i.test(e.text);
      const text = e.text.replace(/^\[(réel|simulation)\]\s*/i, '').replace(/(\d)\.(\d)/g, '$1,$2');
      return `<li><button type="button" class="je" data-j="${i}" aria-expanded="false"><span class="jd">${esc(date)}${sim ? ' · ' + esc(ucT(this._hass, 'journal_simulation')) : ''}</span><span class="jt">${esc(text)}</span></button></li>`;
    }).join('')}</ul>`;
  }

  _tpl(key, fallback) {
    const slot = this._ucTpl && this._ucTpl[key];
    return slot && slot.value !== undefined ? slot.value : fallback;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const c = this._config;
    const title = c.title_template ? this._tpl('h', '') : (c.title || '');
    const aside = c.aside_template ? this._tpl('a', '') : '';
    const headline = c.headline_template ? this._tpl('l', '…') : c.headline;
    const text = c.template ? this._tpl('t', '') : (c.text || '');
    const details = c.details ? this._tpl('d', '') : '';
    const buttons = [];
    const why = this._panel === 'why';
    if (c.details) buttons.push(`<button type="button" class="b uc-key${why ? ' on' : ''}" data-k="why" aria-expanded="${why}">${esc(why ? (c.details_close_label || ucT(this._hass, 'reduire')) : (c.details_label || ucT(this._hass, 'pourquoi')))}</button>`);
    (c.buttons || []).forEach((b, i) => {
      const on = b.logbook && this._panel === 'journal';
      buttons.push(`<button type="button" class="b uc-key${on ? ' on' : ''}" data-k="${i}"${b.logbook ? ` aria-expanded="${on}"` : ''}>${b.icon ? `<ha-icon icon="${esc(b.icon)}"></ha-icon>` : ''}${esc(on ? ucT(this._hass, 'reduire') : (b.name || ''))}</button>`);
    });
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        section { box-sizing: border-box; padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; border: 1px solid var(--uc-card-border); border-radius: 12px; background: var(--uc-card-bg); box-shadow: var(--uc-card-shadow); }
        .head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
        .t { font-size: 15px; color: var(--uc-label); }
        .a { font-size: 13px; color: #9CC9F5; text-align: right; }
        .l { font: 700 21px/1.2 var(--uc-font); }
        .x { font-size: 15px; line-height: 1.35; color: #E6ECF5; }
        .btns { display: flex; gap: 8px; margin-top: 4px; }
        .b { height: 44px; flex: 1 1 0; min-width: 0; display: flex; align-items: center; justify-content: center; gap: 6px; border: 1px solid var(--uc-tab-border); border-radius: 22px; background: linear-gradient(180deg, #123A68 0%, #0A2546 100%); color: var(--uc-tab); font: 400 15px var(--uc-font); cursor: pointer; --mdc-icon-size: 20px; }
        .d { margin-top: 4px; padding-top: 8px; border-top: 1px solid #1C4F86; font-size: 15px; line-height: 1.4; color: #E6ECF5; }
        .d[hidden] { display: none; }
        .d h4 { margin: 4px 0 6px; font: 700 15px var(--uc-font); color: var(--uc-label); }
        .d p { margin: 0 0 8px; }
        .d ul, .d ol { margin: 0 0 8px; padding-left: 20px; }
        .d li { margin-bottom: 4px; }
        .d b { color: #FFFFFF; }
        .b.on { background: rgba(0,209,214,0.14); }
        .m { margin: 0; color: #9CC9F5; }
        .jl { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
        .je { width: 100%; padding: 6px 0; border: 0; border-bottom: 1px solid #16365F; background: transparent; color: #E6ECF5; font: 400 14px/1.35 var(--uc-font); text-align: left; display: flex; flex-direction: column; gap: 2px; cursor: pointer; }
        .jd { font-size: 12px; color: var(--uc-label); text-transform: capitalize; }
        .jt { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
        .je[aria-expanded="true"] .jt { display: block; }
      </style>
      <section aria-label="${esc(title || headline)}">
        ${title || aside ? `<div class="head"><span class="t">${esc(title)}</span><span class="a">${esc(aside)}</span></div>` : ''}
        <span class="l">${esc(headline)}</span>
        ${text ? `<span class="x">${esc(text)}</span>` : ''}
        ${buttons.length ? `<div class="btns">${buttons.join('')}</div>` : ''}
        ${c.details ? `<div class="d"${why ? '' : ' hidden'}>${ucMiniMarkdown(details)}</div>` : ''}
        ${this._panel === 'journal' ? `<div class="d">${this._journalHtml()}</div>` : ''}
      </section>`;
    // 0.5.0 : la carte se retourne quand la décision change (fondu en mode allégé).
    const known = this._lastHead !== undefined && this._lastHead !== '…';
    if (known && headline !== '…' && headline !== this._lastHead && !UC_REDUCED) {
      const sec = this.shadowRoot.querySelector('section');
      const kf = UC_LIGHT ? [{ opacity: 0 }, { opacity: 1 }]
        : [{ transform: 'perspective(900px) rotateY(-180deg)', opacity: 0.2 }, { transform: 'perspective(900px) rotateY(-90deg)', opacity: 0.5, offset: 0.45 }, { transform: 'perspective(900px) rotateY(0deg)', opacity: 1 }];
      try { sec.animate(kf, { duration: UC_LIGHT ? 400 : 900, easing: 'cubic-bezier(.2,.8,.2,1)' }); } catch (e) { /* sans animation */ }
    }
    if (headline !== '…') this._lastHead = headline;
    this.shadowRoot.querySelectorAll('.je').forEach((el) => el.addEventListener('click', () => {
      el.setAttribute('aria-expanded', String(el.getAttribute('aria-expanded') !== 'true'));
    }));
    this.shadowRoot.querySelectorAll('.b').forEach((el) => el.addEventListener('click', () => {
      if (el.dataset.k === 'why') { this._panel = this._panel === 'why' ? null : 'why'; this._render(); return; }
      const b = c.buttons[Number(el.dataset.k)];
      if (b.logbook) {
        this._panel = this._panel === 'journal' ? null : 'journal';
        if (this._panel) this._loadJournal(b); else this._render();
        return;
      }
      if (b.navigation_path) ucNavigate(b.navigation_path);
      else ucMoreInfo(this, b.entity);
    }));
  }
}

/* ------------------------------------------------------------------ graphique heure par heure */

/*
 * custom:ucaness-hours-card : un seul graphique de la journée, heure par heure, avec un choix en haut.
 * Données : statistiques horaires de Home Assistant (heure en cours complétée par les statistiques
 * à 5 minutes). Un appui sur une heure affiche sa valeur ; un second appui revient au total.
 *   tabs:
 *     - name: Soleil
 *       statistic: sensor.production_totale     # compteur d'énergie (stat_type: change, par défaut)
 *       unit: kWh ; color: "#F5C542" ; digits: 1
 *       hours: auto                              # ou [7, 19] ; par défaut toute la journée
 *       total_label: Produit aujourd'hui
 *       forecast_entity: sensor.solcast_...      # facultatif : prévision en pointillés
 *       forecast_attribute: detailedHourly ; forecast_key: pv_estimate ; forecast_label: prévu
 *     - name: Batterie
 *       statistic: sensor.soc ; stat_type: mean ; kind: line ; unit: "%" ; min: 0 ; max: 100
 *       floor_entity: input_number.plancher      # facultatif : ligne du plancher
 */
class UcanessHoursCard extends HTMLElement {
  setConfig(config) {
    if (!config || !Array.isArray(config.tabs) || !config.tabs.length) throw new Error(ucT(null, 'err_hours_tabs'));
    if (config.tabs.some((t) => !t.statistic)) throw new Error(ucT(null, 'err_hours_stat'));
    this._config = config;
    this._tab = Math.min(Number(config.default_tab) || 0, config.tabs.length - 1);
    this._sel = null;
    this._data = {};
    this._ucSeen = null;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._render();
    if (this._hass) this._load(true);
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._load();
    const ids = this._config.tabs.flatMap((t) => [t.forecast_entity, t.floor_entity]).filter(Boolean);
    if (ucChanged(this, hass, ids)) this._render();
  }

  connectedCallback() {
    clearInterval(this._timer);
    this._timer = setInterval(() => this._load(true), 5 * 60 * 1000);
    if (this._hass) this._load();
  }

  disconnectedCallback() { clearInterval(this._timer); }

  getCardSize() { return 5; }

  async _load(force) {
    const hass = this._hass;
    const key = this._tab;
    const t = this._config.tabs[key];
    const cached = this._data[key];
    const today = new Date().toDateString();
    if (!hass || !hass.callWS) return;
    if (!force && cached && cached.day === today && Date.now() - cached.at < 5 * 60 * 1000) { this._render(); return; }
    if (this._loading === key) return;
    this._loading = key;
    const type = t.stat_type || 'change';
    const start = new Date(); start.setHours(0, 0, 0, 0);
    const hour = new Date(); hour.setMinutes(0, 0, 0);
    const vals = new Array(24).fill(null);
    try {
      const ask = (from, period) => hass.callWS({ type: 'recorder/statistics_during_period', start_time: from.toISOString(), period, statistic_ids: [t.statistic], types: [type], units: {} });
      const [hourly, recent] = await Promise.all([ask(start, 'hour'), ask(hour, '5minute')]);
      (hourly[t.statistic] || []).forEach((p) => {
        const d = new Date(p.start);
        if (d >= start && p[type] !== null && p[type] !== undefined) vals[d.getHours()] = Number(p[type]);
      });
      const five = (recent[t.statistic] || []).map((p) => p[type]).filter((v) => v !== null && v !== undefined).map(Number);
      if (five.length && hour >= start) vals[hour.getHours()] = type === 'change' ? five.reduce((a, b) => a + b, 0) : five.reduce((a, b) => a + b, 0) / five.length;
      if (!cached || cached.day !== today) this._grow = true;  // première fois pour cet onglet : les barres poussent
      this._data[key] = { at: Date.now(), day: today, vals, current: hour.getHours() };
    } catch (e) {
      this._data[key] = { at: Date.now(), day: today, vals, current: hour.getHours(), error: true };
    }
    this._loading = null;
    if (key === this._tab) this._render();
  }

  _forecast(t) {
    if (!t.forecast_entity || !this._hass) return null;
    const st = this._hass.states[t.forecast_entity];
    const list = st && st.attributes ? st.attributes[t.forecast_attribute || 'detailedHourly'] : null;
    if (!Array.isArray(list)) return null;
    const out = new Array(24).fill(null);
    const today = new Date().toDateString();
    list.forEach((p) => {
      const d = new Date(p.period_start || p.start || p.datetime);
      const v = Number(p[t.forecast_key || 'pv_estimate']);
      if (!Number.isNaN(d.getTime()) && d.toDateString() === today && Number.isFinite(v)) out[d.getHours()] = v;
    });
    return out;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const hass = this._hass;
    const c = this._config;
    const t = c.tabs[this._tab];
    const data = this._data[this._tab];
    const vals = data ? data.vals : new Array(24).fill(null);
    const fc = this._forecast(t);
    const line = t.kind === 'line';
    const unit = t.unit || '';
    const digits = t.digits !== undefined ? t.digits : (unit === '%' ? 0 : 1);
    const fmt = (v, d = digits) => ucFormat(hass, v, d, unit);
    // Plage d'heures : fixe, ou « auto » autour des heures non nulles (mesure ou prévision).
    let from = 0, to = 24;
    if (Array.isArray(t.hours) && t.hours.length === 2) [from, to] = t.hours.map(Number);
    else if (t.hours === 'auto') {
      const on = [...Array(24).keys()].filter((h) => (vals[h] || 0) > 0.005 || (fc && (fc[h] || 0) > 0.005));
      if (on.length) { from = Math.max(0, on[0] - 1); to = Math.min(24, on[on.length - 1] + 2); }
      if (to - from < 6) { const mid = (from + to) / 2; from = Math.max(0, Math.floor(mid - 3)); to = Math.min(24, from + 6); }
    }
    const n = Math.max(1, to - from);
    const shown = vals.slice(from, to);
    const shownFc = fc ? fc.slice(from, to) : null;
    const floor = t.floor_entity ? ucNum(hass, t.floor_entity) : null;
    const all = [...shown, ...(shownFc || []), floor].filter((v) => v !== null && Number.isFinite(v));
    let max = t.max !== undefined ? Number(t.max) : Math.max(0, ...all);
    if (t.max === undefined) {
      const step = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000].find((s) => s * 2 >= max) || Math.ceil(max / 2);
      max = Math.max(step * 2, 0.1);
    }
    const min = t.min !== undefined ? Number(t.min) : 0;
    const W = 340, H = 150, x0 = 30, x1 = W - 4, y0 = 10, y1 = H - 22;
    const bw = (x1 - x0) / n;
    const X = (i) => x0 + bw * i + bw / 2;
    const Y = (v) => y1 - (Math.max(min, Math.min(max, v)) - min) / (max - min || 1) * (y1 - y0);
    const color = t.color || 'var(--uc-value)';
    const ticks = [min, (min + max) / 2, max];
    const tickDigits = (v) => (Math.abs(max) < 1 ? 1 : Number.isInteger(v) ? 0 : 1);
    const every = n > 16 ? 6 : n > 8 ? 3 : 2;
    let marks = '';
    ticks.forEach((v, k) => {
      marks += `<line x1="${x0}" y1="${Y(v).toFixed(1)}" x2="${x1}" y2="${Y(v).toFixed(1)}" stroke="${k === 0 ? '#3A6A9A' : '#1C3F6A'}" stroke-width="1"/>`;
      marks += `<text x="${x0 - 4}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end" class="ax">${esc(ucNumber(hass, v, tickDigits(v)))}</text>`;
    });
    for (let h = from; h < to; h += 1) if ((h - from) % every === 0) marks += `<text x="${(x0 + bw * (h - from)).toFixed(1)}" y="${H - 6}" class="ax">${h} h</text>`;
    let body = '';
    // 0.5.0 : barres qui poussent en cascade et courbe qui se trace (à l'ouverture et au changement d'onglet seulement).
    const grow = !!(this._grow && data && !UC_REDUCED);
    if (data) this._grow = false;
    let defs = '';
    if (line) {
      const pts = shown.map((v, i) => (v === null ? null : [X(i), Y(v)]));
      let seg = [];
      const segs = [];
      pts.forEach((p) => { if (p) seg.push(p); else if (seg.length) { segs.push(seg); seg = []; } });
      if (seg.length) segs.push(seg);
      defs = `<defs><linearGradient id="ucarea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity="0.38"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>`;
      segs.forEach((sg) => {
        if (sg.length < 2) return;
        const d = sg.map((p, k) => `${k ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
        body += `<path class="${grow && !UC_LIGHT ? 'area' : ''}" d="${d} L${sg[sg.length - 1][0].toFixed(1)} ${y1} L${sg[0][0].toFixed(1)} ${y1} Z" fill="url(#ucarea)"/>`;
        body += `<path class="${grow && !UC_LIGHT ? 'trace' : ''}" pathLength="1" d="${d}" fill="none" stroke="${color}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>`;
      });
      shown.forEach((v, i) => { if (v !== null) body += `<circle cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="${this._sel === from + i ? 4.5 : 2.6}" fill="${color}"/>`; });
    } else {
      shown.forEach((v, i) => {
        if (v === null || v <= 0) return;
        const cur = data && from + i === data.current;
        const y = Y(v);
        const x = X(i) - bw * 0.36;
        const w = bw * 0.72;
        const h = Math.max(1, y1 - y);
        const r = Math.min(3, w / 2, h);
        // Haut de la barre arrondi.
        const d = `M${x.toFixed(1)} ${y1} V${(y + r).toFixed(1)} Q${x.toFixed(1)} ${y.toFixed(1)} ${(x + r).toFixed(1)} ${y.toFixed(1)} H${(x + w - r).toFixed(1)} Q${(x + w).toFixed(1)} ${y.toFixed(1)} ${(x + w).toFixed(1)} ${(y + r).toFixed(1)} V${y1} Z`;
        body += `<path class="${grow ? 'bar' : ''}" style="${grow ? `animation-delay:${i * 25}ms` : ''}" d="${d}" fill="${color}" opacity="${cur ? 0.55 : (this._sel !== null && this._sel !== from + i ? 0.6 : 1)}"/>`;
      });
    }
    if (shownFc) {
      const p = shownFc.map((v, i) => (v === null ? null : `${X(i).toFixed(1)},${Y(v).toFixed(1)}`)).filter(Boolean);
      if (p.length > 1) body += `<polyline points="${p.join(' ')}" fill="none" stroke="#FFFFFF" stroke-width="1.6" stroke-dasharray="5 4"/>`;
    }
    if (floor !== null) body += `<line x1="${x0}" y1="${Y(floor).toFixed(1)}" x2="${x1}" y2="${Y(floor).toFixed(1)}" stroke="#F39C12" stroke-width="1.4" stroke-dasharray="4 4"/><text x="${x1}" y="${(Y(floor) - 4).toFixed(1)}" text-anchor="end" class="ax" style="fill:#F39C12">plancher</text>`;
    if (this._sel !== null && this._sel >= from && this._sel < to) {
      body += `<rect x="${(x0 + bw * (this._sel - from)).toFixed(1)}" y="${y0 - 4}" width="${bw.toFixed(1)}" height="${(y1 - y0 + 4).toFixed(1)}" rx="4" fill="rgba(0,209,214,0.10)" stroke="#00D1D6" stroke-width="1"/>`;
      // Bulle au toucher : la valeur de l'heure choisie, au-dessus de la barre.
      const v = vals[this._sel];
      if (v !== null) {
        const txt = `${this._sel} h : ${fmt(v, line ? digits : 2)}`;
        const tw = Math.max(44, txt.length * 6.2 + 12);
        const tx = Math.max(x0, Math.min(x1 - tw, X(this._sel - from) - tw / 2));
        const ty = Math.max(0, Y(v) - 24);
        body += `<g class="tip"><rect x="${tx.toFixed(1)}" y="${ty.toFixed(1)}" width="${tw.toFixed(1)}" height="18" rx="9" fill="#0A2546" stroke="#00D1D6"/><text x="${(tx + tw / 2).toFixed(1)}" y="${(ty + 13).toFixed(1)}" text-anchor="middle" class="tt">${esc(txt)}</text></g>`;
      }
    }
    let hits = '';
    for (let i = 0; i < n; i += 1) hits += `<rect data-h="${from + i}" x="${(x0 + bw * i).toFixed(1)}" y="0" width="${bw.toFixed(1)}" height="${H}" fill="transparent"/>`;
    // Légende sous le graphique : total de la journée, ou la valeur de l'heure choisie.
    const known = vals.filter((v) => v !== null);
    let caption;
    if (!data) caption = ucT(this._hass, 'chargement');
    else if (data.error && !known.length) caption = ucT(this._hass, 'historique_indisponible');
    else if (!known.length) caption = ucT(this._hass, 'pas_de_mesure');
    else if (this._sel !== null) {
      const v = vals[this._sel];
      const f = fc ? fc[this._sel] : null;
      caption = `${this._sel} h – ${this._sel + 1} h : ${v === null ? '—' : fmt(v, line ? digits : 2)}${f !== null && f !== undefined ? ` · ${t.forecast_label || ucT(this._hass, 'prevu')} ${fmt(f, 2)}` : ''}`;
    } else if (line) {
      caption = ucT(this._hass, 'de_a', { nom: t.total_label || t.name, min: fmt(Math.min(...known)), max: fmt(Math.max(...known)) });
    } else {
      const total = known.reduce((a, b) => a + b, 0);
      const fTotal = fc ? fc.filter((v) => v !== null).reduce((a, b) => a + b, 0) : null;
      caption = `${t.total_label || t.name} : ${fmt(total)}${fTotal !== null ? ` · ${t.forecast_label || ucT(this._hass, 'prevu')} ${fmt(fTotal)}` : ''}`;
    }
    const legend = [line ? '' : (data && data.current >= from && data.current < to ? ucT(this._hass, 'heure_en_cours') : ''), shownFc ? ucT(this._hass, 'pointilles_prevision') : ''].filter(Boolean).join(' · ');
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        section { box-sizing: border-box; padding: 8px 10px 10px; display: flex; flex-direction: column; gap: 6px; border: 1px solid var(--uc-card-border); border-radius: 12px; background: var(--uc-card-bg); box-shadow: var(--uc-card-shadow); }
        .tabs { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 6px; }
        .tabs button { height: 40px; border: 1px solid var(--uc-tab-border); border-radius: 20px; background: linear-gradient(180deg, #123A68 0%, #0A2546 100%); color: #CFE6FF; font: 400 15px var(--uc-font); cursor: pointer; }
        .tabs button[aria-selected="true"] { background: linear-gradient(180deg, #33E4E8 0%, var(--uc-tab) 55%, #00A9AE 100%); border-color: #7FF3F5; color: #06203F; font-weight: 700; }
        .bar { transform-box: fill-box; transform-origin: 50% 100%; animation: ucGrow .6s cubic-bezier(.2,.8,.2,1) both; }
        @keyframes ucGrow { from { transform: scaleY(0); } to { transform: scaleY(1); } }
        .trace { stroke-dasharray: 1 1; animation: ucTrace 1.6s ease-out both; }
        @keyframes ucTrace { from { stroke-dashoffset: 1; } to { stroke-dashoffset: 0; } }
        .area { transform-box: fill-box; transform-origin: 50% 100%; animation: ucArea 1.1s cubic-bezier(.2,.8,.2,1) .5s both; }
        @keyframes ucArea { from { opacity: 0; transform: scaleY(.2); } to { opacity: 1; transform: none; } }
        .tt { fill: #FFFFFF; font: 11px var(--uc-font); }
        svg { width: 100%; height: auto; max-height: 240px; display: block; touch-action: manipulation; }
        svg rect[data-h] { cursor: pointer; }
        .ax { fill: #9CC9F5; font: 12px var(--uc-font); }
        .cap { font-size: 15px; color: #E6ECF5; }
        .leg { font-size: 12px; color: #9CC9F5; }
      </style>
      <section aria-label="${esc(ucT(this._hass, 'graphique_heures'))}">
        ${c.tabs.length > 1 ? `<div class="tabs" role="tablist">${c.tabs.map((x, i) => `<button type="button" class="uc-key" role="tab" data-i="${i}" aria-selected="${i === this._tab}">${esc(x.name)}</button>`).join('')}</div>` : ''}
        <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(ucT(this._hass, 'nom_heures', { nom: t.name }))}">${defs}${marks}${body}${hits}</svg>
        <span class="cap">${esc(caption)}</span>
        ${legend ? `<span class="leg">${esc(legend)}</span>` : ''}
      </section>`;
    this.shadowRoot.querySelectorAll('.tabs button').forEach((b) => b.addEventListener('click', () => {
      this._tab = Number(b.dataset.i);
      this._sel = null;
      this._grow = true;
      this._render();
      this._load();
    }));
    this.shadowRoot.querySelectorAll('rect[data-h]').forEach((r) => r.addEventListener('click', () => {
      const h = Number(r.dataset.h);
      this._sel = this._sel === h ? null : h;
      this._render();
    }));
  }
}

/* ------------------------------------------------------------------ Ucan, l'assistant */

/*
 * custom:ucaness-ucan-card : Ucan, la batterie UHome avec un visage, et son conseil du moment.
 *   conseil: sensor.ucan_conseil (pilotage/packages/ucan_conseils.yaml) ; soc: sensor.uhome_soc ;
 *   alert_entities: [...] (comme ucaness-status-card) ; script: script.ucan_conseil_reponse ;
 *   compact: true (téléphone : petit avatar à côté de la bulle) ;
 *   simulateur: {puissance_actuelle_kva, abonnement_actuel_eur_an, jours} (0.5.5) : boutons « Et si… » dans la
 *   fenêtre (contrat, puissance), calcul seul par ucaness.simuler ;
 *   floating: true (0.5.3) : Ucan en bouton rond en bas à droite, devant les cartes ; un appui ouvre la
 *   conversation ; pastille et léger battement quand un conseil attend ; offset_bottom, offset_right (px).
 * Expression : « à surveiller » (lumière orange) si une alerte est en cours, « un conseil » si un
 * conseil attend, « la nuit » (yeux fermés) quand le soleil est couché, sinon « tout va bien ».
 * Les barres des trois modules s'allument avec la charge (au-dessus de 0, 33 et 66 %).
 * Boutons : « Je le fais », « Pas maintenant », « Ne plus proposer » (réponse au script).
 */
const UC_UCAN_POS = 'ucaness-ucan-position';

function ucUcanSvg(humeur, charge) {
  const lum = humeur === 'alerte' ? '#F39C12' : '#00D1D6';
  const off = '#1B2230';
  const c = Number.isFinite(charge) ? charge : 0;
  const bar = (seuil) => (c > seuil ? lum : off);
  const caisse = 'fill="#2A2D33" stroke="#50555F" stroke-width="2"';
  const face = {
    dort: `<path d="M74 62q10 7 20 0M126 62q10 7 20 0M102 84q8 4 16 0" fill="none" stroke="${lum}" stroke-width="4" stroke-linecap="round"/>`,
    content: `<rect x="76" y="52" width="16" height="16" rx="8" fill="${lum}"/><rect x="128" y="52" width="16" height="16" rx="8" fill="${lum}"/><path d="M94 80q16 14 32 0" fill="none" stroke="${lum}" stroke-width="4" stroke-linecap="round"/>`,
    conseil: `<rect x="76" y="52" width="16" height="16" rx="8" fill="${lum}"/><rect x="128" y="52" width="16" height="16" rx="8" fill="${lum}"/><path d="M96 82q14 9 28 0M124 44l20-5" fill="none" stroke="${lum}" stroke-width="4" stroke-linecap="round"/>`,
    alerte: `<rect x="76" y="52" width="16" height="16" rx="8" fill="${lum}"/><rect x="128" y="52" width="16" height="16" rx="8" fill="${lum}"/><rect x="104" y="78" width="12" height="12" rx="6" fill="${lum}"/><path d="M72 44l20 6M148 44l-20 6" fill="none" stroke="${lum}" stroke-width="3.5" stroke-linecap="round"/>`,
  }[humeur] || '';
  return `<svg viewBox="0 0 220 300" role="img" aria-label="Ucan">
    <ellipse cx="110" cy="286" rx="92" ry="10" fill="#000" opacity=".35"/>
    <rect x="34" y="18" width="152" height="96" rx="22" ${caisse}/>
    <rect x="34" y="120" width="152" height="50" rx="8" ${caisse}/><rect x="34" y="174" width="152" height="50" rx="8" ${caisse}/><rect x="34" y="228" width="152" height="50" rx="8" ${caisse}/>
    <rect x="74" y="143" width="72" height="5" rx="2.5" fill="${bar(66)}"/><rect x="74" y="197" width="72" height="5" rx="2.5" fill="${bar(33)}"/><rect x="74" y="251" width="72" height="5" rx="2.5" fill="${bar(0)}"/>
    <rect x="172" y="132" width="5" height="138" rx="2.5" fill="${lum}" opacity=".85"/>
    <rect x="44" y="24" width="132" height="84" rx="26" fill="${lum}" opacity=".14"/>
    <rect x="52" y="32" width="116" height="68" rx="20" fill="#061B3D" stroke="${lum}" stroke-width="2.5"/>
    ${face}</svg>`;
}

class UcanessUcanCard extends HTMLElement {
  setConfig(config) {
    this._config = Object.assign({ conseil: 'sensor.ucan_conseil', soc: 'sensor.uhome_soc', script: 'script.ucan_conseil_reponse' }, config || {});
    this._ucSeen = null;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    if (this.isConnected) this._flottant();
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const c = this._config;
    const ids = [c.conseil, c.soc, 'sun.sun', ...ucAlertList(c.alert_entities).map((a) => a.entity)];
    if (ucChanged(this, hass, ids)) this._render();
  }

  connectedCallback() { this._flottant(); this._render(); }

  disconnectedCallback() {
    if (this._flot) { this._flot.remove(); this._flot = null; }
    if (this._echap) { window.removeEventListener('keydown', this._echap); this._echap = null; }
  }

  getCardSize() { return this._config && this._config.floating ? 0 : this._config && this._config.compact ? 3 : 5; }

  /* Mode « bulle » (floating: true) : Ucan vit en bas à droite de l'écran, devant les cartes.
     L'élément est posé sur <body> pour ne dépendre d'aucune carte (ni transformation ni défilement). */
  _flottant() {
    if (!this._config || !this._config.floating) {
      if (this._flot) { this._flot.remove(); this._flot = null; }
      return;
    }
    if (this._flot || typeof document === 'undefined') return;
    this._flot = document.createElement('div');
    this._flot.className = 'ucaness-ucan-bulle';
    this._flot.attachShadow({ mode: 'open' });
    document.body.appendChild(this._flot);
    this._echap = (e) => { if (e.key === 'Escape' && this._ouvert) { this._ouvert = false; this._render(); } };
    window.addEventListener('keydown', this._echap);
  }

  /* Position de la bulle : celle choisie par l'utilisateur sur cet appareil (glisser-déposer,
     gardée dans le navigateur), sinon offset_bottom / offset_right. Toujours ramenée dans l'écran. */
  _position() {
    const c = this._config;
    if (this._deplace === undefined) {
      try { this._deplace = JSON.parse(window.localStorage.getItem(UC_UCAN_POS) || 'null'); } catch (e) { this._deplace = null; }
    }
    const p = this._deplace || { droite: Number(c.offset_right ?? 20), bas: Number(c.offset_bottom ?? 20) };
    const w = window.innerWidth || 1280;
    const h = window.innerHeight || 800;
    return { droite: Math.min(Math.max(4, p.droite), Math.max(4, w - 68)), bas: Math.min(Math.max(4, p.bas), Math.max(4, h - 68)) };
  }

  /* Un appui ouvre ou ferme ; un glissement de plus de 6 px déplace la bulle (souris ou doigt). */
  _glisser(fab) {
    let depart = null;
    fab.addEventListener('pointerdown', (e) => {
      const p = this._position();
      depart = { x: e.clientX, y: e.clientY, droite: p.droite, bas: p.bas, bouge: false };
      try { fab.setPointerCapture(e.pointerId); } catch (err) { /* pointeur déjà relâché */ }
    });
    fab.addEventListener('pointermove', (e) => {
      if (!depart) return;
      const dx = e.clientX - depart.x;
      const dy = e.clientY - depart.y;
      if (!depart.bouge && Math.hypot(dx, dy) < 6) return;
      depart.bouge = true;
      this._enGlisse = true;
      fab.classList.add('glisse');
      const w = window.innerWidth || 1280;
      const h = window.innerHeight || 800;
      const droite = Math.min(Math.max(4, depart.droite - dx), w - 68);
      const bas = Math.min(Math.max(4, depart.bas - dy), h - 68);
      this._flot.style.setProperty('right', `${droite}px`, 'important');
      this._flot.style.setProperty('bottom', `${bas}px`, 'important');
      depart.fin = { droite, bas };
    });
    const fin = () => {
      if (!depart) return;
      const d = depart;
      depart = null;
      this._enGlisse = false;
      if (d.bouge && d.fin) {
        this._deplace = d.fin;
        try { window.localStorage.setItem(UC_UCAN_POS, JSON.stringify(d.fin)); } catch (e) { /* stockage indisponible */ }
        this._flot.style.removeProperty('right');
        this._flot.style.removeProperty('bottom');
      } else {
        this._ouvert = !this._ouvert;
      }
      this._render();
    };
    fab.addEventListener('pointerup', fin);
    fab.addEventListener('pointercancel', () => { depart = null; this._enGlisse = false; this._render(); });
    // Clavier (Entrée, Espace) ou appel du programme : un « click » sans pointeur (detail 0).
    fab.addEventListener('click', (e) => { if (e.detail === 0) { this._ouvert = !this._ouvert; this._render(); } });
  }

  _etat() {
    const h = this._hass;
    const c = this._config;
    const st = h && h.states[c.conseil];
    const conseil = st && !['aucun', 'unknown', 'unavailable'].includes(st.state) ? st : null;
    const soc = h && h.states[c.soc] ? parseFloat(h.states[c.soc].state) : NaN;
    const alertes = ucActiveAlerts(h, c.alert_entities);
    const nuit = !!(h && h.states['sun.sun'] && h.states['sun.sun'].state === 'below_horizon');
    const humeur = alertes.length ? 'alerte' : conseil ? 'conseil' : nuit ? 'dort' : 'content';
    return { conseil, soc, alertes, humeur };
  }

  _corps(conseil, alertes) {
    const a = conseil ? conseil.attributes : {};
    if (conseil) {
      return `<p class="k">${esc(a.titre || ucT(this._hass, 'un_conseil'))}</p>
        <p class="t">${esc(a.constat || '')}</p><p class="t">${esc(a.geste || '')}</p>
        ${a.gain ? `<p class="t g">${esc(a.gain)}</p>` : ''}${a.avertissement ? `<p class="n">${esc(a.avertissement)}</p>` : ''}
        <div class="btns">
          <button type="button" class="uc-key p" data-r="fait">${esc(ucT(this._hass, 'je_le_fais'))}</button>
          <button type="button" class="uc-key s" data-r="plus_tard">${esc(ucT(this._hass, 'pas_maintenant'))}</button>
          <button type="button" class="uc-key q" data-r="jamais">${esc(ucT(this._hass, 'ne_plus_proposer'))}</button>
        </div>`;
    }
    if (alertes.length) return `<p class="t">${esc(ucT(this._hass, 'alerte_conseils_attendront', { noms: alertes.map((x) => x.name).join(', ') }))}</p>`;
    return `<p class="t">${esc(ucT(this._hass, 'ucan_tout_va_bien'))}</p>`;
  }

  /* Simulateur « et si » (option simulateur: {puissance_actuelle_kva, abonnement_actuel_eur_an, jours}) :
     calcul seul par l'action ucaness.simuler, réponse affichée comme un message d'Ucan. */
  _etsiHtml() {
    const c = this._config;
    if (!c.simulateur) return '';
    const s = this._simu;
    const h = this._hass;
    const eur = (v) => `${Math.round(v).toLocaleString(ucLang(h))} €`;
    let rep = '';
    if (s && s.charge) rep = `<p class="t">${esc(ucT(h, 'calcul_en_cours'))}</p>`;
    else if (s && s.erreur) rep = `<p class="t">${esc(ucT(h, 'calcul_impossible', { erreur: s.erreur }))}</p>`;
    else if (s && s.r && s.r.question === 'contrat') {
      const r = s.r;
      const act = r.contrat_actuel;
      const lignes = (r.classement || []).slice(0, 3).map((l) => `<li>${esc(ucT(h, 'offre_par_an', { nom: l.nom, montant: eur(l.cout_annuel_eur) }))}${typeof l.ecart_avec_contrat_actuel_eur_an === 'number' ? ` (${l.ecart_avec_contrat_actuel_eur_an <= 0 ? '' : '+'}${eur(l.ecart_avec_contrat_actuel_eur_an)})` : ''}</li>`).join('');
      const fiab = ['fiable', 'indicatif', 'insuffisant'].includes(r.fiabilite) ? ucT(h, 'fiab_' + r.fiabilite) : r.fiabilite;
      rep = `<p class="t">${esc(ucT(h, 'sur_vos_jours', { jours: act ? act.jours_mesures : r.jours_demandes, fiabilite: fiab }))}</p>
        ${act ? `<p class="t">${esc(ucT(h, 'contrat_actuel_par_an', { montant: eur(act.cout_annuel_eur) }))}</p>` : ''}<ul class="t">${lignes}</ul>
        <p class="n">${esc((r.limites || [])[0] || '')} ${esc(ucT(h, 'prix_a_verifier'))}</p>`;
    } else if (s && s.r && s.r.question === 'puissance') {
      const r = s.r;
      const nb = (v) => Number(v).toLocaleString(ucLang(h));
      rep = r.conseil === 'inconnu' ? `<p class="t">${esc(r.raison || '')}</p>`
        : `<p class="t">${esc(['garder', 'baisser', 'augmenter'].includes(r.conseil) ? ucT(h, 'puissance_' + r.conseil, { pointe: nb(r.pointe_mesuree_kva), jours: r.jours_mesures, actuelle: nb(r.puissance_souscrite_kva), reco: nb(r.puissance_recommandee_kva), marge: r.marge_pct }) : (r.raison || r.conseil || ''))}</p>
          ${(r.remarques || []).map((x) => `<p class="n">${esc(x)}</p>`).join('')}`;
    }
    return `<div class="etsi"><p class="k">${esc(ucT(h, 'et_si'))}</p><div class="btns">
        <button type="button" class="uc-key s" data-q="contrat">${esc(ucT(h, 'q_contrat'))}</button>
        <button type="button" class="uc-key s" data-q="puissance">${esc(ucT(h, 'q_puissance'))}</button></div>
        ${rep ? `<div class="msg">${rep}</div>` : ''}</div>`;
  }

  async _simuler(question) {
    const c = this._config;
    const sim = c.simulateur || {};
    this._simu = { charge: true };
    this._render();
    try {
      const data = { question, jours: sim.jours || 30 };
      if (sim.puissance_actuelle_kva) data.puissance_actuelle_kva = sim.puissance_actuelle_kva;
      if (sim.abonnement_actuel_eur_an != null) data.abonnement_actuel_eur_an = sim.abonnement_actuel_eur_an;
      const rep = await this._hass.connection.sendMessagePromise({ type: 'call_service', domain: 'ucaness', service: 'simuler', service_data: data, return_response: true });
      this._simu = { r: rep && rep.response };
    } catch (err) {
      this._simu = { erreur: (err && err.message) || ucT(this._hass, 'erreur_inconnue') };
    }
    this._render();
  }

  _boutons(root) {
    const c = this._config;
    root.querySelectorAll('button[data-q]').forEach((b) => b.addEventListener('click', () => this._simuler(b.dataset.q)));
    root.querySelectorAll('button[data-r]').forEach((b) => b.addEventListener('click', () => {
      const [dom, svc] = String(c.script).split('.');
      if (this._hass && dom && svc) this._hass.callService(dom, svc, { reponse: b.dataset.r });
    }));
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const c = this._config;
    const { conseil, soc, alertes, humeur } = this._etat();
    const cssBulle = `
        p { margin: 0; }
        .k { font-size: 13px; letter-spacing: .1em; text-transform: uppercase; color: var(--uc-label); }
        .t { font: 400 16px/1.45 var(--uc-font); }
        .g { color: var(--uc-green); }
        .n { font-size: 13px; color: var(--uc-muted); }
        .btns { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
        button[data-r] { min-height: 44px; padding: 0 16px; border-radius: 22px; cursor: pointer; font: 400 16px var(--uc-font); }
        .p { border: 0; background: var(--uc-tab); color: #031428; }
        .s { border: 1px solid var(--uc-tab-border); background: linear-gradient(180deg, rgba(26,111,190,.35) 0%, rgba(10,37,70,.6) 100%); color: var(--uc-text); }
        .q { border: 1px solid var(--uc-tab-border); background: transparent; color: #9CC9F5; }`;
    if (c.floating) {
      this.shadowRoot.innerHTML = '<style>:host { display: none; }</style>';
      if (!this._flot || this._enGlisse) return;
      const pos = this._position();
      const bas = pos.bas;
      const droite = pos.droite;
      const ouvrirDessous = bas > (window.innerHeight || 800) / 2;
      const attente = !!conseil || alertes.length > 0;
      const label = esc(conseil ? ucT(this._hass, 'ucan_conseil_attend') : alertes.length ? ucT(this._hass, 'ucan_alerte') : 'Ucan');
      const r = this._flot.shadowRoot;
      r.innerHTML = `
        <style>${UC_BASE_CSS}
          :host { position: fixed; right: ${droite}px; bottom: ${bas}px; z-index: 9; display: flex; flex-direction: ${ouvrirDessous ? 'column-reverse' : 'column'}; align-items: flex-end; gap: 12px; }
          .fab { position: relative; touch-action: none; width: 64px; height: 64px; padding: 0; border-radius: 50%; border: 2px solid ${humeur === 'alerte' ? '#F39C12' : '#00D1D6'}; background: radial-gradient(circle at 50% 40%, #0D2A58 0%, #061B3D 70%); cursor: pointer; box-shadow: 0 6px 18px rgba(0,0,0,.5), 0 0 14px rgba(0,209,214,.35); }
          .fab svg { position: absolute; left: 6px; top: 7px; width: 50px; height: 50px; }
          .pastille { position: absolute; top: -2px; right: -2px; width: 16px; height: 16px; border-radius: 50%; background: ${humeur === 'alerte' ? '#F39C12' : '#2ECC71'}; border: 2px solid #061B3D; }
          @keyframes ucan-appel { 0%, 100% { box-shadow: 0 6px 18px rgba(0,0,0,.5), 0 0 0 0 rgba(0,209,214,.55); } 50% { box-shadow: 0 6px 18px rgba(0,0,0,.5), 0 0 0 10px rgba(0,209,214,0); } }
          .fab.appel { animation: ucan-appel 2.4s ease-in-out infinite; }
          .fab.glisse { cursor: grabbing; }
          .panneau { width: min(360px, calc(100vw - 32px)); max-height: calc(100vh - ${ouvrirDessous ? (window.innerHeight || 800) - bas + 30 : bas + 110}px); overflow: auto; box-sizing: border-box; border: 1px solid var(--uc-panel-border); border-radius: 14px; background: var(--uc-panel-bg); box-shadow: 0 10px 30px rgba(0,0,0,.55); }
          .tete { display: flex; align-items: center; gap: 10px; padding: 8px 8px 8px 14px; background: var(--uc-title-bg); border-bottom: 2px solid var(--uc-tab); border-radius: 14px 14px 0 0; }
          .tete .av { width: 30px; height: 41px; }
          .tete .av svg { width: 100%; height: 100%; display: block; }
          .tete h2 { margin: 0; font: 400 19px var(--uc-font); flex: 1; }
          .replacer { min-height: 36px; padding: 0 10px; border: 1px solid var(--uc-tab-border); border-radius: 18px; background: transparent; color: #9CC9F5; font: 400 14px var(--uc-font); cursor: pointer; }
          .fermer { width: 44px; height: 44px; border: 0; background: transparent; color: var(--uc-text); cursor: pointer; border-radius: 22px; }
          .etsi { margin: 0 14px 14px; display: flex; flex-direction: column; gap: 8px; }
          .etsi .msg { margin: 4px 0 0; }
          .etsi ul { margin: 0; padding-left: 18px; }
          .msg { margin: 14px; padding: 14px 16px; border: 1px solid var(--uc-card-border); border-radius: 4px 14px 14px 14px; background: var(--uc-card-bg); display: flex; flex-direction: column; gap: 8px; }
          ${cssBulle}
        </style>
        ${this._ouvert ? `<section class="panneau" role="dialog" aria-label="Ucan">
          <div class="tete"><div class="av">${ucUcanSvg(humeur, soc)}</div><h2>Ucan</h2>
            ${this._deplace ? `<button type="button" class="replacer">${esc(ucT(this._hass, 'replacer'))}</button>` : ''}
            <button type="button" class="fermer" aria-label="${esc(ucT(this._hass, 'fermer'))}"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
          <div class="msg">${this._corps(conseil, alertes)}</div>${this._etsiHtml()}</section>` : ''}
        <button type="button" class="fab uc-tap${attente && !this._ouvert && !UC_REDUCED && !UC_LIGHT ? ' appel' : ''}" aria-label="${label}" aria-expanded="${this._ouvert ? 'true' : 'false'}">
          ${ucUcanSvg(humeur, soc).replace('viewBox="0 0 220 300"', 'viewBox="30 4 160 118"')}${attente && !this._ouvert ? '<span class="pastille" aria-hidden="true"></span>' : ''}
        </button>`;
      this._glisser(r.querySelector('.fab'));
      const rp = r.querySelector('.replacer');
      if (rp) rp.addEventListener('click', () => {
        this._deplace = null;
        try { window.localStorage.removeItem(UC_UCAN_POS); } catch (e) { /* stockage indisponible */ }
        this._render();
      });
      const f = r.querySelector('.fermer');
      if (f) f.addEventListener('click', () => { this._ouvert = false; this._render(); });
      this._boutons(r);
      return;
    }
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        .w { display: flex; flex-wrap: wrap; gap: 12px 16px; align-items: flex-start; }
        .av { flex: 0 0 auto; width: ${c.compact ? 64 : 150}px; height: ${c.compact ? 87 : 204}px; }
        .av svg { width: 100%; height: 100%; display: block; }
        .b { flex: 1 1 230px; min-width: 0; padding: 14px 18px; border: 1px solid var(--uc-card-border); border-radius: 4px 14px 14px 14px; background: var(--uc-card-bg); box-shadow: var(--uc-card-shadow); display: flex; flex-direction: column; gap: 8px; }
        ${cssBulle}
        .t { font-size: ${c.compact ? 16 : 17}px; }
      </style>
      <div class="w"><div class="av">${ucUcanSvg(humeur, soc)}</div><div class="b">${this._corps(conseil, alertes)}</div></div>`;
    this._boutons(this.shadowRoot);
  }
}

/* ------------------------------------------------------------------ enregistrement */

const UC_CARDS = [
  ['ucaness-layout-card', UcanessLayoutCard, ucT(null, 'carte_layout_nom'), ucT(null, 'carte_layout_desc')],
  ['ucaness-header-card', UcanessHeaderCard, ucT(null, 'carte_header_nom'), ucT(null, 'carte_header_desc')],
  ['ucaness-panel-card', UcanessPanelCard, ucT(null, 'carte_panel_nom'), ucT(null, 'carte_panel_desc')],
  ['ucaness-flow-card', UcanessFlowCard, ucT(null, 'carte_flow_nom'), ucT(null, 'carte_flow_desc')],
  ['ucaness-note-card', UcanessNoteCard, ucT(null, 'carte_note_nom'), ucT(null, 'carte_note_desc')],
  ['ucaness-soc-card', UcanessSocCard, ucT(null, 'carte_soc_nom'), ucT(null, 'carte_soc_desc')],
  ['ucaness-app-card', UcanessAppCard, ucT(null, 'carte_app_nom'), ucT(null, 'carte_app_desc')],
  ['ucaness-status-card', UcanessStatusCard, ucT(null, 'carte_status_nom'), ucT(null, 'carte_status_desc')],
  ['ucaness-stats-card', UcanessStatsCard, ucT(null, 'carte_stats_nom'), ucT(null, 'carte_stats_desc')],
  ['ucaness-info-card', UcanessInfoCard, ucT(null, 'carte_info_nom'), ucT(null, 'carte_info_desc')],
  ['ucaness-shortcuts-card', UcanessShortcutsCard, ucT(null, 'carte_shortcuts_nom'), ucT(null, 'carte_shortcuts_desc')],
  ['ucaness-detail-card', UcanessDetailCard, ucT(null, 'carte_detail_nom'), ucT(null, 'carte_detail_desc')],
  ['ucaness-ucan-card', UcanessUcanCard, ucT(null, 'carte_ucan_nom'), ucT(null, 'carte_ucan_desc')],
  ['ucaness-hours-card', UcanessHoursCard, ucT(null, 'carte_hours_nom'), ucT(null, 'carte_hours_desc')],
];

for (const [tag, cls, name, description] of UC_CARDS) {
  if (!customElements.get(tag)) customElements.define(tag, cls);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === tag)) {
    window.customCards.push({ type: tag, name, description, preview: false });
  }
}

console.info(`%c UCANESS HOME ASSISTANT %c ${UC_VERSION} `, 'background:#0B4F8F;color:#fff;font-weight:700', 'background:#00D1D6;color:#06203F');

export { UcanessFlowCard, UcanessNoteCard, UcanessPanelCard, UcanessLayoutCard, UcanessHeaderCard, UcanessSocCard, UcanessAppCard, UcanessStatusCard, UcanessStatsCard, UcanessInfoCard, UcanessShortcutsCard, UcanessDetailCard, UcanessHoursCard, UcanessUcanCard, ucUcanSvg, ucMiniMarkdown, ucWatts, ucNum, ucChanged, ucFormat, UC_LIGHT, UC_VERSION };
