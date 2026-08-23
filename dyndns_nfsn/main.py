import logging
import os
import threading
import time

from .config import get_settings_path, load_settings
from .dns import check_and_update
from .log_service import configure_logging
from .web import create_app

HEARTBEAT_FILE = "/tmp/healthy"


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

    while True:
        try:
            settings = load_settings()
            log = configure_logging(settings)
            check_and_update(settings)
        except Exception:
            log.exception("DDNS check failed")

        with open(HEARTBEAT_FILE, "w", encoding="utf-8") as heartbeat_file:
            heartbeat_file.write(str(time.time()))

        time.sleep(int(settings.get("CHECK_INTERVAL", 300)))


if __name__ == "__main__":
    main()
