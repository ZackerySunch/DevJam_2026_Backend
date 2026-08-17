"""
Uplink (主題2: 電纜狀態 × DNS 流向圖) queries, backing routers/uplink.py.

Cable route/incident data comes from data/uplink/cables.json and
data/uplink/incidents.json (scripts/fetch_cables.py). Each cable's current
`status` is derived, not stored directly:
- "building"  -> cable.building is true (planned/under construction)
- "broken"    -> has an unresolved incident with status "disconnected"
- "partial"   -> has an unresolved incident with status "partial_disconnected"
- "normal"    -> otherwise
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "uplink"
_cables = json.loads((DATA_DIR / "cables.json").read_text(encoding="utf-8"))
_incidents = json.loads((DATA_DIR / "incidents.json").read_text(encoding="utf-8"))

_incidents_by_cable: dict[str, list[dict]] = {}
for _i in _incidents:
    _incidents_by_cable.setdefault(_i["cableid"], []).append(_i)


def _ongoing(cable_id: str) -> list[dict]:
    return [i for i in _incidents_by_cable.get(cable_id, []) if not i["resolved_at"]]


def _status(cable: dict) -> str:
    if cable.get("building"):
        return "building"
    ongoing = _ongoing(cable["id"])
    if any(i["status"] == "disconnected" for i in ongoing):
        return "broken"
    if any(i["status"] == "partial_disconnected" for i in ongoing):
        return "partial"
    return "normal"


def list_cables() -> list[dict]:
    """All cables with route geometry + a derived `status` and any currently
    unresolved incidents attached."""
    return [
        {**cable, "status": _status(cable), "active_incidents": _ongoing(cable["id"])}
        for cable in _cables
    ]


def list_incidents(active_only: bool = False) -> list[dict]:
    """All incident records, or only the ones still unresolved."""
    if active_only:
        return [i for i in _incidents if not i["resolved_at"]]
    return _incidents
