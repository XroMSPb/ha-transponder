"""Config flow for the Transponder (ЗСД / Автодор) integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import get_client, TransponderAuthError, TransponderConnectionError
from .const import (
    CONF_PROVIDER,
    CONF_SCAN_INTERVAL,
    DEFAULT_HEADERS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL_MINUTES,
    PROVIDERS,
)

_LOGGER = logging.getLogger(__name__)

CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate(hass, provider: str, username: str, password: str) -> None:
    """Try to log in and fetch balances; raise on failure."""
    session = async_create_clientsession(hass, headers=DEFAULT_HEADERS)
    client = get_client(provider, session, username, password)
    await client.async_get_accounts()


class TransponderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow: pick a provider, then enter credentials."""

    VERSION = 1

    def __init__(self) -> None:
        self._provider: str | None = None
        self._reauth_entry = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step: choose the provider."""
        if user_input is not None:
            self._provider = user_input[CONF_PROVIDER]
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_PROVIDER): vol.In(PROVIDERS)}
            ),
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Second step: enter credentials for the chosen provider."""
        assert self._provider is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            await self.async_set_unique_id(f"{self._provider}:{username.lower()}")
            self._abort_if_unique_id_configured()

            errors = await self._try_login(self._provider, username, password)
            if not errors:
                return self.async_create_entry(
                    title=f"{PROVIDERS[self._provider]} · {username}",
                    data={
                        CONF_PROVIDER: self._provider,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="credentials",
            data_schema=CREDENTIALS_SCHEMA,
            errors=errors,
            description_placeholders={"provider": PROVIDERS[self._provider]},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._reauth_entry is not None
        errors: dict[str, str] = {}
        provider = self._reauth_entry.data[CONF_PROVIDER]
        username = self._reauth_entry.data[CONF_USERNAME]

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            errors = await self._try_login(provider, username, password)
            if not errors:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data={
                        CONF_PROVIDER: provider,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={
                "provider": PROVIDERS.get(provider, provider),
                "username": username,
            },
            errors=errors,
        )

    async def _try_login(
        self, provider: str, username: str, password: str
    ) -> dict[str, str]:
        try:
            await _validate(self.hass, provider, username, password)
        except TransponderAuthError:
            return {"base": "invalid_auth"}
        except TransponderConnectionError:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error validating credentials")
            return {"base": "unknown"}
        return {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> TransponderOptionsFlow:
        return TransponderOptionsFlow()


class TransponderOptionsFlow(OptionsFlow):
    """Options: the polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, int(DEFAULT_SCAN_INTERVAL.total_seconds() // 60)
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_MINUTES)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
