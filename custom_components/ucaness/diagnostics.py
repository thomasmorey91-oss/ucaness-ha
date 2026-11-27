"""Diagnostics téléchargeables (Paramètres → Appareils et services → UCANESS → Télécharger les diagnostics).

Le fichier peut être joint à un ticket public : tout ce qui permet de se connecter au compte
ou d'identifier l'installation est masqué.
- secrets : e-mail, empreinte MD5 du mot de passe, clé et secret d'application, jeton de session ;
- identifiants : ID EMS, identifiant d'appareil de l'API tierce, numéros de série, nom de l'installation ;
- lieu, si le portail en renvoie un.
Le jeton de session du client n'est jamais lu ici : seule sa présence est indiquée.
"""
from __future__ import annotations

import copy
from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .cle_application import cle_effective
from .const import CONF_APP_KEY, CONF_APP_SECRET, CONF_DEV_SN, CONF_DEVICE_CODE, CONF_PASSWORD_MD5, CONF_WRITE_ENABLED
from .coordinator import UcanessConfigEntry

# Clés masquées à tous les niveaux (données de l'entrée et réponses du portail).
TO_REDACT = {
    # secrets
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PASSWORD_MD5,
    CONF_APP_KEY,
    CONF_APP_SECRET,
    "token",
    "reglages",          # réglages du pilotage : prix du contrat, capacité
    "signature",
    "sign",
    # identifiants de l'installation
    CONF_DEVICE_CODE,
    CONF_DEV_SN,
    "device_id",
    "sn",
    "device_name",
    "unique_id",
    "title",
    # lieu
    "address",
    "latitude",
    "longitude",
    "lat",
    "lng",
    "lon",
}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: UcanessConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    client = coordinator.client
    data = coordinator.data or {}

    raw = copy.deepcopy(data.get("raw") or {})
    # « code » désigne l'ID EMS dans device_info, mais un code d'alarme ailleurs : masqué ici seulement.
    info = (raw.get("detail") or {}).get("device_info")
    if isinstance(info, dict) and "code" in info:
        info["code"] = REDACTED

    return {
        "entree": async_redact_data({"data": dict(entry.data), "options": dict(entry.options)}, TO_REDACT),
        "client": {
            "session_ouverte": client.has_token,
            "cle_application_presente": client.has_app_key,
            # Origine de la clé (« personnelle » ou « livree »), jamais la clé elle-même.
            "origine_cle_application": cle_effective(entry.options)[2],
            "ecriture_autorisee": bool(entry.options.get(CONF_WRITE_ENABLED, False)),
        },
        "coordinateur": {
            "derniere_mise_a_jour_reussie": coordinator.last_update_success,
            "intervalle_s": coordinator.update_interval.total_seconds() if coordinator.update_interval else None,
        },
        "donnees": async_redact_data(
            {
                "en_ligne": data.get("online"),
                "valeurs": data.get("values"),
                "dernier_evenement": data.get("last_event"),
                "brut": raw,
            },
            TO_REDACT,
        ),
    }
