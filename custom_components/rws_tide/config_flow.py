"""Config flow for RWS tide integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import (
    CONF_FORECAST_URL,
    CONF_LOCATION_KEY,
    CONF_METADATA_URL,
    CONF_PARAMETER_CODE,
    DEFAULT_FORECAST_URL,
    DEFAULT_LOCATION_KEY,
    DEFAULT_METADATA_URL,
    DEFAULT_NAME,
    DEFAULT_PARAMETER_CODE,
    DOMAIN,
    KNOWN_RWS_LOCATIONS,
)


class RwsTideConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an RWS tide config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_LOCATION_KEY]}_{user_input[CONF_PARAMETER_CODE]}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_LOCATION_KEY, default=DEFAULT_LOCATION_KEY): vol.In(KNOWN_RWS_LOCATIONS),
                vol.Required(CONF_PARAMETER_CODE, default=DEFAULT_PARAMETER_CODE): str,
                vol.Required(CONF_METADATA_URL, default=DEFAULT_METADATA_URL): str,
                vol.Required(CONF_FORECAST_URL, default=DEFAULT_FORECAST_URL): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return RwsTideOptionsFlow(config_entry)


class RwsTideOptionsFlow(config_entries.OptionsFlow):
    """Handle options for RWS tide."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=current[CONF_NAME]): str,
                vol.Required(
                    CONF_LOCATION_KEY,
                    default=current.get(CONF_LOCATION_KEY, DEFAULT_LOCATION_KEY),
                ): vol.In(KNOWN_RWS_LOCATIONS),
                vol.Required(
                    CONF_PARAMETER_CODE,
                    default=current.get(CONF_PARAMETER_CODE, DEFAULT_PARAMETER_CODE),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
