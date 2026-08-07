"""Client for the ЗСД (Магистраль Северной Столицы) Onyma cabinet.

The cabinet has no public API, so this client replicates the browser flow:

1. ``POST /onyma/`` with ``login`` / ``password`` establishes an HttpOnly
   session cookie.
2. ``POST /onyma/system/literpc/`` invokes the ``toll-balance-refresher``
   RPC package, which returns an HTML fragment containing the live balance for
   every contract on the account.

The client keeps a session alive between polls and transparently re-logs in when
the session expires.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import aiohttp

try:  # Package import inside Home Assistant.
    from .const import (
        BALANCE_FN,
        BALANCE_PACKAGE,
        LOGIN_URL,
        RPC_URL,
    )
except ImportError:  # Standalone import (e.g. tools/test_login.py).
    from const import (  # type: ignore[no-redef]
        BALANCE_FN,
        BALANCE_PACKAGE,
        LOGIN_URL,
        RPC_URL,
    )

_LOGGER = logging.getLogger(__name__)

# Rows inside the returned fragment look like:
#   <td class="infoblock name">Договор</td>
#   <td class="infoblock value balance-value">716.25</td>
_ROW_RE = re.compile(
    r'<td class="infoblock name">(?P<name>.*?)</td>\s*'
    r'<td class="infoblock value(?P<classes>[^"]*)">(?P<value>.*?)</td>',
    re.DOTALL,
)
# Each contract is wrapped in its own <li class="dog-info ...">…</li>.
_CONTRACT_RE = re.compile(r'<li class="dog-info[^"]*">(?P<block>.*?)</li>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")

# Balance label variants (server may localise); we also fall back to the CSS class.
_BALANCE_LABELS = ("Баланс", "Balance")
_CONTRACT_LABELS = ("Договор", "Contract")
_STATUS_LABELS = ("Статус", "Status")


class ZsdError(Exception):
    """Base error for the ЗСД client."""


class ZsdAuthError(ZsdError):
    """Raised when the credentials are rejected."""


class ZsdConnectionError(ZsdError):
    """Raised when the cabinet is unreachable or returns an unexpected reply."""


@dataclass(slots=True)
class ContractBalance:
    """Balance information for a single contract."""

    contract: str
    balance: float | None
    status: str | None
    updated_at: str | None
    raw: dict[str, str]


def _strip_tags(value: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = _TAG_RE.sub("", value)
    text = text.replace("&amp;", "&").replace("&nbsp;", " ")
    return " ".join(text.split()).strip()


def _parse_balance(value: str) -> float | None:
    """Parse a Russian-formatted balance string (``716.25`` / ``1 234,50``)."""
    cleaned = value.replace("\xa0", " ").replace(" ", "").replace(",", ".")
    cleaned = re.sub(r"[^\d.\-]", "", cleaned)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_balance_fragment(html: str) -> list[ContractBalance]:
    """Parse the RPC HTML fragment into a list of contract balances."""
    contracts: list[ContractBalance] = []
    blocks = [m.group("block") for m in _CONTRACT_RE.finditer(html)]
    if not blocks:
        # Single unwrapped block (defensive) – treat the whole fragment as one.
        blocks = [html]

    for block in blocks:
        fields: dict[str, str] = {}
        balance: float | None = None
        for row in _ROW_RE.finditer(block):
            name = _strip_tags(row.group("name"))
            value = _strip_tags(row.group("value"))
            classes = row.group("classes")
            if "balance-value" in classes:
                balance = _parse_balance(value)
            if name:
                fields[name] = value

        contract = next(
            (fields[k] for k in _CONTRACT_LABELS if k in fields),
            "",
        )
        status = next((fields[k] for k in _STATUS_LABELS if k in fields), None)
        if balance is None:
            balance_text = next(
                (fields[k] for k in _BALANCE_LABELS if k in fields), None
            )
            if balance_text is not None:
                balance = _parse_balance(balance_text)

        # Skip empty blocks that carried no usable data.
        if not contract and balance is None and status is None:
            continue

        contracts.append(
            ContractBalance(
                contract=contract or "unknown",
                balance=balance,
                status=status,
                updated_at=None,
                raw=fields,
            )
        )
    return contracts


class ZsdApiClient:
    """Async client that logs in and fetches balances from the ЗСД cabinet."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._logged_in = False

    async def async_login(self) -> None:
        """Authenticate against the cabinet, raising on failure."""
        # Prime base cookies (onm_group etc.) before posting credentials.
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
            raise ZsdConnectionError(f"Cannot reach ЗСД cabinet: {err}") from err

        if _looks_like_login_page(text):
            self._logged_in = False
            raise ZsdAuthError("Invalid ЗСД username or password")

        self._logged_in = True

    async def _async_rpc_balance(self) -> tuple[str, str | None]:
        """Call the balance-refresher RPC. Returns (html_fragment, date)."""
        payload = [
            {"id": 0, "package": BALANCE_PACKAGE, "fn": BALANCE_FN, "data": {}}
        ]
        try:
            async with self._session.post(
                RPC_URL,
                data={"body": json.dumps(payload), "queue": 0},
                headers={"X-Requested-With": "XMLHttpRequest"},
                allow_redirects=False,
            ) as resp:
                # A 302/redirect means the session expired.
                if resp.status in (301, 302, 303, 401, 403):
                    raise ZsdAuthError("Session expired")
                if resp.status != 200:
                    raise ZsdConnectionError(
                        f"Unexpected RPC status {resp.status}"
                    )
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise ZsdConnectionError(f"RPC request failed: {err}") from err
        except (ValueError, json.JSONDecodeError) as err:
            raise ZsdAuthError("RPC did not return JSON (session expired?)") from err

        return _extract_rpc_result(data)

    async def async_get_balances(self) -> list[ContractBalance]:
        """Return balances, logging in (or re-logging in) as needed."""
        if not self._logged_in:
            await self.async_login()

        try:
            html, date = await self._async_rpc_balance()
        except ZsdAuthError:
            # Session likely expired mid-life; retry once with a fresh login.
            self._logged_in = False
            await self.async_login()
            html, date = await self._async_rpc_balance()

        contracts = parse_balance_fragment(html)
        if not contracts:
            raise ZsdConnectionError("Could not parse any balance from response")
        for contract in contracts:
            contract.updated_at = date
        return contracts


def _looks_like_login_page(text: str) -> bool:
    """Heuristic: the login page still shows the password field and no logout."""
    lowered = text.lower()
    has_password_field = 'name="password"' in lowered
    has_logout = "выход" in lowered or "/logout" in lowered
    return has_password_field and not has_logout


def _extract_rpc_result(data: dict) -> tuple[str, str | None]:
    """Pull the (html, date) tuple out of the literpc envelope."""
    try:
        inner = data["result"][0]["result"]
    except (KeyError, IndexError, TypeError) as err:
        raise ZsdConnectionError(f"Unexpected RPC envelope: {data!r}") from err

    if isinstance(inner, dict):
        html = inner.get("result", "")
        date = inner.get("date")
    else:  # Some deployments return the HTML directly.
        html = inner if isinstance(inner, str) else ""
        date = None

    if not html:
        raise ZsdConnectionError("RPC returned an empty balance fragment")
    return html, date
