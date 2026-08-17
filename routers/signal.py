from typing import Optional
from fastapi import APIRouter, HTTPException

from Feature.signal import DEFAULT_COUNTY, station_locations, traffic_pulse, traffic_flows

router = APIRouter()


@router.get("/stations")
async def get_stations(county: int = DEFAULT_COUNTY):
    """Base station coordinates with real-time load and pulsing status.
    Pass county=-1 for every station in Taiwan (10,733 points)."""
    try:
        return station_locations(county)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/traffic")
async def get_traffic():
    """Current Taiwan-wide traffic pulse level: bigger number = higher traffic."""
    try:
        return traffic_pulse()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flows")
@router.get("/traffic_flows")
async def get_traffic_flows(county: Optional[int] = None):
    """Point-to-Point (點對點) network traffic flow lines with exact latitude/longitude.
    - Omit or pass county=-1 for nationwide backbone flows.
    - Pass county=0-21 for county micro-capillary flow lines (station to hub).
    """
    try:
        return traffic_flows(county)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

