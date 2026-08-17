"""
One-time enrichment: reverse-geocodes each base station's county via Google
Maps (OpenCelliD points have no address text to parse, unlike the WiFi
datasets, so there's no free alternative to an actual geocoding call).

Results are cached in data/base_station_location/county_cache.json, keyed by
"lat,lng", so re-running this only geocodes points that aren't cached yet
(e.g. after adding more stations) or that failed last time (cached as null).
Safe/cheap to re-run.

Run:
    python scripts/geocode_stations.py
"""
import concurrent.futures
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIONS_PATH = BASE_DIR / "data" / "processed" / "base_station_location.json"
CACHE_PATH = BASE_DIR / "data" / "base_station_location" / "county_cache.json"

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
RETRYABLE_STATUSES = {"OVER_QUERY_LIMIT", "UNKNOWN_ERROR"}

COUNTY_ALIASES = {
    "台北市": "臺北市", "台中市": "臺中市", "台南市": "臺南市", "台東縣": "臺東縣",
}


def normalize_county(name: str) -> str:
    return COUNTY_ALIASES.get(name, name)


def reverse_geocode_county(lat: float, lng: float, api_key: str) -> str | None:
    for attempt in range(5):
        resp = requests.get(
            GOOGLE_GEOCODE_URL,
            params={
                "latlng": f"{lat},{lng}",
                "key": api_key,
                "language": "zh-TW",
                "result_type": "administrative_area_level_1",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data["status"]

        if status == "OK":
            for component in data["results"][0]["address_components"]:
                if "administrative_area_level_1" in component["types"]:
                    return normalize_county(component["long_name"])
            return None
        if status == "ZERO_RESULTS":
            return None
        if status in RETRYABLE_STATUSES:
            time.sleep(0.5 * (2 ** attempt))
            continue
        raise RuntimeError(f"geocode failed for {lat},{lng}: {status}")

    raise RuntimeError(f"geocode failed for {lat},{lng}: exhausted retries")


def main():
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not set (check .env)")

    stations = json.loads(STATIONS_PATH.read_text(encoding="utf-8"))
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}

    all_keys = {f"{s['lat']},{s['lng']}" for s in stations}
    # Retry anything missing OR previously failed (cached as null).
    to_fetch = sorted(k for k in all_keys if cache.get(k) is None)
    print(f"{len(stations)} stations, {len(to_fetch)} need geocoding "
          f"({len(cache) - sum(1 for v in cache.values() if v is None)} already cached with a result)")

    def fetch(key: str):
        lat, lng = map(float, key.split(","))
        try:
            return key, reverse_geocode_county(lat, lng, api_key), None
        except Exception as e:
            return key, None, str(e)

    errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for i, (key, county, err) in enumerate(pool.map(fetch, to_fetch)):
            cache[key] = county
            if err:
                errors.append((key, err))
            if (i + 1) % 500 == 0:
                print(f"  {i + 1}/{len(to_fetch)} done ({len(errors)} errors so far)")
                CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"cache saved -> {CACHE_PATH}")

    missing = sum(1 for v in cache.values() if v is None)
    print(f"done. {missing} points still without a county")
    if errors:
        print(f"{len(errors)} requests errored (not just zero-results), first 5:")
        for key, err in errors[:5]:
            print(f"  {key}: {err}")


if __name__ == "__main__":
    main()
