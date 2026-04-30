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
)
from .api import fetch_available_locations


async def _async_fetch_location_options(hass, metadata_url: str, parameter_code: str) -> dict[str, str]:
    """Fetch the current list of online RWS locations for the selected parameter."""
    locations = await hass.async_add_executor_job(
        fetch_available_locations,
        metadata_url,
        parameter_code,
    )
    return {item.code: item.name for item in locations}


def _resolve_location_value(value: str, location_options: dict[str, str]) -> str | None:
    """Resolve either a location code or a label to the canonical location code."""
    normalized = value.strip().lower()
    if normalized in {code.lower() for code in location_options}:
        for code in location_options:
            if code.lower() == normalized:
                return code
    for code, label in location_options.items():
        if label.lower() == normalized:
            return code
    return None


def _location_schema_field(location_options: dict[str, str]) -> object:
    """Build the location field, preferring a live dropdown when available."""
    if location_options:
        return vol.In(location_options)
    return str


def _default_location_value(current_value: str, location_options: dict[str, str]) -> str:
    """Pick a safe default for the location field."""
    if not location_options:
        return current_value
    if current_value in location_options:
        return current_value
    resolved = _resolve_location_value(current_value, location_options)
    if resolved is not None:
        return resolved
    return next(iter(location_options))


class RwsTideConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an RWS tide config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        current = user_input or {}
        metadata_url = current.get(CONF_METADATA_URL, DEFAULT_METADATA_URL)
        parameter_code = current.get(CONF_PARAMETER_CODE, DEFAULT_PARAMETER_CODE)
        location_options: dict[str, str] = {}

        try:
            location_options = await _async_fetch_location_options(
                self.hass,
                metadata_url,
                parameter_code,
            )
        except Exception:  # pylint: disable=broad-except
            if user_input is None:
                errors["base"] = "cannot_connect"

        if user_input is not None:
            if location_options:
                resolved_location = _resolve_location_value(
                    user_input[CONF_LOCATION_KEY],
                    location_options,
                )
                if resolved_location is None:
                    errors[CONF_LOCATION_KEY] = "invalid_location"
                else:
                    user_input = {**user_input, CONF_LOCATION_KEY: resolved_location}
            if not errors:
                await self.async_set_unique_id(
                    f"{user_input[CONF_LOCATION_KEY]}_{user_input[CONF_PARAMETER_CODE]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=current.get(CONF_NAME, DEFAULT_NAME)): str,
                vol.Required(
                    CONF_LOCATION_KEY,
                    default=_default_location_value(
                        current.get(CONF_LOCATION_KEY, DEFAULT_LOCATION_KEY),
                        location_options,
                    ),
                ): _location_schema_field(location_options),
                vol.Required(
                    CONF_PARAMETER_CODE,
                    default=current.get(CONF_PARAMETER_CODE, DEFAULT_PARAMETER_CODE),
                ): str,
                vol.Required(
                    CONF_METADATA_URL,
                    default=current.get(CONF_METADATA_URL, DEFAULT_METADATA_URL),
                ): str,
                vol.Required(
                    CONF_FORECAST_URL,
                    default=current.get(CONF_FORECAST_URL, DEFAULT_FORECAST_URL),
                ): str,
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
        errors = {}
        if user_input is not None:
            location_options: dict[str, str] = {}
            current_urls = {**self.config_entry.data, **self.config_entry.options}
            metadata_url = current_urls.get(CONF_METADATA_URL, DEFAULT_METADATA_URL)
            try:
                location_options = await _async_fetch_location_options(
                    self.hass,
                    metadata_url,
                    user_input.get(CONF_PARAMETER_CODE, DEFAULT_PARAMETER_CODE),
                )
            except Exception:  # pylint: disable=broad-except
                location_options = {}

            if location_options:
                resolved_location = _resolve_location_value(
                    user_input[CONF_LOCATION_KEY],
                    location_options,
                )
                if resolved_location is None:
                    errors[CONF_LOCATION_KEY] = "invalid_location"
                else:
                    user_input = {**user_input, CONF_LOCATION_KEY: resolved_location}

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        location_options: dict[str, str] = {}
        try:
            location_options = await _async_fetch_location_options(
                self.hass,
                current.get(CONF_METADATA_URL, DEFAULT_METADATA_URL),
                current.get(CONF_PARAMETER_CODE, DEFAULT_PARAMETER_CODE),
            )
        except Exception:  # pylint: disable=broad-except
            errors["base"] = "cannot_connect"
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=current[CONF_NAME]): str,
                vol.Required(
                    CONF_LOCATION_KEY,
                    default=_default_location_value(
                        current.get(CONF_LOCATION_KEY, DEFAULT_LOCATION_KEY),
                        location_options,
                    ),
                ): _location_schema_field(location_options),
                vol.Required(
                    CONF_PARAMETER_CODE,
                    default=current.get(CONF_PARAMETER_CODE, DEFAULT_PARAMETER_CODE),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
