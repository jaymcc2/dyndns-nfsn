import logging
import os
import threading
import time
from datetime import datetime, timedelta

from .config import get_settings_path, get_time_zone, load_settings, normalize_forced_dns_check_time
from .dns import check_and_update
from .log_service import configure_logging
from .web import create_app

HEARTBEAT_FILE = "/tmp/healthy"


def next_forced_check_time(now: datetime, force_time: str) -> datetime:
    hours, minutes = [int(part) for part in force_time.split(":", 1)]
    candidate = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def main(run_web: bool = True) -> None:
    settings = load_settings()
    log = configure_logging(settings)

    log.info("DDNS service starting")
    log.info("Check interval: %s seconds", settings.get("CHECK_INTERVAL", 300))

    if run_web:
        app = create_app(get_settings_path())
        web_thread = threading.Thread(
            target=app.run,
            kwargs={
                "host": "0.0.0.0",
                "port": int(os.getenv("WEB_PORT", "8080")),
                "use_reloader": False,
            },
            daemon=True,
        )
        web_thread.start()

    settings = load_settings()
    tz = get_time_zone(settings.get("TIME_ZONE"))
    now = datetime.now(tz=tz)
    check_interval = int(settings.get("CHECK_INTERVAL", 300))
    force_time = normalize_forced_dns_check_time(settings.get("FORCED_DNS_CHECK_TIME"))
    next_check = now + timedelta(seconds=check_interval)
    next_forced_check = next_forced_check_time(now, force_time)

    while True:
        now = datetime.now(tz=tz)
        sleep_until = min(next_check, next_forced_check)
        wait_seconds = max(0, (sleep_until - now).total_seconds())
        time.sleep(wait_seconds)

        now = datetime.now(tz=tz)
        settings = load_settings()
        tz = get_time_zone(settings.get("TIME_ZONE"))
        check_interval = int(settings.get("CHECK_INTERVAL", 300))
        force_time = normalize_forced_dns_check_time(settings.get("FORCED_DNS_CHECK_TIME"))

        try:
            log = configure_logging(settings)
            force_remote_dns = now >= next_forced_check
            check_and_update(settings, force_remote_dns=force_remote_dns)
            next_check = now + timedelta(seconds=check_interval)
            next_forced_check = next_forced_check_time(now, force_time)
            if next_check >= next_forced_check:
                next_check = next_forced_check
        except Exception:
            log.exception("DDNS check failed")

        with open(HEARTBEAT_FILE, "w", encoding="utf-8") as heartbeat_file:
            heartbeat_file.write(str(time.time()))


if __name__ == "__main__":
    main()
