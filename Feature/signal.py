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
from pathlib import Path

import requests
from dotenv import load_dotenv

from Feature.density import COUNTY_LIST, COUNTY_FULL_TO_INDEX

load_dotenv()

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "base_station_location.json"
_stations = json.loads(DATA_PATH.read_text(encoding="utf-8"))

CLOUDFLARE_RADAR_URL = "https://api.cloudflare.com/client/v4/radar/http/timeseries"
DEFAULT_COUNTY = COUNTY_FULL_TO_INDEX["臺北市"]


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


def traffic_pulse(hours: int = 24) -> dict:
    """Taiwan-wide HTTP request volume over the last `hours`, plus a 0-1
    `intensity` score (latest value normalized against the window's min/max)
    the frontend can use to drive pillar pulse strength."""
    token = os.environ.get("CLOUDFLARE_RADAR_TOKEN")
    if not token:
        raise RuntimeError("CLOUDFLARE_RADAR_TOKEN is not set (check .env)")

    # Radar's dateRange only accepts day/week units (e.g. "1d", "7d"), not hours.
    date_range_days = max(1, round(hours / 24))

    resp = requests.get(
        CLOUDFLARE_RADAR_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={"location": "TW", "dateRange": f"{date_range_days}d", "aggInterval": "1h", "format": "json"},
        timeout=5,
    )
    if not resp.ok:
        raise RuntimeError(f"Cloudflare Radar request failed ({resp.status_code}): {resp.text}")
    data = resp.json()

    if not data.get("success"):
        raise RuntimeError(f"Cloudflare Radar request failed: {data.get('errors')}")

    series = data["result"]["serie_0"]
    timestamps = series["timestamps"]
    values = [float(v) for v in series["values"]]

    lo, hi = min(values), max(values)
    intensity = (values[-1] - lo) / (hi - lo) if hi > lo else 0.0

    return {
        "timestamps": timestamps,
        "values": values,
        "intensity": round(intensity, 3),
    }
