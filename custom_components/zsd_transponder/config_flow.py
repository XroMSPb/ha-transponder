"""Config flow for the ЗСД Transponder integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import ZsdApiClient, ZsdAuthError, ZsdConnectionError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate(hass, username: str, password: str) -> None:
    """Try to log in and fetch a balance; raise on failure."""
    session = async_create_clientsession(hass)
    client = ZsdApiClient(session, username, password)
    await client.async_get_balances()


class ZsdConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ЗСД Transponder."""

    VERSION = 1

    reauth_entry = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            errors = await self._try_login(username, password)
            if not errors:
                return self.async_create_entry(
                    title=f"ЗСД {username}",
                    data={CONF_USERNAME: username, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when the session/password stops working."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication."""
        errors: dict[str, str] = {}
        assert self.reauth_entry is not None
        username = self.reauth_entry.data[CONF_USERNAME]

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            errors = await self._try_login(username, password)
            if not errors:
                return self.async_update_reload_and_abort(
                    self.reauth_entry,
                    data={CONF_USERNAME: username, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"username": username},
            errors=errors,
        )

    async def _try_login(self, username: str, password: str) -> dict[str, str]:
        """Return an errors dict (empty on success)."""
        try:
            await _validate(self.hass, username, password)
        except ZsdAuthError:
            return {"base": "invalid_auth"}
        except ZsdConnectionError:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001 - surface unexpected issues to the user
            _LOGGER.exception("Unexpected error validating ЗСД credentials")
            return {"base": "unknown"}
        return {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> ZsdOptionsFlow:
        return ZsdOptionsFlow()


class ZsdOptionsFlow(OptionsFlow):
    """Handle the polling-interval option."""

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
