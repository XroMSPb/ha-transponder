"""ЗСД (Магистраль Северной Столицы) provider client.

The Onyma cabinet has no public API, so this replicates the browser flow:

1. ``POST /onyma/`` with ``login`` / ``password`` establishes a session cookie.
2. ``POST /onyma/system/literpc/`` invokes the ``toll-balance-refresher`` RPC,
   returning an HTML fragment with the balance for every contract.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import re

import aiohttp

from .base import (
    Account,
    TransponderAuthError,
    TransponderClient,
    TransponderConnectionError,
)

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://cabinet.nch-spb.com"
LOGIN_URL = f"{BASE_URL}/onyma/"
RPC_URL = f"{BASE_URL}/onyma/system/literpc/"
BALANCE_PACKAGE = "toll-balance-refresher"
BALANCE_FN = "refresh"

_ROW_RE = re.compile(
    r'<td class="infoblock name">(?P<name>.*?)</td>\s*'
    r'<td class="infoblock value(?P<classes>[^"]*)">(?P<value>.*?)</td>',
    re.DOTALL,
)
_CONTRACT_RE = re.compile(r'<li class="dog-info[^"]*">(?P<block>.*?)</li>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
# The "Пополнить" (top-up) anchor inside the balance-link cell.
_TOPUP_RE = re.compile(
    r'balance-link[^>]*>\s*<a[^>]+href="([^"]+)"', re.DOTALL
)

_CONTRACT_LABELS = ("Договор", "Contract")
_STATUS_LABELS = ("Статус", "Status")
_BALANCE_LABELS = ("Баланс", "Balance")


def _strip_tags(value: str) -> str:
    text = _TAG_RE.sub("", value).replace("&amp;", "&").replace("&nbsp;", " ")
    return " ".join(text.split()).strip()


def _parse_balance(value: str) -> float | None:
    cleaned = value.replace("\xa0", " ").replace(" ", "").replace(",", ".")
    cleaned = re.sub(r"[^\d.\-]", "", cleaned)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_balance_fragment(html: str) -> list[dict]:
    """Parse the RPC HTML fragment into a list of field/balance dicts."""
    results: list[dict] = []
    blocks = [m.group("block") for m in _CONTRACT_RE.finditer(html)] or [html]
    for block in blocks:
        fields: dict[str, str] = {}
        balance: float | None = None
        for row in _ROW_RE.finditer(block):
            name = _strip_tags(row.group("name"))
            value = _strip_tags(row.group("value"))
            if "balance-value" in row.group("classes"):
                balance = _parse_balance(value)
            if name:
                fields[name] = value

        contract = next((fields[k] for k in _CONTRACT_LABELS if k in fields), "")
        status = next((fields[k] for k in _STATUS_LABELS if k in fields), None)
        if balance is None:
            text = next((fields[k] for k in _BALANCE_LABELS if k in fields), None)
            if text is not None:
                balance = _parse_balance(text)

        if not contract and balance is None and status is None:
            continue
        topup_match = _TOPUP_RE.search(block)
        topup_url = html_lib.unescape(topup_match.group(1)) if topup_match else None
        results.append(
            {
                "contract": contract or "unknown",
                "balance": balance,
                "status": status,
                "topup_url": topup_url,
            }
        )
    return results


class ZsdClient(TransponderClient):
    """Client for the ЗСД Onyma cabinet."""

    provider = "zsd"

    def __init__(
        self, session: aiohttp.ClientSession, username: str, password: str
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._logged_in = False

    async def async_login(self) -> None:
        try:
            await self._session.get(LOGIN_URL, allow_redirects=True)
            async with self._session.post(
                LOGIN_URL,
                data={
                    "login": self._username,
                    "password": self._password,
                    "submit": "Вход",
                },
                allow_redirects=True,
            ) as resp:
                text = await resp.text()
        except aiohttp.ClientError as err:
            raise TransponderConnectionError(f"Cannot reach ЗСД cabinet: {err}") from err

        if _looks_like_login_page(text):
            self._logged_in = False
            raise TransponderAuthError("Invalid ЗСД username or password")
        self._logged_in = True

    async def _async_rpc_balance(self) -> tuple[str, str | None]:
        payload = [{"id": 0, "package": BALANCE_PACKAGE, "fn": BALANCE_FN, "data": {}}]
        try:
            async with self._session.post(
                RPC_URL,
                data={"body": json.dumps(payload), "queue": 0},
                headers={"X-Requested-With": "XMLHttpRequest"},
                allow_redirects=False,
            ) as resp:
                if resp.status in (301, 302, 303, 401, 403):
                    raise TransponderAuthError("Session expired")
                if resp.status != 200:
                    raise TransponderConnectionError(
                        f"Unexpected RPC status {resp.status}"
                    )
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise TransponderConnectionError(f"RPC request failed: {err}") from err
        except (ValueError, json.JSONDecodeError) as err:
            raise TransponderAuthError("RPC did not return JSON") from err
        return _extract_rpc_result(data)

    async def async_get_accounts(self) -> list[Account]:
        if not self._logged_in:
            await self.async_login()
        try:
            html, date = await self._async_rpc_balance()
        except TransponderAuthError:
            # Session expired: re-login, then retry the RPC once.
            self._logged_in = False
            await self.async_login()
            try:
                html, date = await self._async_rpc_balance()
            except TransponderAuthError as err:
                # Login succeeded (it raises on bad credentials), so a repeat
                # failure here is a transient server problem, not a wrong
                # password. Retry later rather than forcing reauth.
                raise TransponderConnectionError(
                    f"ЗСД session not accepted after re-login: {err}"
                ) from err

        parsed = parse_balance_fragment(html)
        if not parsed:
            raise TransponderConnectionError("Could not parse any ЗСД balance")

        return [
            Account(
                provider=self.provider,
                account_id=row["contract"],
                balance=row["balance"],
                name=row["contract"],
                contract=row["contract"],
                status=row["status"],
                updated_at=date,
                topup_url=row.get("topup_url"),
            )
            for row in parsed
        ]


def _looks_like_login_page(text: str) -> bool:
    lowered = text.lower()
    return 'name="password"' in lowered and "выход" not in lowered


def _extract_rpc_result(data: dict) -> tuple[str, str | None]:
    try:
        inner = data["result"][0]["result"]
    except (KeyError, IndexError, TypeError) as err:
        raise TransponderConnectionError(f"Unexpected RPC envelope: {data!r}") from err
    if isinstance(inner, dict):
        html = inner.get("result", "")
        date = inner.get("date")
    else:
        html = inner if isinstance(inner, str) else ""
        date = None
    if not html:
        raise TransponderConnectionError("Empty ЗСД balance fragment")
    return html, date
