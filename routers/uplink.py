from fastapi import APIRouter

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
