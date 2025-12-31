"""The Twilio SMS integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.network import get_url
from homeassistant.helpers.service import async_set_service_schema

from .const import (
    DOMAIN,
    CONF_ACCOUNT_SID,
    CONF_AUTH_TOKEN,
    CONF_PHONE_NUMBERS,
    CONF_EXTERNAL_URL,
    CONF_DEBUG,
    ATTR_TARGET,
    ATTR_MESSAGE,
    ATTR_MEDIA_URL,
    ATTR_FROM_NUMBER,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_MESSAGE = "send_message"

LOCAL_PATH_PREFIXES = ("/local/", "/media/", "/api/")


def _get_all_phone_numbers(hass: HomeAssistant) -> list[str]:
    """Get all configured phone numbers from all entries."""
    all_numbers = []
    for entry_data in hass.data.get(DOMAIN, {}).values():
        for number in entry_data.get("phone_numbers", []):
            if number not in all_numbers:
                all_numbers.append(number)
    return all_numbers


def _get_service_schema(phone_numbers: list[str]) -> vol.Schema:
    """Generate service schema with dynamic phone number options."""
    return vol.Schema(
        {
            vol.Required(ATTR_TARGET): vol.All(cv.ensure_list, [cv.template]),
            vol.Required(ATTR_MESSAGE): cv.template,
            vol.Optional(ATTR_MEDIA_URL): vol.All(cv.ensure_list, [cv.template]),
            vol.Required(ATTR_FROM_NUMBER): vol.In(phone_numbers) if phone_numbers else cv.string,
        }
    )


def _update_service_schema(hass: HomeAssistant) -> None:
    """Update the service schema with current phone numbers."""
    phone_numbers = _get_all_phone_numbers(hass)

    service_desc = {
        "name": "Send Message",
        "description": "Send an SMS or MMS message via Twilio. Supports Jinja2 templates.",
        "fields": {
            ATTR_TARGET: {
                "name": "Target Numbers",
                "description": "Phone number(s) to send to. Supports Jinja2 templates.",
                "required": True,
                "example": "+15551234567",
                "selector": {"text": {"multiple": True}},
            },
            ATTR_MESSAGE: {
                "name": "Message",
                "description": "Message body. Supports Jinja2 templates.",
                "required": True,
                "example": "HA Version: {{ state_attr('update.home_assistant_core_update', 'installed_version') }}",
                "selector": {"text": {"multiline": True}},
            },
            ATTR_MEDIA_URL: {
                "name": "Media URL",
                "description": (
                    "URL(s) for MMS media attachments. Twilio fetches media from these URLs, "
                    "so they must be publicly accessible.\n\n"
                    "**External URLs:** Use any public URL (https://example.com/image.jpg).\n\n"
                    "**Local files:** Use /local/filename.jpg for files in /config/www/ folder. "
                    "Auto-converts to your external HA URL.\n\n"
                    "**Requirements:** HA must be externally accessible (Nabu Casa, reverse proxy). "
                    "Supported paths: /local/, /media/, /api/. Supports Jinja2 templates."
                ),
                "required": False,
                "example": "/local/camera_snapshot.jpg",
                "selector": {"text": {"multiple": True}},
            },
            ATTR_FROM_NUMBER: {
                "name": "From Number",
                "description": "The Twilio phone number to send from.",
                "required": True,
                "selector": {
                    "select": {
                        "options": phone_numbers,
                        "custom_value": False,
                    }
                },
            },
        },
    }

    async_set_service_schema(hass, DOMAIN, SERVICE_SEND_MESSAGE, service_desc)


def _render_template(hass: HomeAssistant, tpl: template.Template | str) -> str:
    """Render a template to string."""
    if isinstance(tpl, template.Template):
        return tpl.async_render(parse_result=False)
    return str(tpl)


def _get_external_url(hass: HomeAssistant) -> str | None:
    """Get the configured external URL from any entry."""
    for entry_data in hass.data.get(DOMAIN, {}).values():
        external_url = entry_data.get("external_url")
        if external_url:
            return external_url
    return None


def _is_debug_enabled(hass: HomeAssistant) -> bool:
    """Check if debug logging is enabled."""
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if entry_data.get("debug", False):
            return True
    return False


def _convert_local_path_to_url(hass: HomeAssistant, path: str) -> str:
    """Convert local HA path to external URL."""
    if path.startswith(("http://", "https://")):
        return path

    for prefix in LOCAL_PATH_PREFIXES:
        if path.startswith(prefix):
            # First try user-configured external URL
            base_url = _get_external_url(hass)

            # Fall back to HA's get_url if not configured
            if not base_url:
                try:
                    base_url = get_url(hass, allow_internal=False, prefer_external=True)
                except Exception:
                    _LOGGER.warning(
                        "Could not get external URL for local path %s. "
                        "Configure external URL in integration settings.",
                        path,
                    )
                    return path

            full_url = f"{base_url.rstrip('/')}{path}"
            if _is_debug_enabled(hass):
                _LOGGER.warning("Twilio SMS Debug: Converted %s to %s", path, full_url)
            return full_url

    return path


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Twilio SMS from a config entry."""
    account_sid = entry.data[CONF_ACCOUNT_SID]
    auth_token = entry.data[CONF_AUTH_TOKEN]

    phone_numbers = entry.options.get(
        CONF_PHONE_NUMBERS, entry.data.get(CONF_PHONE_NUMBERS, [])
    )
    external_url = entry.options.get(
        CONF_EXTERNAL_URL, entry.data.get(CONF_EXTERNAL_URL, "")
    )

    client = Client(account_sid, auth_token)

    debug = entry.options.get(
        CONF_DEBUG, entry.data.get(CONF_DEBUG, False)
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "phone_numbers": phone_numbers,
        "external_url": external_url,
        "debug": debug,
    }

    async def async_send_message(call: ServiceCall) -> None:
        """Handle the send_message service call."""
        targets_raw = call.data[ATTR_TARGET]
        message_raw = call.data[ATTR_MESSAGE]
        media_urls_raw = call.data.get(ATTR_MEDIA_URL)
        from_number = call.data[ATTR_FROM_NUMBER]

        targets = [_render_template(hass, t) for t in targets_raw]
        message = _render_template(hass, message_raw)

        media_urls = None
        if media_urls_raw:
            media_urls = [
                _convert_local_path_to_url(hass, _render_template(hass, url))
                for url in media_urls_raw
            ]

        all_numbers = _get_all_phone_numbers(hass)
        if from_number not in all_numbers:
            _LOGGER.error("from_number %s not in configured numbers", from_number)
            return

        entry_client = None
        for entry_data in hass.data.get(DOMAIN, {}).values():
            if from_number in entry_data.get("phone_numbers", []):
                entry_client = entry_data["client"]
                break

        if entry_client is None:
            _LOGGER.error("No client found for from_number %s", from_number)
            return

        for target in targets:
            try:
                if _is_debug_enabled(hass):
                    _LOGGER.warning(
                        "Twilio SMS Debug: Sending to %s from %s with media_urls: %s",
                        target, from_number, media_urls
                    )
                await hass.async_add_executor_job(
                    _send_twilio_message,
                    entry_client,
                    target,
                    message,
                    from_number,
                    media_urls,
                )
                _LOGGER.debug("SMS sent to %s", target)
            except TwilioRestException as err:
                _LOGGER.error("Failed to send SMS to %s: %s", target, err)

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_MESSAGE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_MESSAGE,
            async_send_message,
            schema=_get_service_schema(phone_numbers),
        )

    _update_service_schema(hass)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


def _send_twilio_message(
    client: Client,
    to: str,
    body: str,
    from_number: str,
    media_urls: list[str] | None = None,
) -> None:
    """Send a message via Twilio (blocking)."""
    kwargs: dict[str, Any] = {
        "to": to,
        "from_": from_number,
        "body": body,
    }
    if media_urls:
        kwargs["media_url"] = media_urls

    client.messages.create(**kwargs)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)

    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_SEND_MESSAGE)
    else:
        _update_service_schema(hass)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
