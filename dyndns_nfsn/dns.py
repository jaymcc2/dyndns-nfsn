import logging
import time

import requests
from nfsn_cli import Nfsn, NfsnTransport
from nfsn_cli.config import Credentials
from nfsn_cli.resources import Record

from .config import format_timestamp, load_settings, save_settings

log = logging.getLogger("ddns")
IPIFY_URL = "https://api.ipify.org"


def parse_domains(settings: dict) -> list[str]:
    raw = str(settings.get("NFSN_DOMAINS", "") or "").strip()
    if not raw:
        raw = str(settings.get("NFSN_HOSTNAMES", "") or "").strip()

    lines = []
    for part in raw.replace(",", "\n").splitlines():
        domain = part.strip().rstrip('.')
        if domain:
            lines.append(domain)
    return lines


def get_dns_ip(settings: dict | None = None, domain: str | None = None) -> str | None:
    settings = settings or load_settings()
    domain = str(domain or "").strip().rstrip('.')
    login = str(settings.get("NFSN_LOGIN", "") or "").strip()
    api_key = str(settings.get("NFSN_API_KEY", "") or "").strip()

    if not domain:
        raise RuntimeError("A domain is required to query DNS records")

    if not login or not api_key:
        raise RuntimeError("NFSN_LOGIN or NFSN_API_KEY is not set in the config file")

    credentials = Credentials(login=login, api_key=api_key)
    with NfsnTransport(credentials) as transport:
        nfsn = Nfsn(transport)
        for record in nfsn.dns(domain).list_rrs():
            if record.type == "A" and record.name in {"", "@"}:
                return record.data
    return None


def update_dns(ip: str, settings: dict | None = None, domain: str | None = None) -> None:
    settings = settings or load_settings()
    domain = str(domain or "").strip().rstrip('.')
    login = str(settings.get("NFSN_LOGIN", "") or "").strip()
    api_key = str(settings.get("NFSN_API_KEY", "") or "").strip()

    if not domain:
        raise RuntimeError("A domain is required to update DNS records")

    if not login or not api_key:
        raise RuntimeError("NFSN_LOGIN or NFSN_API_KEY is not set in the config file")

    credentials = Credentials(login=login, api_key=api_key)
    record = Record(name="@", type="A", data=ip, ttl=3600)
    with NfsnTransport(credentials) as transport:
        nfsn = Nfsn(transport)
        nfsn.dns(domain).replace_rr(record)
    log.info("DNS record updated to %s (%s)", ip, domain)


def get_public_ip() -> str:
    response = requests.get(IPIFY_URL, timeout=10)
    response.raise_for_status()

    ip = response.text.strip()
    if not ip:
        raise RuntimeError("ipify returned an empty response")

    log.debug("ipify returned %s", ip)
    return ip


def check_and_update(settings: dict | None = None, config_path: str | None = None) -> None:
    settings = settings or load_settings(config_path)

    if not settings.get("ENABLE", True):
        message = "DDNS is disabled; skipping DNS check"
        log.info(message)
        settings["LAST_RESULT"] = "skipped"
        settings["LAST_MESSAGE"] = message
        settings["LAST_RUN"] = format_timestamp(settings.get("TIME_ZONE"))
        save_settings(settings, config_path)
        return

    if not settings.get("NFSN_LOGIN") or not settings.get("NFSN_API_KEY"):
        message = "NFSN_LOGIN or NFSN_API_KEY is not set; skipping DNS check"
        log.warning(message)
        settings["LAST_RESULT"] = "skipped"
        settings["LAST_MESSAGE"] = message
        settings["LAST_RUN"] = format_timestamp(settings.get("TIME_ZONE"))
        save_settings(settings, config_path)
        return

    domains = parse_domains(settings)
    if not domains:
        message = "No domains are configured; skipping DNS check"
        log.warning(message)
        settings["LAST_RESULT"] = "skipped"
        settings["LAST_MESSAGE"] = message
        settings["LAST_RUN"] = format_timestamp(settings.get("TIME_ZONE"))
        settings["HOST_STATUSES"] = {}
        save_settings(settings, config_path)
        return

    public_ip = get_public_ip()
    log.info("Starting DNS check; public IP=%s", public_ip)
    host_statuses = {}
    overall_status = "current"
    error_messages = []

    for domain in domains:
        try:
            current_dns_ip = get_dns_ip(settings, domain)
            if public_ip == current_dns_ip:
                status = "current"
                message = "DNS record is current"
                log.info("%s: %s (dns_ip=%s)", domain, message, current_dns_ip or 'unknown')
            else:
                update_dns(public_ip, settings, domain)
                new_dns_ip = get_dns_ip(settings, domain)
                status = "updated"
                message = f"Updated DNS from {current_dns_ip or 'unknown'} to {public_ip}"
                current_dns_ip = new_dns_ip
                log.info("%s: %s (dns_ip=%s)", domain, message, current_dns_ip or 'unknown')

            host_statuses[domain] = {
                "status": status,
                "message": message,
                "dns_ip": current_dns_ip,
            }
            if status != "current":
                overall_status = "updated"
        except Exception as exc:
            log.exception("DNS check failed for %s", domain)
            host_statuses[domain] = {
                "status": "failure",
                "message": str(exc),
                "dns_ip": None,
            }
            overall_status = "partial" if overall_status == "current" else overall_status
            error_messages.append(f"{domain}: {exc}")

    if overall_status == "current":
        summary = "All DNS records are current"
    elif overall_status == "updated":
        summary = "Updated DNS records"
    else:
        summary = "Some DNS updates failed: " + "; ".join(error_messages)

    log.info("DNS check complete: %s; summary=%s", overall_status, summary)
    settings["LAST_PUBLIC_IP"] = public_ip
    settings["LAST_RESULT"] = overall_status
    settings["LAST_MESSAGE"] = summary
    settings["LAST_RUN"] = format_timestamp(settings.get("TIME_ZONE"))
    settings["HOST_STATUSES"] = host_statuses
    save_settings(settings, config_path)
