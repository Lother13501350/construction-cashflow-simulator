# 現金流與資金缺口模擬器（第 7 組｜Option B 第六題）

從承包商角度，固定同一工程的進度、成本與合約價，比較不同付款條件（收款延遲、預付款）
對最大資金缺口、最高借款餘額與融資利息的影響。

## 環境與安裝

- Python 3.10 以上（開發環境為 3.12）
- 相依套件見 `requirements.txt`（pandas、matplotlib、openpyxl；notebook 另需 jupyter）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 執行

```powershell
.\.venv\Scripts\python.exe src\make_case.py     # （可省略）重新產生 data\ 的案例輸入檔
.\.venv\Scripts\python.exe src\run.py           # 跑全部方案，輸出到 output\
```

或開啟 `main.ipynb` 依序執行。

## 輸入檔（data\）

| 檔案 | 內容 |
|---|---|
| `items.csv` | 30 個估價項目：施工成本、合約價、成本支付延遲（月） |
| `progress.csv` | 各項目第 1～9 月新增進度比例（每列合計 1） |
| `scenarios.csv` | 付款方案：收款延遲、保留款比例與返還月、預付款與扣回比例、期初現金、年利率 |

案例為自建的三層樓 RC 住宅教學模擬資料，非真實工程紀錄。合約價 1,000 萬元，施工成本 900 萬元。

## 輸出（output\）

- `summary.csv`：各方案最大資金缺口（不含利息、扣除期初現金）、最高借款餘額（含利息）、總利息、期末現金與借款
- `ledger_<方案>.csv`：逐月帳表（成本支付、核定請款、保留款、預付款扣回、收款、借款、利息、還款、現金）
- `item_cost_incurred.csv`、`item_certified_billing.csv`：項目 × 月份的成本與請款分配
- `fig_*.png`：累計現金流、借款餘額、成本與請款 S 曲線

## 計算規則

見 `src/cashflow.py` 開頭說明。重點：月初付成本（不足借款）→ 月內借款本金 × 年利率/12 計息 →
月末收款後先付息（不足新增借款，自次月計息）再還本。保留款按核定請款 5% 扣留、第 15 月月末返還；
預付款按核定請款 10% 逐期扣回，以未扣回餘額為上限。

## 自動測試（tests\）

```powershell
.\.venv\Scripts\python.exe -m pytest
```

包含兩個可手算的小案例（有無預付款，計算過程寫在測試說明中）、預付款扣回上限、成本支付延遲、
輸入檢查，以及正式案例的守恆與方向性檢查。

## 驗證（validation\）

```powershell
.\.venv\Scripts\python.exe validation\build_excel_check.py   # 產生全公式 Excel 試算表
powershell -ExecutionPolicy Bypass -File validation\recalc_excel.ps1   # 用 Excel 重算（需安裝 Microsoft Excel）
.\.venv\Scripts\python.exe validation\compare.py              # 逐月比對，輸出 comparison_*.csv
```

`excel_check.xlsx` 內每個月的數值都是 Excel 公式，獨立於 Python 程式計算。
另外 `run.py` 每次執行都會做守恆檢查：收款總額 = 合約價；期末現金 − 期末借款 = 期初現金 + 合約價 − 成本 − 利息。
