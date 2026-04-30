"""Sensor for Rijkswaterstaat tide forecasts."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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
from .api import RwsLocation, fetch_available_locations, fetch_forecasts

_LOGGER = logging.getLogger(__name__)

ATTR_REQUESTED_LOCATION = "requested_location"
ATTR_SELECTED_DATAPOINT = "selected_datapoint"
ATTR_FORECASTS = "forecasts"


def setup_platform(hass, config: ConfigType, add_entities: AddEntitiesCallback, discovery_info: DiscoveryInfoType | None = None) -> None:
    """Set up the sensor platform from YAML."""
    name = config.get(CONF_NAME, DEFAULT_NAME)
    add_entities([_build_sensor(name, config)], True)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensor from config entry."""
    conf = {**entry.data, **entry.options}
    async_add_entities(
        [
            _build_sensor(
                conf.get(CONF_NAME, DEFAULT_NAME),
                conf,
                entry.entry_id,
            )
        ],
        True,
    )


def _build_sensor(name: str, conf: dict[str, Any], unique_suffix: str | None = None) -> "RwsTideSensor":
    sensor = RwsTideSensor(
        name=name,
        requested_location_key=conf.get(CONF_LOCATION_KEY, DEFAULT_LOCATION_KEY),
        parameter_code=conf.get(CONF_PARAMETER_CODE, DEFAULT_PARAMETER_CODE),
        metadata_url=conf.get(CONF_METADATA_URL, DEFAULT_METADATA_URL),
        forecast_url=conf.get(CONF_FORECAST_URL, DEFAULT_FORECAST_URL),
    )
    if unique_suffix:
        sensor._attr_unique_id = f"{DOMAIN}_{unique_suffix}"
    return sensor


class RwsTideSensor(SensorEntity):
    _attr_icon = "mdi:waves"

    def __init__(self, *, name: str, requested_location_key: str, parameter_code: str, metadata_url: str, forecast_url: str) -> None:
        self._attr_name = name
        self._requested_location_key = requested_location_key
        self._parameter_code = parameter_code
        self._metadata_url = metadata_url
        self._forecast_url = forecast_url
        self._native_value: int | None = None
        self._attr_extra_state_attributes: dict[str, Any] = {}

    @property
    def native_value(self) -> int | None:
        return self._native_value

    def update(self) -> None:
        try:
            locations = fetch_available_locations(
                self._metadata_url,
                self._parameter_code,
            )
            selected_location = self._resolve_location(locations)
            forecasts = fetch_forecasts(
                self._forecast_url,
                selected_location.code,
                self._parameter_code,
            )
            self._native_value = len(forecasts)
            self._attr_extra_state_attributes = {
                ATTR_REQUESTED_LOCATION: self._requested_location_key,
                ATTR_SELECTED_DATAPOINT: {
                    "code": selected_location.code,
                    "name": selected_location.name,
                    "latitude": selected_location.latitude,
                    "longitude": selected_location.longitude,
                },
                ATTR_FORECASTS: forecasts,
            }
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Failed updating RWS tide forecast: %s", err)

    def _resolve_location(self, locations: list[RwsLocation]) -> RwsLocation:
        requested_key = self._requested_location_key.replace("_", " ").lower()
        by_code = {location.code.lower(): location for location in locations}
        by_name = {location.name.lower(): location for location in locations}
        if requested_key in by_code:
            return by_code[requested_key]
        if requested_key in by_name:
            return by_name[requested_key]
        if "scheveningen" in by_code:
            _LOGGER.warning(
                "Configured location '%s' unavailable, falling back to Scheveningen",
                self._requested_location_key,
            )
            return by_code["scheveningen"]
        if "scheveningen" in by_name:
            _LOGGER.warning(
                "Configured location '%s' unavailable, falling back to Scheveningen",
                self._requested_location_key,
            )
            return by_name["scheveningen"]
        return locations[0]
