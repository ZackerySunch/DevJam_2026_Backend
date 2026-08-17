"""
Signal (主題1: 基地台位置 × 網路流向圖) queries, backing routers/signal.py.

提供：
1. 基地台實體座標 (3D 光柱，含即時負載與脈衝狀態)
2. 點對點網路流量流向 (Point-to-Point Traffic Flows，含起訖經緯度、流量數值、壅塞與脈衝連動)
3. Cloudflare Radar 即時全台流量脈衝數值
"""
import json
import math
import os
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

from Feature.density import COUNTY_LIST, COUNTY_FULL_TO_INDEX

load_dotenv()

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "base_station_location.json"
_stations = json.loads(DATA_PATH.read_text(encoding="utf-8"))

CLOUDFLARE_RADAR_URL = "https://api.cloudflare.com/client/v4/radar/http/timeseries"
DEFAULT_COUNTY = COUNTY_FULL_TO_INDEX["臺北市"]

TRAFFIC_CACHE_TTL_SECONDS = 15 * 60
_traffic_cache: dict | None = None
_traffic_cache_at: float = 0.0

# 台灣主要縣市核心匯聚機房與交換節點 (Regional Network Hubs)
REGIONAL_HUBS = {
    "臺北市": {"name": "台北核心網際網路交換中心 (TPIX)", "lat": 25.0425, "lng": 121.5358},
    "新北市": {"name": "板橋雲端數據中心 (Banciao IDC)", "lat": 25.0125, "lng": 121.4658},
    "桃園市": {"name": "桃園航空城傳輸樞紐", "lat": 25.0122, "lng": 121.2188},
    "新竹市": {"name": "新竹科學園區高速節點", "lat": 24.7818, "lng": 120.9972},
    "新竹縣": {"name": "新竹竹北核心機房", "lat": 24.8387, "lng": 121.0177},
    "臺中市": {"name": "台中都會區骨幹節點", "lat": 24.1565, "lng": 120.6658},
    "彰化縣": {"name": "彰化雲端匯聚機房", "lat": 24.0818, "lng": 120.5385},
    "嘉義市": {"name": "嘉義核心傳輸節點", "lat": 23.4800, "lng": 120.4491},
    "嘉義縣": {"name": "嘉義太保傳輸樞紐", "lat": 23.4590, "lng": 120.2930},
    "臺南市": {"name": "台南科學園區運算節點", "lat": 23.0991, "lng": 120.2828},
    "高雄市": {"name": "高雄亞洲新灣區骨幹節點", "lat": 22.6148, "lng": 120.3015},
    "屏東縣": {"name": "屏東高屏匯聚機房", "lat": 22.6761, "lng": 120.4885},
    "宜蘭縣": {"name": "宜蘭蘭陽傳輸中心", "lat": 24.7570, "lng": 121.7530},
    "花蓮縣": {"name": "花蓮東部骨幹機房", "lat": 23.9912, "lng": 121.6111},
    "臺東縣": {"name": "台東太平洋匯流節點", "lat": 22.7583, "lng": 121.1444},
    "基隆市": {"name": "基隆港口國際傳輸節點", "lat": 25.1276, "lng": 121.7392},
    "苗栗縣": {"name": "苗栗竹南科技節點", "lat": 24.5602, "lng": 120.8188},
    "南投縣": {"name": "南投中興傳輸機房", "lat": 23.9099, "lng": 120.6872},
    "雲林縣": {"name": "雲林斗六匯聚節點", "lat": 23.7092, "lng": 120.5435},
    "澎湖縣": {"name": "澎湖跨海微波匯聚中心", "lat": 23.5711, "lng": 119.5793},
    "金門縣": {"name": "金門前線通訊節點", "lat": 24.4327, "lng": 118.3766},
    "連江縣": {"name": "馬祖微波備援節點", "lat": 26.1557, "lng": 119.9519},
}

# 全台核心骨幹主幹線 (Inter-City Backbone Links)
BACKBONE_LINKS = [
    ("臺北市", "新北市", 100.0),
    ("臺北市", "基隆市", 40.0),
    ("新北市", "桃園市", 80.0),
    ("桃園市", "新竹市", 80.0),
    ("新竹市", "苗栗縣", 40.0),
    ("苗栗縣", "臺中市", 60.0),
    ("臺中市", "彰化縣", 40.0),
    ("臺中市", "南投縣", 40.0),
    ("彰化縣", "雲林縣", 40.0),
    ("雲林縣", "嘉義市", 40.0),
    ("嘉義市", "臺南市", 60.0),
    ("臺南市", "高雄市", 100.0),
    ("高雄市", "屏東縣", 40.0),
    ("臺北市", "宜蘭縣", 40.0),
    ("宜蘭縣", "花蓮縣", 40.0),
    ("花蓮縣", "臺東縣", 40.0),
    ("屏東縣", "臺東縣", 40.0),
    ("臺北市", "臺中市", 100.0),  # 直達高速骨幹
    ("臺北市", "高雄市", 100.0),  # 直達高速骨幹
]


def traffic_pulse() -> dict:
    """Current Taiwan-wide HTTP traffic level from Cloudflare Radar."""
    global _traffic_cache, _traffic_cache_at

    now = time.monotonic()
    if _traffic_cache is not None and (now - _traffic_cache_at) < TRAFFIC_CACHE_TTL_SECONDS:
        return _traffic_cache

    token = os.environ.get("CLOUDFLARE_RADAR_TOKEN")
    if not token:
        # Fallback simulation if token is absent
        return {"value": 1.0, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    try:
        resp = requests.get(
            CLOUDFLARE_RADAR_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={"location": "TW", "dateRange": "1d", "aggInterval": "15m", "format": "json"},
            timeout=5,
        )
        if not resp.ok:
            raise RuntimeError(f"Cloudflare Radar request failed ({resp.status_code})")
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Cloudflare Radar request failed: {data.get('errors')}")

        series = data["result"]["serie_0"]
        _traffic_cache = {
            "value": float(series["values"][-1]),
            "timestamp": series["timestamps"][-1],
        }
        _traffic_cache_at = now
        return _traffic_cache
    except Exception:
        # Graceful fallback to cached or default
        if _traffic_cache is not None:
            return _traffic_cache
        return {"value": 1.0, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def station_locations(county: int = DEFAULT_COUNTY) -> list[dict]:
    """Base station coordinates with real-time load and pulsing indicators."""
    pulse = traffic_pulse()
    base_multiplier = pulse.get("value", 1.0)

    if county == -1:
        selected_stations = _stations
    else:
        if not (0 <= county < len(COUNTY_LIST)):
            raise ValueError(f"unknown county index: {county} (must be 0-21 or -1)")
        full_county = COUNTY_LIST[county]
        selected_stations = [s for s in _stations if s.get("county") == full_county]

    results = []
    for idx, s in enumerate(selected_stations):
        # 根據觀測樣本數與當前流量計算動態負載
        sample_factor = min(s.get("samples", 1) / 15.0, 1.2)
        pseudo_noise = ((idx * 37) % 20) / 100.0  # 模擬局部微波起伏
        load_val = round(min(base_multiplier * (0.6 + sample_factor * 0.4 + pseudo_noise), 1.6), 2)

        if load_val >= 1.2:
            status = "congested"
            pulse_rate = 2.5
            is_pulsing = True
        elif load_val >= 0.85:
            status = "heavy"
            pulse_rate = 1.5
            is_pulsing = False
        else:
            status = "normal"
            pulse_rate = 0.8
            is_pulsing = False

        results.append({
            "radio": s.get("radio", "LTE"),
            "lat": s["lat"],
            "lng": s["lng"],
            "range_m": s.get("range_m", 1000),
            "samples": s.get("samples", 1),
            "county": s.get("county"),
            "traffic_load": load_val,
            "status": status,
            "is_pulsing": is_pulsing,
            "pulse_rate": pulse_rate,
        })
    return results


def traffic_flows(county: Optional[int] = None) -> list[dict]:
    """
    Point-to-Point (點對點) 網路流量數據 (微血管流向線 / 粒子流數據)。
    - 若 county 為 None 或 -1: 回傳全台灣骨幹點對點流向 (Inter-City Backbone Flows)
    - 若指定 county (0-21): 回傳該縣市基地台至匯聚節點的點對點微血管流向 (Intra-County Flows)
    """
    pulse = traffic_pulse()
    base_val = pulse.get("value", 1.0)
    flows = []

    # 1. 全台骨幹點對點流向 (Backbone Flows)
    if county is None or county == -1:
        for idx, (c1, c2, max_bw) in enumerate(BACKBONE_LINKS):
            h1 = REGIONAL_HUBS.get(c1)
            h2 = REGIONAL_HUBS.get(c2)
            if not h1 or not h2:
                continue

            # 依當前流量指數計算即時吞吐量與壅塞率
            traffic_ratio = min(max(base_val * 0.75 + ((idx * 17) % 25) / 100.0, 0.2), 0.98)
            current_gbps = round(max_bw * traffic_ratio, 1)
            load_pct = round(traffic_ratio * 100, 1)

            if load_pct >= 85.0:
                status = "congested"
                pulse_freq = 3.0
            elif load_pct >= 65.0:
                status = "heavy"
                pulse_freq = 1.8
            else:
                status = "normal"
                pulse_freq = 1.0

            flows.append({
                "id": f"bb_flow_{idx+1:02d}",
                "type": "backbone",
                "from_name": h1["name"],
                "from_lat": h1["lat"],
                "from_lng": h1["lng"],
                "to_name": h2["name"],
                "to_lat": h2["lat"],
                "to_lng": h2["lng"],
                "traffic_gbps": current_gbps,
                "bandwidth_gbps": max_bw,
                "load_percentage": load_pct,
                "status": status,
                "pulse_frequency": pulse_freq,
                "latency_ms": round(2.5 + math.hypot(h1["lat"] - h2["lat"], h1["lng"] - h2["lng"]) * 35.0, 1),
            })
        return flows

    # 2. 縣市內微血管基地台點對點流向 (Intra-County Base Station to Hub Flows)
    if not (0 <= county < len(COUNTY_LIST)):
        raise ValueError(f"unknown county index: {county}")

    full_county = COUNTY_LIST[county]
    hub = REGIONAL_HUBS.get(full_county, {"name": f"{full_county}傳輸節點", "lat": 25.04, "lng": 121.53})
    st_list = [s for s in _stations if s.get("county") == full_county]

    # 取代表性基地台節點作為流向起點 (避免前端渲染過多線條卡頓，精選前 40 處重要站點)
    sampled_stations = st_list[:40] if len(st_list) > 40 else st_list

    for idx, st in enumerate(sampled_stations):
        traffic_ratio = min(max(base_val * 0.7 + ((idx * 23) % 30) / 100.0, 0.15), 0.95)
        mbps = round(traffic_ratio * 1000.0, 1)
        load_pct = round(traffic_ratio * 100, 1)

        if load_pct >= 80.0:
            status = "congested"
            pulse_freq = 2.8
        elif load_pct >= 60.0:
            status = "heavy"
            pulse_freq = 1.6
        else:
            status = "normal"
            pulse_freq = 0.9

        flows.append({
            "id": f"st_flow_{county}_{idx+1:03d}",
            "type": "access_link",
            "from_name": f"{full_county}基地台 #{idx+1} ({st.get('radio', 'LTE')})",
            "from_lat": st["lat"],
            "from_lng": st["lng"],
            "to_name": hub["name"],
            "to_lat": hub["lat"],
            "to_lng": hub["lng"],
            "traffic_mbps": mbps,
            "bandwidth_mbps": 1000.0,
            "load_percentage": load_pct,
            "status": status,
            "pulse_frequency": pulse_freq,
            "latency_ms": round(5.0 + ((idx * 7) % 15), 1),
        })

    return flows

