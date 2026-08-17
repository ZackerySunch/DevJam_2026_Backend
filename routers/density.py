from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from Feature.density import query_by_provider, query_by_location_time

router = APIRouter()


class ProviderRequest(BaseModel):
    provider: str  # carrier code: "CHT" / "TWM" / "FET"


class LocationTimeRequest(BaseModel):
    location: int  # county index 0-21, see data/processed/county_index.json
    time: str       # "YYY/MM" ROC format, e.g. "115/07"


@router.post("/provider")
async def get_by_provider(body: ProviderRequest):
    try:
        return query_by_provider(body.provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/location")
async def get_by_location(body: LocationTimeRequest):
    try:
        return query_by_location_time(body.location, body.time)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
