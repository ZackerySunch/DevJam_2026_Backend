"""
Cleans raw datasets under data/ and writes frontend-ready JSON to data/processed/.

Run manually whenever a raw file under data/ changes:
    python scripts/prepare_data.py
"""
import csv
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUT_DIR = DATA_DIR / "processed"

COORD_DECIMALS = 6  # frontend needs at least 4, at most 6 decimal places

# Some source rows use the simplified 台 variant instead of the official 臺.
# Normalize to the same canonical name Feature/density.py uses.
COUNTY_NAME_ALIASES = {
    "台北市": "臺北市",
    "台中市": "臺中市",
    "台南市": "臺南市",
    "台東縣": "臺東縣",
}

DISTRICT_RE = re.compile(r"([一-鿿]{1,3}?(?:區|鄉|鎮|市))")

# These 4 townships/districts have 區/鄉/鎮/市 as a non-final character
# (前鎮"區", 左鎮"區", 平鎮"區", 新市"區"), which would otherwise make the
# non-greedy DISTRICT_RE above stop one character too early. Checked against
# all 368 official 鄉/鎮/市/區 names; these are the only ones affected.
KNOWN_AMBIGUOUS_DISTRICTS = ["前鎮區", "左鎮區", "平鎮區", "新市區"]


def round_coord(value: str | float) -> float:
    return round(float(value), COORD_DECIMALS)


def normalize_county(name: str) -> str:
    return COUNTY_NAME_ALIASES.get(name, name)


def normalize_district(name: str) -> str:
    return name.replace("台", "臺")


def extract_district(address: str, county: str) -> str | None:
    """Taiwan addresses are zip + county + district + street, e.g.
    "100臺北市中正區徐州路5號1樓" -> district "中正區". Anchor on the county
    name so leading zip-code digits can't confuse the match."""
    idx = address.find(county)
    if idx == -1:
        return None
    rest = address[idx + len(county):]

    for name in KNOWN_AMBIGUOUS_DISTRICTS:
        if rest.startswith(name):
            return name

    m = DISTRICT_RE.match(rest)
    return normalize_district(m.group(1)) if m else None


def _parse_itaiwan() -> list[dict]:
    src = DATA_DIR / "wifi_location" / "iTaiwan.csv"
    records = []
    with open(src, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                lat = round_coord(row["Latitude"])
                lng = round_coord(row["Longitude"])
            except (KeyError, ValueError):
                continue
            county = normalize_county(row["Area"].strip())
            address = row["Address"].strip()
            records.append({
                "source": "iTaiwan",
                "name": row["Name"].strip(),
                "area": county,
                "district": extract_district(address, county),
                "address": address,
                "category": row["Administration"].strip(),
                "agency": row["Agency"].strip(),
                "lat": lat,
                "lng": lng,
            })
    return records


def _parse_taipeifree() -> list[dict]:
    src = DATA_DIR / "wifi_location" / "TaipeiFree.csv"
    records = []
    with open(src, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                lat = round_coord(row["LATITUDE"])
                lng = round_coord(row["LONGITUDE"])
            except (KeyError, ValueError):
                continue
            records.append({
                "source": "TaipeiFree",
                "name": row["NAME"].strip(),
                "area": normalize_county(row["county"].strip()),
                "district": normalize_district(row["AREA"].strip()) or None,
                "address": row["ADDR"].strip(),
                "category": row["STYPE"].strip(),
                "agency": row["AGENCY"].strip(),
                "lat": lat,
                "lng": lng,
            })
    return records


# Add a `_parse_xxx() -> list[dict]` function per new dataset and register it
# here; each record must have source/name/area/address/category/agency/lat/lng.
WIFI_SOURCE_PARSERS = [_parse_itaiwan, _parse_taipeifree]


def process_wifi_hotspots():
    out = OUT_DIR / "wifi_hotspots.json"

    hotspots = []
    for parser in WIFI_SOURCE_PARSERS:
        hotspots.extend(parser())

    out.write_text(json.dumps(hotspots, ensure_ascii=False), encoding="utf-8")
    print(f"[wifi_hotspots] wrote {len(hotspots)} records from {len(WIFI_SOURCE_PARSERS)} sources -> {out}")


def roc_date_to_iso(period: str) -> str:
    # e.g. "1150731" -> ROC year 115, month 07, day 31 -> "2026-07-31"
    roc_year = int(period[:-4])
    month = period[-4:-2]
    day = period[-2:]
    year = roc_year + 1911
    return f"{year}-{month}-{day}"


def process_base_station_density():
    src = DATA_DIR / "base_station_density" / "base_station_density.csv"
    out = OUT_DIR / "base_station_density.json"

    records = []
    periods = set()
    with open(src, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            period = roc_date_to_iso(row["統計期"].strip())
            periods.add(period)
            records.append({
                "county": row["縣市"].strip(),
                "period": period,
                "operator": row["業者名稱"].strip(),
                "category": row["類別"].strip(),
                "count": int(row["基地臺"]),
            })

    payload = {
        "periods": sorted(periods),
        "records": records,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"[base_station_density] wrote {len(records)} records across {len(periods)} periods -> {out}")


def process_base_station_location(filename: str = "466.csv"):
    """Parses an OpenCelliD country export (radio,mcc,net,area,cell,unit,lon,lat,range,
    samples,changeable,created,updated,averageSignal). Country export filename must be
    dropped into data/base_station_location/ (466 = Taiwan's MCC) before running.
    """
    src = DATA_DIR / "base_station_location" / filename
    out = OUT_DIR / "base_station_location.json"

    if not src.exists():
        print(f"[base_station_location] skipped: {src} not found")
        return

    fields = ["radio", "mcc", "net", "area", "cell", "unit", "lon", "lat",
              "range", "samples", "changeable", "created", "updated", "averageSignal"]

    stations = []
    with open(src, encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            record = dict(zip(fields, row))
            stations.append({
                "radio": record["radio"],
                "lat": round_coord(record["lat"]),
                "lng": round_coord(record["lon"]),
                "range_m": int(record["range"]),
                "samples": int(record["samples"]),
            })

    out.write_text(json.dumps(stations, ensure_ascii=False), encoding="utf-8")
    print(f"[base_station_location] wrote {len(stations)} records -> {out}")


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    process_wifi_hotspots()
    process_base_station_density()
    process_base_station_location()
