"""RWS location-mapping smoke test for Katwijk aan Zee.

Usage:
  python scripts_simulate_katwijk_mapping.py --offline
  python scripts_simulate_katwijk_mapping.py --live
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from math import asin, cos, radians, sin, sqrt

METADATA_URL = "https://waterwebservices.rijkswaterstaat.nl/METADATASERVICES_DBO/OphalenCatalogus"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "HomeAssistant-rws_tide",
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
    payload = {"CatalogusFilter": {"Locaties": True}}
    request = urllib.request.Request(
        METADATA_URL,
        data=json.dumps(payload).encode(),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def select_closest(metadata_payload: dict) -> tuple[str, str, float]:
    katwijk_aan_zee = (52.2033, 4.3986)
    locations = metadata_payload.get("LocatieLijst") or metadata_payload.get("locaties") or []
    parsed = []
    for item in locations:
        code = item.get("Code") or item.get("code")
        lat, lon = extract_lat_lon(item)
        if code and lat is not None and lon is not None:
            parsed.append((code, item.get("Naam") or code, lat, lon))
    closest = min(parsed, key=lambda l: haversine_km(katwijk_aan_zee[0], katwijk_aan_zee[1], l[2], l[3]))
    distance = round(haversine_km(katwijk_aan_zee[0], katwijk_aan_zee[1], closest[2], closest[3]), 3)
    return closest[0], closest[1], distance


def offline_metadata() -> dict:
    return {
        "LocatieLijst": [
            {"Code": "HOEKVHLD", "Naam": "Hoek van Holland", "GeoCoordinaat": {"Latitude": 51.98, "Longitude": 4.12}},
            {"Code": "KATWKBNN", "Naam": "Katwijk binnen", "GeoCoordinaat": {"Latitude": 52.2033, "Longitude": 4.3986}},
            {"Code": "SCHEVNGN", "Naam": "Scheveningen", "GeoCoordinaat": {"Latitude": 52.11, "Longitude": 4.28}},
        ]
    }


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
