"""Assistant de configuration : identifiants UCANESS + ID EMS de l'appareil."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import UcanessApiError, UcanessAuthError, UcanessClient, UcanessError, hash_password
from .reglages import CONF_REGLAGES
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
            # Les réglages du pilotage (reglages.py) vivent aussi dans les options : on les garde.
            if CONF_REGLAGES in options:
                data[CONF_REGLAGES] = options[CONF_REGLAGES]
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
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
