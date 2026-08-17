from fastapi import APIRouter, HTTPException

from Feature.signal import DEFAULT_COUNTY, station_locations, traffic_pulse

router = APIRouter()


@router.get("/stations")
async def get_stations(county: int = DEFAULT_COUNTY):
    """Base station coordinates for one county (defaults to 臺北市, index 13).
    Pass county=-1 for every station in Taiwan (10,733 points)."""
    try:
        return station_locations(county)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/traffic")
async def get_traffic():
    """Current Taiwan-wide traffic level: bigger number = higher traffic."""
    try:
        return traffic_pulse()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
