import logging
import os
import time

import requests


IPIFY_URL = "https://api.ipify.org"
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)

log = logging.getLogger("ddns")


def get_public_ip() -> str:
    """Return our public IPv4 address from ipify."""

    response = requests.get(
        IPIFY_URL,
        timeout=10,
    )

    response.raise_for_status()

    ip = response.text.strip()

    if not ip:
        raise RuntimeError("ipify returned an empty response")

    log.debug("ipify returned %s", ip)

    return ip


def get_dns_ip() -> str | None:
    """Return the current NFSN A record."""

    # TODO: NFSN API
    raise NotImplementedError


def update_dns(ip: str) -> None:
    """Update the NFSN A record."""

    # TODO: NFSN API
    raise NotImplementedError


def check_and_update() -> None:
    public_ip = get_public_ip()
    dns_ip = get_dns_ip()

    log.info("Public IP: %s", public_ip)
    log.info("DNS IP:    %s", dns_ip)

    if public_ip == dns_ip:
        log.info("DNS record is current")
        return

    log.info(
        "DNS record needs updating: %s -> %s",
        dns_ip,
        public_ip,
    )

    update_dns(public_ip)


def main() -> None:
    log.info("DDNS service starting")
    log.info("Check interval: %s seconds", CHECK_INTERVAL)

    while True:
        try:
            check_and_update()

        except Exception:
            log.exception("DDNS check failed")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()