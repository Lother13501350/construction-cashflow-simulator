"""產生教學模擬案例的輸入檔（三層樓 RC 住宅，30 個估價項目）。

這是自行建立的測試資料，非真實工程紀錄。執行一次即可在 data/ 產生：
  items.csv      各估價項目的施工成本、合約價、成本支付延遲（月）
  progress.csv   各項目每月新增進度（比例，0~1，每列合計為 1）
  scenarios.csv  比較的付款方案參數

用法： python src/make_case.py
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
MONTHS = 9  # 第 9 月完工驗收

# (編號, 名稱, 類別, 施工成本 NT$, {月份: 進度比例})
ITEMS = [
    (1, "臨時設施（工務所、圍籬、臨時水電）", "臨時設施", 150_000, {1: .6, **{m: .05 for m in range(2, 10)}}),
    (2, "放樣與測量", "臨時設施", 30_000, {1: 1}),
    (3, "整地及土方開挖", "土方", 220_000, {1: 1}),
    (4, "土方回填及剩餘土方處理", "土方", 120_000, {2: .6, 3: .4}),
    (5, "基礎 PC 及防水", "基礎", 90_000, {1: .5, 2: .5}),
    (6, "基礎鋼筋", "基礎", 380_000, {2: 1}),
    (7, "基礎模板", "基礎", 260_000, {2: 1}),
    (8, "基礎混凝土", "基礎", 330_000, {2: 1}),
    (9, "1F 柱牆鋼筋", "1F 結構", 260_000, {3: 1}),
    (10, "1F 柱牆模板", "1F 結構", 230_000, {3: 1}),
    (11, "2F 梁板鋼筋", "1F 結構", 300_000, {3: .5, 4: .5}),
    (12, "2F 梁板模板", "1F 結構", 280_000, {3: .5, 4: .5}),
    (13, "1F 柱牆及 2F 梁板混凝土", "1F 結構", 340_000, {4: 1}),
    (14, "2F 柱牆鋼筋", "2F 結構", 250_000, {4: .3, 5: .7}),
    (15, "2F 柱牆模板", "2F 結構", 220_000, {5: 1}),
    (16, "3F 梁板鋼筋", "2F 結構", 290_000, {5: .5, 6: .5}),
    (17, "3F 梁板模板", "2F 結構", 270_000, {5: .5, 6: .5}),
    (18, "2F 柱牆及 3F 梁板混凝土", "2F 結構", 330_000, {6: 1}),
    (19, "3F 柱牆鋼筋", "3F 結構", 240_000, {6: .4, 7: .6}),
    (20, "3F 柱牆模板", "3F 結構", 210_000, {7: 1}),
    (21, "屋頂層梁板鋼筋及模板", "3F 結構", 430_000, {7: 1}),
    (22, "3F 柱牆及屋頂層混凝土", "3F 結構", 320_000, {7: 1}),
    (23, "外牆砌磚及粉刷", "裝修", 520_000, {7: .2, 8: .5, 9: .3}),
    (24, "內牆隔間及粉刷", "裝修", 420_000, {6: .2, 7: .3, 8: .5}),
    (25, "屋頂防水隔熱", "裝修", 210_000, {8: 1}),
    (26, "門窗工程", "裝修", 480_000, {7: .2, 8: .5, 9: .3}),
    (27, "地坪及磁磚工程", "裝修", 450_000, {8: .4, 9: .6}),
    (28, "油漆工程", "裝修", 300_000, {8: .3, 9: .7}),
    (29, "水電管線及設備", "水電",
     950_000, {1: .05, 2: .1, 3: .1, 4: .1, 5: .1, 6: .1, 7: .1, 8: .15, 9: .2}),
    (30, "竣工清潔、測試及驗收", "驗收", 120_000, {9: 1}),
]

CONTRACT_TOTAL = 10_000_000


def main() -> None:
    DATA.mkdir(exist_ok=True)
    rows, prog = [], []
    for item_id, name, cat, cost, plan in ITEMS:
        assert abs(sum(plan.values()) - 1) < 1e-9, f"項目 {item_id} 進度合計不為 1"
        # 合約單價 = 成本 / 0.9，取至千元；差額由最大項目吸收，使合約總價剛好 1,000 萬
        rows.append({"item_id": item_id, "name": name, "category": cat, "cost": cost,
                     "contract_price": round(cost / 0.9, -3), "cost_pay_lag": 0})
        prog.append({"item_id": item_id, **{f"M{m}": plan.get(m, 0) for m in range(1, MONTHS + 1)}})

    items = pd.DataFrame(rows)
    items.loc[items["cost"].idxmax(), "contract_price"] += CONTRACT_TOTAL - items["contract_price"].sum()
    items["contract_price"] = items["contract_price"].astype(int)
    assert items["cost"].sum() == 9_000_000 and items["contract_price"].sum() == CONTRACT_TOTAL

    scenarios = pd.DataFrame([
        {"scenario": "A_延遲2月", "payment_delay": 2, "retention_rate": .05, "retention_release_month": 15,
         "advance_rate": 0, "advance_recovery_rate": .10, "initial_cash": 0, "annual_rate": .06},
        {"scenario": "B_延遲1月", "payment_delay": 1, "retention_rate": .05, "retention_release_month": 15,
         "advance_rate": 0, "advance_recovery_rate": .10, "initial_cash": 0, "annual_rate": .06},
        {"scenario": "C_延遲2月+預付10%", "payment_delay": 2, "retention_rate": .05, "retention_release_month": 15,
         "advance_rate": .10, "advance_recovery_rate": .10, "initial_cash": 0, "annual_rate": .06},
    ])

    items.to_csv(DATA / "items.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(prog).to_csv(DATA / "progress.csv", index=False, encoding="utf-8-sig")
    scenarios.to_csv(DATA / "scenarios.csv", index=False, encoding="utf-8-sig")
    print(f"寫入 {len(items)} 個項目；成本 {items['cost'].sum():,}，合約價 {items['contract_price'].sum():,}")


if __name__ == "__main__":
    main()
