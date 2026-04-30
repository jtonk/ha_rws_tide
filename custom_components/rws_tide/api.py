"""Helpers for the current RWS WaterWebservices API."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import requests

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
DEFAULT_COMPARTMENT_CODE = "OW"
DEFAULT_PROCESS_TYPE = "verwachting"
_CATALOG_CACHE_TTL = timedelta(hours=12)
_CATALOG_FILTER_PAYLOAD = {
    "CatalogusFilter": {
        "Compartimenten": True,
        "Grootheden": True,
        "ProcesTypes": True,
    }
}
_REQUEST_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "HomeAssistant-rws_tide",
    "X-API-KEY": "HomeAssistant-rws_tide",
}
_catalog_cache: dict[str, tuple[datetime, dict[str, Any]]] = {}


@dataclass(frozen=True)
class RwsLocation:
    code: str
    name: str
    latitude: float | None = None
    longitude: float | None = None


def fetch_available_locations(
    metadata_url: str,
    parameter_code: str,
    *,
    process_type: str = DEFAULT_PROCESS_TYPE,
    compartment_code: str = DEFAULT_COMPARTMENT_CODE,
) -> list[RwsLocation]:
    """Return the online locations that support the requested metadata."""
    catalog = _fetch_catalog(metadata_url)
    metadata_ids = {
        item["AquoMetadata_MessageID"]
        for item in catalog.get("AquoMetadataLijst", [])
        if item.get("Grootheid", {}).get("Code") == parameter_code
        and item.get("ProcesType") == process_type
        and item.get("Compartiment", {}).get("Code") in (None, compartment_code)
    }
    if not metadata_ids:
        raise ValueError(
            f"No RWS metadata entries found for parameter={parameter_code!r} "
            f"and process_type={process_type!r}"
        )

    location_ids = {
        item.get("Locatie_MessageID")
        for item in catalog.get("AquoMetadataLocatieLijst", [])
        if item.get("AquoMetaData_MessageID") in metadata_ids
    }
    if not location_ids:
        raise ValueError(
            f"No RWS locations linked to parameter={parameter_code!r} "
            f"and process_type={process_type!r}"
        )

    parsed: list[RwsLocation] = []
    seen_codes: set[str] = set()
    for item in catalog.get("LocatieLijst", []):
        if item.get("Locatie_MessageID") not in location_ids:
            continue
        code = item.get("Code") or item.get("code")
        if not code or code in seen_codes:
            continue
        lat, lon = _extract_lat_lon(item)
        name = item.get("Naam") or item.get("name") or code
        parsed.append(RwsLocation(code=code, name=name, latitude=lat, longitude=lon))
        seen_codes.add(code)

    if not parsed:
        raise ValueError("No usable RWS locations returned for the selected metadata")

    parsed.sort(key=lambda item: item.name.lower())
    return parsed


def fetch_forecasts(
    forecast_url: str,
    location_code: str,
    parameter_code: str,
    *,
    process_type: str = DEFAULT_PROCESS_TYPE,
    compartment_code: str = DEFAULT_COMPARTMENT_CODE,
    hours_ahead: int = 48,
) -> list[dict[str, Any]]:
    """Fetch and normalize forecast measurements for a single location."""
    now = datetime.now().astimezone()
    period_start = now - timedelta(minutes=10)
    period_end = now + timedelta(hours=hours_ahead)
    payload = {
        "Locatie": {"Code": location_code},
        "AquoPlusWaarnemingMetadata": {
            "AquoMetadata": {
                "Compartiment": {"Code": compartment_code},
                "Grootheid": {"Code": parameter_code},
                "ProcesType": process_type,
            }
        },
        "Periode": {
            "Begindatumtijd": _format_dt(period_start),
            "Einddatumtijd": _format_dt(period_end),
        },
    }

    response = requests.post(
        forecast_url,
        json=payload,
        headers=_REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code == 204:
        return []
    response.raise_for_status()
    data = response.json()

    records: list[dict[str, Any]] = []
    for series in data.get("WaarnemingenLijst", []):
        for item in series.get("MetingenLijst", []):
            raw_time = item.get("Tijdstip") or item.get("tijdstip")
            if not raw_time:
                continue
            parsed_time = _parse_dt(raw_time)
            if parsed_time is None:
                continue
            if not period_start.astimezone(timezone.utc) <= parsed_time <= period_end.astimezone(timezone.utc):
                continue
            value = item.get("Meetwaarde", {}).get("Waarde_Numeriek")
            if value is None:
                value = item.get("Meetwaarde", {}).get("Waarde_Alfanumeriek")
            records.append({"time": parsed_time.isoformat(), "value": value})

    records.sort(key=lambda item: item["time"])
    return records


def _fetch_catalog(metadata_url: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cached = _catalog_cache.get(metadata_url)
    if cached and now - cached[0] < _CATALOG_CACHE_TTL:
        return cached[1]

    response = requests.post(
        metadata_url,
        json=_CATALOG_FILTER_PAYLOAD,
        headers=_REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    _catalog_cache[metadata_url] = (now, payload)
    return payload


def _extract_lat_lon(item: dict[str, Any]) -> tuple[float | None, float | None]:
    for lat_key, lon_key in (
        ("Lat", "Lon"),
        ("Latitude", "Longitude"),
        ("latitude", "longitude"),
    ):
        if lat_key in item and lon_key in item:
            return float(item[lat_key]), float(item[lon_key])
    geo = item.get("GeoCoordinaat") or item.get("geo") or {}
    lat = geo.get("Latitude") or geo.get("latitude")
    lon = geo.get("Longitude") or geo.get("longitude")
    if lat is not None and lon is not None:
        return float(lat), float(lon)
    return None, None


def _format_dt(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds")


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        _LOGGER.debug("Could not parse RWS timestamp %s", value)
        return None
