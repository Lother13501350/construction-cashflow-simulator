"""承包商現金流與資金缺口模擬器：核心計算。

現金流分配、保留款、預付款扣回、借還款及計息均為本組自行實作，
未呼叫任何既有的財務或排程套件（pandas 只用於讀檔與整理表格）。

時間約定（月份 t = 0, 1, 2, ...）
  t = 0      開工前。預付款於此時收到。
  t >= 1     月初：支付當月應付成本，現金不足時借款。
             月內：利息 = 月初借款後的借款本金 × 年利率 / 12。
             月末：收到當月到期的工程款 → 付息（不足時新增借款，自次月計息）→ 以剩餘現金還本。
  請款      第 t 月核定的請款，於第 t + 收款延遲 月月末收款。
            實收 = 核定請款 − 保留款（核定 × 保留比例）− 預付款扣回。
  預付款扣回（兩種方式，均以未扣回餘額為上限）
            proportional：每期扣回 核定請款 × 扣回比例。
            band：依工程採購契約範本 §5(一)1，累計估驗達合約價 20% 起至 80% 止按比例扣回：
                  每期扣回 = 預付款 ÷ (80% − 20%) × 合約價 × 本期累計估驗落在 20%～80% 區間內的金額。
  保留款    累計扣留的保留款於返還月月末一次返還。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd

RECOVERY_METHODS = ("proportional", "band")


@dataclass
class Scenario:
    scenario: str
    payment_delay: int = 2            # 核定後幾個月月末收款
    retention_rate: float = 0.05      # 保留款比例（按核定請款）
    retention_release_month: int = 15 # 保留款返還月份（月末）
    advance_rate: float = 0.0         # 預付款占合約價比例，開工前（t=0）支付
    advance_recovery_rate: float = 0.10  # proportional：每期按核定請款扣回比例
    initial_cash: float = 0.0         # 期初現金
    annual_rate: float = 0.06         # 借款年利率
    advance_recovery_method: str = "proportional"  # "proportional" 或 "band"
    recovery_band_start: float = 0.20  # band：累計估驗達合約價此比例起開始扣回
    recovery_band_end: float = 0.80    # band：累計估驗達合約價此比例時扣回完畢

    def __post_init__(self):
        if self.advance_recovery_method not in RECOVERY_METHODS:
            raise ValueError(f"advance_recovery_method 必須是 {RECOVERY_METHODS} 之一，"
                             f"收到 {self.advance_recovery_method!r}")
        if not 0 <= self.recovery_band_start < self.recovery_band_end <= 1:
            raise ValueError("扣回區間須滿足 0 ≤ recovery_band_start < recovery_band_end ≤ 1")


def advance_recovery(sc: Scenario, advance: float, contract_total: float, certified: float,
                     cum_before: float, unrecovered: float) -> float:
    """單期預付款扣回金額。cum_before 為本期之前的累計核定請款。"""
    if advance <= 0 or unrecovered <= 0:
        return 0.0
    if sc.advance_recovery_method == "proportional":
        due = sc.advance_recovery_rate * certified
    else:  # band
        lo, hi = sc.recovery_band_start * contract_total, sc.recovery_band_end * contract_total
        in_band = max(0.0, min(cum_before + certified, hi) - max(cum_before, lo))
        due = advance / (hi - lo) * in_band
    return min(due, unrecovered)


# ---------------------------------------------------------------- 讀檔
def load_case(data_dir: str | Path):
    data_dir = Path(data_dir)
    items = pd.read_csv(data_dir / "items.csv", encoding="utf-8-sig")
    progress = pd.read_csv(data_dir / "progress.csv", encoding="utf-8-sig").set_index("item_id")
    scenarios = pd.read_csv(data_dir / "scenarios.csv", encoding="utf-8-sig")
    progress = progress.loc[items["item_id"]]
    bad = (progress.sum(axis=1) - 1).abs() > 1e-6
    if bad.any():
        raise ValueError(f"以下項目的每月進度合計不為 1：{list(progress.index[bad])}")
    # 空白欄位視為未填，改用 Scenario 的預設值
    records = [{k: v for k, v in r.items() if not (isinstance(v, float) and math.isnan(v))}
               for r in scenarios.to_dict("records")]
    return items, progress, [Scenario(**r) for r in records]


# ---------------------------------------------------------------- 工項層級：成本與請款按月分配
def item_monthly(items: pd.DataFrame, progress: pd.DataFrame):
    """回傳三張「項目 × 月份」表：當月完成成本、當月應付成本（考慮支付延遲）、當月核定請款。"""
    months = [int(c[1:]) for c in progress.columns]
    p = progress.to_numpy()
    cost = items["cost"].to_numpy()[:, None]
    price = items["contract_price"].to_numpy()[:, None]
    lag = items["cost_pay_lag"].to_numpy()

    incurred = pd.DataFrame(cost * p, index=items["item_id"], columns=months)
    billing = pd.DataFrame(price * p, index=items["item_id"], columns=months)

    last_paid = max(months) + int(lag.max())
    paid = pd.DataFrame(0.0, index=items["item_id"], columns=range(1, last_paid + 1))
    for i, item_id in enumerate(items["item_id"]):
        for m in months:
            paid.loc[item_id, m + lag[i]] += incurred.loc[item_id, m]
    return incurred, paid, billing


# ---------------------------------------------------------------- 專案層級：按月現金流與借款
def simulate(items: pd.DataFrame, progress: pd.DataFrame, sc: Scenario) -> pd.DataFrame:
    _, paid_by_item, billing_by_item = item_monthly(items, progress)
    cost_paid = paid_by_item.sum()          # Series：月份 -> 應付成本
    billing = billing_by_item.sum()         # Series：月份 -> 核定請款
    contract_total = items["contract_price"].sum()

    last_receipt = int(billing.index.max()) + sc.payment_delay
    if sc.retention_release_month < last_receipt:
        raise ValueError("保留款返還月份早於最後一期工程款收款月份")
    horizon = max(sc.retention_release_month, last_receipt, int(cost_paid.index.max()))
    T = range(0, horizon + 1)

    advance = sc.advance_rate * contract_total
    r_m = sc.annual_rate / 12

    # 1) 核定請款 → 保留款、預付款扣回、應收淨額（記在核定月）
    cert = {t: float(billing.get(t, 0.0)) for t in T}
    retention_withheld, recovery, net_due = {}, {}, {}
    unrecovered, cum_cert = advance, 0.0
    for t in T:
        retention_withheld[t] = sc.retention_rate * cert[t]
        recovery[t] = advance_recovery(sc, advance, contract_total, cert[t], cum_cert, unrecovered)
        cum_cert += cert[t]
        unrecovered -= recovery[t]
        net_due[t] = cert[t] - retention_withheld[t] - recovery[t]

    # 2) 實際收款（記在收款月）
    total_retention = sum(retention_withheld.values())
    rows = []
    cash, loan = sc.initial_cash, 0.0
    cum_paid = cum_recv = 0.0
    ret_balance, adv_balance = 0.0, 0.0
    for t in T:
        pay = float(cost_paid.get(t, 0.0))
        recv_progress = net_due.get(t - sc.payment_delay, 0.0) if t - sc.payment_delay >= 1 else 0.0
        recv_retention = total_retention if t == sc.retention_release_month else 0.0
        recv_advance = advance if t == 0 else 0.0
        receipts = recv_progress + recv_retention + recv_advance

        # 不含利息的資金缺口：月初付款後、月末收款前的累計淨流出（扣除期初現金）
        cum_paid += pay
        gap = cum_paid - cum_recv - sc.initial_cash
        cum_recv += receipts

        # 月初付款
        borrow_start = max(0.0, pay - cash)
        cash = max(0.0, cash - pay)
        loan += borrow_start
        loan_in_month = loan
        # 月內計息
        interest = loan_in_month * r_m
        # 月末：收款 → 付息 → 還本
        cash += receipts
        borrow_interest = max(0.0, interest - cash)
        cash = max(0.0, cash - interest)
        loan += borrow_interest
        repay = min(cash, loan)
        loan -= repay
        cash -= repay

        ret_balance += retention_withheld[t] - recv_retention
        adv_balance += recv_advance - recovery[t]
        rows.append({
            "month": t,
            "cost_paid": pay,
            "certified_billing": cert[t],
            "retention_withheld": retention_withheld[t],
            "advance_recovered": recovery[t],
            "receipt_progress": recv_progress,
            "receipt_retention": recv_retention,
            "receipt_advance": recv_advance,
            "receipts": receipts,
            "net_cf_ex_interest": receipts - pay,
            "cum_cf_ex_interest": cum_recv - cum_paid + sc.initial_cash,
            "funding_gap": gap,
            "borrow_start": borrow_start,
            "loan_in_month": loan_in_month,
            "interest": interest,
            "borrow_interest": borrow_interest,
            "repayment": repay,
            "loan_end": loan,
            "cash_end": cash,
            "retention_balance": ret_balance,
            "advance_unrecovered": adv_balance,
        })
    return pd.DataFrame(rows)


def summarize(ledger: pd.DataFrame, sc: Scenario) -> dict:
    peak_loan = ledger[["loan_in_month", "loan_end"]].max(axis=1)
    return {
        "scenario": sc.scenario,
        "max_funding_gap": max(0.0, ledger["funding_gap"].max()),
        "max_gap_month": int(ledger.loc[ledger["funding_gap"].idxmax(), "month"]),
        "max_loan": peak_loan.max(),
        "max_loan_month": int(ledger.loc[peak_loan.idxmax(), "month"]),
        "total_interest": ledger["interest"].sum(),
        "ending_cash": ledger["cash_end"].iloc[-1],
        "ending_loan": ledger["loan_end"].iloc[-1],
        "horizon_month": int(ledger["month"].iloc[-1]),
    }


def check_identities(items: pd.DataFrame, ledger: pd.DataFrame, sc: Scenario, tol: float = 1e-6) -> list[str]:
    """內建守恆檢查：收款總額 = 合約價；期末現金 − 期末借款 = 期初現金 + 合約價 − 成本 − 利息。"""
    errors = []
    contract, cost = items["contract_price"].sum(), items["cost"].sum()
    if abs(ledger["receipts"].sum() - contract) > tol:
        errors.append(f"收款總額 {ledger['receipts'].sum():,.2f} ≠ 合約價 {contract:,}")
    lhs = ledger["cash_end"].iloc[-1] - ledger["loan_end"].iloc[-1]
    rhs = sc.initial_cash + contract - cost - ledger["interest"].sum()
    if abs(lhs - rhs) > tol:
        errors.append(f"期末淨現金 {lhs:,.2f} ≠ 守恆值 {rhs:,.2f}")
    if abs(ledger["retention_balance"].iloc[-1]) > tol:
        errors.append("保留款未全數返還")
    if abs(ledger["advance_unrecovered"].iloc[-1]) > tol:
        errors.append("預付款未全數扣回")
    return errors


def scenario_params(sc: Scenario) -> dict:
    return asdict(sc)
