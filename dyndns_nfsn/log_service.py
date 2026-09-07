import glob
import logging
import os
from datetime import datetime
from typing import Optional

from .config import get_time_zone

INFO_PLUS = 25
logging.addLevelName(INFO_PLUS, "INFO+")


def info_plus(self, message, *args, **kwargs):
    if self.isEnabledFor(INFO_PLUS):
        self._log(INFO_PLUS, message, args, **kwargs)


logging.Logger.info_plus = info_plus

LOG_DIR = "/logs"
LOG_FILENAME = "dyndns_nfsn.log"
LOG_PATH = os.path.join(LOG_DIR, LOG_FILENAME)


class TimestampFormatter(logging.Formatter):
    def __init__(self, fmt: str | None = None, datefmt: str | None = None, style: str = "%", tz_name: str | None = None):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)
        self.timezone = get_time_zone(tz_name)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=self.timezone)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)


def get_log_path() -> str:
    ensure_log_dir()
    if not os.path.exists(LOG_PATH):
        open(LOG_PATH, "a", encoding="utf-8").close()
    return LOG_PATH


def _log_is_from_previous_day(path: str, tz_name: str | None = None) -> bool:
    if not os.path.exists(path):
        return False

    tz = get_time_zone(tz_name)
    modified = datetime.fromtimestamp(os.path.getmtime(path), tz=tz).date()
    return modified < datetime.now(tz=tz).date()


def _rotate_log_files(path: str) -> None:
    oldest = f"{path}.7"
    if os.path.exists(oldest):
        os.remove(oldest)

    for index in range(6, 0, -1):
        source = f"{path}.{index}"
        target = f"{path}.{index + 1}"
        if os.path.exists(source):
            os.rename(source, target)

    os.rename(path, f"{path}.1")


def configure_logging(settings: dict) -> logging.Logger:
    ensure_log_dir()
    if _log_is_from_previous_day(LOG_PATH, settings.get("TIME_ZONE")):
        _rotate_log_files(LOG_PATH)

    level_name = str(settings.get("LOG_LEVEL", "INFO")).upper()
    if level_name == "INFO+":
        level = INFO_PLUS
    else:
        level = logging.getLevelName(level_name)
        if not isinstance(level, int):
            level = logging.INFO

    logger = logging.getLogger("ddns")
    logger.setLevel(level)
    logger.propagate = False

    formatter = TimestampFormatter("%(asctime)s %(levelname)s %(message)s", tz_name=settings.get("TIME_ZONE"))

    # Clear existing handlers to avoid duplicate logs on reconfigure
    logger.handlers.clear()

    file_handler = logging.FileHandler(get_log_path(), encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def read_log() -> str:
    path = get_log_path()
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as log_file:
            return log_file.read()
    except OSError:
        return ""


def rotate_log() -> None:
    path = get_log_path()
    if not os.path.exists(path):
        ensure_log_dir()
        open(path, "a", encoding="utf-8").close()
        return

    _rotate_log_files(path)
    open(path, "a", encoding="utf-8").close()
