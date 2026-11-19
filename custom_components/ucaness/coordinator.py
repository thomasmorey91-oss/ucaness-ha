"""Coordinateur de mise à jour : un seul appel groupé par cycle (lecture seulement)."""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import parser
from .api import UcanessApiError, UcanessAuthError, UcanessClient, UcanessError
from .const import CONFIG_REFRESH_S, EVENTS_REFRESH_S

_LOGGER = logging.getLogger(__name__)


class UcanessCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, client: UcanessClient, device_code: str, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"UCANESS {device_code}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.device_code = device_code
        self._config: dict[str, Any] = {}
        self._config_at = 0.0
        self._events: dict[str, Any] = {}
        self._events_at = 0.0

    def invalidate_config(self) -> None:
        """Force la relecture des réglages au prochain cycle (après une écriture)."""
        self._config_at = 0.0

    async def _async_update_data(self) -> dict[str, Any]:
        now = time.time()
        try:
            detail = await self.client.get_detail(self.device_code)
            if not self._config or now - self._config_at > CONFIG_REFRESH_S:
                try:
                    self._config = await self.client.get_config(self.device_code)
                    self._config_at = now
                except UcanessApiError as err:
                    _LOGGER.debug("Réglages onduleur indisponibles : %s", err)
            if now - self._events_at > EVENTS_REFRESH_S:
                try:
                    self._events = await self.client.get_events(self.device_code)
                    self._events_at = now
                except UcanessApiError as err:
                    _LOGGER.debug("Journal d'événements indisponible : %s", err)
        except UcanessAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except UcanessError as err:
            raise UpdateFailed(str(err)) from err

        raw = {"detail": detail, "config": self._config, "events": self._events, "now": now}
        return {
            "raw": raw,
            "values": parser.extract(raw),
            "online": parser.is_online(raw),
            "last_event": parser.last_event(raw),
        }
