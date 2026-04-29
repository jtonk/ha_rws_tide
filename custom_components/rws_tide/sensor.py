"""Sensor for Rijkswaterstaat tide forecasts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
import logging
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_FORECAST_URL,
    CONF_METADATA_URL,
    CONF_PARAMETER_CODE,
    DEFAULT_FORECAST_URL,
    DEFAULT_METADATA_URL,
    DEFAULT_NAME,
    DEFAULT_PARAMETER_CODE,
    DOMAIN,
    TIDE_SPEED_M_S,
)

_LOGGER = logging.getLogger(__name__)

_REQUEST_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "HomeAssistant-rws_tide",
}

ATTR_REQUESTED_LOCATION = "requested_location"
ATTR_SELECTED_DATAPOINT = "selected_datapoint"
ATTR_TIME_ADJUSTMENT_MINUTES = "time_adjustment_minutes"
ATTR_FORECASTS = "forecasts"
ATTR_DISTANCE_KM = "distance_km"


def setup_platform(hass, config: ConfigType, add_entities: AddEntitiesCallback, discovery_info: DiscoveryInfoType | None = None) -> None:
    """Set up the sensor platform from YAML."""
    name = config.get(CONF_NAME, DEFAULT_NAME)
    latitude = config.get(CONF_LATITUDE)
    longitude = config.get(CONF_LONGITUDE)

    if latitude is None or longitude is None:
        _LOGGER.error("rws_tide requires latitude and longitude in config")
        return

    add_entities([_build_sensor(name, float(latitude), float(longitude), config)], True)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensor from config entry."""
    conf = {**entry.data, **entry.options}
    async_add_entities(
        [
            _build_sensor(
                conf.get(CONF_NAME, DEFAULT_NAME),
                float(conf[CONF_LATITUDE]),
                float(conf[CONF_LONGITUDE]),
                conf,
                entry.entry_id,
            )
        ],
        True,
    )


def _build_sensor(name: str, latitude: float, longitude: float, conf: dict[str, Any], unique_suffix: str | None = None) -> "RwsTideSensor":
    sensor = RwsTideSensor(
        name=name,
        latitude=latitude,
        longitude=longitude,
        parameter_code=conf.get(CONF_PARAMETER_CODE, DEFAULT_PARAMETER_CODE),
        metadata_url=conf.get(CONF_METADATA_URL, DEFAULT_METADATA_URL),
        forecast_url=conf.get(CONF_FORECAST_URL, DEFAULT_FORECAST_URL),
    )
    if unique_suffix:
        sensor._attr_unique_id = f"{DOMAIN}_{unique_suffix}"
    return sensor


@dataclass
class RwsLocation:
    code: str
    name: str
    latitude: float
    longitude: float


class RwsTideSensor(SensorEntity):
    _attr_icon = "mdi:waves"

    def __init__(self, *, name: str, latitude: float, longitude: float, parameter_code: str, metadata_url: str, forecast_url: str) -> None:
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
        try:
            locations = self._fetch_locations()
            closest = self._nearest_location(locations)
            distance_km = _haversine_km(self._requested_lat, self._requested_lon, closest.latitude, closest.longitude)
            shift_minutes = round((distance_km * 1000.0) / TIDE_SPEED_M_S / 60.0)
            raw_forecast = self._fetch_forecast(closest.code)
            adjusted = self._adjust_and_filter_forecast(raw_forecast, shift_minutes)
            self._native_value = len(adjusted)
            self._attr_extra_state_attributes = {
                ATTR_REQUESTED_LOCATION: {"latitude": self._requested_lat, "longitude": self._requested_lon},
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
        payload = {"CatalogusFilter": {"Locaties": True}}
        candidate_urls = [self._metadata_url]
        if self._metadata_url.endswith("/OphalenCatalogus"):
            candidate_urls.append(self._metadata_url.rsplit("/", 1)[0] + "/OphalenLocatieLijst")

        response_payload: dict[str, Any] | None = None
        last_error: Exception | None = None
        for url in candidate_urls:
            try:
                response = requests.post(url, json=payload, headers=_REQUEST_HEADERS, timeout=20)
                response.raise_for_status()
                response_payload = response.json()
                break
            except requests.exceptions.HTTPError as err:
                last_error = err
                if err.response is not None and err.response.status_code == 403:
                    _LOGGER.warning(
                        "RWS metadata endpoint denied access for %s. "
                        "This endpoint is POST-only and may block browser-style checks.",
                        _safe_origin(url),
                    )
                continue

        if response_payload is None:
            if last_error is not None:
                raise last_error
            raise ValueError("Unable to fetch RWS locations from metadata service")

        raw_locations = response_payload.get("LocatieLijst") or response_payload.get("locaties") or []
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
        payload = {"Locatie": {"Code": location_code}, "AquoPlusWaarnemingMetadata": {"AquoMetadata": {"Grootheid": {"Code": self._parameter_code}}}}
        response = requests.post(self._forecast_url, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        return data.get("VerwachtingenLijst") or data.get("WaarnemingenLijst") or data.get("MetingenLijst") or []

    def _nearest_location(self, locations: list[RwsLocation]) -> RwsLocation:
        return min(locations, key=lambda l: _haversine_km(self._requested_lat, self._requested_lon, l.latitude, l.longitude))

    def _adjust_and_filter_forecast(self, records: list[dict[str, Any]], shift_minutes: int) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        limit = now + timedelta(hours=48)
        adjusted: list[dict[str, Any]] = []
        for item in records:
            raw_time = item.get("Tijdstip") or item.get("tijdstip") or item.get("DateTime") or item.get("datetime")
            if not raw_time:
                continue
            parsed_time = _parse_dt(raw_time)
            if parsed_time is None:
                continue
            shifted = parsed_time + timedelta(minutes=shift_minutes)
            if now <= shifted <= limit:
                value = item.get("NumeriekeWaarde") or item.get("Meetwaarde") or item.get("value")
                adjusted.append({"time": shifted.isoformat(), "original_time": parsed_time.isoformat(), "value": value})
        adjusted.sort(key=lambda x: x["time"])
        return adjusted


def _extract_lat_lon(item: dict[str, Any]) -> tuple[float | None, float | None]:
    for lat_key, lon_key in (("Latitude", "Longitude"), ("latitude", "longitude"), ("Lat", "Lon")):
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


def _safe_origin(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
