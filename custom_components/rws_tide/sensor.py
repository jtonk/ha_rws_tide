"""Sensor for Rijkswaterstaat tide forecasts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
import logging
from typing import Any

import requests

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "RWS Tide Forecast"
DEFAULT_PARAMETER_CODE = "WATHTE"
DEFAULT_METADATA_URL = (
    "https://waterwebservices.rijkswaterstaat.nl/METADATASERVICES_DBO/OphalenLocatieLijst"
)
DEFAULT_FORECAST_URL = (
    "https://waterwebservices.rijkswaterstaat.nl/ONLINEWAARNEMINGENSERVICES_DBO/OphalenVerwachtingen"
)
DEFAULT_UPDATE_MINUTES = 60
TIDE_SPEED_M_S = 12.0

ATTR_REQUESTED_LOCATION = "requested_location"
ATTR_SELECTED_DATAPOINT = "selected_datapoint"
ATTR_TIME_ADJUSTMENT_MINUTES = "time_adjustment_minutes"
ATTR_FORECASTS = "forecasts"
ATTR_DISTANCE_KM = "distance_km"


def setup_platform(
    hass,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform from YAML."""
    name = config.get(CONF_NAME, DEFAULT_NAME)
    latitude = config.get(CONF_LATITUDE)
    longitude = config.get(CONF_LONGITUDE)

    if latitude is None or longitude is None:
        _LOGGER.error("rws_tide requires latitude and longitude in config")
        return

    parameter_code = config.get("parameter_code", DEFAULT_PARAMETER_CODE)
    metadata_url = config.get("metadata_url", DEFAULT_METADATA_URL)
    forecast_url = config.get("forecast_url", DEFAULT_FORECAST_URL)
    add_entities(
        [
            RwsTideSensor(
                name=name,
                latitude=float(latitude),
                longitude=float(longitude),
                parameter_code=parameter_code,
                metadata_url=metadata_url,
                forecast_url=forecast_url,
            )
        ],
        True,
    )


@dataclass
class RwsLocation:
    code: str
    name: str
    latitude: float
    longitude: float


class RwsTideSensor(SensorEntity):
    """RWS tide forecast sensor entity."""

    _attr_icon = "mdi:waves"

    def __init__(
        self,
        *,
        name: str,
        latitude: float,
        longitude: float,
        parameter_code: str,
        metadata_url: str,
        forecast_url: str,
    ) -> None:
        self._attr_name = name
        self._requested_lat = latitude
        self._requested_lon = longitude
        self._parameter_code = parameter_code
        self._metadata_url = metadata_url
        self._forecast_url = forecast_url
        self._native_value: int | None = None
        self._attr_extra_state_attributes: dict[str, Any] = {}

    @property
    def native_value(self) -> int | None:
        return self._native_value

    def update(self) -> None:
        """Fetch forecast for the next 48 hours."""
        try:
            locations = self._fetch_locations()
            closest = self._nearest_location(locations)
            distance_km = _haversine_km(
                self._requested_lat,
                self._requested_lon,
                closest.latitude,
                closest.longitude,
            )
            shift_minutes = round((distance_km * 1000.0) / TIDE_SPEED_M_S / 60.0)
            raw_forecast = self._fetch_forecast(closest.code)
            adjusted = self._adjust_and_filter_forecast(raw_forecast, shift_minutes)
            self._native_value = len(adjusted)
            self._attr_extra_state_attributes = {
                ATTR_REQUESTED_LOCATION: {
                    "latitude": self._requested_lat,
                    "longitude": self._requested_lon,
                },
                ATTR_SELECTED_DATAPOINT: {
                    "code": closest.code,
                    "name": closest.name,
                    "latitude": closest.latitude,
                    "longitude": closest.longitude,
                },
                ATTR_DISTANCE_KM: round(distance_km, 3),
                ATTR_TIME_ADJUSTMENT_MINUTES: shift_minutes,
                ATTR_FORECASTS: adjusted,
            }
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Failed updating RWS tide forecast: %s", err)

    def _fetch_locations(self) -> list[RwsLocation]:
        response = requests.post(self._metadata_url, json={}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        raw_locations = payload.get("LocatieLijst") or payload.get("locaties") or []

        parsed: list[RwsLocation] = []
        for item in raw_locations:
            lat, lon = _extract_lat_lon(item)
            if lat is None or lon is None:
                continue
            code = item.get("Code") or item.get("code")
            if not code:
                continue
            name = item.get("Naam") or item.get("name") or code
            parsed.append(RwsLocation(code=code, name=name, latitude=lat, longitude=lon))

        if not parsed:
            raise ValueError("No mappable RWS locations returned")
        return parsed

    def _fetch_forecast(self, location_code: str) -> list[dict[str, Any]]:
        payload = {
            "Locatie": {"Code": location_code},
            "AquoPlusWaarnemingMetadata": {"AquoMetadata": {"Grootheid": {"Code": self._parameter_code}}},
        }
        response = requests.post(self._forecast_url, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        # Endpoint structures vary. Support common variants.
        return (
            data.get("VerwachtingenLijst")
            or data.get("WaarnemingenLijst")
            or data.get("MetingenLijst")
            or []
        )

    def _nearest_location(self, locations: list[RwsLocation]) -> RwsLocation:
        return min(
            locations,
            key=lambda l: _haversine_km(
                self._requested_lat, self._requested_lon, l.latitude, l.longitude
            ),
        )

    def _adjust_and_filter_forecast(
        self, records: list[dict[str, Any]], shift_minutes: int
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        limit = now + timedelta(hours=48)
        adjusted: list[dict[str, Any]] = []
        for item in records:
            raw_time = (
                item.get("Tijdstip")
                or item.get("tijdstip")
                or item.get("DateTime")
                or item.get("datetime")
            )
            if not raw_time:
                continue
            parsed_time = _parse_dt(raw_time)
            if parsed_time is None:
                continue
            shifted = parsed_time + timedelta(minutes=shift_minutes)
            if now <= shifted <= limit:
                value = item.get("NumeriekeWaarde") or item.get("Meetwaarde") or item.get("value")
                adjusted.append(
                    {
                        "time": shifted.isoformat(),
                        "original_time": parsed_time.isoformat(),
                        "value": value,
                    }
                )
        adjusted.sort(key=lambda x: x["time"])
        return adjusted


def _extract_lat_lon(item: dict[str, Any]) -> tuple[float | None, float | None]:
    for lat_key, lon_key in (
        ("Latitude", "Longitude"),
        ("latitude", "longitude"),
        ("Lat", "Lon"),
    ):
        if lat_key in item and lon_key in item:
            return float(item[lat_key]), float(item[lon_key])

    geo = item.get("GeoCoordinaat") or item.get("geo") or {}
    lat = geo.get("Latitude") or geo.get("latitude")
    lon = geo.get("Longitude") or geo.get("longitude")
    if lat is not None and lon is not None:
        return float(lat), float(lon)

    return None, None


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_km = 6371.0088
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r_km * asin(sqrt(a))
