# API 參考

所有 endpoint 都吃/回傳 JSON，錯誤格式統一為 `{"detail": "錯誤訊息"}`（400 = 參數錯誤，500 = 伺服器/設定錯誤）。

縣市一律用整數 index（0-21）表示，不用中文字串比對，對照表見 [data/processed/county_index.json](data/processed/county_index.json)（0=南投縣、13=臺北市...依此類推）。

---

# 功能1：Signal（基地台位置 × 網路流量） — prefix `/api/signal`

## 使用流程

1. 進場先呼叫 `GET /stations`（不帶參數預設臺北市），畫成 3D 光柱；使用者可以自行切換縣市重新呼叫。
2. 呼叫 `GET /traffic` 拿目前這個時間點的流量數字，全部光柱同步套用做「高頻脈衝閃爍」效果，數字越大代表流量越高，脈衝應該越強——**Cloudflare Radar 只有國家級的流量資料，沒有縣市級的區域數據**，所以目前是全台光柱同步閃爍，不是個別縣市各自閃爍。之後前端可以定時（例如每 5-10 分鐘）重打 `/traffic` 更新數字。

---

## `GET /stations`

某縣市的基地台座標，給 3D 光柱地圖用。預設只回傳臺北市，避免一次给太多資料。

**Request**：Query string，`county`（可選，縣市 index 0-21，預設 `13` 臺北市；傳 `-1` 拿全台灣所有 10,733 筆）。
```
GET /api/signal/stations?county=13
```

**Response**
```json
[
  { "radio": "LTE", "lat": 25.0854, "lng": 121.5254, "range_m": 1000, "samples": 8, "county": "臺北市" }
]
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `radio` | string | 制式，`"LTE"` 或 `"UMTS"` |
| `lat` / `lng` | float | 座標 |
| `range_m` | int | 訊號涵蓋半徑（公尺），可用來決定光柱粗細/範圍 |
| `samples` | int | 該基地台的觀測樣本數，數字越大代表資料越可信 |
| `county` | string \| null | 縣市全名。原始資料沒有地址文字，縣市是用 Google 反向地理編碼一次性查出來的；全台約 15 筆（0.1%）查不到，`county` 會是 `null`，這些點只會出現在 `county=-1` 的全台檢視 |

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
| 欄位 | 型別 | 說明 |
|---|---|---|
| `timestamps` | string[] | ISO 8601 時間戳，逐小時 |
| `values` | float[] | 對應時間點的流量指數（Cloudflare Radar 原始正規化數值） |
| `intensity` | float | 0-1，`values` 最後一筆（最新）相對這段時間內最小/最大值的位置，數字越高代表目前處於這段時間的流量高峰，建議直接拿來當光柱閃爍強度 |

**錯誤**：`500`：後端 `.env` 沒設定 `CLOUDFLARE_RADAR_TOKEN`（設定問題，不是使用者輸入錯誤）

---

# 功能3：Navigator（公共 WiFi） — prefix `/api/navigator`

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

## `POST /hotspots`

某縣市（可選：某行政區）的實際熱點清單，給地圖標點用。

**Request**
```json
{ "county": 13, "district": "信義區" }
```
| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `county` | int | 是 | 縣市 index（0-21） |
| `district` | string | 否 | 行政區全名；省略則回傳整個縣市所有熱點（可能到千筆等級，臺北市總共 4,405 筆） |

**Response**
```json
[
  {
    "source": "iTaiwan",
    "name": "台北世貿郵局",
    "area": "臺北市",
    "district": "信義區",
    "address": "110臺北市信義區信義路五段5號",
    "category": "洽公場所",
    "agency": "中華郵政股份有限公司",
    "lat": 25.033317,
    "lng": 121.562303
  }
]
```
| 欄位 | 型別 | 說明 |
|---|---|---|
| `source` | string | `"iTaiwan"` 或 `"TaipeiFree"` |
| `name` | string | 熱點/站點名稱 |
| `area` | string | 縣市全名（繁體「臺」字，非「台」） |
| `district` | string \| null | 行政區全名，極少數為 `null` |
| `address` | string | 完整地址 |
| `category` | string | 場所類型；`iTaiwan` 是「洽公場所」類的分類，`TaipeiFree` 是站點類型（公車站/圖書館/醫院/商圈市集等 12 種） |
| `agency` | string | 管理機關 |
| `lat` / `lng` | float | 座標，小數點後 4-6 位 |

**錯誤**：`county` 不在 0-21 範圍內 → `400`

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

給地點名稱文字（例："台北101"），後端用 Google Geocoding API 轉成座標，再回傳附近熱點。

**Request**
```json
{ "query": "台北101", "radius_m": 500 }
```
| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `query` | string | 是 | 地點名稱、地址、地標，任何 Google 地圖搜得到的文字都可以 |
| `radius_m` | int | 否 | 同 `/nearby`，省略預設 `1000` |

**Response**：跟 `/nearby` 完全一樣的格式（含 `distance_m`）。

**錯誤**：
- `400`：Google 找不到這個地點（文字打錯、太模糊、`radius_m` 不合法）
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
