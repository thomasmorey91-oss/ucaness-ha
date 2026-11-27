"""Constantes de l'intégration UCANESS (non officielle)."""
DOMAIN = "ucaness"
# hass.data[DATA_WRITE_LOG][ID EMS] : horodatages des écritures de l'heure écoulée, gardés hors de
# l'entrée de configuration pour que le plafond d'écritures survive à son rechargement.
DATA_WRITE_LOG = f"{DOMAIN}_write_log"

CONF_DEVICE_CODE = "device_code"      # « ID EMS » affiché dans le portail (ex. abcd1234ef)
CONF_PASSWORD_MD5 = "password_md5"    # seule l'empreinte du mot de passe est stockée
CONF_DEV_SN = "dev_sn"
CONF_SCAN_INTERVAL = "scan_interval"

# Options de l'API tierce UCanpower (pilotage).
CONF_APP_KEY = "app_key"
CONF_APP_SECRET = "app_secret"
CONF_WRITE_ENABLED = "write_enabled"   # interrupteur général de l'écriture, éteint par défaut

DEFAULT_SCAN_INTERVAL = 60   # secondes ; le portail web interroge toutes les 10 s
MIN_SCAN_INTERVAL = 30
CONFIG_REFRESH_S = 1800      # réglages onduleur relus toutes les 30 min
EVENTS_REFRESH_S = 300       # journal d'événements relu toutes les 5 min
STALE_AFTER_S = 900          # données jugées figées au-delà de 15 min

# Relecture après une écriture : l'onduleur doit avoir appliqué la consigne.
READBACK_DELAY_S = 5
READBACK_ATTEMPTS = 4
MODE_READBACK_ATTEMPTS = 12  # le mode se confirme aussi par l'état remonté par l'onduleur (≈ 1 min)

BATTERY_CHARGE_TEMP_MIN = 0.0    # °C, manuel UHome V1.9 : charge entre 0 et 50 °C
BATTERY_CHARGE_TEMP_MAX = 50.0

# Identifiants proposés à la création des entités : ceux que lisent les packages de pilotage et le
# tableau de bord du dépôt, pour qu'il n'y ait rien à renommer. Home Assistant ne les applique
# qu'à une entité nouvelle (une entité déjà enregistrée garde son identifiant) et ajoute un
# suffixe s'ils sont pris (deuxième onduleur).
OBJECT_IDS = {
    # capteurs (clé de parser.MEASURES)
    "soc": "uhome_soc",
    "soh": "uhome_sante_batterie",
    "battery_temp": "uhome_temperature_batterie",
    "battery_power": "uhome_puissance_batterie",
    "battery_voltage": "uhome_tension_batterie",
    "battery_current": "uhome_courant_batterie",
    "load_power": "uhome_puissance_maison",
    "grid_power": "uhome_puissance_reseau",
    "solar_power": "uhome_puissance_solaire",
    "solar_voltage": "uhome_tension_solaire",
    "pv1_power": "uhome_puissance_mppt_1",
    "pv2_power": "uhome_puissance_mppt_2",
    "grid_voltage": "uhome_tension_reseau",
    "grid_frequency": "uhome_frequence_reseau",
    "inverter_temp": "uhome_temperature_onduleur",
    "work_mode": "uhome_mode",
    "work_state": "uhome_etat",
    "battery_fault_code": "uhome_code_defaut_batterie",
    "battery_alarm_code": "uhome_code_alarme_batterie",
    "energy_solar_today": "uhome_production_solaire_aujourdhui",
    "energy_solar_total": "uhome_production_solaire_totale",
    "energy_grid_import_total": "uhome_soutirage_reseau_total",
    "energy_grid_export_total": "uhome_injection_reseau_totale",
    "energy_battery_charge_total": "uhome_charge_batterie_totale",
    "energy_battery_discharge_total": "uhome_decharge_batterie_totale",
    # contrôles (clé de binary_sensor.CHECKS)
    "cloud_connection": "uhome_connexion_cloud",
    "battery_fault": "uhome_defaut_batterie",
    "battery_temp_out_of_charge_range": "uhome_temperature_hors_plage",
}
# Entités sans lesquelles le pilotage de nuit ne peut pas décider (pilotage/README.md).
ENTITES_PILOTAGE = (
    "sensor.uhome_soc",
    "sensor.uhome_temperature_batterie",
    "sensor.uhome_puissance_batterie",
    "sensor.uhome_puissance_maison",
    "sensor.uhome_puissance_reseau",
    "sensor.uhome_mode",
    "sensor.uhome_soutirage_reseau_total",
    "binary_sensor.uhome_connexion_cloud",
    "binary_sensor.uhome_defaut_batterie",
    "binary_sensor.uhome_temperature_hors_plage",
)
