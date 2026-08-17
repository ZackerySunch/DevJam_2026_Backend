import pandas as pd

df = pd.read_csv("base_station_density.csv", encoding="utf-8-sig")

filtered = df[
    (df["縣市"] == "宜蘭縣") & (df["業者名稱"] == "中華電信股份有限公司")
].sort_values("統計期")

filtered.to_json("yilan_cht_filtered.json", orient="records", force_ascii=False, indent=2)

print(f"wrote {len(filtered)} rows -> yilan_cht_filtered.json")
