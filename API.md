# API 參考

所有 endpoint 都吃/回傳 JSON，錯誤格式統一為 `{"detail": "錯誤訊息"}`（400 = 參數錯誤，500 = 伺服器/設定錯誤）。

縣市一律用整數 index（0-21）表示，不用中文字串�# 功能1：Signal（基地台位置 × 網路流向圖） — prefix `/api/signal`

## 使用流程

1. **3D 基地台發光柱**：呼叫 `GET /stations?county=13`（預設臺北市），取得各基地台精確經緯度、訊號涵蓋範圍、即時負載與 `is_pulsing` 狀態。
2. **點對點微血管/骨幹流量光線（粒子流）**：呼叫 `GET /flows?county=13`，取得該縣市各基地台至區域匯聚節點的微血管流量線；若不帶參數（或 `county=-1`）則取得全台灣跨縣市核心骨幹流量網絡。
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

**Response**
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

**Response**
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

台灣目前這個時間點的整體流量指數（Cloudflare Radar 原始脈衝數據）。

**Request**：無 body，直接 GET。

**Response**
```json
{ "value": 1.0, "timestamp": "2026-08-17T14:00:00Z" }
```
�理編碼一次性查出來的；全台約 15 筆（0.1%）查不到，`county` 會是 `null`，這些點只會出現在 `county=-1` 的全台檢視 |

全台灣沒有澎湖縣/連江縣/金門縣的基地台資料（原始 OpenCelliD 資料集在這三個離島本來就沒有樣本，不是查詢遺漏）。

**錯誤**：`county` 不在 0-21 範圍內（且不是 -1）→ `400`

---

## `GET /traffic`

台灣目前這個時間點的流量數字。**後端有做 15 分鐘快取**，前端可以放心每秒或每分鐘一直打這個 endpoint 做「即時更新」的視覺效果，不會真的每次都打到 Cloudflare（實際上限是 15 分鐘一次，因為 Cloudflare 資料本身最細也只到 15 分鐘一個資料點）——同一個 15 分鐘區間內重複呼叫會拿到一模一樣的數值跟 `timestamp`，是正常的，不是沒更新到。

**Request**：無 body，直接 GET，不用參數。

**Response**
```json
{ "value": 1.0, "timestamp": "2026-08-17T14:00:00Z" }
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `value` | float | 目前流量數字（Cloudflare Radar 原始正規化數值），**數字越大代表流量越高**，越小代表越低，直接拿來對應光柱脈衝強度即可 |
| `timestamp` | string | 這個數值對應的 ISO 8601 時間戳（Cloudflare 目前資料的最新一筆，可能比呼叫當下略晚個幾十分鐘） |

**錯誤**：`500`：後端 `.env` 沒設定 `CLOUDFLARE_RADAR_TOKEN`（設定問題，不是使用者輸入錯誤）

---

# 功能2：Uplink（電纜狀態 × DNS流向圖） — prefix `/api/uplink`

## 使用流程

1. 呼叫 `GET /cables` 拿全部 27 條海纜的路徑座標，依 `status` 決定畫線顏色/動畫：`normal`=正常（綠色流動）、`broken`=斷線（紅色斷裂特效）、`partial`=部分斷線、`building`=規劃中/建置中（虛線，通常沒有完整路徑座標）。
2. 想單獨列出目前有問題的纜線，呼叫 `GET /incidents?active_only=true`。

資料來源：[smc.peering.tw](https://smc.peering.tw) 的公開部署資料（原始資料庫是私有的，但網站本身公開部署了海纜路徑跟事故紀錄），用 `scripts/fetch_cables.py` 抓取，之後要更新最新資料直接重跑該腳本即可。RIPE Atlas 的 DNS/延遲數據還沒接，之後會補在這個 prefix 底下。

---

## `GET /cables`

全部海纜路徑 + 目前狀態。

**Request**：無 body，直接 GET。

**Response**
```json
[
  {
    "id": "apg",
    "name": "APG",
    "color": "#xxxxxx",
    "building": false,
    "available_path": [["TW", "apg-seg-1", "TW-JP"]],
    "equipments": [],
    "segments": [
      { "id": "apg-seg-1", "hidden": false, "coordinates": [[121.5, 25.0], ["..."]] }
    ],
    "status": "broken",
    "active_incidents": [
      {
        "date": "2024-09-18T00:00:00+08:00",
        "status": "disconnected",
        "reason": "unknown",
        "cableid": "apg",
        "segment": "apg-seg-1",
        "title": "...",
        "description": "...",
        "reparing_at": "",
        "resolved_at": ""
      }
    ]
  }
]
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | string | 纜線代號，跟 incidents 的 `cableid` 對應 |
| `name` | string | 纜線全名 |
| `color` | string | 建議畫線顏色（hex） |
| `building` | bool | 是否為規劃中/建置中的纜線 |
| `segments` | array | 每個 segment 有 `coordinates`（`[經度, 緯度]` 陣列，注意是**先經度後緯度**，跟一般 `lat,lng` 相反，因為是 GeoJSON 慣例），畫線直接照順序連起來即可 |
| `status` | string | `"normal"` / `"broken"` / `"partial"` / `"building"`，後端算好的，不用自己判斷 |
| `active_incidents` | array | 這條纜線目前未解決的事故（`resolved_at` 是空字串），沒有問題時是空陣列 |

目前分布：27 條纜線中 12 條 `normal`、5 條 `broken`、4 條 `partial`、6 條 `building`。

---

## `GET /incidents`

事故紀錄清單。

**Request**：Query string，`active_only`（可選，預設 `false`；`true` 只回傳目前未解決的）。
```
GET /api/uplink/incidents?active_only=true
```

**Response**
```json
[
  {
    "date": "2024-09-18T00:00:00+08:00",
    "status": "disconnected",
    "reason": "unknown",
    "cableid": "frnal-nacs",
    "segment": "nacs-seg-2",
    "title": "NACS 香港方向斷線",
    "description": "於 24°43.3750'N 122°5.27'E 處發生故障",
    "reparing_at": "",
    "resolved_at": "2025-11-03T17:11:00+08:00"
  }
]
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `status` | string | `"disconnected"` 全斷 / `"partial_disconnected"` 部分斷線 / `"notice"` 公告事項 |
| `cableid` / `segment` | string | 對應 `/cables` 裡的 `id` / `segments[].id` |
| `resolved_at` | string | 空字串代表**目前仍未解決** |

全部 76 筆，`active_only=true` 目前有 17 筆未解決。

---

# 功能3: 公共WIFI
## 使用流程

前端畫面設計成三層鑽取：

1. **全台總覽**：呼叫 `GET /counties`，畫出 22 縣市的熱點數量分布（例如色階地圖或長條圖）。
2. **點進一個縣市**：呼叫 `POST /districts`，畫出該縣市底下各行政區的熱點數量。
3. **點進一個行政區（或整個縣市）**：呼叫 `POST /hotspots`，拿到實際座標點，在地圖上標記。

另外有獨立的「找附近」流程，不需要先鑽取：

- 使用者給座標（例如點地圖上一點）→ `POST /nearby`
- 使用者打地名文字（例如「台北101」）→ `POST /nearby_by_text`（後端會先用 Google 把文字轉成座標，再做跟 `/nearby` 一樣的事）

資料來源共 2 個、合計 **18,046** 筆熱點：`iTaiwan`（政府機關洽公場所等，14,741 筆）+ `TaipeiFree`（台北市公車站/圖書館/醫院等，3,305 筆，只涵蓋臺北市）。之後可能再加其他來源，物件裡都會有 `source` 欄位標示。

---

## `GET /counties`

全台縣市熱點數量總覽（第一層畫面用）。

**Request**：無 body，直接 GET。

**Response**
```json
{ "0": 540, "1": 259, "2": 456, "...": "...", "13": 4405, "...": "...", "21": 1357 }
```
- key：縣市 index（字串，`"0"`~`"21"`）
- value：該縣市熱點總數（兩個來源合計）

---

## `POST /districts`

點進某縣市後，該縣市各行政區的熱點數量。

**Request**
```json
{ "county": 13 }
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `county` | int | 縣市 index（0-21） |

**Response**
```json
{ "中正區": 744, "信義區": 544, "大安區": 476, "...": "..." }
```
- key：行政區中文全名（例：`"中正區"`、`"三峽區"`、`"魚池鄉"`）
- value：該行政區熱點數
- 極少數（約 0.01%）原始資料地址格式異常、解析不出行政區，會歸類為 `"未分類"`，前端可以選擇忽略或另外顯示

**錯誤**：`county` 不在 0-21 範圍內 → `400`

---

## `GET /api/navigator/hotspots` 或 `POST /api/navigator/hotspots`

取得 WIFI 熱點精確經緯度與完整資料（支援全台 18,046 筆、單一縣市、或特定行政區）。

**Request (GET)**：Query 參數
```
GET /api/navigator/hotspots?county=13&district=信義區
GET /api/navigator/hotspots?county=-1   # 拿全台灣所有 18,046 筆
GET /api/navigator/hotspots             # 不帶參數等同全台灣
```

**Request (POST)**
```json
{ "county": 13, "district": "信義區" }
```
| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `county` | int | 否 | 縣市 index（0-21）；傳 `-1`、`null` 或省略代表**取得全台灣所有 18,046 筆熱點** |
| `district` | string | 否 | 行政區全名；省略則回傳該範圍內所有熱點 |

**Response**
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
| 欄位 | 型別 | 說明 |
|---|---|---|
| `source` | string | 資料來源：`"iTaiwan"` 或 `"TaipeiFree"` |
| `name` | string | 熱點/站點名稱 |
| `address` | string | 完整詳細地址 |
| `latitude` | float | 緯度 |
| `longtitude` | float | 經度 |

**錯誤**：`county` 不在 0-21 範圍內（且不是 -1）→ `400`

---

## `POST /nearby`

給經緯度，找方圓內最近的熱點，依距離排序。

**Request**
```json
{ "lat": 25.0339639, "lng": 121.5644722, "radius_m": 500 }
```
| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `lat` / `lng` | float | 是 | 查詢中心點座標 |
| `radius_m` | int | 否 | 搜尋半徑，**只能是 `500` / `1000` / `2000` 三選一**（給使用者當選項用），省略預設 `1000` |

**Response**：跟 `/hotspots` 的物件格式相同，每筆多一個 `distance_m`（公尺，四捨五入到小數1位），陣列已依距離由近到遠排序。
```json
[
  {
    "source": "TaipeiFree",
    "name": "101國際購物中心-N-松智路",
    "...": "...",
    "lat": 25.034626,
    "lng": 121.565562,
    "distance_m": 170.5
  }
]
```

**錯誤**：`radius_m` 不是 500/1000/2000 之一 → `400`

---

## `POST /nearby_by_text`

給地點名稱文字（例："台北101"），後端用 Google Geocoding API 轉成座標、判斷屬於哪個縣市，回傳該縣市**全部**熱點——不在後端做距離篩選，前端拿到中心點座標後，用自己的圖資（地圖 SDK）自行做「附近」的搜尋/縮放，就跟 `/hotspots` 一樣是整個縣市的資料。

**Request**
```json
{ "query": "台北101" }
```
| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `query` | string | 是 | 地點名稱、地址、地標，任何 Google 地圖搜得到的文字都可以 |

**Response**
```json
{
  "center": { "lat": 25.0332276, "lng": 121.5648681 },
  "county": 13,
  "hotspots": [ { "...": "跟 /hotspots 回傳陣列裡每個物件格式完全一樣" } ]
}
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `center` | object | Google Geocoding 解析出來的座標，前端可以拿來當地圖中心點/縮放目標 |
| `county` | int | 解析出來的縣市 index（0-21） |
| `hotspots` | array | 該縣市**全部**熱點（不分行政區、不篩距離），格式跟 `/hotspots` 一樣 |

**錯誤**：
- `400`：Google 找不到這個地點，或地點不在台灣 22 縣市範圍內（文字打錯、太模糊、查到國外地點）
- `500`：後端環境設定問題（`.env` 沒設 `GOOGLE_MAPS_API_KEY`），不是使用者輸入錯誤，前端可以顯示「服務暫時無法使用」

---

# 功能4：Density（基地台密度） — prefix `/api/density`

## 使用流程

1. 前端先讓使用者選一家業者，呼叫 `POST /provider`，拿回最近 12 個月、22 縣市的 5G/4G 數，畫時間軸滑桿 + 縣市地圖（顏色/高度代表數量）。
2. 使用者拖曳到某個月份、點選某個縣市時，呼叫 `POST /location`，拿回該縣市當月三家業者的細分數字，畫成比較圖表。

`/provider` 回傳的月份 key（例：`"115/07"`）可以直接原封不動傳給 `/location` 的 `time` 參數，兩邊格式是刻意對齊的。

---

## `POST /provider`

依業者查最近 12 個月、22 縣市的 5G/4G 基地台數。

**Request**
```json
{ "provider": "CHT" }
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `provider` | string | 業者代號：`"CHT"`（中華電信）/ `"TWM"`（台灣大哥大）/ `"FET"`（遠傳），大小寫不敏感 |

**Response**
```json
{
  "115/07": {
    "0": [827, 760],
    "1": [312, 358],
    "...": "...",
    "21": [3906, 3200]
  },
  "114/08": { "...": "..." }
}
```
- 外層 key：民國年月字串 `"YYY/MM"`，固定回**最近 12 個月**
- 內層 key：縣市 index（字串，`"0"`~`"21"`）
- value：`[5G數, 4G數]`（固定順序，5G 在前）

**錯誤**：`provider` 不是 CHT/TWM/FET 之一 → `400`

---

## `POST /location`

依縣市 + 時間查該期三家業者的 5G/4G 數。

**Request**
```json
{ "location": 4, "time": "115/07" }
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `location` | int | 縣市 index（0-21） |
| `time` | string | 民國年月 `"YYY/MM"`，建議直接用 `/provider` 回傳的 key |

**Response**
```json
{ "CHT": [827, 760], "TWM": [552, 506], "FET": [602, 482] }
```
- key：業者代號
- value：`[5G數, 4G數]`
- 若該月份/縣市/業者沒有資料（例如 5G 尚未布建），對應數值會是 `0`，不會缺 key

**錯誤**：`location` 不在 0-21 範圍、或 `time` 格式不是 `"YYY/MM"` → `400`
