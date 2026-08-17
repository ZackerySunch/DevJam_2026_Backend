"""
agent/tools.py

提供給 AI Agent 使用的工具集 (Tool Definitions & Execution Functions)。
封裝了三大核心功能 (Signal, Navigator, Density) 的即時與統計資料，
包含自動參數正規化 (縣市名稱自動辨識、電信代碼轉譯) 與統一的結構化摘要輸出。
"""
from typing import Optional, Any
import json

from Feature.density import (
    COUNTY_LIST,
    COUNTY_FULL_TO_INDEX,
    PROVIDER_CODE_TO_FULL,
    PROVIDER_FULL_TO_CODE,
    latest_period_roc,
    query_by_provider,
    query_by_location_time,
)
from Feature.signal import station_locations, traffic_pulse, traffic_flows
from Feature.navigator import (
    county_counts,
    district_counts,
    hotspots_in_district,
    search_by_text,
    nearby_hotspots,
)

# 縣市別名映射表 (支援口語化的「台北」、「台南」、「台中」等)
COUNTY_ALIAS_MAP = {
    "台北": "臺北市", "台北市": "臺北市", "臺北": "臺北市", "臺北市": "臺北市",
    "新北": "新北市", "新北市": "新北市",
    "基隆": "基隆市", "基隆市": "基隆市",
    "桃園": "桃園市", "桃園市": "桃園市",
    "新竹": "新竹市", "新竹市": "新竹市",
    "新竹縣": "新竹縣",
    "苗栗": "苗栗縣", "苗栗縣": "苗栗縣",
    "台中": "臺中市", "台中市": "臺中市", "臺中": "臺中市", "臺中市": "臺中市",
    "彰化": "彰化縣", "彰化縣": "彰化縣",
    "南投": "南投縣", "南投縣": "南投縣",
    "雲林": "雲林縣", "雲林縣": "雲林縣",
    "嘉義": "嘉義市", "嘉義市": "嘉義市",
    "嘉義縣": "嘉義縣",
    "台南": "臺南市", "台南市": "臺南市", "臺南": "臺南市", "臺南市": "臺南市",
    "高雄": "高雄市", "高雄市": "高雄市",
    "屏東": "屏東縣", "屏東縣": "屏東縣",
    "宜蘭": "宜蘭縣", "宜蘭縣": "宜蘭縣",
    "花蓮": "花蓮縣", "花蓮縣": "花蓮縣",
    "台東": "臺東縣", "台東縣": "臺東縣", "臺東": "臺東縣", "臺東縣": "臺東縣",
    "澎湖": "澎湖縣", "澎湖縣": "澎湖縣",
    "金門": "金門縣", "金門縣": "金門縣",
    "連江": "連江縣", "連江縣": "連江縣", "馬祖": "連江縣",
    # 機場/常見英文代碼別名 (decision agent 偶爾會用這種格式回傳縣市)
    "TPE": "臺北市", "TSA": "臺北市", "KHH": "高雄市", "RMQ": "臺中市",
    "TNN": "臺南市", "HUN": "花蓮縣", "MZG": "澎湖縣", "KNH": "金門縣", "TTT": "臺東縣",
}

# 電信業者別名映射表
PROVIDER_ALIAS_MAP = {
    "中華": "CHT", "中華電信": "CHT", "CHT": "CHT",
    "台哥大": "TWM", "台灣大哥大": "TWM", "台灣大": "TWM", "TWM": "TWM",
    "遠傳": "FET", "遠傳電信": "FET", "FET": "FET",
}


def _resolve_county_index(county_input: str | int) -> tuple[int, str]:
    """將使用者或 Agent 傳入的縣市名稱轉為 index (0-21) 與全名"""
    if isinstance(county_input, int):
        if 0 <= county_input < len(COUNTY_LIST):
            return county_input, COUNTY_LIST[county_input]
        raise ValueError(f"縣市 index 超出範圍 (0-21): {county_input}")

    normalized = str(county_input).strip()
    if normalized.isdigit():
        return _resolve_county_index(int(normalized))

    full_name = COUNTY_ALIAS_MAP.get(normalized) or COUNTY_ALIAS_MAP.get(normalized.upper()) or normalized
    if full_name in COUNTY_FULL_TO_INDEX:
        return COUNTY_FULL_TO_INDEX[full_name], full_name

    raise ValueError(f"無法識別的縣市名稱: '{county_input}'")


def _resolve_provider_code(provider_input: str) -> tuple[str, str]:
    """將電信業者名稱轉為代碼 (CHT/TWM/FET) 與全名"""
    code = PROVIDER_ALIAS_MAP.get(provider_input.strip().upper(), provider_input.strip().upper())
    if code in PROVIDER_CODE_TO_FULL:
        return code, PROVIDER_CODE_TO_FULL[code]
    raise ValueError(f"無法識別的電信業者: '{provider_input}' (支援 CHT中華電信 / TWM台灣大哥大 / FET遠傳電信)")


# ==========================================
# 1. Signal Tools (即時流量與基地台觀測)
# ==========================================

def get_realtime_network_traffic() -> dict:
    """
    【Tool 1】取得台灣目前即時網路流量指標。
    資料來源：Cloudflare Radar 即時觀測。
    適合回答：「目前全台網路順暢嗎？」、「現在是上網尖峰時段嗎？」
    """
    pulse = traffic_pulse()
    val = pulse.get("value", 1.0)
    
    # 流量強度等級評估
    if val >= 1.2:
        level = "高負載 / 尖峰時段"
    elif val >= 0.8:
        level = "正常負載"
    else:
        level = "低負載 / 離峰時段"

    return {
        "status": "success",
        "traffic_value": val,
        "traffic_level": level,
        "timestamp": pulse.get("timestamp"),
        "description": f"目前全台灣網路流量數值為 {val}，處於「{level}」。",
    }


def get_base_stations_summary(county: str | int) -> dict:
    """
    【Tool 2】查詢指定縣市的基地台實體分佈概況與訊號制式 (LTE / UMTS)。
    適合回答：「台北市有多少基地台？」、「某縣市的基地台訊號涵蓋概況」。
    """
    idx, name = _resolve_county_index(county)
    stations = station_locations(idx)
    
    total = len(stations)
    lte_count = sum(1 for s in stations if s.get("radio") == "LTE")
    umts_count = sum(1 for s in stations if s.get("radio") == "UMTS")
    avg_range = round(sum(s.get("range_m", 0) for s in stations) / max(total, 1), 1)

    return {
        "status": "success",
        "county": name,
        "county_id": idx,
        "total_stations": total,
        "lte_stations": lte_count,
        "umts_stations": umts_count,
        "avg_coverage_radius_meters": avg_range,
        "sample_stations": stations[:3] if stations else [],
        "description": f"{name} 目前觀測到 {total} 座基地台 (LTE 4G: {lte_count} 座, UMTS 3G: {umts_count} 座)，平均單站涵蓋半徑約 {avg_range} 公尺。",
    }


def get_point_to_point_traffic_flows(county: Optional[str | int] = None) -> dict:
    """
    【Tool 3】查詢全台骨幹或特定縣市基地台的點對點 (Point-to-Point) 網路流量數據與微血管粒子流。
    county 若為 None 則回傳全台主要跨縣市骨幹網路傳輸數據；若指定縣市則回傳該縣市基地台至匯聚節點的微血管流量線。
    包含：起訖經緯度、即時流量 (Mbps/Gbps)、負載狀態 (normal/heavy/congested)、脈衝頻率與延遲。
    適合回答：「目前哪裡的網路線路壅塞？」、「台北市微血管基地台流量流向」、「全台骨幹傳輸狀態」。
    """
    if county is None or county == "" or county == -1:
        flows = traffic_flows(None)
        congested = [f for f in flows if f["status"] == "congested"]
        heavy = [f for f in flows if f["status"] == "heavy"]
        return {
            "status": "success",
            "scope": "全台灣核心骨幹網絡",
            "total_flows": len(flows),
            "congested_count": len(congested),
            "heavy_count": len(heavy),
            "flows": flows,
            "description": f"全台核心骨幹共監控 {len(flows)} 條點對點傳輸線路，目前有 {len(congested)} 條高負載壅塞線路與 {len(heavy)} 條繁忙線路。",
        }

    idx, name = _resolve_county_index(county)
    flows = traffic_flows(idx)
    congested = [f for f in flows if f["status"] == "congested"]

    return {
        "status": "success",
        "county": name,
        "county_id": idx,
        "total_flows": len(flows),
        "congested_count": len(congested),
        "flows": flows,
        "description": f"{name} 目前共監測 {len(flows)} 條基地台至匯聚節點的微血管點對點流量線，其中 {len(congested)} 條處於壅塞狀態並觸發高頻脈衝閃爍。",
    }


# ==========================================
# 2. Navigator Tools (公共 WiFi 與地點熱點)
# ==========================================

def search_wifi_around_location(query: str) -> dict:
    """
    【Tool 3】透過地名、地標或地址 (例: '台北101', '高雄駁二', '台中火車站') 搜尋周邊可用的免費公共 WiFi。
    資料來源：iTaiwan 與 TaipeiFree。
    回傳：中心座標與最近的 WiFi 熱點清單 (名稱、地址、經緯度)。
    """
    res = search_by_text(query)
    hotspots = res.get("hotspots", [])
    
    return {
        "status": "success",
        "query": query,
        "resolved_county_id": res.get("county"),
        "resolved_center": res.get("center"),
        "total_found": len(hotspots),
        "nearby_hotspots": hotspots[:10],  # 回傳前 10 個最靠近的熱點
        "description": f"已定位到 '{query}'，該區域共有 {len(hotspots)} 個免費 WiFi 熱點，已列出前 10 處詳細地點。",
    }


def get_wifi_city_statistics(county: Optional[str | int] = None) -> dict:
    """
    【Tool 4】查詢全台或特定縣市的公共 WiFi 熱點統計數據。
    county 若為 None 則回傳全台灣各縣市分佈排行；若指定縣市則回傳各行政區熱點數量。
    """
    if county is None or county == "":
        counts = county_counts()
        ranked = sorted(
            [{"county_id": int(k), "county_name": COUNTY_LIST[int(k)], "count": v} for k, v in counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )
        total_taiwan = sum(counts.values())
        return {
            "status": "success",
            "scope": "全台灣",
            "total_hotspots": total_taiwan,
            "top_counties": ranked[:5],
            "all_counties": ranked,
            "description": f"全台灣目前共有 {total_taiwan} 處公共 WiFi 熱點，熱點最多的前三縣市為：{ranked[0]['county_name']}({ranked[0]['count']}處), {ranked[1]['county_name']}({ranked[1]['count']}處), {ranked[2]['county_name']}({ranked[2]['count']}處)。",
        }
    
    idx, name = _resolve_county_index(county)
    districts = district_counts(idx)
    sorted_districts = sorted(districts.items(), key=lambda x: x[1], reverse=True)
    total_county = sum(districts.values())

    return {
        "status": "success",
        "county": name,
        "county_id": idx,
        "total_hotspots": total_county,
        "district_distribution": dict(sorted_districts),
        "description": f"{name} 共有 {total_county} 處公共 WiFi 熱點，分佈最密集的行政區為 {sorted_districts[0][0]}({sorted_districts[0][1]}處)。",
    }


# ==========================================
# 3. Density Tools (三大電信 4G/5G 密度與歷史趨勢)
# ==========================================

def get_county_telecom_density(county: str | int, period: Optional[str] = None) -> dict:
    """
    【Tool 5】比較特定縣市中三大電信（中華電信、台灣大哥大、遠傳電信）的 4G/5G 基地台建設總數。
    period 預設為最新統計月份 (例: '115/07')。
    適合回答：「在台中市哪一家電信的 5G 基地台最多？」、「高雄市中華電信和遠傳誰的基地台比較多？」。
    """
    idx, name = _resolve_county_index(county)
    roc_period = period or latest_period_roc()
    
    data = query_by_location_time(idx, roc_period)
    
    # 統計整理各家電信
    breakdown = []
    for code, full_name in PROVIDER_CODE_TO_FULL.items():
        stats = data.get(code, [0, 0])
        g5, g4 = stats[0], stats[1]
        breakdown.append({
            "provider_code": code,
            "provider_name": full_name,
            "5G_count": g5,
            "4G_count": g4,
            "total_count": g5 + g4,
        })
    
    breakdown.sort(key=lambda x: x["5G_count"], reverse=True)
    
    return {
        "status": "success",
        "county": name,
        "county_id": idx,
        "period": roc_period,
        "operators": breakdown,
        "leader_5G": breakdown[0]["provider_name"],
        "description": f"在 {name} (統計期: {roc_period})，5G 基地台建設最多的業者為「{breakdown[0]['provider_name']}」({breakdown[0]['5G_count']}座 5G，{breakdown[0]['4G_count']}座 4G)。",
    }


def get_telecom_carrier_growth_trend(provider: str) -> dict:
    """
    【Tool 6】查詢指定電信業者（中華電信、台灣大哥大、遠傳電信）近 12 個月全台 4G 與 5G 基地台數量的演變與增長趨勢。
    適合回答：「中華電信最近 5G 蓋得快嗎？」、「遠傳近一年的基地台成長趨勢」。
    """
    code, full_name = _resolve_provider_code(provider)
    trend_data = query_by_provider(code)
    
    # 計算最新與最早月份的全台總數
    periods = list(trend_data.keys())
    earliest_p, latest_p = periods[0], periods[-1]
    
    def sum_taiwan(p_dict):
        total_5g = sum(vals[0] for vals in p_dict.values())
        total_4g = sum(vals[1] for vals in p_dict.values())
        return total_5g, total_4g

    early_5g, early_4g = sum_taiwan(trend_data[earliest_p])
    late_5g, late_4g = sum_taiwan(trend_data[latest_p])
    diff_5g = late_5g - early_5g

    return {
        "status": "success",
        "provider_code": code,
        "provider_name": full_name,
        "observation_period_range": f"{earliest_p} ~ {latest_p}",
        "latest_totals": {"5G": late_5g, "4G": late_4g, "period": latest_p},
        "earliest_totals": {"5G": early_5g, "4G": early_4g, "period": earliest_p},
        "5G_net_growth": diff_5g,
        "description": f"「{full_name}」自 {earliest_p} 至 {latest_p}，全台 5G 基地台由 {early_5g} 座成長至 {late_5g} 座 (淨增長 {diff_5g} 座)。",
    }


# ==========================================
# 4. LLM Function Calling Tool Registry & Schemas
# ==========================================

AGENT_TOOLS_REGISTRY = {
    "get_realtime_network_traffic": get_realtime_network_traffic,
    "get_base_stations_summary": get_base_stations_summary,
    "get_point_to_point_traffic_flows": get_point_to_point_traffic_flows,
    "search_wifi_around_location": search_wifi_around_location,
    "get_wifi_city_statistics": get_wifi_city_statistics,
    "get_county_telecom_density": get_county_telecom_density,
    "get_telecom_carrier_growth_trend": get_telecom_carrier_growth_trend,
}

TOOL_DECLARATIONS = [
    {
        "name": "get_realtime_network_traffic",
        "description": "取得全台灣目前即時網路流量指標與負載強度 (尖峰/正常/離峰狀態)。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_base_stations_summary",
        "description": "查詢指定縣市的基地台實體觀測總數、LTE/UMTS 制式佔比與平均涵蓋半徑。",
        "parameters": {
            "type": "object",
            "properties": {
                "county": {
                    "type": "string",
                    "description": "縣市名稱 (例: '台北市', '台中', '高雄市', '新竹縣') 或縣市代碼 0-21",
                }
            },
            "required": ["county"],
        },
    },
    {
        "name": "get_point_to_point_traffic_flows",
        "description": "查詢全台灣骨幹或特定縣市基地台的點對點 (Point-to-Point) 網路流量數據、微血管流向線與壅塞狀態。",
        "parameters": {
            "type": "object",
            "properties": {
                "county": {
                    "type": "string",
                    "description": "可選。填寫縣市名稱 (例: '台北市') 查詢該縣市基地台微血管流向；留空則查詢全台主要跨縣市骨幹網路傳輸。",
                }
            },
            "required": [],
        },
    },
    {
        "name": "search_wifi_around_location",
        "description": "輸入具體地標、地址或商圈名稱 (例: '台北101', '台中火車站', '逢甲夜市')，搜尋周邊可用的免費公共 WiFi 熱點清單。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "想要搜尋的地名、景點或地址 (例: '台北車站', '台南孔廟')",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_wifi_city_statistics",
        "description": "查詢全台灣或指定縣市的公共 WiFi 熱點分佈統計與熱門行政區分佈。",
        "parameters": {
            "type": "object",
            "properties": {
                "county": {
                    "type": "string",
                    "description": "可選。若填寫則查詢該縣市各區分佈 (例: '台北市')；若不填則查詢全台各縣市排行榜。",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_county_telecom_density",
        "description": "比較指定縣市中三大電信 (中華電信、台灣大哥大、遠傳電信) 各自的 4G 與 5G 基地台建設數量與佔比。",
        "parameters": {
            "type": "object",
            "properties": {
                "county": {
                    "type": "string",
                    "description": "縣市名稱 (例: '台中市', '台北', '高雄市', '花蓮縣')",
                },
                "period": {
                    "type": "string",
                    "description": "可選。民國年月 (例: '115/07')，預設為最新統計月份。",
                },
            },
            "required": ["county"],
        },
    },
    {
        "name": "get_telecom_carrier_growth_trend",
        "description": "查詢特定電信業者 (中華電信 CHT / 台灣大哥大 TWM / 遠傳電信 FET) 近 12 個月全台 4G 與 5G 基地台的演變與增長趨勢。",
        "parameters": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "description": "電信業者名稱或代碼 (例: '中華電信', 'CHT', '台哥大', 'TWM', '遠傳', 'FET')",
                }
            },
            "required": ["provider"],
        },
    },
]


def execute_tool(tool_name: str, arguments: dict) -> dict:
    """執行指定工具並回傳結果"""
    if tool_name not in AGENT_TOOLS_REGISTRY:
        return {"status": "error", "message": f"未知的工具: {tool_name}"}
    try:
        fn = AGENT_TOOLS_REGISTRY[tool_name]
        return fn(**arguments)
    except Exception as e:
        return {"status": "error", "message": str(e)}
