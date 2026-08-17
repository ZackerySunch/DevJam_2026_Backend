"""
Navigator (主題3: 公共 WiFi × AI 嚮導) queries, backing routers/navigator.py.

Flow: county overview (counts per county) -> pick a county -> district
breakdown -> pick a district -> hotspot markers. Also supports free-text /
lat-lng "find nearby hotspots" search (text queries go through Google's
Geocoding API to resolve to coordinates first).
"""
import json
import math
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from Feature.density import COUNTY_LIST, COUNTY_FULL_TO_INDEX

load_dotenv()

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "wifi_hotspots.json"
_raw_hotspots = json.loads(DATA_PATH.read_text(encoding="utf-8"))
_hotspots = [
    {**r, "county_id": COUNTY_FULL_TO_INDEX.get(r.get("area"))}
    for r in _raw_hotspots
]

EARTH_RADIUS_M = 6_371_000
NEARBY_RADIUS_OPTIONS_M = [500, 1000, 2000]  # presets shown to the end user

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Same 台/臺 normalization used in scripts/prepare_data.py and
# scripts/geocode_stations.py, so Google's result lines up with COUNTY_LIST.
COUNTY_NAME_ALIASES = {
    "台北市": "臺北市", "台中市": "臺中市", "台南市": "臺南市", "台東縣": "臺東縣",
}


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def county_counts() -> dict:
    """{"0": count, ..., "21": count} hotspot count per county (all sources)."""
    counts = {str(i): 0 for i in range(len(COUNTY_LIST))}
    for r in _hotspots:
        idx = r.get("county_id")
        if idx is not None:
            counts[str(idx)] += 1
    return counts


def district_counts(county: int) -> dict:
    """{district_name: count} within one county. Hotspots with no parseable
    district (a handful of malformed source addresses) are grouped as "未分類"."""
    if not (0 <= county < len(COUNTY_LIST)):
        raise ValueError(f"unknown county index: {county}")
    full_county = COUNTY_LIST[county]

    counts: dict[str, int] = {}
    for r in _hotspots:
        if r["area"] != full_county:
            continue
        district = r["district"] or "未分類"
        counts[district] = counts.get(district, 0) + 1
    return counts


def _format_hotspot(r: dict) -> dict:
    return {
        "source": r["source"],
        "name": r["name"],
        "address": r["address"],
        "latitude": r["lat"],
        "longtitude": r["lng"],
    }


def hotspots_in_district(county: int | None = None, district: str | None = None) -> list[dict]:
    """Hotspot markers for all Taiwan (if county is None or -1), or for one county,
    optionally narrowed to one district. Returns only source, name, address, latitude, longtitude."""
    if county is None or county == -1:
        if district is not None:
            return [_format_hotspot(r) for r in _hotspots if r.get("district") == district]
        return [_format_hotspot(r) for r in _hotspots]

    if not (0 <= county < len(COUNTY_LIST)):
        raise ValueError(f"unknown county index: {county} (must be 0-21, or -1/omit for all)")
    full_county = COUNTY_LIST[county]

    results = [r for r in _hotspots if r.get("area") == full_county]
    if district is not None:
        results = [r for r in results if r.get("district") == district]
    return [_format_hotspot(r) for r in results]


def nearby_hotspots(lat: float, lng: float, radius_m: int) -> list[dict]:
    """Hotspots within radius_m of (lat, lng), nearest first."""
    if radius_m not in NEARBY_RADIUS_OPTIONS_M:
        raise ValueError(f"radius_m must be one of {NEARBY_RADIUS_OPTIONS_M}")

    results = []
    for r in _hotspots:
        d = haversine_m(lat, lng, r["lat"], r["lng"])
        if d <= radius_m:
            results.append({**r, "distance_m": round(d, 1)})
    results.sort(key=lambda r: r["distance_m"])
    return results


def geocode(query: str) -> dict:
    """Resolves free text (a place name/address) to a center point and, if
    resolvable, which of our 22 counties it falls in. Requires
    GOOGLE_MAPS_API_KEY in the environment/.env."""
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not set (check .env)")

    resp = requests.get(
        GOOGLE_GEOCODE_URL,
        params={"address": query, "key": api_key, "region": "tw", "language": "zh-TW"},
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()

    if data["status"] != "OK" or not data["results"]:
        raise ValueError(f"could not geocode '{query}' (status: {data['status']})")

    result = data["results"][0]
    location = result["geometry"]["location"]

    county_name = None
    for component in result["address_components"]:
        if "administrative_area_level_1" in component["types"]:
            county_name = COUNTY_NAME_ALIASES.get(component["long_name"], component["long_name"])
            break

    return {
        "lat": location["lat"],
        "lng": location["lng"],
        "county": COUNTY_FULL_TO_INDEX.get(county_name),
    }


def search_by_text(query: str) -> dict:
    """Geocodes free text to a center point, then returns every hotspot in
    that county — no backend distance filtering; the frontend's own map
    library handles "nearby" from here using `center` to zoom/search."""
    located = geocode(query)
    if located["county"] is None:
        raise ValueError(f"'{query}' did not resolve to one of the 22 counties")

    return {
        "center": {"lat": located["lat"], "lng": located["lng"]},
        "county": located["county"],
        "hotspots": hotspots_in_district(located["county"]),
    }
