"""RWS live location smoke test for Katwijk aan Zee.

Usage:
  python scripts_simulate_katwijk_mapping.py --offline
  python scripts_simulate_katwijk_mapping.py --live
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt

METADATA_URL = "https://ddapi20-waterwebservices.rijkswaterstaat.nl/METADATASERVICES/OphalenCatalogus"
FORECAST_URL = "https://ddapi20-waterwebservices.rijkswaterstaat.nl/ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "HomeAssistant-rws_tide",
    "X-API-KEY": "HomeAssistant-rws_tide",
}


def extract_lat_lon(item: dict):
    for lat_key, lon_key in (("Latitude", "Longitude"), ("latitude", "longitude"), ("Lat", "Lon")):
        if lat_key in item and lon_key in item:
            return float(item[lat_key]), float(item[lon_key])
    geo = item.get("GeoCoordinaat") or item.get("geo") or {}
    lat = geo.get("Latitude") or geo.get("latitude")
    lon = geo.get("Longitude") or geo.get("longitude")
    if lat is not None and lon is not None:
        return float(lat), float(lon)
    return None, None


def haversine_km(lat1, lon1, lat2, lon2):
    r_km = 6371.0088
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r_km * asin(sqrt(a))


def fetch_live_metadata() -> dict:
    payload = {
        "CatalogusFilter": {
            "Compartimenten": True,
            "Grootheden": True,
            "ProcesTypes": True,
        }
    }
    request = urllib.request.Request(
        METADATA_URL,
        data=json.dumps(payload).encode(),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def fetch_live_forecast(location_code: str) -> list[dict]:
    now = datetime.now().astimezone()
    payload = {
        "Locatie": {"Code": location_code},
        "AquoPlusWaarnemingMetadata": {
            "AquoMetadata": {
                "Compartiment": {"Code": "OW"},
                "Grootheid": {"Code": "WATHTE"},
                "ProcesType": "verwachting",
            }
        },
        "Periode": {
            "Begindatumtijd": (now - timedelta(hours=24)).isoformat(timespec="milliseconds"),
            "Einddatumtijd": (now + timedelta(hours=48)).isoformat(timespec="milliseconds"),
        },
    }
    request = urllib.request.Request(
        FORECAST_URL,
        data=json.dumps(payload).encode(),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode())
    measurements = []
    for series in data.get("WaarnemingenLijst", []):
        measurements.extend(series.get("MetingenLijst", []))
    return measurements


def select_closest(metadata_payload: dict) -> tuple[str, str, float]:
    katwijk_aan_zee = (52.2033, 4.3986)
    metadata_by_id = {
        item["AquoMetadata_MessageID"]: item
        for item in metadata_payload.get("AquoMetadataLijst", [])
    }
    valid_location_ids = {
        item.get("Locatie_MessageID")
        for item in metadata_payload.get("AquoMetadataLocatieLijst", [])
        if metadata_by_id.get(item.get("AquoMetaData_MessageID"), {}).get("Grootheid", {}).get("Code")
        == "WATHTE"
        and metadata_by_id.get(item.get("AquoMetaData_MessageID"), {}).get("ProcesType") == "verwachting"
        and metadata_by_id.get(item.get("AquoMetaData_MessageID"), {}).get("Compartiment", {}).get("Code") in ("OW", None)
    }
    parsed = []
    for item in metadata_payload.get("LocatieLijst") or []:
        if item.get("Locatie_MessageID") not in valid_location_ids:
            continue
        code = item.get("Code") or item.get("code")
        lat, lon = extract_lat_lon(item)
        if code and lat is not None and lon is not None:
            parsed.append((code, item.get("Naam") or code, lat, lon))
    closest = min(parsed, key=lambda l: haversine_km(katwijk_aan_zee[0], katwijk_aan_zee[1], l[2], l[3]))
    distance = round(haversine_km(katwijk_aan_zee[0], katwijk_aan_zee[1], closest[2], closest[3]), 3)
    return closest[0], closest[1], distance


def offline_metadata() -> dict:
    return {
        "AquoMetadataLijst": [
            {
                "AquoMetadata_MessageID": 1,
                "Compartiment": {"Code": "OW"},
                "Grootheid": {"Code": "WATHTE"},
                "ProcesType": "verwachting",
            }
        ],
        "AquoMetadataLocatieLijst": [
            {"AquoMetaData_MessageID": 1, "Locatie_MessageID": 10},
            {"AquoMetaData_MessageID": 1, "Locatie_MessageID": 20},
            {"AquoMetaData_MessageID": 1, "Locatie_MessageID": 30},
        ],
        "LocatieLijst": [
            {"Locatie_MessageID": 10, "Code": "hoekvanholland", "Naam": "Hoek van Holland", "Lat": 51.98, "Lon": 4.12},
            {"Locatie_MessageID": 20, "Code": "katwijkbinnen", "Naam": "Katwijk binnen", "Lat": 52.2033, "Lon": 4.3986},
            {"Locatie_MessageID": 30, "Code": "scheveningen", "Naam": "Scheveningen", "Lat": 52.11, "Lon": 4.28},
        ]
    }


def offline_forecast() -> list[dict]:
    return [
        {
            "Tijdstip": "2026-04-30T00:00:00.000+02:00",
            "Meetwaarde": {"Waarde_Numeriek": -12.0},
        },
        {
            "Tijdstip": "2026-04-30T00:10:00.000+02:00",
            "Meetwaarde": {"Waarde_Numeriek": -10.0},
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    use_live = args.live and not args.offline
    try:
        payload = fetch_live_metadata() if use_live else offline_metadata()
    except urllib.error.URLError as err:
        print(f"Live fetch failed: {err}")
        return 2

    code, name, distance = select_closest(payload)
    print("Closest code:", code)
    print("Closest name:", name)
    print("Distance km:", distance)
    forecast = fetch_live_forecast(code) if use_live else offline_forecast()
    print("Forecast points:", len(forecast))
    if forecast:
        first = forecast[0]
        value = first.get("Meetwaarde", {}).get("Waarde_Numeriek")
        print("First forecast time:", first.get("Tijdstip"))
        print("First forecast value:", value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
