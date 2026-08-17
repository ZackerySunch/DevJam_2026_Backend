"""
Public WiFi hotspot queries, backing routers/public_wifi.py.

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

from Feature.base_tower_density import COUNTY_LIST, COUNTY_FULL_TO_INDEX

load_dotenv()

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "wifi_hotspots.json"
_hotspots = json.loads(DATA_PATH.read_text(encoding="utf-8"))

EARTH_RADIUS_M = 6_371_000
NEARBY_RADIUS_OPTIONS_M = [500, 1000, 2000]  # presets shown to the end user

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


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
        idx = COUNTY_FULL_TO_INDEX.get(r["area"])
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


def hotspots_in_district(county: int, district: str | None = None) -> list[dict]:
    """Hotspot markers for one county, optionally narrowed to one district."""
    if not (0 <= county < len(COUNTY_LIST)):
        raise ValueError(f"unknown county index: {county}")
    full_county = COUNTY_LIST[county]

    results = [r for r in _hotspots if r["area"] == full_county]
    if district is not None:
        results = [r for r in results if r["district"] == district]
    return results


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


def geocode(query: str) -> tuple[float, float]:
    """Resolves free text (a place name/address) to (lat, lng) via Google's
    Geocoding API. Requires GOOGLE_MAPS_API_KEY in the environment/.env."""
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not set (check .env)")

    resp = requests.get(
        GOOGLE_GEOCODE_URL,
        params={"address": query, "key": api_key, "region": "tw"},
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()

    if data["status"] != "OK" or not data["results"]:
        raise ValueError(f"could not geocode '{query}' (status: {data['status']})")

    location = data["results"][0]["geometry"]["location"]
    return location["lat"], location["lng"]


def search_nearby_by_text(query: str, radius_m: int) -> list[dict]:
    """Geocodes free text to coordinates, then finds nearby hotspots."""
    lat, lng = geocode(query)
    return nearby_hotspots(lat, lng, radius_m)
