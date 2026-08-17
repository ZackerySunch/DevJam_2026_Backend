from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime, timezone

from Feature.uplink import list_cables, list_incidents

router = APIRouter()


@router.get("/cables")
async def get_cables():
    """All submarine cables with route geometry + current status
    (building/broken/partial/normal) and any unresolved incidents."""
    return list_cables()


@router.get("/incidents")
async def get_incidents(active_only: bool = False):
    """All incident records, or only currently unresolved ones."""
    return list_incidents(active_only)


class EventRequest(BaseModel):
    project_id: Optional[str] = None


@router.post("/get_events")
@router.post("/events")
@router.get("/events")
async def get_cable_events(body: Optional[EventRequest] = None):
    """Real ongoing submarine cable incidents formatted for UI events/feed."""
    incidents = list_incidents(active_only=True)
    events = []
    for idx, inc in enumerate(incidents):
        cable_name = (inc.get("cableid") or "海纜").upper()
        events.append({
            "id": idx + 1,
            "title": inc.get("title") or f"{cable_name} 海纜異常事件",
            "desc": inc.get("description") or f"偵測到 {cable_name} 發生線路異常",
            "time": inc.get("date") or datetime.now(timezone.utc).isoformat(),
            "label": 2 if inc.get("status") == "disconnected" else 1,
            "status": inc.get("status"),
            "cableid": inc.get("cableid"),
            "segment": inc.get("segment"),
        })
    return events

