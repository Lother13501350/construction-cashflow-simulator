"""逐月比對 Python 工具值與 Excel 公式參考值，輸出差異表。

用法： python validation/compare.py
輸出： validation/comparison_monthly.csv   每方案 × 每月 × 每欄位：參考值、工具值、差異
       validation/comparison_summary.csv   每方案關鍵指標的比對
"""
import sys
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from cashflow import load_case, simulate, summarize  # noqa: E402

TOL = 0.01  # 元
FIELDS = ["cost_paid", "certified_billing", "retention_withheld", "advance_recovered", "receipts",
          "funding_gap", "loan_in_month", "interest", "borrow_interest", "repayment", "loan_end", "cash_end"]
KEYS = ["max_funding_gap", "max_loan", "total_interest", "ending_cash", "ending_loan"]

items, progress, scenarios = load_case(ROOT / "data")
wb = load_workbook(ROOT / "validation/excel_check.xlsx", data_only=True)

monthly, summary = [], []
for sc in scenarios:
    ws = wb[f"Ledger_{sc.scenario}"[:31]]
    header = [c.value for c in ws[10]]
    rows = []
    r = 12
    while isinstance(ws.cell(r, 1).value, (int, float)):
        rows.append([ws.cell(r, j + 1).value for j in range(len(header))])
        r += 1
    if rows and rows[0][1] is None:
        raise RuntimeError("Excel 檔還沒有計算結果，請先執行 recalc_excel.ps1 或用 Excel 開啟存檔")
    ref = pd.DataFrame(rows, columns=header)
    excel_sum = {ws.cell(i, 1).value: ws.cell(i, 2).value for i in range(r + 1, r + 1 + len(KEYS))}

    tool = simulate(items, progress, sc)
    for f in FIELDS:
        for t in range(len(tool)):
            a, b = float(ref.loc[t, f]), float(tool.loc[t, f])
            monthly.append({"scenario": sc.scenario, "month": t, "field": f,
                            "excel_ref": a, "tool": b, "diff": b - a})
    ts = summarize(tool, sc)
    for k in KEYS:
        summary.append({"scenario": sc.scenario, "metric": k, "excel_ref": excel_sum[k], "tool": ts[k],
                        "diff": ts[k] - excel_sum[k]})

monthly, summary = pd.DataFrame(monthly), pd.DataFrame(summary)
monthly.to_csv(ROOT / "validation/comparison_monthly.csv", index=False, encoding="utf-8-sig")
summary.to_csv(ROOT / "validation/comparison_summary.csv", index=False, encoding="utf-8-sig")

n_bad = (monthly["diff"].abs() > TOL).sum()
print(f"逐月比對 {len(monthly)} 個數值，差異超過 {TOL} 元者：{n_bad}；最大絕對差異 {monthly['diff'].abs().max():.2e}")
pd.set_option("display.width", 200)
print(summary.round(2).to_string(index=False))
