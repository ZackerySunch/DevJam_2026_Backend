# scripts/write_agent_md.py
from pathlib import Path

content = """# HolyPing AI Agent 系統架構與工具規範 (AGENT.md)

HolyPing AI Agent 是專為全台網路狀態即時診斷、基地台負載分析、國際海纜事件監測與公共 WiFi 導航設計的領域專用智慧助理（Domain-Specific AI Network Assistant）。

---

## 1. 系統定位與核心職責

傳統網路異常時，使用者常面臨「重刷頁面焦慮」，無法辨別是「手機設備問題」、「區域基地台過度擁擠」、「骨幹網路塞車」還是「國際海纜斷裂」。

HolyPing AI Agent 透過**記憶體內直接調用（In-Process Direct Function Calling）**，即時串接後端三大核心資料流：
1. **Signal**：NCC 實體基地台經緯度座標、訊號覆蓋半徑、點對點（Point-to-Point）微血管/骨幹流量光線、Cloudflare Radar 即時流量負載與高頻脈衝閃爍狀態。
2. **Navigator**：全台 18,046 處 iTaiwan / TaipeiFree 免費公共 WiFi 熱點精確座標與地址導航。
3. **Density**：中華電信 (CHT)、台灣大哥大 (TWM)、遠傳電信 (FET) 近 12 個月 4G/5G 基地台歷史建設與各縣市消長趨勢。

---

## 2. 工具調用架構 (In-Process Execution Model)

### 零網路延遲機制 (No Internal HTTP / In-Memory Direct Calls)
AI Agent 在處理工具呼叫時，**絕不發送內部 HTTP 請求**，而是透過 Python 記憶體字典分派（Function Pointers）在同一個後端 Process 內執行，執行耗時通常小於 1 毫秒。

```
                    ┌─────────────────────────┐
                    │ 使用者輸入 (User Query)  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ LLM 推理與決策引擎       │ ◄── 載入 TOOL_DECLARATIONS (JSON Schema)
                    └────────────┬────────────┘
                                 │ 輸出 Function Calling 指令
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Python In-Process Memory Execution (agent/tools.py)                    │
│                                                                        │
│  execute_tool(name, args)                                              │
│    └─► AGENT_TOOLS_REGISTRY[name](**args)                              │
│          ├─► Feature.signal (基地台座標 / P2P流量流向)                  │
│          ├─► Feature.navigator (18,046 筆公共 WiFi 熱點快取)            │
│          └─► Feature.density (三大電信 4G/5G 密度資料庫)                │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │ 回傳結構化資料 + 人性化 Description
                                 ▼
                    ┌─────────────────────────┐
                    │ LLM 綜整真實數據生成回覆 │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ 前端使用者介面 (UI)      │
                    └─────────────────────────┘
```

---

## 3. 工具庫詳細規格 (Agent Tools Specification)

所有工具實作於 [`agent/tools.py`](agent/tools.py)，內建口語化模糊辨識（自動支援「台北」、「台中」、「台哥大」、「遠傳」等別名轉換）。

### 🛠️ 工具 1：`get_realtime_network_traffic()`
* **用途**：取得全台灣即時網路流量指標與負載強度等級。
* **資料來源**：Cloudflare Radar 即時 HTTP 觀測。
* **適用問句**：「目前全台網路順暢嗎？」、「現在是上網尖峰時段嗎？」
* **回傳範例**：
```json
{
  "status": "success",
  "traffic_value": 1.15,
  "traffic_level": "正常負載",
  "timestamp": "2026-08-18T04:30:00Z",
  "description": "目前全台灣網路流量數值為 1.15，處於「正常負載」。"
}
```

---

### 🛠️ 工具 2：`get_base_stations_summary(county)`
* **用途**：查詢指定縣市的基地台實體觀測總數、LTE/UMTS 制式佔比與平均涵蓋半徑。
* **資料來源**：OpenCelliD 實體基地台空間觀測。
* **參數**：
  * `county` (str | int): 縣市名稱（如 `"台北市"`、`"台中"`）或代碼 `0~21`。
* **適用問句**：「台北市有多少基地台？」、「新竹縣的基地台訊號涵蓋範圍如何？」。
* **回傳範例**：
```json
{
  "status": "success",
  "county": "臺北市",
  "county_id": 13,
  "total_stations": 2259,
  "lte_stations": 1819,
  "umts_stations": 440,
  "avg_coverage_radius_meters": 1198.8,
  "description": "臺北市目前觀測到 2259 座基地台 (LTE 4G: 1819 座, UMTS 3G: 440 座)，平均單站涵蓋半徑約 1198.8 公尺。"
}
```

---

### 🛠️ 工具 3：`get_point_to_point_traffic_flows(county?)`
* **用途**：查詢點對點（Point-to-Point）網路傳輸流向、底層微血管光線與線路壅塞狀態（含起訖經緯度）。
* **參數**：
  * `county` (str | int, 選填): 填寫縣市名稱查詢該縣市基地台至匯聚節點的微血管流向；留空則查詢全台主要跨縣市骨幹網路傳輸。
* **適用問句**：「目前哪條網路骨幹壅塞？」、「台北市基地台微血管流量流向與延遲」。
* **回傳範例**：
```json
{
  "status": "success",
  "scope": "全台灣核心骨幹網絡",
  "total_flows": 19,
  "congested_count": 2,
  "heavy_count": 4,
  "description": "全台核心骨幹共監控 19 條點對點傳輸線路，目前有 2 條高負載壅塞線路與 4 條繁忙線路。"
}
```

---

### 🛠️ 工具 4：`search_wifi_around_location(query)`
* **用途**：輸入具體地標、商圈或地址，自動定位座標並搜尋周邊可用的免費公共 WiFi 熱點清單。
* **資料來源**：Google Geocode 座標定位 + iTaiwan / TaipeiFree 18,046 筆熱點。
* **參數**：
  * `query` (str): 地名或景點（如 `"台北101"`、`"高雄駁二"`、`"逢甲夜市"`）。
* **適用問句**：「我在台北車站附近，哪裡有免費 WiFi？」、「駁二特區周邊有哪些熱點？」。
* **回傳範例**：
```json
{
  "status": "success",
  "query": "台北101",
  "resolved_center": {"lat": 25.0339, "lng": 121.5644},
  "total_found": 4405,
  "nearby_hotspots": [
    {
      "source": "TaipeiFree",
      "name": "台北101/世貿捷運站",
      "address": "110臺北市信義區信義路5段20號地下層",
      "latitude": 25.0331,
      "longtitude": 121.5638
    }
  ],
  "description": "已定位到 '台北101'，該區域共有 4405 個免費 WiFi 熱點，已列出前 10 處詳細地點。"
}
```

---

### 🛠️ 工具 5：`get_wifi_city_statistics(county?)`
* **用途**：查詢全台灣或指定縣市的公共 WiFi 熱點分佈統計與熱門行政區分佈。
* **參數**：
  * `county` (str | int, 選填): 縣市名稱（如 `"台中市"`）或留空取得全台排行。
* **適用問句**：「全台灣哪裡公共 WiFi 最多？」、「台南市哪個區熱點最多？」。
* **回傳範例**：
```json
{
  "status": "success",
  "scope": "全台灣",
  "total_hotspots": 18046,
  "top_counties": [
    {"county_name": "臺北市", "count": 4405},
    {"county_name": "新北市", "count": 2774},
    {"county_name": "臺中市", "count": 1850}
  ],
  "description": "全台灣目前共有 18046 處公共 WiFi 熱點，熱點最多的前三縣市為：臺北市(4405處), 新北市(2774處), 臺中市(1850處)。"
}
```

---

### 🛠️ 工具 6：`get_county_telecom_density(county, period?)`
* **用途**：比較特定縣市中三大電信（中華電信、台灣大哥大、遠傳電信）各自的 4G 與 5G 基地台建設數量。
* **參數**：
  * `county` (str | int): 縣市名稱（如 `"台中市"`、`"高雄"`）。
  * `period` (str, 選填): 民國年月（如 `"115/07"`），預設為最新統計月份。
* **適用問句**：「台中市哪一家電信 5G 蓋得最多？」、「高雄市中華電信和遠傳誰基地台多？」。
* **回傳範例**：
```json
{
  "status": "success",
  "county": "臺中市",
  "period": "115/07",
  "operators": [
    {"provider_name": "中華電信股份有限公司", "5G_count": 630, "4G_count": 1763},
    {"provider_name": "台灣大哥大股份有限公司", "5G_count": 512, "4G_count": 1420},
    {"provider_name": "遠傳電信股份有限公司", "5G_count": 498, "4G_count": 1390}
  ],
  "leader_5G": "中華電信股份有限公司",
  "description": "在 臺中市 (統計期: 115/07)，5G 基地台建設最多的業者為「中華電信股份有限公司」(630座 5G，1763座 4G)。"
}
```

---

### 🛠️ 工具 7：`get_telecom_carrier_growth_trend(provider)`
* **用途**：查詢指定電信業者（中華電信 CHT / 台灣大哥大 TWM / 遠傳電信 FET）近 12 個月全台 4G 與 5G 基地台歷史消長與淨成長。
* **參數**：
  * `provider` (str): 電信名稱或代碼（如 `"中華電信"`、`"CHT"`、`"遠傳"`、`"TWM"`）。
* **適用問句**：「中華電信過去一年 5G 基地台增加了多少？」、「遠傳近期的建設速度如何？」。
* **回傳範例**：
```json
{
  "status": "success",
  "provider_code": "CHT",
  "provider_name": "中華電信股份有限公司",
  "observation_period_range": "114/08 ~ 115/07",
  "latest_totals": {"5G": 5677, "4G": 18230, "period": "115/07"},
  "earliest_totals": {"5G": 4850, "4G": 18900, "period": "114/08"},
  "5G_net_growth": 827,
  "description": "「中華電信股份有限公司」自 114/08 至 115/07，全台 5G 基地台由 4850 座成長至 5677 座 (淨增長 827 座)。"
}
```

---

## 4. Prompt Engineering & 角色設定指引

AI Agent 的系統提示詞（System Prompt）建議規範如下：

```markdown
你是由 HolyPing 開發的專業網路診斷與空間導航智慧助理。
你的目標是以繁體中文、客觀且具備數據佐證的語調，回答使用者關於全台灣網路狀態、基地台分佈、訊號壅塞、公共 WiFi 熱點與電信商 5G 涵蓋的問題。

【行為原則】
1. 當使用者詢問特定區域的網路狀況時，優先呼叫 `get_point_to_point_traffic_flows` 與 `get_realtime_network_traffic` 分析是否存在壅塞。
2. 當使用者詢問周邊上網地點時，呼叫 `search_wifi_around_location` 並列出具體名稱、地址與來源。
3. 當使用者比較電信公司訊號品質時，呼叫 `get_county_telecom_density` 提供精確的 4G/5G 基地台數量客觀比較，避免主觀偏見。
4. 簡明扼要，直接給出答案與行動建議，消除使用者的斷線與延遲焦慮。
```

---

## 5. 快速測試 (Smoke Test)

可直接在終端機使用 Python 驗證全工具鏈：

```powershell
& C:\\Users\\william\\anaconda3\\python.exe -c "
from agent.tools import execute_tool, TOOL_DECLARATIONS
print(f'已就緒 Tools 總數: {len(TOOL_DECLARATIONS)}')
res = execute_tool('get_county_telecom_density', {'county': '台北市'})
print(res['description'])
"
```
"""

out = Path(__file__).resolve().parent.parent / "AGENT.md"
out.write_text(content, encoding="utf-8")
print(f"Updated {out} successfully.")
