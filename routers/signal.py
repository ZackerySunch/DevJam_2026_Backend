from fastapi import APIRouter
from fastapi.responses import JSONResponse
import json


router = APIRouter()

@router.post("/run/{project_id}")
async def run_cable_dns(project_id: str):
    # Your implementation here
    pass