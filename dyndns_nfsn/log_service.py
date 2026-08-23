import glob
import logging
import os
from datetime import datetime
from typing import Optional

from .config import get_time_zone

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


def configure_logging(settings: dict) -> logging.Logger:
    ensure_log_dir()
    level_name = str(settings.get("LOG_LEVEL", "INFO")).upper()
    level = logging.getLevelName(level_name)
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

    existing = glob.glob(f"{path}.*")
    max_index = 0
    for candidate in existing:
        suffix = candidate[len(path) + 1 :]
        if suffix.isdigit():
            max_index = max(max_index, int(suffix))
    next_index = max_index + 1
    os.rename(path, f"{path}.{next_index}")
    open(path, "a", encoding="utf-8").close()
