"""Автодор — Платные дороги provider client.

The cabinet (lk.avtodor-tr.ru) is a Spring Boot BFF in front of Keycloak
(realm ``avtodor``, client ``lkmp``). The OAuth code exchange happens
server-side, so authentication boils down to a browser-style login that ends
with an HttpOnly ``SESSION`` cookie; API calls then just ride that cookie.

Flow:
    1. GET /  → 302 chain → Keycloak login page (parse the form).
    2. POST username/password to the form's authenticate URL → 302 back to
       /sso/login?code=… → Spring sets the authenticated SESSION cookie.
    3. GET /api/client/extended → JSON with balances.
"""

from __future__ import annotations

import html as html_lib
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

BASE_URL = "https://lk.avtodor-tr.ru"
START_URL = f"{BASE_URL}/"
EXTENDED_URL = f"{BASE_URL}/api/client/extended"
STATUS_DICT_URL = (
    f"{BASE_URL}/api/public/dictionaries/all?dictionary_name=contract_statuses"
)
AUTH_HOST = "auth-lkmp.avtodor-tr.ru"

_FORM_ACTION_RE = re.compile(
    r'<form[^>]*\bid="kc-form-login"[^>]*\baction="([^"]+)"', re.IGNORECASE
)
_ANY_FORM_ACTION_RE = re.compile(
    r'<form[^>]*\baction="([^"]+)"[^>]*>', re.IGNORECASE
)

# Markers Keycloak renders on the login page when the credentials themselves
# were rejected. If we land back on the login page WITHOUT any of these, the
# re-render is almost certainly transient (expired form, anti-bot challenge,
# rate limiting, server hiccup) and must NOT be treated as a bad password –
# otherwise the user is nagged to re-enter credentials that are actually fine.
_CREDENTIAL_ERROR_MARKERS = (
    'id="input-error"',
    "kc-feedback-text",
    "alert-error",
    "pf-m-danger",
    "pf-m-error",
)


class AvtodorClient(TransponderClient):
    """Client for the Автодор Keycloak-backed cabinet."""

    provider = "avtodor"

    def __init__(
        self, session: aiohttp.ClientSession, username: str, password: str
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._status_map: dict[int, str] | None = None

    async def async_login(self) -> None:
        # 1. Reach the Keycloak login page via the redirect chain.
        try:
            async with self._session.get(START_URL, allow_redirects=True) as resp:
                page = await resp.text()
                landed = str(resp.url)
        except aiohttp.ClientError as err:
            raise TransponderConnectionError(
                f"Cannot reach Автодор cabinet: {err}"
            ) from err

        # Already authenticated? Then there is no login form.
        if AUTH_HOST not in landed:
            return

        action = self._parse_login_action(page)
        if action is None:
            raise TransponderConnectionError("Автодор login form not found")

        # 2. Submit credentials; follow the redirect back into the app.
        try:
            async with self._session.post(
                action,
                data={
                    "username": self._username,
                    "password": self._password,
                    "credentialId": "",
                },
                allow_redirects=True,
            ) as resp:
                final_url = str(resp.url)
                result_page = await resp.text()
        except aiohttp.ClientError as err:
            raise TransponderConnectionError(f"Автодор login failed: {err}") from err

        # Redirected off the auth host → login succeeded.
        if AUTH_HOST not in final_url:
            return

        # Still on the auth host: distinguish a rejected password from a
        # transient re-render. Only a page that actually shows a credential
        # error means the user must re-authenticate.
        if self._page_shows_credential_error(result_page):
            raise TransponderAuthError("Invalid Автодор login or password")
        raise TransponderConnectionError(
            "Автодор login did not complete (no credential error shown); "
            "treating as transient and will retry"
        )

    async def _async_fetch_extended(self) -> dict:
        async with self._session.get(EXTENDED_URL, allow_redirects=False) as resp:
            if resp.status in (301, 302, 303, 401, 403):
                raise TransponderAuthError("Session expired")
            if resp.status != 200:
                raise TransponderConnectionError(
                    f"Unexpected status {resp.status} from client/extended"
                )
            return await resp.json(content_type=None)

    async def async_get_accounts(self) -> list[Account]:
        try:
            data = await self._async_fetch_extended()
        except TransponderAuthError:
            # Session expired: log in again, then retry the fetch once.
            await self.async_login()
            try:
                data = await self._async_fetch_extended()
            except TransponderAuthError as err:
                # Login itself succeeded (it would have raised otherwise), yet
                # the fresh session still isn't accepted. That's a transient
                # server-side problem, not bad credentials – retry later
                # instead of forcing the user through reauth.
                raise TransponderConnectionError(
                    f"Автодор session not accepted after re-login: {err}"
                ) from err
        except aiohttp.ClientError as err:
            raise TransponderConnectionError(str(err)) from err

        status_map = await self._async_status_map()
        return self._build_accounts(data, status_map)

    async def _async_status_map(self) -> dict[int, str]:
        if self._status_map is not None:
            return self._status_map
        mapping: dict[int, str] = {}
        try:
            async with self._session.get(STATUS_DICT_URL) as resp:
                if resp.status == 200:
                    payload = await resp.json(content_type=None)
                    for item in payload.get("contract_statuses", []):
                        mapping[item["id"]] = item.get("name") or str(item["id"])
        except (aiohttp.ClientError, ValueError, KeyError):
            _LOGGER.debug("Could not load Автодор contract_statuses dictionary")
        self._status_map = mapping
        return mapping

    def _build_accounts(
        self, data: dict, status_map: dict[int, str]
    ) -> list[Account]:
        client = data.get("client") or {}
        client_name = client.get("name")
        account_no = client.get("id")
        contracts = data.get("contracts") or []
        if not contracts:
            raise TransponderConnectionError("Автодор response has no contracts")

        accounts: list[Account] = []
        for c in contracts:
            status_id = c.get("contract_status_id")
            status = status_map.get(status_id, f"status_{status_id}")
            accounts.append(
                Account(
                    provider=self.provider,
                    account_id=str(c.get("id")),
                    balance=_to_float(c.get("account_balance")),
                    name=c.get("title") or client_name,
                    contract=c.get("num"),
                    status=status,
                    updated_at=c.get("account_balance_dt"),
                    bonus_points=_to_float(c.get("loyalty_member_balance")),
                    transponders_count=c.get("transponders_count"),
                    extra={"account": str(account_no) if account_no else ""},
                )
            )
        return accounts

    @staticmethod
    def _parse_login_action(page: str) -> str | None:
        match = _FORM_ACTION_RE.search(page) or _ANY_FORM_ACTION_RE.search(page)
        if not match:
            return None
        return html_lib.unescape(match.group(1))

    @staticmethod
    def _page_shows_credential_error(page: str) -> bool:
        """True only if Keycloak rendered a real credential-rejection error."""
        lowered = page.lower()
        return any(marker in lowered for marker in _CREDENTIAL_ERROR_MARKERS)


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
