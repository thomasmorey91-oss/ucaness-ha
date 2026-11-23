"""Client de l'API UCANESS (UCanpower UHome).

Deux familles d'appels :

1. Lecture par les chemins du portail web oss.ucaness.com (non documentés) :
   mesures temps réel, réglages, journal. Inchangé depuis la version 0.1.0.
2. API tierce documentée par UCanpower (« App与业务平台接口-第三方 », chemins /api/v1/…),
   signée par une clé d'application (app_key + app_secret, HMAC-SHA256) en plus du jeton.
   Elle sert à la lecture des réglages et à l'ÉCRITURE LIMITÉE du pilotage.

Garde-fous :
- seuls les chemins des listes ci-dessous peuvent être appelés ; tout autre chemin est
  refusé avant d'atteindre le réseau (retour usine, commandes, configuration EMS…) ;
- l'écriture ne peut porter que sur le mode de fonctionnement (autoconsommation ou
  arbitrage horaire, jamais Backup) et sur les 6 plages horaires de l'arbitrage ;
  aucun réglage de fond (DOD, hystérésis, courant, protections réseau, type de batterie…) ;
- les valeurs sont contrôlées avant l'envoi, et le nombre d'écritures est limité.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from collections import deque
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://app.ucaness.com"
DEFAULT_TIMEOUT = 30

OK_CODES = {2000, "2000"}
# Codes renvoyés par le portail quand la session a expiré.
SESSION_EXPIRED_CODES = {4018, 4031, "4018", "4031"}
# Code renvoyé par /user/signin quand l'identifiant ou le mot de passe est refusé.
BAD_CREDENTIALS_CODES = {5032, "5032"}

# --------------------------------------------------------------------------- chemins
# Lectures par les chemins du portail web (jeton seul).
READ_ONLY_PATHS = frozenset(
    {
        "/user/signin",          # connexion (obtention du jeton)
        "/device/detail/load",   # mesures temps réel, compteurs d'énergie, infos batterie et onduleur
        "/device/config",        # réglages de l'onduleur (lecture)
        "/device/status",        # état résumé
        "/oss/event/info",       # journal des événements / alarmes
        "/report/usage2",        # bilan énergétique sur une période
    }
)
# Lectures par l'API tierce signée.
SIGNED_READ_PATHS = frozenset(
    {
        "/api/v1/device/list",
        "/api/v1/device/config",
        "/api/v1/device/status",
    }
)
# Seule écriture autorisée : réglages de l'onduleur, réduits à la liste blanche ci-dessous.
SETTINGS_UPDATE_PATH = "/api/v1/device/settings/update"
SIGNED_PATHS = SIGNED_READ_PATHS | {SETTINGS_UPDATE_PATH}

# --------------------------------------------------------------------------- réglages
# Identifiants des réglages UHome (tableau « uhome » de la documentation, § 6.18).
SET_WORK_MODE = 1
# (début, fin) des plages de charge et de décharge du mode arbitrage horaire.
CHARGE_WINDOWS = ((44, 45), (48, 49), (52, 53))
DISCHARGE_WINDOWS = ((46, 47), (50, 51), (54, 55))
WINDOW_SET_IDS = frozenset(i for pair in CHARGE_WINDOWS + DISCHARGE_WINDOWS for i in pair)
ALLOWED_SET_IDS = frozenset({SET_WORK_MODE}) | WINDOW_SET_IDS

# Modes autorisés : 0 autoconsommation, 1 arbitrage horaire. Le mode 2 (« Bat Priority »,
# Backup du manuel) n'est pas utilisé par le pilotage et reste refusé.
WORK_MODES = {"autoconsommation": 0, "arbitrage_horaire": 1}

# Clé du réglage dans la réponse de /api/v1/device/config (data.pcs.<modèle>), pour la relecture.
CONFIG_KEYS: dict[int, tuple[str, ...]] = {SET_WORK_MODE: ("work_mode",)}
for _n, (_s, _e) in enumerate(CHARGE_WINDOWS, start=1):
    CONFIG_KEYS[_s] = (f"charge_time{_n}_start",)
    CONFIG_KEYS[_e] = (f"charge_time{_n}_end",)
for _n, (_s, _e) in enumerate(DISCHARGE_WINDOWS, start=1):
    # La documentation écrit « discharge_timeN_star » (sic) : on accepte les deux orthographes.
    CONFIG_KEYS[_s] = (f"discharge_time{_n}_star", f"discharge_time{_n}_start")
    CONFIG_KEYS[_e] = (f"discharge_time{_n}_end",)

# Modèles dont la table des réglages (set_id) est confirmée pour le mode et les plages.
# - « uhome » : documentation UCanpower (§ 6.18).
# - « mr » (déclaré par un UHome 6K, absent de la documentation) : confirmé le 18/11/2026 par
#   l'enregistrement fait depuis le portail UCANESS (set_id 1, set_data 0, inverter_model « mr »)
#   et par la table du formulaire du portail : mode 1 ; charges 44/45, 48/49, 52/53 ;
#   décharges 46/47, 50/51, 54/55 ; heures envoyées en nombre HHMM (01:00 -> 100).
#   Les autres réglages de ce modèle sont stockés à l'échelle ×10 : ils restent hors liste blanche.
WRITE_MODELS: frozenset[str] = frozenset({"uhome", "mr"})

# Limites d'écriture « de bon sens » : un plan de nuit coûte 3 à 6 envois.
MIN_WRITE_INTERVAL_S = 2.0
MAX_WRITES_PER_HOUR = 20
MAX_ITEMS_PER_WRITE = 2          # une plage (début, fin) par envoi
DEVICE_TIMEOUT_CODES = {"5019"}  # « Device operation timeout »
# Un 5019 n'est pas toujours un échec : une plage envoyée a reçu un 5019 alors que l'onduleur
# l'avait bien enregistrée (relue quelques minutes plus tard). Après un 5019, la configuration
# est relue pendant TIMEOUT_CONFIRM_ATTEMPTS × TIMEOUT_CONFIRM_DELAY_S (2 min) avant de conclure.
TIMEOUT_CONFIRM_ATTEMPTS = 6
TIMEOUT_CONFIRM_DELAY_S = 20.0


class UcanessError(Exception):
    """Erreur générique du client UCANESS."""


class UcanessAuthError(UcanessError):
    """Identifiants refusés ou jeton impossible à obtenir."""


class UcanessApiError(UcanessError):
    """Réponse inattendue du serveur."""

    def __init__(self, code: Any, message: str | None = None) -> None:
        super().__init__(f"Erreur API UCANESS {code} : {message or ''}".strip())
        self.code = code


class UcanessWriteRefused(UcanessError):
    """Écriture refusée par le garde-fou local (rien n'a été envoyé)."""


def hash_password(password: str) -> str:
    """Empreinte MD5 (hexadécimale) attendue par /user/signin, comme le fait le portail web."""
    return hashlib.md5(password.encode("utf-8")).hexdigest()  # noqa: S324 - imposé par l'API


def sign(path: str, app_key: str, timestamp: str, app_secret: str) -> str:
    """Signature de l'API tierce (§ 3.3) : HMAC-SHA256 de « url=<chemin>&app_key=<clé>&timestamp=<t> »."""
    message = f"url={path}&app_key={app_key}&timestamp={timestamp}"
    return hmac.new(app_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def hhmm(value: Any) -> int:
    """Convertit « 2300 », « 23:00 » ou 2300 en entier HHMM, en vérifiant l'heure."""
    text = str(value).strip().replace(":", "")
    if not text.isdigit() or len(text) > 4:
        raise UcanessWriteRefused(f"Heure invalide : {value!r}")
    number = int(text)
    if number > 2359 or number % 100 > 59:
        raise UcanessWriteRefused(f"Heure invalide : {value!r}")
    return number


def validate_settings(items: dict[int, int]) -> list[dict[str, int]]:
    """Contrôle la liste blanche et les valeurs ; renvoie le corps « pcs » à envoyer."""
    if not items:
        raise UcanessWriteRefused("Aucun réglage à envoyer")
    pcs: list[dict[str, int]] = []
    for set_id, value in sorted(items.items()):
        if set_id not in ALLOWED_SET_IDS:
            raise UcanessWriteRefused(f"Réglage {set_id} hors de la liste autorisée")
        if set_id == SET_WORK_MODE:
            if value not in WORK_MODES.values():
                raise UcanessWriteRefused(f"Mode {value} non autorisé")
        else:
            value = hhmm(value)
        pcs.append({"set_id": int(set_id), "set_data": int(value)})
    return pcs


def windows_to_settings(charge: list[tuple[Any, Any]]) -> dict[int, int]:
    """3 plages de charge au plus ; les plages non fournies et toutes les décharges sont vidées (0000)."""
    if len(charge) > len(CHARGE_WINDOWS):
        raise UcanessWriteRefused("Trois plages de charge au plus")
    items: dict[int, int] = {}
    for index, (start_id, end_id) in enumerate(CHARGE_WINDOWS):
        start, end = charge[index] if index < len(charge) else (0, 0)
        items[start_id] = hhmm(start)
        items[end_id] = hhmm(end)
    for start_id, end_id in DISCHARGE_WINDOWS:
        # Une plage de décharge renverrait la batterie sur le réseau (énergie revendue à bas prix).
        items[start_id] = 0
        items[end_id] = 0
    return items


def model_write_confirmed(model: str | None) -> bool:
    return (model or "").strip().lower() in WRITE_MODELS


def read_back(settings: dict[str, Any], set_id: int) -> Any:
    for key in CONFIG_KEYS.get(set_id, ()):
        if key in settings:
            return settings[key]
    return None


def read_back_value(settings: dict[str, Any], set_id: int) -> int | None:
    """Valeur relue, comme la lit le portail : un réglage absent vaut 0.

    La configuration du cloud omet les valeurs nulles (mode autoconsommation, plages vides).
    """
    value = read_back(settings, set_id)
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def pcs_settings(config: dict[str, Any], model: str | None = None) -> dict[str, Any]:
    """Réglages de l'onduleur dans une réponse de configuration : data.pcs.<modèle>."""
    pcs = (config or {}).get("pcs") or {}
    model = model or (config or {}).get("inverter_model")
    if model and isinstance(pcs.get(model), dict):
        return pcs[model]
    return next((v for v in pcs.values() if isinstance(v, dict)), {})


class UcanessClient:
    """Client asynchrone : lecture, et écriture limitée par l'API tierce signée."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password_md5: str,
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        app_key: str | None = None,
        app_secret: str | None = None,
        write_log: deque[float] | None = None,
    ) -> None:
        """write_log : horodatages (time.monotonic) des écritures envoyées, pour le plafond horaire.

        Home Assistant passe une file gardée hors du client (hass.data) : le plafond de
        MAX_WRITES_PER_HOUR survit ainsi au rechargement de l'intégration (changement d'options).
        Sans file fournie, le client garde la sienne (sonde, tests).
        """
        self._session = session
        self._email = email
        self._password_md5 = password_md5
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._token: str | None = None
        self._login_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._app_key = (app_key or "").strip()
        self._app_secret = (app_secret or "").strip()
        self._writes: deque[float] = write_log if write_log is not None else deque()
        self._device_v1: tuple[str, str | None] | None = None

    @property
    def has_token(self) -> bool:
        return self._token is not None

    @property
    def has_app_key(self) -> bool:
        return bool(self._app_key and self._app_secret)

    async def login(self) -> None:
        """Ouvre une session et mémorise le jeton (jamais journalisé)."""
        async with self._login_lock:
            body = await self._request(
                "/user/signin",
                {"sign": self._email, "password": self._password_md5},
                auth=False,
            )
            code = body.get("error_code")
            token = body.get("token")
            if code in BAD_CREDENTIALS_CODES or not token:
                raise UcanessAuthError(body.get("msg") or "Connexion refusée par UCANESS")
            self._token = token

    # ---------------------------------------------------------- lectures (portail)

    async def get_detail(self, device_code: str, tz: int = 3600) -> dict[str, Any]:
        """Mesures temps réel et compteurs d'énergie (identique au tableau de bord du portail)."""
        return await self._call("/device/detail/load", {"code": device_code, "tz": tz})

    async def get_config(self, device_code: str) -> dict[str, Any]:
        """Réglages de l'onduleur : DOD, hystérésis, courant de charge, plages horaires…"""
        return await self._call("/device/config", {"device_id": device_code})

    async def get_status(self, device_code: str) -> dict[str, Any]:
        return await self._call("/device/status", {"device_id": device_code})

    async def get_events(self, device_code: str, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        """Journal des événements (alarmes, défauts) de l'appareil."""
        return await self._call(
            "/oss/event/info",
            {
                "page": page,
                "pageSize": page_size,
                "device_id": device_code,
                "start_time": "",
                "end_time": "",
                "key_word": "",
            },
        )

    async def get_usage(self, device_code: str, dev_sn: str, start_ts: int, end_ts: int) -> dict[str, Any]:
        """Bilan énergétique (Wh) entre deux horodatages Unix."""
        return await self._call(
            "/report/usage2",
            {
                "device_id": device_code,
                "dev_sn": dev_sn,
                "start_time": start_ts,
                "end_time": end_ts,
                "date_type": "",
            },
        )

    # ---------------------------------------------------------- API tierce signée

    async def list_devices_v1(self) -> list[dict[str, Any]]:
        body = await self._signed_call("/api/v1/device/list", {})
        items = body.get("list")
        if items is None and isinstance(body.get("data"), dict):
            items = body["data"].get("list")
        return [i for i in (items or []) if isinstance(i, dict)]

    async def resolve_device_v1(self, device_code: str) -> tuple[str, str | None]:
        """Identifiant d'appareil attendu par l'API tierce (« MA-… » ou « MA_… ») et modèle d'onduleur."""
        if self._device_v1 is not None:
            return self._device_v1
        wanted = device_code.strip().lower()
        for item in await self.list_devices_v1():
            device_id = str(item.get("device_id") or "")
            short = device_id[3:] if device_id[:3].upper() in ("MA-", "MA_") else device_id
            if wanted in (device_id.lower(), short.lower()):
                self._device_v1 = (device_id, item.get("inverter_model"))
                return self._device_v1
        raise UcanessApiError("device_not_found", f"Appareil {device_code} absent de /api/v1/device/list")

    async def get_config_v1(self, device_code: str) -> dict[str, Any]:
        device_id, _ = await self.resolve_device_v1(device_code)
        body = await self._signed_call("/api/v1/device/config", {"device_id": device_id})
        data = body.get("data")
        return data if isinstance(data, dict) else {}

    async def update_settings(self, device_code: str, items: dict[int, int]) -> list[dict[str, int]]:
        """Envoie des réglages de la liste blanche. Renvoie les réglages réellement envoyés.

        Comme le portail : seuls les réglages qui diffèrent de la configuration actuelle sont
        envoyés, par paquets de MAX_ITEMS_PER_WRITE. L'onduleur répond « 5019 Device operation
        timeout » à un envoi de 12 réglages d'un coup, et parfois à un envoi pourtant appliqué :
        en cas de 5019, la configuration est relue avant de conclure, puis les réglages qui ne
        sont pas en place sont renvoyés un par un.
        """
        pcs = validate_settings(items)
        async with self._write_lock:
            device_id, model = await self.resolve_device_v1(device_code)
            config = await self.get_config_v1(device_code)
            model = model or config.get("inverter_model")
            if not model_write_confirmed(model):
                raise UcanessWriteRefused(
                    f"Modèle d'onduleur « {model} » : table des réglages non confirmée, écriture bloquée"
                )
            current = pcs_settings(config, model)
            todo = [i for i in pcs if read_back_value(current, i["set_id"]) != i["set_data"]]
            if not todo:
                _LOGGER.info("UCANESS : réglages %s déjà en place, rien à envoyer", pcs)
                return []
            for start in range(0, len(todo), MAX_ITEMS_PER_WRITE):
                chunk = todo[start:start + MAX_ITEMS_PER_WRITE]
                await self._send_chunk(device_code, device_id, model, chunk)
        return todo

    async def _send_chunk(
        self, device_code: str, device_id: str, model: str, chunk: list[dict[str, int]]
    ) -> None:
        """Envoie un paquet. Sur 5019 : relit avant de conclure, puis renvoie un par un ce qui manque."""
        try:
            await self._post_settings(device_id, model, chunk)
            return
        except UcanessApiError as err:
            if str(err.code) not in DEVICE_TIMEOUT_CODES:
                raise
            pending = await self._pending_after_timeout(device_code, model, chunk)
            if not pending:
                return
            if len(chunk) == 1:
                raise
        _LOGGER.warning("UCANESS : %s non appliqué après le délai dépassé, envoi réglage par réglage", pending)
        for item in pending:
            try:
                await self._post_settings(device_id, model, [item])
            except UcanessApiError as err:
                if str(err.code) not in DEVICE_TIMEOUT_CODES:
                    raise
                if await self._pending_after_timeout(device_code, model, [item]):
                    raise

    async def _pending_after_timeout(
        self, device_code: str, model: str, chunk: list[dict[str, int]]
    ) -> list[dict[str, int]]:
        """Après un 5019 : relit la configuration jusqu'à TIMEOUT_CONFIRM_ATTEMPTS fois.

        Renvoie les réglages du paquet qui ne sont toujours pas en place (liste vide : appliqués).
        """
        _LOGGER.warning("UCANESS : délai dépassé (5019) pour %s, vérification par relecture", chunk)
        pending = list(chunk)
        for attempt in range(TIMEOUT_CONFIRM_ATTEMPTS):
            await asyncio.sleep(TIMEOUT_CONFIRM_DELAY_S)
            try:
                current = pcs_settings(await self.get_config_v1(device_code), model)
            except UcanessError as err:
                _LOGGER.debug("Relecture après 5019 impossible (essai %s) : %s", attempt + 1, err)
                continue
            pending = [i for i in chunk if read_back_value(current, i["set_id"]) != i["set_data"]]
            if not pending:
                _LOGGER.warning("UCANESS : malgré le 5019, l'onduleur a bien enregistré %s", chunk)
                return []
        return pending

    async def _post_settings(self, device_id: str, model: str, chunk: list[dict[str, int]]) -> None:
        await self._wait_write_slot()
        payload = {"device_id": device_id, "inverter_model": model, "pcs": chunk}
        _LOGGER.info("UCANESS : envoi des réglages %s (modèle %s)", chunk, model)
        self._writes.append(time.monotonic())
        await self._signed_call(SETTINGS_UPDATE_PATH, payload)

    async def _wait_write_slot(self) -> None:
        now = time.monotonic()
        while self._writes and now - self._writes[0] > 3600:
            self._writes.popleft()
        if len(self._writes) >= MAX_WRITES_PER_HOUR:
            raise UcanessWriteRefused(f"Plus de {MAX_WRITES_PER_HOUR} écritures en une heure : envoi bloqué")
        if self._writes and now - self._writes[-1] < MIN_WRITE_INTERVAL_S:
            await asyncio.sleep(MIN_WRITE_INTERVAL_S - (now - self._writes[-1]))

    # ------------------------------------------------------------------ interne

    async def _call(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Appel authentifié. Reconnexion automatique (une fois) si la session a expiré."""
        if self._token is None:
            await self.login()
        body = await self._request(path, payload, auth=True)
        if body.get("error_code") in SESSION_EXPIRED_CODES:
            _LOGGER.debug("Session UCANESS expirée, reconnexion")
            self._token = None
            await self.login()
            body = await self._request(path, payload, auth=True)
        if body.get("error_code") not in OK_CODES:
            raise UcanessApiError(body.get("error_code"), body.get("msg"))
        data = body.get("data")
        return data if isinstance(data, dict) else {"value": data}

    async def _signed_call(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Appel de l'API tierce : jeton + signature. Renvoie le corps complet."""
        if not self.has_app_key:
            raise UcanessWriteRefused("Clé d'application UCanpower absente (options de l'intégration)")
        if self._token is None:
            await self.login()
        body = await self._request(path, payload, auth=True, signed=True)
        if body.get("error_code") in SESSION_EXPIRED_CODES:
            self._token = None
            await self.login()
            body = await self._request(path, payload, auth=True, signed=True)
        if body.get("error_code") not in OK_CODES:
            raise UcanessApiError(body.get("error_code"), body.get("msg"))
        return body

    async def _request(
        self, path: str, payload: dict[str, Any], auth: bool, signed: bool = False
    ) -> dict[str, Any]:
        allowed = SIGNED_PATHS if signed else READ_ONLY_PATHS
        if path not in allowed:
            raise ValueError(f"Chemin refusé : {path}")
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self._token}"
        if signed:
            timestamp = str(int(time.time()))
            headers["app_key"] = self._app_key
            headers["timestamp"] = timestamp
            headers["signature"] = sign(path, self._app_key, timestamp, self._app_secret)
        try:
            async with self._session.post(
                f"{self._base_url}{path}", json=payload, headers=headers, timeout=self._timeout
            ) as resp:
                if resp.status >= 400:
                    raise UcanessApiError(resp.status, f"HTTP {resp.status} sur {path}")
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UcanessError(f"UCANESS injoignable ({path}) : {err}") from err
        if not isinstance(body, dict):
            raise UcanessApiError("format", f"Réponse inattendue sur {path}")
        return body
