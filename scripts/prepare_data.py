"""
Cleans raw datasets under data/ and writes frontend-ready JSON to data/processed/.

Run manually whenever a raw file under data/ changes:
    python scripts/prepare_data.py
"""
import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUT_DIR = DATA_DIR / "processed"


def process_wifi_hotspots():
    src = DATA_DIR / "wifi_location" / "hotspotlist_tw.csv"
    out = OUT_DIR / "wifi_hotspots.json"

    hotspots = []
    skipped = 0
    with open(src, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                lat = float(row["Latitude"])
                lng = float(row["Longitude"])
            except (KeyError, ValueError):
                skipped += 1
                continue

            hotspots.append({
                "name": row["Name"].strip(),
                "area": row["Area"].strip(),
                "address": row["Address"].strip(),
                "category": row["Administration"].strip(),
                "agency": row["Agency"].strip(),
                "lat": lat,
                "lng": lng,
            })

    out.write_text(json.dumps(hotspots, ensure_ascii=False), encoding="utf-8")
    print(f"[wifi_hotspots] wrote {len(hotspots)} records, skipped {skipped} -> {out}")


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
    """
    Parses an OpenCelliD country export (radio,mcc,net,area,cell,unit,lon,lat,range,
    samples,changeable,created,updated,averageSignal). Not run by default because the
    only file currently in data/base_station_location/ (452.csv) is Vietnam (MCC 452),
    not Taiwan (MCC 466). Drop the correct Taiwan export in as data/base_station_location/466.csv
    and call this function (see __main__ below) to generate the processed JSON.
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
                "lat": float(record["lat"]),
                "lng": float(record["lon"]),
                "range_m": int(record["range"]),
                "samples": int(record["samples"]),
            })

    out.write_text(json.dumps(stations, ensure_ascii=False), encoding="utf-8")
    print(f"[base_station_location] wrote {len(stations)} records -> {out}")


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    process_wifi_hotspots()
    process_base_station_density()
    process_base_station_location()  # no-op until data/base_station_location/466.csv exists
