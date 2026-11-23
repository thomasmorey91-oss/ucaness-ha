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
