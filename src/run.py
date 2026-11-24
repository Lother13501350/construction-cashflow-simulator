"""執行全部付款方案，輸出比較表、逐月帳表與圖。

用法： python src/run.py            （讀 data/，寫 output/）
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cashflow import load_case, simulate, summarize, check_identities, item_monthly  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "Noto Sans CJK TC",
                                   "PingFang TC", "Heiti TC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def run(data_dir: Path = ROOT / "data", out_dir: Path = ROOT / "output", show: bool = False):
    out_dir.mkdir(exist_ok=True)
    items, progress, scenarios = load_case(data_dir)

    incurred, paid, billing = item_monthly(items, progress)
    incurred.to_csv(out_dir / "item_cost_incurred.csv", encoding="utf-8-sig")
    billing.to_csv(out_dir / "item_certified_billing.csv", encoding="utf-8-sig")

    ledgers, summary = {}, []
    for sc in scenarios:
        ledger = simulate(items, progress, sc)
        errs = check_identities(items, ledger, sc)
        if errs:
            raise AssertionError(f"{sc.scenario} 守恆檢查失敗：{errs}")
        ledger.round(2).to_csv(out_dir / f"ledger_{sc.scenario}.csv", index=False, encoding="utf-8-sig")
        ledgers[sc.scenario] = ledger
        summary.append(summarize(ledger, sc))

    summary = pd.DataFrame(summary)
    summary.round(0).to_csv(out_dir / "summary.csv", index=False, encoding="utf-8-sig")

    # 圖 1：不含利息的累計現金流
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for name, lg in ledgers.items():
        ax.step(lg["month"], lg["cum_cf_ex_interest"] / 1e4, where="post", label=name)
        ax.plot(lg["month"], -lg["funding_gap"].clip(lower=0) / 1e4, "o", ms=3, color=ax.lines[-1].get_color(),
                alpha=.6)
    ax.axhline(0, color="grey", lw=.8)
    ax.set(xlabel="月份", ylabel="萬元", title="累計現金流（不含利息；點 = 月初付款後的資金缺口）")
    ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(out_dir / "fig_cumulative_cashflow.png", dpi=150)

    # 圖 2：借款餘額
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for name, lg in ledgers.items():
        ax.plot(lg["month"], lg["loan_in_month"] / 1e4, marker="o", ms=3, label=name)
    ax.set(xlabel="月份", ylabel="萬元", title="月內借款餘額（含利息滾入）")
    ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(out_dir / "fig_loan_balance.png", dpi=150)

    # 圖 3：成本與請款 S 曲線
    fig, ax = plt.subplots(figsize=(9, 4.8))
    m = incurred.columns
    ax.plot(m, incurred.sum().cumsum() / 1e4, marker="o", label="累計施工成本")
    ax.plot(m, billing.sum().cumsum() / 1e4, marker="s", label="累計核定請款")
    ax.set(xlabel="月份", ylabel="萬元", title="成本與請款 S 曲線")
    ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(out_dir / "fig_s_curve.png", dpi=150)
    if not show:
        plt.close("all")
    return items, progress, scenarios, ledgers, summary


if __name__ == "__main__":
    *_, summary = run()
    pd.set_option("display.width", 200)
    print(summary.round(0).to_string(index=False))
