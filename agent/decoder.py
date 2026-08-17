"""
agent/decoder.py

負責解析 decision 輸出的指令，並依據指令規格直接調用後端核心 Feature 資料：
1. cable_status: 取得海底電纜狀態 (Feature.uplink.list_cables)
2. user_public_wifi: 取得使用者周邊公共 WiFi (Feature.navigator.nearby_hotspots / search_by_text)
3. AP_count: 取得指定縣市基地台數量 ["version(4G/5G/all)", "縣市代號或名稱"] (Feature.density & Feature.signal)
4. get_new_events: 取得即時異常事件 (routers.uplink.get_cable_events)
"""
import json
from typing import Optional, Any

from Feature.uplink import list_cables, list_incidents
from Feature.navigator import nearby_hotspots, search_by_text, hotspots_in_district
from Feature.density import COUNTY_LIST, COUNTY_FULL_TO_INDEX, query_by_location_time, latest_period_roc, PROVIDER_CODE_TO_FULL
from Feature.signal import station_locations
from agent.tools import _resolve_county_index


def decoder(command: dict, user_data: Optional[dict] = None) -> dict:
    """
    根據 decision 產生的 command 字典，抓取對應的真實後端資料。

    :param command: 例如 {"cable_status": "", "AP_count": ["5G", "13"]}
    :param user_data: 使用者上下文 (例如座標 {"lat": 25.04, "lng": 121.51} 或縣市)
    :return: 抓取到的各項資料聚合字典
    """
    if not isinstance(command, dict):
        return {}

    user_data = user_data or {}
    results = {}

    for feature_name, data_param in command.items():
        # 1. 取得海底電纜狀態
        if feature_name == "cable_status":
            try:
                cables = list_cables()
                broken = [c for c in cables if c["status"] == "broken"]
                partial = [c for c in cables if c["status"] == "partial"]
                normal = [c for c in cables if c["status"] == "normal"]
                results["cable_status"] = {
                    "total_cables": len(cables),
                    "broken_count": len(broken),
                    "broken_cables": [{"id": c["id"], "name": c["name"]} for c in broken],
                    "partial_count": len(partial),
                    "normal_count": len(normal),
                    "summary": f"全台共監控 {len(cables)} 條國際海底電纜，目前 {len(normal)} 條正常、{len(broken)} 條斷訊 ({', '.join(c['name'] for c in broken) if broken else '無'})、{len(partial)} 條部分異常。"
                }
            except Exception as e:
                results["cable_status"] = {"error": str(e)}

        # 2. 附近的公共網路
        elif feature_name == "user_public_wifi":
            try:
                hotspots = []
                query_loc = data_param if isinstance(data_param, str) and data_param.strip() else user_data.get("location_text")
                lat = user_data.get("lat")
                lng = user_data.get("lng")

                if lat is not None and lng is not None:
                    # 使用精確經緯度搜尋半徑 1000m
                    hotspots = nearby_hotspots(float(lat), float(lng), 1000)
                elif query_loc:
                    # 使用地名或關鍵字搜尋
                    search_res = search_by_text(query_loc)
                    hotspots = search_res.get("hotspots", [])
                else:
                    # 預設台北市熱點
                    hotspots = hotspots_in_district(13)

                results["user_public_wifi"] = {
                    "count": len(hotspots),
                    "sample_hotspots": hotspots[:5],
                    "summary": f"已尋找到 {len(hotspots)} 處免費公共 WiFi 熱點，最近地點包括：{hotspots[0]['name']}({hotspots[0]['address']})" if hotspots else "該區域未搜尋到公共熱點。"
                }
            except Exception as e:
                results["user_public_wifi"] = {"error": str(e)}

        # 3. 取得指定縣市的基地台數量: ["version(4G/5G/all)", "縣市代號"]
        elif feature_name == "AP_count":
            try:
                version = "all"
                county_input = 13  # 預設台北

                if isinstance(data_param, list) and len(data_param) >= 2:
                    version = str(data_param[0]).upper()
                    county_input = data_param[1]
                elif isinstance(data_param, list) and len(data_param) == 1:
                    county_input = data_param[0]

                idx, county_name = _resolve_county_index(county_input)
                period = latest_period_roc()
                density_data = query_by_location_time(idx, period)

                total_5g = sum(vals[0] for vals in density_data.values())
                total_4g = sum(vals[1] for vals in density_data.values())

                breakdown = []
                for code, name in PROVIDER_CODE_TO_FULL.items():
                    vals = density_data.get(code, [0, 0])
                    breakdown.append({
                        "provider": name,
                        "5G": vals[0],
                        "4G": vals[1],
                        "total": vals[0] + vals[1]
                    })

                results["AP_count"] = {
                    "county": county_name,
                    "county_id": idx,
                    "period": period,
                    "target_version": version,
                    "total_5G": total_5g,
                    "total_4G": total_4g,
                    "total_all": total_5g + total_4g,
                    "operators": breakdown,
                    "summary": f"{county_name} (統計期: {period}) 共有 {total_5g} 座 5G 基地台與 {total_4g} 座 4G 基地台 (總計 {total_5g + total_4g} 座)。"
                }
            except Exception as e:
                results["AP_count"] = {"error": str(e)}

        # 4. 取得最新事件
        elif feature_name == "get_new_events":
            try:
                incidents = list_incidents(active_only=True)
                results["get_new_events"] = {
                    "active_incidents_count": len(incidents),
                    "events": incidents[:5],
                    "summary": f"目前共有 {len(incidents)} 筆進行中的通訊與海纜異常事件通報。" if incidents else "目前全台網路與國際海纜無重大異常通報。"
                }
            except Exception as e:
                results["get_new_events"] = {"error": str(e)}

    return results
