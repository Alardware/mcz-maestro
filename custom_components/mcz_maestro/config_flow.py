"""Config, options and reconfigure flows."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    CannotConnect,
    NoResponse,
    async_validate,
    normalize_mac,
    normalize_serial,
    stove_id,
)
from .const import (
    CONF_MAC,
    CONF_OVERHEAT_TEMP,
    CONF_SAFETY_DELAY,
    CONF_SAFETY_NOTIFY,
    CONF_SAFETY_OVERHEAT,
    CONF_SAFETY_REVERT,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL,
    CONF_SHUTDOWN_TEMP,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_URL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SAFETY_DEFAULTS,
    VALIDATE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class MaestroConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a stove with its serial number and remote MAC address."""

    VERSION = 1

    async def _validate(self, serial: str, mac: str) -> str | None:
        """Return an error key, or None when the stove answered."""
        try:
            await async_validate(
                async_get_clientsession(self.hass),
                serial,
                mac,
                url=DEFAULT_URL,
                timeout=VALIDATE_TIMEOUT,
            )
        except CannotConnect:
            return "cannot_connect"
        except NoResponse:
            return "no_response"
        except Exception as err:  # noqa: BLE001
            # No traceback: its text could carry the serial or MAC into the log.
            detail = repr(err)
            for secret in (serial, mac, mac.lower()):
                detail = detail.replace(secret, "**REDACTED**")
            _LOGGER.error("Unexpected error while checking the stove: %s", detail)
            return "unknown"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            serial = mac = ""
            try:
                serial = normalize_serial(user_input[CONF_SERIAL])
            except ValueError:
                errors[CONF_SERIAL] = "invalid_serial"
            try:
                mac = normalize_mac(user_input[CONF_MAC])
            except ValueError:
                errors[CONF_MAC] = "invalid_mac"
            if not errors:
                await self.async_set_unique_id(stove_id(serial))
                self._abort_if_unique_id_configured()
                if (error := await self._validate(serial, mac)) is None:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME].strip() or DEFAULT_NAME,
                        data={CONF_SERIAL: serial, CONF_MAC: mac},
                    )
                errors["base"] = error

        values = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=values.get(CONF_NAME, DEFAULT_NAME)): str,
                vol.Required(CONF_SERIAL, default=values.get(CONF_SERIAL, "")): str,
                vol.Required(CONF_MAC, default=values.get(CONF_MAC, "")): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the remote MAC address (e.g. after replacing the Wi-Fi module)."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                mac = normalize_mac(user_input[CONF_MAC])
            except ValueError:
                errors[CONF_MAC] = "invalid_mac"
            else:
                if (error := await self._validate(entry.data[CONF_SERIAL], mac)) is None:
                    return self.async_update_reload_and_abort(
                        entry, data_updates={CONF_MAC: mac}
                    )
                errors["base"] = error
        schema = vol.Schema(
            {vol.Required(CONF_MAC, default=entry.data.get(CONF_MAC, "")): str}
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> MaestroOptionsFlow:
        return MaestroOptionsFlow()


class MaestroOptionsFlow(OptionsFlow):
    """Refresh interval and safety settings."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_SHUTDOWN_TEMP] <= user_input[CONF_OVERHEAT_TEMP]:
                errors[CONF_SHUTDOWN_TEMP] = "shutdown_below_overheat"
            else:
                return self.async_create_entry(data=user_input)
        values = {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            **SAFETY_DEFAULTS,
            **self.config_entry.options,
            **(user_input or {}),
        }

        def req(key: str, validator) -> tuple:
            return vol.Required(key, default=values[key]), validator

        schema = vol.Schema(
            dict(
                (
                    req(
                        CONF_SCAN_INTERVAL,
                        vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
                    ),
                    req(CONF_SAFETY_REVERT, bool),
                    req(CONF_SAFETY_DELAY, vol.All(vol.Coerce(int), vol.Range(min=5, max=480))),
                    req(CONF_SAFETY_OVERHEAT, bool),
                    req(CONF_OVERHEAT_TEMP, vol.All(vol.Coerce(float), vol.Range(min=18, max=40))),
                    req(CONF_SHUTDOWN_TEMP, vol.All(vol.Coerce(float), vol.Range(min=20, max=45))),
                    req(CONF_SAFETY_NOTIFY, bool),
                )
            )
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
