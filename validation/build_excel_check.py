"""建立獨立的 Excel 公式試算表（validation/excel_check.xlsx）。

所有月計算都寫成 Excel 公式（不是把 Python 結果貼進去），由 Excel 自行計算，
作為與 Python 工具逐月比對的參考值。

用法： python validation/build_excel_check.py
之後用 Excel 開啟並存檔（或執行 recalc_excel.ps1）讓公式算出數值，再執行 compare.py。
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter as col

ROOT = Path(__file__).resolve().parent.parent
items = pd.read_csv(ROOT / "data/items.csv", encoding="utf-8-sig")
progress = pd.read_csv(ROOT / "data/progress.csv", encoding="utf-8-sig").set_index("item_id").loc[items["item_id"]]
scenarios = pd.read_csv(ROOT / "data/scenarios.csv", encoding="utf-8-sig")

N = len(items)
M = progress.shape[1]                      # 施工月數
MAX_LAG = int(items["cost_pay_lag"].max())
H_PAY = M + MAX_LAG                        # 成本支付最晚月份
r0, r1 = 2, N + 1                          # 項目資料列範圍
P0, P1 = col(6), col(5 + M)                # 進度欄 F..
bold = Font(bold=True)
head = PatternFill("solid", fgColor="DDE6F2")

wb = Workbook()
ws = wb.active
ws.title = "Items"
ws.append(["item_id", "name", "cost", "contract_price", "cost_pay_lag"] + [f"M{m}" for m in range(1, M + 1)])
for (_, it), (_, pr) in zip(items.iterrows(), progress.iterrows()):
    ws.append([it.item_id, it["name"], it.cost, it.contract_price, it.cost_pay_lag] + list(pr.values))
ws.append(["合計", None, f"=SUM(C{r0}:C{r1})", f"=SUM(D{r0}:D{r1})"])

# 各項目各月應付成本（考慮支付延遲）
cp = wb.create_sheet("CostPaid")
cp.append(["item_id"] + list(range(1, H_PAY + 1)))
for r in range(r0, r1 + 1):
    row = [f"=Items!A{r}"]
    for m in range(1, H_PAY + 1):
        c = col(m + 1)
        row.append(f"=IF(AND({c}$1-Items!$E{r}>=1,{c}$1-Items!$E{r}<={M}),"
                   f"Items!$C{r}*INDEX(Items!${P0}{r}:${P1}{r},{c}$1-Items!$E{r}),0)")
    cp.append(row)
CP_RANGE = f"CostPaid!$B${r0}:${col(H_PAY + 1)}${r1}"

COLS = ["month", "cost_paid", "certified_billing", "retention_withheld", "advance_recovered", "net_due",
        "receipt_progress", "receipt_retention", "receipt_advance", "receipts", "cum_cost_paid", "funding_gap",
        "loan_in_month", "cash_after_pay", "interest", "cash_after_receipts", "borrow_interest",
        "cash_after_interest", "repayment", "loan_end", "cash_end"]

for _, s in scenarios.iterrows():
    sh = wb.create_sheet(f"Ledger_{s.scenario}"[:31])
    params = [("payment_delay", s.payment_delay), ("retention_rate", s.retention_rate),
              ("retention_release_month", s.retention_release_month), ("advance_rate", s.advance_rate),
              ("advance_recovery_rate", s.advance_recovery_rate), ("initial_cash", s.initial_cash),
              ("annual_rate", s.annual_rate), ("advance_amount", f"=B4*Items!D{r1 + 1}")]
    for i, (k, v) in enumerate(params, start=1):
        sh.cell(i, 1, k).font = bold
        sh.cell(i, 2, v)
    horizon = max(int(s.retention_release_month), M + int(s.payment_delay), H_PAY)
    HR, IR, F = 10, 11, 12                 # 表頭列、期初列、第 0 月所在列
    L = F + horizon                        # 最後一月所在列
    for j, name in enumerate(COLS, start=1):
        c = sh.cell(HR, j, name); c.font = bold; c.fill = head
    sh.cell(IR, 1, "期初")
    sh.cell(IR, 20, 0)                     # loan_end
    sh.cell(IR, 21, "=B6")                 # cash_end
    for t in range(horizon + 1):
        r, p = F + t, F + t - 1
        f = {
            "A": t,
            "B": f"=IF(AND(A{r}>=1,A{r}<={H_PAY}),SUM(INDEX({CP_RANGE},0,A{r})),0)",
            "C": f"=IF(AND(A{r}>=1,A{r}<={M}),SUMPRODUCT(Items!$D${r0}:$D${r1},INDEX(Items!${P0}${r0}:${P1}${r1},0,A{r})),0)",
            "D": f"=$B$2*C{r}",
            "E": f"=IF($B$8>0,MIN($B$5*C{r},$B$8-SUM(E${IR}:E{p})),0)",
            "F": f"=C{r}-D{r}-E{r}",
            "G": f"=IF(A{r}-$B$1>=1,INDEX($F${F}:$F${L},A{r}-$B$1+1),0)",
            "H": f"=IF(A{r}=$B$3,SUM($D${F}:$D${L}),0)",
            "I": f"=IF(A{r}=0,$B$8,0)",
            "J": f"=G{r}+H{r}+I{r}",
            "K": f"=SUM(B${F}:B{r})",
            "L": f"=K{r}-SUM(J${IR}:J{p})-$B$6",
            "M": f"=T{p}+MAX(0,B{r}-U{p})",
            "N": f"=MAX(0,U{p}-B{r})",
            "O": f"=M{r}*$B$7/12",
            "P": f"=N{r}+J{r}",
            "Q": f"=MAX(0,O{r}-P{r})",
            "R": f"=MAX(0,P{r}-O{r})",
            "S": f"=MIN(R{r},M{r}+Q{r})",
            "T": f"=M{r}+Q{r}-S{r}",
            "U": f"=R{r}-S{r}",
        }
        for c, v in f.items():
            sh[f"{c}{r}"] = v
    s0 = L + 2
    summary = [("max_funding_gap", f"=MAX(0,MAX(L{F}:L{L}))"),
               ("max_loan", f"=MAX(MAX(M{F}:M{L}),MAX(T{F}:T{L}))"),
               ("total_interest", f"=SUM(O{F}:O{L})"),
               ("ending_cash", f"=U{L}"),
               ("ending_loan", f"=T{L}")]
    for i, (k, v) in enumerate(summary):
        sh.cell(s0 + i, 1, k).font = bold
        sh.cell(s0 + i, 2, v)
    for j in range(2, len(COLS) + 1):
        sh.column_dimensions[col(j)].width = 14
        for r in range(F, s0 + len(summary)):
            sh.cell(r, j).number_format = "#,##0.00"

out = ROOT / "validation/excel_check.xlsx"
wb.save(out)
print("寫入", out)
