"""產生手算驗證工作表（validation/hand_check_worksheet.xlsx）。

工作表「手算」只列出要算的項目與輸入資料提示，答案欄留白，由組員手算後填入。
工具計算值放在另一個工作表「工具值」；填入手算值後，「比對」欄會自動顯示 ✓ 或差異。
請先手算、再看比對結果，不要先打開「工具值」。

用法： python validation/make_hand_check.py
"""
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from cashflow import item_monthly, load_case, simulate  # noqa: E402

TOL = 1  # 元；手算四捨五入的容許差

items, progress, scenarios = load_case(ROOT / "data")
by_name = {s.scenario: s for s in scenarios}
incurred, _, billing = item_monthly(items, progress)
item = items.set_index("item_id")

rows = []  # (編號, 方案, 月份, 工項, 項目, 提示, 工具值)


def add(scenario, month, item_label, quantity, hint, value):
    rows.append((f"H{len(rows) + 1:02d}", scenario, month, item_label, quantity, hint, float(value)))


# 1) 工項層級：成本與請款按月分配
for iid in (6, 23, 29):
    it = item.loc[iid]
    for m in progress.columns:
        share = progress.loc[iid, m]
        if share == 0:
            continue
        mm = int(m[1:])
        add("—", mm, f"{iid} {it['name']}", "當月施工成本",
            f"成本 {it.cost:,} × 第 {mm} 月進度 {share:.0%}", incurred.loc[iid, mm])
        add("—", mm, f"{iid} {it['name']}", "當月核定請款",
            f"合約價 {it.contract_price:,} × 第 {mm} 月進度 {share:.0%}", billing.loc[iid, mm])

# 2) 方案 A 第 1～4 月逐月帳
sc_a = scenarios[0]
lg = simulate(items, progress, sc_a).set_index("month")
hints = {
    "cost_paid": ("月初應付成本", "30 個工項當月施工成本合計"),
    "certified_billing": ("當月核定請款", "30 個工項當月核定請款合計"),
    "receipts": ("月末收款", f"第 t−{sc_a.payment_delay} 月核定請款 × (1 − 保留款 {sc_a.retention_rate:.0%})"),
    "loan_in_month": ("月內借款本金", "上月月末借款 + max(0, 本月應付成本 − 上月月末現金)"),
    "interest": ("當月利息", f"月內借款本金 × {sc_a.annual_rate:.0%} ÷ 12"),
    "loan_end": ("月末借款", "月內借款本金 + 付息不足的新增借款 − 還本"),
    "cash_end": ("月末現金", "收款 − 利息 − 還本後剩下的現金"),
}
for t in range(1, 5):
    for col, (label, hint) in hints.items():
        add(sc_a.scenario, t, "全部", label, hint, lg.loc[t, col])
add(sc_a.scenario, "全期", "全部", "最大資金缺口（不含利息）",
    "各月「累計已付成本 − 上月底以前累計收款」的最大值", max(0.0, lg["funding_gap"].max()))

# 3) 方案 D：契約範本區間扣回
sc_d = next(s for s in scenarios if s.advance_recovery_method == "band")
lg_d = simulate(items, progress, sc_d).set_index("month")
contract = items["contract_price"].sum()
advance = sc_d.advance_rate * contract
lo, hi = sc_d.recovery_band_start * contract, sc_d.recovery_band_end * contract
add(sc_d.scenario, 0, "全部", "預付款", f"合約價 {contract:,} × {sc_d.advance_rate:.0%}", advance)
for t in range(1, len(progress.columns) + 1):
    add(sc_d.scenario, t, "全部", "預付款扣回",
        f"預付款 ÷ ({hi:,.0f} − {lo:,.0f}) × 本月累計估驗落在 {lo:,.0f}～{hi:,.0f} 區間內的金額",
        lg_d.loc[t, "advance_recovered"])

# ---------------------------------------------------------------- 寫檔
wb = Workbook()
ws = wb.active
ws.title = "手算"
ws.append(["說明：黃色欄填入手算結果（元，可四捨五入到整數）。填完後「比對」欄會顯示 ✓ 或差異。"
           "請先算完再看比對，不要先打開「工具值」工作表。"])
ws.merge_cells("A1:H1")
ws.append([])
head = ["編號", "方案", "月份", "工項", "要算的項目", "輸入資料與算法提示", "手算值", "比對"]
ws.append(head)
bold, fill_h = Font(bold=True), PatternFill("solid", fgColor="DDE6F2")
fill_in = PatternFill("solid", fgColor="FFF2CC")
for c in ws[3]:
    c.font, c.fill = bold, fill_h

tv = wb.create_sheet("工具值")
tv.append(["編號", "工具值"])
for i, (rid, scen, month, it, qty, hint, value) in enumerate(rows):
    r = i + 4
    ws.append([rid, scen, month, it, qty, hint, None,
               f'=IF(G{r}="","",IF(ABS(G{r}-工具值!B{i + 2})<={TOL},"✓",'
               f'"✗ 差 "&TEXT(G{r}-工具值!B{i + 2},"#,##0.00")))'])
    ws.cell(r, 7).fill = fill_in
    ws.cell(r, 7).number_format = "#,##0.00"
    tv.append([rid, round(value, 4)])
for col, width in zip("ABCDEFGH", (7, 26, 7, 22, 22, 62, 16, 18)):
    ws.column_dimensions[col].width = width
for row in ws.iter_rows(min_row=4):
    row[5].alignment = Alignment(wrap_text=True, vertical="top")
ws.freeze_panes = "A4"
tv.sheet_state = "hidden"

out = ROOT / "validation/hand_check_worksheet.xlsx"
wb.save(out)
print(f"寫入 {out}（{len(rows)} 個手算項目）")
