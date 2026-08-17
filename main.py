# main.py
from fastapi import FastAPI
import routers.density as density
import routers.uplink as uplink
import routers.signal as signal
import routers.navigator as navigator
import routers.home as home
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="HolyPing",
    description="The AI Execution Engine for Vibe Coders",
    version="0.1.0 (MVP)"
)

# Phase 1: CORS 全開 (Zero Friction)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # 🔥 讓全世界任何網域、任何人的瀏覽器都可以打進來
    allow_credentials=False, # ⚠️ 致命細節：origins 有 "*" 時，這裡絕對不能是 True
    allow_methods=["*"],     # 允許 GET, POST, PUT, DELETE 等所有方法
    allow_headers=["*"],     # 允許他們帶自訂的 Headers (例如 x-api-key 或 Authorization)
)

# 掛載 Core Router
app.include_router(density.router, prefix="/api/density", tags=["Density"])
app.include_router(uplink.router, prefix="/api/uplink", tags=["Uplink"])
app.include_router(signal.router, prefix="/api/signal", tags=["Signal"])
app.include_router(navigator.router, prefix="/api/navigator", tags=["Navigator"])
app.include_router(home.router, prefix="/api/agent", tags=["AI Agent"])

# 相容舊版前端可能打的 /home_page/get_events
@app.post("/home_page/get_events")
async def legacy_home_page_events():
    return await uplink.get_cable_events()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True) 
    # 注意: 這裡 port 改成 8001 避免跟 Platform (8000) 衝突，如果跑在不同機器可維持 8000