from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from Feature.navigator import (
    NEARBY_RADIUS_OPTIONS_M,
    county_counts,
    district_counts,
    hotspots_in_district,
    nearby_hotspots,
    search_by_text,
)

router = APIRouter()


@router.get("/counties")
async def get_county_counts():
    """{"0": count, ..., "21": count} - national overview, one dot per county."""
    return county_counts()


class DistrictCountsRequest(BaseModel):
    county: int  # index 0-21, see data/processed/county_index.json


@router.post("/districts")
async def get_district_counts(body: DistrictCountsRequest):
    """{district_name: count} after the user clicks into one county."""
    try:
        return district_counts(body.county)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class HotspotsRequest(BaseModel):
    county: int
    district: Optional[str] = None  # omit to get every hotspot in the county


@router.post("/hotspots")
async def get_hotspots(body: HotspotsRequest):
    """Hotspot markers for a county, optionally narrowed to one district."""
    try:
        return hotspots_in_district(body.county, body.district)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class NearbyRequest(BaseModel):
    lat: float
    lng: float
    radius_m: int = NEARBY_RADIUS_OPTIONS_M[1]  # default 1000m


@router.post("/nearby")
async def get_nearby(body: NearbyRequest):
    """Hotspots within radius_m of (lat, lng), nearest first. radius_m must be
    one of NEARBY_RADIUS_OPTIONS_M (500/1000/2000)."""
    try:
        return nearby_hotspots(body.lat, body.lng, body.radius_m)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class NearbyByTextRequest(BaseModel):
    query: str  # e.g. "台北101", "信義區市政府"


@router.post("/nearby_by_text")
async def get_nearby_by_text(body: NearbyByTextRequest):
    """Geocodes free text via Google Maps, then returns every hotspot in
    that county (no backend distance filtering — the frontend does
    "nearby" itself with its own map library, using `center` to zoom)."""
    try:
        return search_by_text(body.query)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
