from fastapi import APIRouter, HTTPException

from Feature.signal import station_locations, traffic_pulse

router = APIRouter()


@router.get("/stations")
async def get_stations():
    """All base station coordinates for the 3D light-pillar map."""
    return station_locations()


@router.get("/traffic")
async def get_traffic(hours: int = 24):
    """Taiwan-wide traffic timeseries + 0-1 pulse intensity for the last `hours`."""
    try:
        return traffic_pulse(hours)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
