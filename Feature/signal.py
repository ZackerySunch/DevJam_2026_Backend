"""
Signal (主題1: 基地台位置 × 網路流向圖) queries, backing routers/signal.py.

Two pieces: (1) all base station coordinates for the 3D light-pillar map, and
(2) a nationwide traffic "pulse intensity" from Cloudflare Radar, applied
uniformly across every pillar (Radar only has country/ASN-level granularity
for Taiwan, not per-county, so there is no way to flicker individual regions
independently with this data source).
"""
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from Feature.density import COUNTY_LIST, COUNTY_FULL_TO_INDEX

load_dotenv()

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "base_station_location.json"
_stations = json.loads(DATA_PATH.read_text(encoding="utf-8"))

CLOUDFLARE_RADAR_URL = "https://api.cloudflare.com/client/v4/radar/http/timeseries"
DEFAULT_COUNTY = COUNTY_FULL_TO_INDEX["臺北市"]

# Radar's finest granularity is 15-minute buckets, so there's no point asking
# more often than that — cache the last fetch and serve it to any number of
# frontend polls (every second, if it wants) in between.
TRAFFIC_CACHE_TTL_SECONDS = 15 * 60
_traffic_cache: dict | None = None
_traffic_cache_at: float = 0.0


def station_locations(county: int = DEFAULT_COUNTY) -> list[dict]:
    """Base station light-pillar coordinates for one county (defaults to
    臺北市). Pass county=-1 to get every station in Taiwan (10,733 points).

    OpenCelliD has no address text, so county comes from a one-time Google
    reverse-geocode pass (scripts/geocode_stations.py) baked into the
    processed data; ~15 stations with no match are excluded from every
    county filter (they still show up in the county=-1 "all" view)."""
    if county == -1:
        return _stations
    if not (0 <= county < len(COUNTY_LIST)):
        raise ValueError(f"unknown county index: {county}")
    full_county = COUNTY_LIST[county]
    return [s for s in _stations if s["county"] == full_county]


def traffic_pulse() -> dict:
    """Current Taiwan-wide HTTP traffic level as a single number — bigger
    when traffic is higher, smaller when lower (Cloudflare's own
    percentage-normalized value, most recent 15-minute data point).

    Cached for TRAFFIC_CACHE_TTL_SECONDS so the frontend can poll this as
    often as it wants (every second, if it wants a "live" feel) without
    hammering Cloudflare's API — the underlying data itself only changes
    every 15 minutes regardless of how often this is called."""
    global _traffic_cache, _traffic_cache_at

    now = time.monotonic()
    if _traffic_cache is not None and (now - _traffic_cache_at) < TRAFFIC_CACHE_TTL_SECONDS:
        return _traffic_cache

    token = os.environ.get("CLOUDFLARE_RADAR_TOKEN")
    if not token:
        raise RuntimeError("CLOUDFLARE_RADAR_TOKEN is not set (check .env)")

    resp = requests.get(
        CLOUDFLARE_RADAR_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={"location": "TW", "dateRange": "1d", "aggInterval": "15m", "format": "json"},
        timeout=5,
    )
    if not resp.ok:
        raise RuntimeError(f"Cloudflare Radar request failed ({resp.status_code}): {resp.text}")
    data = resp.json()

    if not data.get("success"):
        raise RuntimeError(f"Cloudflare Radar request failed: {data.get('errors')}")

    series = data["result"]["serie_0"]

    _traffic_cache = {
        "value": float(series["values"][-1]),
        "timestamp": series["timestamps"][-1],
    }
    _traffic_cache_at = now
    return _traffic_cache
