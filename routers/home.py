from fastapi import APIRouter
from fastapi.responses import JSONResponse
import json


router = APIRouter()

@router.post("/home_page/get_events")
async def run_cable_dns(project_id: str):

    data = [
        1:{
        "title": "APG 海纜發生斷訊",
        "decs" : "偵測到由台灣連往東京之 APG 核心海纜發生異常，延遲飆升至 250ms。",
        "time" : new Date().toISOString(),
        lable: 2,
        }]


    # Your implementation here
    return data
