"""Config flow for Twilio SMS integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_ACCOUNT_SID,
    CONF_AUTH_TOKEN,
    CONF_PHONE_NUMBERS,
    CONF_EXTERNAL_URL,
    CONF_DEBUG,
)

_LOGGER = logging.getLogger(__name__)


def validate_credentials(account_sid: str, auth_token: str) -> list[dict[str, str]]:
    """Validate Twilio credentials and return available phone numbers."""
    client = Client(account_sid, auth_token)

    phone_numbers = []
    for number in client.incoming_phone_numbers.list():
        phone_numbers.append({
            "sid": number.sid,
            "phone_number": number.phone_number,
            "friendly_name": number.friendly_name or number.phone_number,
        })

    return phone_numbers


class TwilioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Twilio SMS."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._account_sid: str | None = None
        self._auth_token: str | None = None
        self._available_numbers: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - credentials input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._account_sid = user_input[CONF_ACCOUNT_SID]
            self._auth_token = user_input[CONF_AUTH_TOKEN]

            try:
                self._available_numbers = await self.hass.async_add_executor_job(
                    validate_credentials, self._account_sid, self._auth_token
                )

                if not self._available_numbers:
                    errors["base"] = "no_phone_numbers"
                else:
                    return await self.async_step_select_numbers()

            except TwilioRestException as err:
                _LOGGER.error("Twilio authentication failed: %s", err)
                if err.code == 20003:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Twilio authentication")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT_SID): str,
                    vol.Required(CONF_AUTH_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_select_numbers(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle phone number selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_numbers = user_input.get(CONF_PHONE_NUMBERS, [])
            external_url = user_input.get(CONF_EXTERNAL_URL, "").strip().rstrip("/")

            if not selected_numbers:
                errors["base"] = "no_selection"
            else:
                await self.async_set_unique_id(self._account_sid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Twilio SMS",
                    data={
                        CONF_ACCOUNT_SID: self._account_sid,
                        CONF_AUTH_TOKEN: self._auth_token,
                        CONF_PHONE_NUMBERS: selected_numbers,
                        CONF_EXTERNAL_URL: external_url,
                    },
                )

        number_options = {
            num["phone_number"]: f"{num['friendly_name']} ({num['phone_number']})"
            for num in self._available_numbers
        }

        return self.async_show_form(
            step_id="select_numbers",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PHONE_NUMBERS): cv.multi_select(number_options),
                    vol.Optional(CONF_EXTERNAL_URL, default=""): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return TwilioOptionsFlow(config_entry)


class TwilioOptionsFlow(OptionsFlow):
    """Handle options flow for Twilio SMS."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._available_numbers: list[dict[str, str]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        account_sid = self._config_entry.data[CONF_ACCOUNT_SID]
        auth_token = self._config_entry.data[CONF_AUTH_TOKEN]

        try:
            self._available_numbers = await self.hass.async_add_executor_job(
                validate_credentials, account_sid, auth_token
            )
        except Exception:
            _LOGGER.exception("Failed to fetch phone numbers")
            errors["base"] = "cannot_connect"
            return self.async_show_form(step_id="init", errors=errors)

        if user_input is not None:
            selected_numbers = user_input.get(CONF_PHONE_NUMBERS, [])
            external_url = user_input.get(CONF_EXTERNAL_URL, "").strip().rstrip("/")
            debug = user_input.get(CONF_DEBUG, False)

            if not selected_numbers:
                errors["base"] = "no_selection"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_PHONE_NUMBERS: selected_numbers,
                        CONF_EXTERNAL_URL: external_url,
                        CONF_DEBUG: debug,
                    },
                )

        current_numbers = self._config_entry.options.get(
            CONF_PHONE_NUMBERS,
            self._config_entry.data.get(CONF_PHONE_NUMBERS, [])
        )

        current_url = self._config_entry.options.get(
            CONF_EXTERNAL_URL,
            self._config_entry.data.get(CONF_EXTERNAL_URL, "")
        )

        current_debug = self._config_entry.options.get(
            CONF_DEBUG,
            self._config_entry.data.get(CONF_DEBUG, False)
        )

        number_options = {
            num["phone_number"]: f"{num['friendly_name']} ({num['phone_number']})"
            for num in self._available_numbers
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PHONE_NUMBERS, default=current_numbers
                    ): cv.multi_select(number_options),
                    vol.Optional(
                        CONF_EXTERNAL_URL, default=current_url
                    ): str,
                    vol.Optional(
                        CONF_DEBUG, default=current_debug
                    ): bool,
                }
            ),
            errors=errors,
        )
