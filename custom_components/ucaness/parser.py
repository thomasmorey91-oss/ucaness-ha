"""Transformation des réponses UCANESS en valeurs exploitables (unités SI, échelles corrigées).

Module sans dépendance à Home Assistant, pour pouvoir être testé seul.

Échelles relevées sur le portail (novembre 2026) :
- tensions et courants : ×0,1 (2364 -> 236,4 V)
- fréquence : ×0,01 (5003 -> 50,03 Hz)
- SOC, SOH, températures, pourcentages de réglage : ×0,1 (410 -> 41,0 %)
- tensions de cellule : millivolts (3340 -> 3,340 V)
- compteurs d'énergie : Wh (7706 -> 7,706 kWh)
- puissances : W
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Measure:
    key: str
    name: str                      # libellé affiché (français)
    getter: Callable[[dict], Any]  # extrait la valeur brute depuis le paquet de données
    scale: float | None = None     # facteur multiplicatif ; None = valeur laissée telle quelle
    unit: str | None = None
    device_class: str | None = None  # power, energy, voltage, current, frequency, temperature, battery, timestamp
    state_class: str | None = None   # measurement, total_increasing
    precision: int | None = None
    diagnostic: bool = False


def _get(*path: Any) -> Callable[[dict], Any]:
    def getter(data: dict) -> Any:
        cur: Any = data
        for p in path:
            if isinstance(p, int):
                if not isinstance(cur, list) or len(cur) <= p:
                    return None
                cur = cur[p]
            else:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(p)
            if cur is None:
                return None
        return cur

    return getter


def _pcs_settings(data: dict) -> dict:
    """Réglages de l'onduleur : data['config']['pcs'][<modèle>]."""
    pcs = (data.get("config") or {}).get("pcs") or {}
    model = (data.get("config") or {}).get("inverter_model")
    if model and isinstance(pcs.get(model), dict):
        return pcs[model]
    return next((v for v in pcs.values() if isinstance(v, dict)), {})


def _setting(name: str) -> Callable[[dict], Any]:
    return lambda data: _pcs_settings(data).get(name)


def _hhmm(name: str) -> Callable[[dict], Any]:
    """Horaire codé HHMM en entier (100 -> 01:00)."""
    def getter(data: dict) -> Any:
        raw = _pcs_settings(data).get(name)
        if raw is None:
            return None
        raw = int(raw)
        return f"{raw // 100:02d}:{raw % 100:02d}"
    return getter


def _grid_power(data: dict) -> Any:
    """Puissance réseau estimée = maison + batterie (charge > 0) − solaire. Positive = soutirage.

    La nuit, le portail n'envoie plus de puissance solaire : elle compte alors pour 0
    (constat du 19/11/2026 : estimation « inconnue » toute la nuit).
    """
    st = _get("detail", "status")(data) or {}
    try:
        return float(st["load_power"]) + float(st["battery_power"]) - float(st.get("solar_power") or 0)
    except (KeyError, TypeError, ValueError):
        return None


def _solar_or_zero(*path: Any) -> Callable[[dict], Any]:
    """Puissance solaire : 0 quand l'onduleur répond mais n'envoie pas de valeur (la nuit)."""
    def getter(data: dict) -> Any:
        parent = _get(*path[:-1])(data)
        if not isinstance(parent, dict):
            return None
        value = parent.get(path[-1])
        return 0 if value is None else value
    return getter


def _data_age(data: dict) -> Any:
    ts = _get("detail", "status", "timestamp")(data)
    if ts is None:
        return None
    return max(0, int(data.get("now", time.time()) - int(ts)))


S = ("detail", "status")
B0 = ("detail", "pcs_info", "battery", 0)
BS = ("detail", "pcs_info", "battery_sum")
INV = ("detail", "pcs_info", "inv")
PV = ("detail", "pcs_info", "pv")

MEASURES: tuple[Measure, ...] = (
    # --- Puissances instantanées
    Measure("solar_power", "Puissance solaire", _solar_or_zero(*S, "solar_power"), None, "W", "power", "measurement", 0),
    Measure("pv1_power", "Puissance MPPT 1", _get(*PV, "PV1_power"), None, "W", "power", "measurement", 0),
    Measure("pv2_power", "Puissance MPPT 2", _get(*PV, "PV2_power"), None, "W", "power", "measurement", 0),
    Measure("battery_power", "Puissance batterie (charge > 0)", _get(*S, "battery_power"), None, "W", "power", "measurement", 0),
    Measure("load_power", "Puissance maison", _get(*S, "load_power"), None, "W", "power", "measurement", 0),
    Measure("grid_power", "Puissance réseau estimée (soutirage > 0)", _grid_power, None, "W", "power", "measurement", 0),
    Measure("inverter_power", "Puissance onduleur", _get(*S, "inv_power"), None, "W", "power", "measurement", 0, True),
    # --- Batterie
    Measure("soc", "Charge batterie (SOC)", _get(*S, "soc"), 0.1, "%", "battery", "measurement", 1),
    Measure("soh", "Santé batterie (SOH)", _get(*B0, "soh"), 0.1, "%", None, "measurement", 1),
    Measure("battery_voltage", "Tension batterie", _get(*S, "battery_volt"), 0.1, "V", "voltage", "measurement", 1),
    Measure("battery_current", "Courant batterie", _get(*S, "battery_current"), 0.1, "A", "current", "measurement", 1),
    Measure("battery_temp", "Température batterie", _get(*INV, "bat_temp"), 0.1, "°C", "temperature", "measurement", 1),
    Measure("cell_temp_max", "Température cellule max", _get(*B0, "max_cell_temp"), 0.1, "°C", "temperature", "measurement", 1),
    Measure("cell_temp_min", "Température cellule min", _get(*B0, "min_cell_temp"), 0.1, "°C", "temperature", "measurement", 1),
    Measure("cell_voltage_max", "Tension cellule max", _get(*B0, "max_cell_voltage"), 0.001, "V", "voltage", "measurement", 3, True),
    Measure("cell_voltage_min", "Tension cellule min", _get(*B0, "min_cell_voltage"), 0.001, "V", "voltage", "measurement", 3, True),
    Measure("battery_modules", "Nombre de modules batterie", _get(*B0, "cell_modnum"), None, None, None, None, 0, True),
    Measure("battery_alarm_code", "Code alarme batterie", _get(*BS, "alarm_code"), None, None, None, None, 0, True),
    Measure("battery_fault_code", "Code défaut batterie", _get(*BS, "fault_code"), None, None, None, None, 0, True),
    Measure("battery_pack_alarm_raw", "Code alarme pack (brut, à interpréter)", _get(*B0, "alarm_code"), None, None, None, None, 0, True),
    # --- Onduleur et réseau
    Measure("grid_voltage", "Tension réseau", _get(*S, "grid_volt"), 0.1, "V", "voltage", "measurement", 1),
    Measure("grid_frequency", "Fréquence réseau", _get(*S, "grid_hz"), 0.01, "Hz", "frequency", "measurement", 2),
    Measure("solar_voltage", "Tension solaire", _get(*S, "solar_volt"), 0.1, "V", "voltage", "measurement", 1, True),
    Measure("inverter_temp", "Température onduleur", _get(*INV, "inv_temp"), 0.1, "°C", "temperature", "measurement", 1),
    Measure("ambient_temp", "Température ambiante onduleur", _get(*INV, "env_temp"), 0.1, "°C", "temperature", "measurement", 1),
    Measure("pv_module_temp", "Température étage PV", _get(*INV, "pv_temp"), 0.1, "°C", "temperature", "measurement", 1, True),
    Measure("leakage_current_raw", "Courant de fuite (brut)", _get(*INV, "other_inv", "gfci_curr"), None, None, None, "measurement", 0, True),
    Measure("work_mode", "Mode de fonctionnement", _get(*S, "work_mode_str")),
    Measure("work_state", "État de fonctionnement", _get(*S, "work_state_str")),
    Measure("last_update", "Dernière mesure reçue", _get(*S, "timestamp"), None, None, "timestamp", None, None, True),
    Measure("data_age", "Âge des données", _data_age, None, "s", None, "measurement", 0, True),
    # --- Compteurs d'énergie (Wh -> kWh)
    Measure("energy_solar_today", "Production solaire aujourd'hui", _get(*S, "usage_solar_today"), 0.001, "kWh", "energy", "total_increasing", 2),
    Measure("energy_solar_total", "Production solaire totale", _get(*S, "usage_solar_total"), 0.001, "kWh", "energy", "total_increasing", 1),
    Measure("energy_grid_import_today", "Soutirage réseau aujourd'hui", _get(*S, "usage_grid_today"), 0.001, "kWh", "energy", "total_increasing", 2),
    Measure("energy_grid_import_total", "Soutirage réseau total", _get(*S, "usage_grid_total"), 0.001, "kWh", "energy", "total_increasing", 1),
    Measure("energy_grid_export_today", "Injection réseau aujourd'hui", _get(*S, "usage_grid_dsgcharge_today"), 0.001, "kWh", "energy", "total_increasing", 2),
    Measure("energy_grid_export_total", "Injection réseau totale", _get(*S, "usage_grid_dsgcharge_total"), 0.001, "kWh", "energy", "total_increasing", 1),
    Measure("energy_load_today", "Consommation maison aujourd'hui", _get(*S, "usage_load_today"), 0.001, "kWh", "energy", "total_increasing", 2),
    Measure("energy_load_total", "Consommation maison totale", _get(*S, "usage_load_total"), 0.001, "kWh", "energy", "total_increasing", 1),
    Measure("energy_battery_charge_today", "Charge batterie aujourd'hui", _get(*S, "usage_batt_charge_today"), 0.001, "kWh", "energy", "total_increasing", 2),
    Measure("energy_battery_charge_total", "Charge batterie totale", _get(*S, "usage_batt_charge_total"), 0.001, "kWh", "energy", "total_increasing", 1),
    Measure("energy_battery_discharge_today", "Décharge batterie aujourd'hui", _get(*S, "usage_batt_discharge_today"), 0.001, "kWh", "energy", "total_increasing", 2),
    Measure("energy_battery_discharge_total", "Décharge batterie totale", _get(*S, "usage_batt_discharge_total"), 0.001, "kWh", "energy", "total_increasing", 1),
    # --- Réglages de l'onduleur (lecture seule)
    Measure("setting_dod", "Réglage DOD raccordé au réseau", _setting("bat_grid_dod"), 0.1, "%", None, None, 0, True),
    Measure("setting_hysteresis", "Réglage hystérésis", _setting("battery_return_difference"), 0.1, "%", None, None, 0, True),
    Measure("setting_charge_current", "Réglage courant de charge", _setting("bat_charge_current"), 0.1, "A", "current", None, 0, True),
    Measure("setting_discharge_power", "Réglage puissance de décharge", _setting("bat_discharge_power"), 0.1, "%", None, None, 0, True),
    Measure("setting_export_power", "Réglage puissance d'export", _setting("grid_power"), 0.1, "%", None, None, 0, True),
    Measure("setting_charge1_start", "Plage de charge 1 : début", _hhmm("charge_time1_start"), None, None, None, None, None, True),
    Measure("setting_charge1_end", "Plage de charge 1 : fin", _hhmm("charge_time1_end"), None, None, None, None, None, True),
    # --- Journal d'événements
    Measure("event_count", "Événements enregistrés", _get("events", "total_count"), None, None, None, "measurement", 0),
)


def extract(data: dict[str, Any]) -> dict[str, Any]:
    """Renvoie {clé: valeur convertie} pour toutes les mesures disponibles."""
    values: dict[str, Any] = {}
    for m in MEASURES:
        raw = m.getter(data)
        if raw is None:
            values[m.key] = None
            continue
        if m.scale is not None:
            try:
                raw = round(float(raw) * m.scale, 6)
            except (TypeError, ValueError):
                raw = None
        values[m.key] = raw
    return values


def is_online(data: dict[str, Any]) -> bool | None:
    return _get("detail", "is_online")(data)


def last_event(data: dict[str, Any]) -> dict[str, Any] | None:
    items = _get("events", "list")(data) or []
    return items[0] if items else None
