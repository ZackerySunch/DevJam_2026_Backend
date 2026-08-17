# HolyPing Backend API 參考文件

所有 endpoint 都吃 / 回傳 JSON，錯誤格式統一為 `{"detail": "錯誤訊息"}`（400 = 參數錯誤，500 = 伺服器/設定錯誤）。

縣市一律支援使用整數 index（`0`~`21`）或中文全名（如 `臺北市`、`台北市`），縣市對照表見 [data/processed/county_index.json](data/processed/county_index.json)（`0=南投縣`、`13=臺北市`...依此類推）。

---

# 功能 1：Signal（基地台位置 × 點對點網路流向圖） — prefix `/api/signal`

結合 NCC 實體基地台觀測資料與 Cloudflare Radar 即時流量數據，呈現「3D 基地台發光柱」與「底層微血管 / 骨幹粒子流光線」。

## 使用流程

1. **3D 基地台發光柱**：呼叫 `GET /stations?county=13`（預設臺北市），取得各基地台精確經緯度、訊號涵蓋半徑、即時負載指數與 `is_pulsing` 狀態。
2. **點對點微血管/骨幹流量光線（粒子流）**：呼叫 `GET /flows?county=13` 取得該縣市內基地台至區域匯聚節點的微血管流量線；不帶參數或 `county=-1` 則取得全台灣跨縣市核心骨幹流量網絡。
3. **閃爍連動**：當某條線路或基地台 `status == "congested"` 且 `is_pulsing == true` 時，前端將該區光柱與流向線切換為「高頻脈衝閃爍」效果（依 `pulse_frequency` 頻率跳動）。
4. **全台總覽脈衝**：呼叫 `GET /traffic` 拿 Cloudflare Radar 當前全台灣即時流量指數。

---

## `GET /api/signal/flows` 或 `GET /api/signal/traffic_flows`

取得點對點（Point-to-Point）網路流量流向數據（底層微血管光線 / 粒子流數據）。

**Request**：Query string，`county`（可選，縣市 index 0-21；省略或傳 `-1` 取得全台骨幹流向）。
```
GET /api/signal/flows?county=13
GET /api/signal/flows
```

**Response 範例**
```json
[
  {
    "id": "st_flow_13_001",
    "type": "access_link",
    "from_name": "臺北市基地台 #1 (LTE)",
    "from_lat": 25.0854,
    "from_lng": 121.5254,
    "to_name": "台北核心網際網路交換中心 (TPIX)",
    "to_lat": 25.0425,
    "to_lng": 121.5358,
    "traffic_mbps": 780.5,
    "bandwidth_mbps": 1000.0,
    "load_percentage": 78.1,
    "status": "normal",
    "pulse_frequency": 1.6,
    "latency_ms": 12.0
  }
]
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | string | 線路/流向唯一識別碼 |
| `type` | string | `"access_link"` (基地台微血管流向) 或 `"backbone"` (跨縣市核心骨幹) |
| `from_name` / `to_name` | string | 起點與終點名稱 |
| `from_lat` / `from_lng` | float | **起點精確經緯度** |
| `to_lat` / `to_lng` | float | **終點精確經緯度** |
| `traffic_mbps` / `traffic_gbps` | float | 即時傳輸流量數值 |
| `load_percentage` | float | 當前頻寬負載百分比（0.0 ~ 100.0%） |
| `status` | string | 狀態：`"normal"` (正常流動) / `"heavy"` (繁忙加速) / `"congested"` (高頻脈衝閃爍) |
| `pulse_frequency` | float | 脈衝跳動頻率 (Hz) |
| `latency_ms` | float | 估計線路延遲 (ms) |

---

## `GET /api/signal/stations`

基地台座標與即時硬體負載/脈衝狀態（給 3D 光柱地圖用）。

**Request**：Query string，`county`（可選，縣市 index 0-21，預設 `13` 臺北市；傳 `-1` 拿全台灣所有 10,733 筆）。
```
GET /api/signal/stations?county=13
```

**Response 範例**
```json
[
  {
    "radio": "LTE",
    "lat": 25.0854,
    "lng": 121.5254,
    "range_m": 1000,
    "samples": 8,
    "county": "臺北市",
    "traffic_load": 0.95,
    "status": "normal",
    "is_pulsing": false,
    "pulse_rate": 0.8
  }
]
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `radio` | string | 制式，`"LTE"` 或 `"UMTS"` |
| `lat` / `lng` | float | **基地台精確經緯度座標** |
| `range_m` | int | 訊號涵蓋半徑（公尺），決定 3D 光柱粗細/範圍 |
| `samples` | int | 該基地台觀測樣本數 |
| `county` | string \| null | 縣市全名 |
| `traffic_load` | float | 當前基地台負載指數 |
| `status` | string | `"normal"` / `"heavy"` / `"congested"` |
| `is_pulsing` | bool | **是否觸發高頻脈衝閃爍**（`true` 時驅動光柱高頻跳動） |
| `pulse_rate` | float | 光柱脈衝頻率 |

---

## `GET /api/signal/traffic`

台灣目前這個時間點的整體流量指數（Cloudflare Radar 原始脈衝數據，後端 15 分鐘快取）。

**Response 範例**
```json
{ "value": 1.0, "timestamp": "2026-08-17T14:00:00Z" }
```

---

# 功能 2：Uplink（國際海纜狀態 × 異常事件） — prefix `/api/uplink`

## `GET /api/uplink/cables`

所有海底電纜清單（含路徑幾何與當前狀態）。

## `GET /api/uplink/incidents`

海纜事故歷史紀錄清單（可選帶 `active_only=true`）。

## `POST /api/uplink/get_events` 或 `GET /api/uplink/events`

取得即時海纜異常事件。

---

# 功能 3：Navigator（公共 WiFi × AI 嚮導） — prefix `/api/navigator`

## `GET /api/navigator/counties`

全台 22 縣市熱點總數統計。

## `GET /api/navigator/hotspots` 或 `POST /api/navigator/hotspots`

取得 WiFi 熱點精確位置（嚴格回傳 5 大核心欄位：`source`, `name`, `address`, `latitude`, `longtitude`）。

```json
[
  {
    "source": "iTaiwan",
    "name": "中央聯合辦公大樓南棟",
    "address": "100臺北市中正區徐州路5號1樓",
    "latitude": 25.04221,
    "longtitude": 121.51947
  }
]
```

## `POST /api/navigator/nearby_by_text`

透過地名或地址搜尋周邊熱點（Body: `{"query": "台北101"}`）。

---

# 功能 4：Density（三大電信 4G/5G 基地台歷史密度） — prefix `/api/density`

## `POST /api/density/provider`

查詢指定電信業者近 12 個月全台 22 縣市基地台消長（Body: `{"provider": "CHT"}`）。

## `POST /api/density/location`

查詢指定縣市與時間點的 4G/5G 基地台分佈（Body: `{"location": 13, "time": "115/07"}`）。

---

# 功能 5：AI Agent（網路異常診斷） — prefix `/api/agent`

## 運作方式

不是直接接 LLM，而是三段式管線，全部由 Simaic 平台上設定好的 agent 驅動（`agent/call_ai.py`）：

1. **decision**：判斷使用者的問題需要查哪些真實資料（例如「哪個縣市」「要不要查海纜狀態」）
2. **decoder**（`agent/decoder.py`）：依 decision 的判斷，實際呼叫我們自己的後端資料（`Feature.uplink` 海纜事故/狀態、`Feature.density` 4G/5G 密度、`Feature.navigator` WiFi），**不會用假資料**
3. **expert**：拿使用者原始問題 + 上一步查到的真實資料，生成最終的診斷回答

好處是回答一定有真實數字佐證（例如「目前 5 條海纜斷訊：APG、EAC1...」），不會憑空瞎猜。

---

## `POST /chat`

**Request**
```json
{ "query": "台北的5G基地台多不多？海纜有沒有斷線？" }
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `query` | string | 自然語言問題，中文即可 |

**Response**
```json
{ "answer": "根據 HolyPing 平台的最新監控數據...臺北市共有 7,299 座 5G 基地台...目前 12 條正常、5 條斷訊..." }
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `answer` | string | 自然語言診斷回答（繁體中文） |

**注意事項**：
- 這個 endpoint 會維持對話上下文（Simaic 端記住 `task_id`），同一個後端 process 內連續呼叫會被視為同一段對話的延續
- 目前是同步阻塞呼叫，Simaic 回應通常要幾秒鐘，前端要處理 loading 狀態

**錯誤**：`502`：Simaic API 呼叫失敗（網路問題、上游服務錯誤），`detail` 會帶原始錯誤訊息
