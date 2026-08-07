"""Constants for the ЗСД Transponder integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "zsd_transponder"

# Base endpoints of the "Магистраль Северной Столицы" (ЗСД) Onyma cabinet.
BASE_URL = "https://cabinet.nch-spb.com"
LOGIN_URL = f"{BASE_URL}/onyma/"
RPC_URL = f"{BASE_URL}/onyma/system/literpc/"

# The literpc package/function that returns the fresh balance HTML fragment.
BALANCE_PACKAGE = "toll-balance-refresher"
BALANCE_FN = "refresh"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)
MIN_SCAN_INTERVAL_MINUTES = 5

# Attribute keys exposed on the sensor.
ATTR_CONTRACT = "contract"
ATTR_STATUS = "status"
ATTR_UPDATED_AT = "updated_at"

CURRENCY_RUB = "RUB"

MANUFACTURER = "Магистраль Северной Столицы (ЗСД)"
