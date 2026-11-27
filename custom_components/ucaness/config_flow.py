"""Assistant de configuration : identifiants UCANESS + ID EMS de l'appareil."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    ColorRGBSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import UcanessApiError, UcanessAuthError, UcanessClient, UcanessError, hash_password
from . import vehicules
from .reglages import CONF_REGLAGES
from .vehicule_ha import CONF_VEHICULE, DEFAUTS as DEFAUTS_VEHICULE, couleur_hex, couleur_rgb
from .const import (
    CONF_APP_KEY,
    CONF_APP_SECRET,
    CONF_DEV_SN,
    CONF_DEVICE_CODE,
    CONF_PASSWORD_MD5,
    CONF_SCAN_INTERVAL,
    CONF_WRITE_ENABLED,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)


async def _validate(hass: HomeAssistant, email: str, password_md5: str, device_code: str) -> dict[str, Any]:
    client = UcanessClient(async_get_clientsession(hass), email, password_md5)
    await client.login()
    detail = await client.get_detail(device_code)
    info = detail.get("device_info") or {}
    return {"name": info.get("device_name") or f"UHome {device_code}", "dev_sn": info.get("dev_sn")}


class UcanessConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            code = user_input[CONF_DEVICE_CODE].strip()
            password_md5 = hash_password(user_input[CONF_PASSWORD])
            try:
                info = await _validate(self.hass, email, password_md5, code)
            except UcanessAuthError:
                errors["base"] = "invalid_auth"
            except UcanessApiError:
                errors["base"] = "device_not_found"
            except UcanessError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(code)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["name"],
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD_MD5: password_md5,
                        CONF_DEVICE_CODE: code,
                        CONF_DEV_SN: info["dev_sn"],
                    },
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_DEVICE_CODE): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors: dict[str, str] = {}
        if user_input is not None and entry is not None:
            password_md5 = hash_password(user_input[CONF_PASSWORD])
            try:
                await _validate(self.hass, entry.data[CONF_EMAIL], password_md5, entry.data[CONF_DEVICE_CODE])
            except UcanessAuthError:
                errors["base"] = "invalid_auth"
            except UcanessError:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_PASSWORD_MD5: password_md5})
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return UcanessOptionsFlow()


class UcanessOptionsFlow(config_entries.OptionsFlow):
    """Options : fréquence d'interrogation, clé d'application UCanpower, écriture autorisée."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        options = self.config_entry.options
        if user_input is not None:
            data = {
                CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                CONF_APP_KEY: (user_input.get(CONF_APP_KEY) or "").strip(),
                # Champ laissé vide : on garde le secret déjà enregistré.
                CONF_APP_SECRET: (user_input.get(CONF_APP_SECRET) or "").strip() or options.get(CONF_APP_SECRET, ""),
                CONF_WRITE_ENABLED: bool(user_input.get(CONF_WRITE_ENABLED, False)),
            }
            # Les réglages du pilotage (reglages.py) et le véhicule vivent aussi dans les options : on les garde.
            for cle in (CONF_REGLAGES, CONF_VEHICULE):
                if cle in options:
                    data[cle] = options[cle]
            if user_input.get("configurer_vehicule"):
                self._data = data
                return await self.async_step_vehicule_marque()
            return self.async_create_entry(title="", data=data)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)),
                vol.Optional(CONF_APP_KEY, default=options.get(CONF_APP_KEY, "")): str,
                vol.Optional(CONF_APP_SECRET, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_WRITE_ENABLED, default=options.get(CONF_WRITE_ENABLED, False)): bool,
                vol.Optional("configurer_vehicule", default=False): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    # ---------------------------------------------------------------- votre véhicule

    async def _catalogue(self) -> tuple[vehicules.Vehicule, ...]:
        return await self.hass.async_add_executor_job(vehicules.charger_catalogue)

    async def async_step_vehicule_marque(self, user_input: dict[str, Any] | None = None):
        """Marque du véhicule (catalogue OpenEV Data), « hors catalogue » ou retrait du véhicule."""
        if user_input is not None:
            choix = user_input["marque"]
            if choix == "retirer":
                self._data.pop(CONF_VEHICULE, None)
                return self.async_create_entry(title="", data=self._data)
            if choix == "autre":
                self._modele = None
                return await self.async_step_vehicule_details()
            self._marque = choix
            return await self.async_step_vehicule_modele()
        cat = await self._catalogue()
        actuel = self._data.get(CONF_VEHICULE) or {}
        options = [{"value": m, "label": m} for m in vehicules.marques(cat)]
        options.append({"value": "autre", "label": "—"})
        if actuel:
            options.append({"value": "retirer", "label": "×"})
        schema = vol.Schema({vol.Required("marque", default=actuel.get("marque") or vol.UNDEFINED): SelectSelector(
            SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN, translation_key="marque_vehicule")
        )})
        return self.async_show_form(step_id="vehicule_marque", data_schema=schema)

    async def async_step_vehicule_modele(self, user_input: dict[str, Any] | None = None):
        cat = await self._catalogue()
        if user_input is not None:
            self._modele = vehicules.par_id(cat, user_input["modele"])
            return await self.async_step_vehicule_details()
        liste = vehicules.de_la_marque(cat, self._marque)
        actuel = (self._data.get(CONF_VEHICULE) or {}).get("id")
        schema = vol.Schema({vol.Required("modele", default=actuel if any(v.id == actuel for v in liste) else vol.UNDEFINED): SelectSelector(
            SelectSelectorConfig(options=[{"value": v.id, "label": f"{v.modele} {v.version} ({v.annee}) · {v.capacite_kwh:g} kWh".replace("  ", " ")} for v in liste],
                                 mode=SelectSelectorMode.DROPDOWN)
        )})
        return self.async_show_form(step_id="vehicule_modele", data_schema=schema,
                                    description_placeholders={"marque": self._marque})

    async def async_step_vehicule_details(self, user_input: dict[str, Any] | None = None):
        """Valeurs proposées par le catalogue, à confirmer ou corriger (la fiche peut se tromper)."""
        actuel = self._data.get(CONF_VEHICULE) or {}
        v = self._modele
        if user_input is not None:
            cfg = {
                "id": v.id if v else None,
                "marque": v.marque if v else None,
                "modele": v.modele if v else None,
                "nom": (user_input.get("nom") or "").strip() or (v.libelle if v else "Véhicule"),
                "gabarit": user_input["gabarit"],
                "couleur": couleur_hex(user_input.get("couleur")),
                "capacite_kwh": float(user_input["capacite_kwh"]),
                "ac_kw": float(user_input["ac_kw"]),
                "phases": int(user_input["phases"]),
                "conso_kwh_100km": float(user_input["conso_kwh_100km"]),
                "soc_cible": float(user_input["soc_cible"]),
                "puissance_borne_kw": float(user_input["puissance_borne_kw"]),
                "entite_soc": user_input.get("entite_soc") or None,
                "image": actuel.get("image", ""),     # photo détourée gardée si le véhicule change
            }
            return self.async_create_entry(title="", data={**self._data, CONF_VEHICULE: cfg})
        meme = actuel if (not v or actuel.get("id") == v.id) else {}
        def defaut(cle, cat):
            return meme.get(cle) if meme.get(cle) is not None else cat
        nombre = lambda mini, maxi, pas, unite: NumberSelector(NumberSelectorConfig(min=mini, max=maxi, step=pas, unit_of_measurement=unite, mode=NumberSelectorMode.BOX))
        schema = vol.Schema({
            vol.Optional("nom", default=defaut("nom", v.libelle if v else "")): str,
            vol.Required("gabarit", default=defaut("gabarit", v.gabarit if v else "citadine")): SelectSelector(
                SelectSelectorConfig(options=list(vehicules.GABARITS), translation_key="gabarit")),
            vol.Required("couleur", default=couleur_rgb(actuel.get("couleur") or DEFAUTS_VEHICULE["couleur"])): ColorRGBSelector(),
            vol.Required("capacite_kwh", default=defaut("capacite_kwh", v.capacite_kwh if v else 50.0)): nombre(5, 250, 0.1, "kWh"),
            vol.Required("ac_kw", default=defaut("ac_kw", v.ac_kw if v else 7.4)): nombre(1, 43, 0.1, "kW"),
            vol.Required("phases", default=str(defaut("phases", v.phases if v else 1))): SelectSelector(
                SelectSelectorConfig(options=["1", "3"], translation_key="phases")),
            vol.Required("conso_kwh_100km", default=defaut("conso_kwh_100km", (v.conso_kwh_100km if v else None) or 17.0)): nombre(5, 60, 0.1, "kWh/100 km"),
            vol.Required("soc_cible", default=actuel.get("soc_cible", DEFAUTS_VEHICULE["soc_cible"])): nombre(20, 100, 5, "%"),
            vol.Required("puissance_borne_kw", default=actuel.get("puissance_borne_kw", DEFAUTS_VEHICULE["puissance_borne_kw"])): nombre(1.4, 22, 0.1, "kW"),
            vol.Optional("entite_soc", description={"suggested_value": actuel.get("entite_soc")}): EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="battery")),
        })
        return self.async_show_form(step_id="vehicule_details", data_schema=schema,
                                    description_placeholders={"vehicule": v.libelle if v else "—"})
