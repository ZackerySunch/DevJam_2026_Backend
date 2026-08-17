"""
Base station density queries, backing routers/base_tower_density.py.

Counties are identified by a fixed integer index (0-21) instead of Chinese
names (see data/processed/county_index.json for the index -> county-name
table), and carriers by ticker-style codes (CHT/TWM/FET) instead of Chinese
names, so callers never need to string-match Chinese text.
"""
import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "base_station_density.json"
_data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
_records = _data["records"]
_periods = _data["periods"]  # sorted ISO date strings, e.g. "2026-07-31"

# Fixed index (0-21) <-> official county/city name. Order is arbitrary but stable
# (alphabetical by the source CSV's own text); the frontend hardcodes this same
# table (data/processed/county_index.json) to label results, so DO NOT reorder
# this list once the frontend has it.
COUNTY_LIST = [
    "南投縣", "嘉義市", "嘉義縣", "基隆市", "宜蘭縣", "屏東縣", "彰化縣", "新北市",
    "新竹市", "新竹縣", "桃園市", "澎湖縣", "臺中市", "臺北市", "臺南市", "臺東縣",
    "花蓮縣", "苗栗縣", "連江縣", "金門縣", "雲林縣", "高雄市",
]
COUNTY_FULL_TO_INDEX = {name: i for i, name in enumerate(COUNTY_LIST)}

# Only the 3 current major carriers (亞太電信/台灣之星 have since merged into these).
# Codes match ticker-style abbreviations the frontend uses: CHT=Chunghwa Telecom,
# TWM=Taiwan Mobile, FET=Far EasTone.
PROVIDER_CODE_TO_FULL = {
    "CHT": "中華電信股份有限公司",
    "TWM": "台灣大哥大股份有限公司",
    "FET": "遠傳電信股份有限公司",
}
PROVIDER_FULL_TO_CODE = {full: code for code, full in PROVIDER_CODE_TO_FULL.items()}


def iso_to_roc(iso_period: str) -> str:
    year, month, _ = iso_period.split("-")
    return f"{int(year) - 1911}/{month}"


def latest_period_roc() -> str:
    return iso_to_roc(_periods[-1])


def last_year_periods() -> list[str]:
    latest_y, latest_m, _ = (int(x) for x in _periods[-1].split("-"))
    cutoff_ym = latest_y * 12 + latest_m - 11  # last 12 months inclusive
    kept = []
    for p in _periods:
        y, m = (int(x) for x in p.split("-")[:2])
        if y * 12 + m >= cutoff_ym:
            kept.append(p)
    return kept


def query_by_provider(provider: str) -> dict:
    """{"115/07": {"0": [5G_count, 4G_count], ..., "21": [...]}, ...} for the last 12 months.

    provider is a carrier code: "CHT" / "TWM" / "FET".
    """
    full_provider = PROVIDER_CODE_TO_FULL.get(provider.strip().upper())
    if full_provider is None:
        raise ValueError(f"unknown provider code: {provider}")

    periods = last_year_periods()
    period_set = set(periods)

    result = {
        iso_to_roc(p): {str(i): [0, 0] for i in range(len(COUNTY_LIST))}
        for p in periods
    }

    for r in _records:
        if r["operator"] != full_provider or r["period"] not in period_set:
            continue
        if r["category"] not in ("5G", "4G"):
            continue
        idx = COUNTY_FULL_TO_INDEX.get(r["county"])
        if idx is None:
            continue
        cat_idx = 0 if r["category"] == "5G" else 1
        result[iso_to_roc(r["period"])][str(idx)][cat_idx] += r["count"]

    return result


def query_by_location_time(location: int, time: str) -> dict:
    """{"CHT": [5G_count, 4G_count], "TWM": [...], "FET": [...]}"""
    if not (0 <= location < len(COUNTY_LIST)):
        raise ValueError(f"unknown location index: {location}")
    full_county = COUNTY_LIST[location]

    try:
        roc_year, month = time.strip().split("/")
        iso_year = int(roc_year) + 1911
        period_prefix = f"{iso_year}-{int(month):02d}"
    except ValueError:
        raise ValueError(f"invalid time format, expected 'YYY/MM': {time}")

    result = {code: [0, 0] for code in PROVIDER_CODE_TO_FULL}

    for r in _records:
        if r["county"] != full_county or not r["period"].startswith(period_prefix):
            continue
        if r["category"] not in ("5G", "4G"):
            continue
        provider_code = PROVIDER_FULL_TO_CODE.get(r["operator"])
        if provider_code is None:
            continue
        idx = 0 if r["category"] == "5G" else 1
        result[provider_code][idx] += r["count"]

    return result
