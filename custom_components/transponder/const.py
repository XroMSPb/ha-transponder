"""Constants for the Transponder (ЗСД / Автодор) integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "transponder"

CONF_PROVIDER = "provider"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

PROVIDER_ZSD = "zsd"
PROVIDER_AVTODOR = "avtodor"

PROVIDERS: dict[str, str] = {
    PROVIDER_ZSD: "ЗСД — Магистраль Северной Столицы",
    PROVIDER_AVTODOR: "Автодор — Платные дороги",
}

DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)
MIN_SCAN_INTERVAL_MINUTES = 5

CURRENCY_RUB = "RUB"

# Attribute keys exposed on sensors.
ATTR_PROVIDER = "provider"
ATTR_CONTRACT = "contract"
ATTR_ACCOUNT = "account"
ATTR_STATUS = "status"
ATTR_UPDATED_AT = "updated_at"
ATTR_TRANSPONDERS = "transponders"

# A browser-like UA – the Автодор site sits behind DDoS-Guard.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 HA-Transponder"
)
DEFAULT_HEADERS = {"User-Agent": USER_AGENT}
