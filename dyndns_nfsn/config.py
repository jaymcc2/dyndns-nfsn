import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones


def get_default_time_zone() -> str:
    try:
        local_tz = datetime.now().astimezone().tzinfo
        return getattr(local_tz, "key", None) or "UTC"
    except Exception:
        return "UTC"


def get_time_zone(name: str | None = None) -> ZoneInfo:
    try:
        return ZoneInfo(name or get_default_time_zone())
    except Exception:
        return ZoneInfo("UTC")


def get_time_zones() -> list[str]:
    try:
        return sorted(available_timezones())
    except Exception:
        return ["UTC"]


TIMESTAMP_ISO_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def format_timestamp(time_zone: str | None = None, fmt: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    return datetime.now(tz=get_time_zone(time_zone)).strftime(fmt)


def current_timestamp(time_zone: str | None = None) -> str:
    return datetime.now(tz=get_time_zone(time_zone)).strftime(TIMESTAMP_ISO_FORMAT)


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


DEFAULT_SETTINGS = {
    "ENABLE": False,
    "NFSN_DOMAINS": "",
    "NFSN_LOGIN": "",
    "NFSN_API_KEY": "",
    "CHECK_INTERVAL": 300,
    "LOG_LEVEL": "INFO",
    "TIME_ZONE": get_default_time_zone(),
    "LAST_RUN": None,
    "LAST_RESULT": "never",
    "LAST_MESSAGE": "No DDNS checks have run yet.",
    "LAST_PUBLIC_IP": None,
    "LAST_PUBLIC_IP_UPDATED": None,
    "HOST_STATUSES": {},
}

EDITABLE_SETTINGS = [
    "ENABLE",
    "NFSN_DOMAINS",
    "NFSN_LOGIN",
    "NFSN_API_KEY",
    "CHECK_INTERVAL",
    "LOG_LEVEL",
    "TIME_ZONE",
]


def get_settings_path(config_path: str | None = None) -> str:
    return config_path or os.getenv("SETTINGS_PATH", "/config/settings.json")


def get_flask_secret_key(config_path: str | None = None) -> str:
    env_secret = os.getenv("FLASK_SECRET_KEY")
    if env_secret:
        return env_secret

    settings_path = Path(get_settings_path(config_path))
    secret_file = settings_path.with_name(".flask_secret_key")

    if secret_file.exists():
        try:
            return secret_file.read_text(encoding="utf-8").strip()
        except OSError:
            pass

    secret = secrets.token_hex(32)
    try:
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_text(secret, encoding="utf-8")
    except OSError:
        return secret

    return secret


def load_settings(config_path: str | None = None) -> dict:
    settings_path = Path(get_settings_path(config_path))
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if not settings_path.exists():
        save_settings(DEFAULT_SETTINGS.copy(), str(settings_path))

    try:
        with settings_path.open("r", encoding="utf-8") as settings_file:
            loaded = json.load(settings_file)
    except json.JSONDecodeError:
        loaded = {}

    merged = DEFAULT_SETTINGS.copy()
    merged.update({key: value for key, value in loaded.items() if key in DEFAULT_SETTINGS})

    try:
        merged["CHECK_INTERVAL"] = int(merged["CHECK_INTERVAL"])
    except (TypeError, ValueError):
        merged["CHECK_INTERVAL"] = DEFAULT_SETTINGS["CHECK_INTERVAL"]

    merged["ENABLE"] = str(merged.get("ENABLE", DEFAULT_SETTINGS["ENABLE"]))
    merged["ENABLE"] = str(merged["ENABLE"]).lower() in {"1", "true", "yes", "on"}

    if not str(merged.get("LOG_LEVEL", "")).strip():
        merged["LOG_LEVEL"] = DEFAULT_SETTINGS["LOG_LEVEL"]

    if not str(merged.get("TIME_ZONE", "")).strip():
        merged["TIME_ZONE"] = DEFAULT_SETTINGS["TIME_ZONE"]
    elif str(merged.get("TIME_ZONE", "")).strip() not in get_time_zones():
        merged["TIME_ZONE"] = DEFAULT_SETTINGS["TIME_ZONE"]

    save_settings(merged, str(settings_path))
    return merged


def save_settings(settings: dict, config_path: str | None = None) -> None:
    config_file = Path(get_settings_path(config_path))
    config_file.parent.mkdir(parents=True, exist_ok=True)

    sanitized = DEFAULT_SETTINGS.copy()
    for key, value in settings.items():
        if key in DEFAULT_SETTINGS:
            sanitized[key] = value

    try:
        sanitized["CHECK_INTERVAL"] = int(sanitized.get("CHECK_INTERVAL", DEFAULT_SETTINGS["CHECK_INTERVAL"]))
    except (TypeError, ValueError):
        sanitized["CHECK_INTERVAL"] = DEFAULT_SETTINGS["CHECK_INTERVAL"]

    sanitized["ENABLE"] = str(sanitized.get("ENABLE", DEFAULT_SETTINGS["ENABLE"]))
    sanitized["ENABLE"] = str(sanitized["ENABLE"]).lower() in {"1", "true", "yes", "on"}

    if not str(sanitized.get("LOG_LEVEL", "")).strip():
        sanitized["LOG_LEVEL"] = DEFAULT_SETTINGS["LOG_LEVEL"]

    if not str(sanitized.get("TIME_ZONE", "")).strip():
        sanitized["TIME_ZONE"] = DEFAULT_SETTINGS["TIME_ZONE"]
    elif str(sanitized.get("TIME_ZONE", "")).strip() not in get_time_zones():
        sanitized["TIME_ZONE"] = DEFAULT_SETTINGS["TIME_ZONE"]

    with config_file.open("w", encoding="utf-8") as settings_file:
        json.dump(sanitized, settings_file, indent=2, sort_keys=True)
        settings_file.write("\n")
