# main.py
from fastapi import FastAPI
import routers.base_tower_density as base_tower_density
import routers.cable_DNS as cable_DNS
import routers.flow as flow
import routers.public_wifi as public_wifi



app = FastAPI(
    title="HolyPing",
    description="The AI Execution Engine for Vibe Coders",
    version="0.1.0 (MVP)"
)

# Phase 1: CORS 全開 (Zero Friction)
# Phase 1: 真正的大平台 CORS 全開 (Zero Friction)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],     # 🔥 讓全世界任何網域、任何人的瀏覽器都可以打進來
#     allow_credentials=False, # ⚠️ 致命細節：origins 有 "*" 時，這裡絕對不能是 True
#     allow_methods=["*"],     # 允許 GET, POST, PUT, DELETE 等所有方法
#     allow_headers=["*"],     # 允許他們帶自訂的 Headers (例如 x-api-key 或 Authorization)
# )

# 掛載 Core Router
app.include_router(base_tower_density.router, prefix="/api/base_tower_density", tags=["Base Tower Density"])
app.include_router(cable_DNS.router, prefix="/api/cable_dns", tags=["Cable DNS"])
app.include_router(flow.router, prefix="/api/flow", tags=["Flow"])
app.include_router(public_wifi.router, prefix="/api/public_wifi", tags=["Public WiFi"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True) 
    # 注意: 這裡 port 改成 8001 避免跟 Platform (8000) 衝突，如果跑在不同機器可維持 8000