"""
Regenerates data/processed/county_index.json and prints example output from
Feature/density.py's query functions.

Run:
    python scripts/density_query.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Feature.density import (
    COUNTY_LIST,
    COUNTY_FULL_TO_INDEX,
    latest_period_roc,
    query_by_provider,
    query_by_location_time,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

if __name__ == "__main__":
    out_path = DATA_DIR / "county_index.json"
    out_path.write_text(
        json.dumps({i: name for i, name in enumerate(COUNTY_LIST)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote county index table -> {out_path}")

    by_provider = query_by_provider("CHT")
    periods_preview = list(by_provider.keys())[:3]
    print("query_by_provider('CHT') periods:", periods_preview, "...")
    first_period = next(iter(by_provider))
    print(f"  {first_period} sample: idx4({COUNTY_LIST[4]})={by_provider[first_period]['4']} "
          f"idx13({COUNTY_LIST[13]})={by_provider[first_period]['13']}")

    latest_roc = latest_period_roc()
    yilan_idx = COUNTY_FULL_TO_INDEX["宜蘭縣"]
    by_location = query_by_location_time(yilan_idx, latest_roc)
    print(f"query_by_location_time({yilan_idx}, '{latest_roc}'):", by_location)
