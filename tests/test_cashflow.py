"""cashflow.py 的自動測試。執行： python -m pytest

小案例的期望值都是手算出來的（計算過程寫在各測試的說明裡），
不是把程式跑出來的數字抄回來，所以能檢查程式是否照規則計算。
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from cashflow import (Scenario, check_identities, item_monthly, load_case,  # noqa: E402
                      simulate, summarize)


# ---------------------------------------------------------------- 小案例
def small_case(lag2: int = 0):
    """兩個工項、兩個月：
    工項 1：成本 1,000、合約價 1,200，第 1 月完成 100%
    工項 2：成本 2,000、合約價 2,400，第 2 月完成 100%
    合約價合計 3,600，成本合計 3,000。
    """
    items = pd.DataFrame({"item_id": [1, 2], "name": ["工項1", "工項2"], "category": ["x", "x"],
                          "cost": [1000, 2000], "contract_price": [1200, 2400], "cost_pay_lag": [0, lag2]})
    progress = pd.DataFrame({"M1": [1.0, 0.0], "M2": [0.0, 1.0]}, index=pd.Index([1, 2], name="item_id"))
    return items, progress


# 年利率 12% → 月利率 1%，方便手算
BASE = dict(payment_delay=1, retention_rate=0.10, retention_release_month=4,
            advance_recovery_rate=0.10, initial_cash=0, annual_rate=0.12)


def test_small_case_without_advance():
    """手算（核定後 1 個月月末收款，保留款 10%，第 4 月返還）：
    核定請款：第 1 月 1,200 → 扣保留款 120 → 第 2 月月末收 1,080
              第 2 月 2,400 → 扣保留款 240 → 第 3 月月末收 2,160
              保留款合計 360 → 第 4 月月末收
    第 1 月：月初付 1,000，借 1,000；利息 10.00；月末無收款 → 再借 10 → 借款 1,010.00
    第 2 月：月初付 2,000 → 借款 3,010.00；利息 30.10；收 1,080 → 付息後剩 1,049.90 還本 → 借款 1,960.10
    第 3 月：利息 19.601；收 2,160 → 付息後剩 2,140.399，還清 1,960.10 → 現金 180.299
    第 4 月：收保留款 360 → 現金 540.299
    總利息 10 + 30.10 + 19.601 = 59.701；最高借款 3,010（第 2 月）
    最大資金缺口（不含利息）：第 2 月月初累計付出 3,000、累計收到 0 → 3,000
    """
    items, progress = small_case()
    sc = Scenario("t", advance_rate=0.0, **BASE)
    lg = simulate(items, progress, sc).set_index("month")

    assert lg.loc[1, "interest"] == pytest.approx(10.00)
    assert lg.loc[1, "loan_end"] == pytest.approx(1010.00)
    assert lg.loc[2, "receipts"] == pytest.approx(1080.00)
    assert lg.loc[2, "loan_end"] == pytest.approx(1960.10)
    assert lg.loc[3, "interest"] == pytest.approx(19.601)
    assert lg.loc[3, "cash_end"] == pytest.approx(180.299)
    assert lg.loc[4, "receipt_retention"] == pytest.approx(360.00)

    s = summarize(lg.reset_index(), sc)
    assert s["total_interest"] == pytest.approx(59.701)
    assert s["max_loan"] == pytest.approx(3010.00)
    assert s["max_loan_month"] == 2
    assert s["max_funding_gap"] == pytest.approx(3000.00)
    assert s["ending_cash"] == pytest.approx(540.299)
    assert s["ending_loan"] == pytest.approx(0)


def test_small_case_with_advance():
    """手算（同上，另加開工前預付款 10% = 360，按核定請款 10% 扣回）：
    扣回：第 1 月 120（餘 240）；第 2 月 min(240, 240) = 240（餘 0）
    應收淨額：第 1 月 1,200 − 120 − 120 = 960；第 2 月 2,400 − 240 − 240 = 1,920
    第 0 月：收預付款 360 → 現金 360
    第 1 月：付 1,000，先用現金 360，借 640；利息 6.40；無收款 → 再借 → 借款 646.40
    第 2 月：付 2,000 → 借款 2,646.40；利息 26.464；收 960 → 剩 933.536 還本 → 借款 1,712.864
    第 3 月：利息 17.12864；收 1,920 → 剩 1,902.87136，還清 → 現金 190.00736
    第 4 月：收保留款 360 → 現金 550.00736
    總利息 49.99264；最高借款 2,646.40
    """
    items, progress = small_case()
    sc = Scenario("t", advance_rate=0.10, **BASE)
    lg = simulate(items, progress, sc).set_index("month")

    assert lg.loc[0, "receipt_advance"] == pytest.approx(360)
    assert list(lg.loc[[1, 2], "advance_recovered"]) == pytest.approx([120, 240])
    assert lg.loc[1, "borrow_start"] == pytest.approx(640)
    assert lg.loc[2, "receipts"] == pytest.approx(960)
    assert lg.loc[3, "receipts"] == pytest.approx(1920)

    s = summarize(lg.reset_index(), sc)
    assert s["total_interest"] == pytest.approx(49.99264)
    assert s["max_loan"] == pytest.approx(2646.40)
    assert s["ending_cash"] == pytest.approx(550.00736)


def test_advance_recovery_capped_at_balance():
    """扣回比例大於預付款比例時，扣回總額不能超過預付款（以未扣回餘額為上限）。"""
    items, progress = small_case()
    sc = Scenario("t", **{**BASE, "advance_recovery_rate": 0.50}, advance_rate=0.10)
    lg = simulate(items, progress, sc)
    assert lg["advance_recovered"].sum() == pytest.approx(360)
    assert list(lg.set_index("month").loc[[1, 2], "advance_recovered"]) == pytest.approx([360, 0])


# ---------------------------------------------------------------- 契約範本區間扣回（工程採購契約範本 §5(一)1）
def template_case():
    """契約價金 NT$90,000,000，預付款 10% = 9,000,000，保留款 5%，累計估驗 20%～80% 區間扣回。

    進度安排使第 1～4 月累計估驗 16,200,000（18%）、第 5 月估驗 9,000,000（累計 28%）；
    第 6 月估驗 19,800,000，累計剛好 50%。
    """
    items = pd.DataFrame({"item_id": [1], "name": ["工程"], "category": ["x"],
                          "cost": [81_000_000], "contract_price": [90_000_000], "cost_pay_lag": [0]})
    plan = [.045, .045, .045, .045, .10, .22, .125, .125, .125, .125]
    progress = pd.DataFrame({f"M{m}": [p] for m, p in enumerate(plan, start=1)},
                            index=pd.Index([1], name="item_id"))
    sc = Scenario("template", payment_delay=1, retention_rate=0.05, retention_release_month=12,
                  advance_rate=0.10, advance_recovery_method="band", annual_rate=0.06)
    return items, progress, sc


def test_band_recovery_month5_worked_example():
    """契約範本 §5(一)1(4) 算例：
    扣回比例 9,000,000 ÷ (90,000,000 × 60%) = 1/6
    第 5 月：上月底累計 16,200,000（18%，尚未進入區間），本月估驗 9,000,000，累計 25,200,000
    扣回預付款 (25,200,000 − 18,000,000) × 1/6 = 1,200,000
    扣保留款 9,000,000 × 5% = 450,000
    本期實付 7,350,000（核定後 1 個月，於第 6 月月末收到）
    """
    items, progress, sc = template_case()
    lg = simulate(items, progress, sc).set_index("month")
    assert lg.loc[5, "certified_billing"] == pytest.approx(9_000_000)
    assert lg.loc[[1, 2, 3, 4], "advance_recovered"].sum() == pytest.approx(0)
    assert lg.loc[5, "advance_recovered"] == pytest.approx(1_200_000)
    assert lg.loc[5, "retention_withheld"] == pytest.approx(450_000)
    assert lg.loc[6, "receipt_progress"] == pytest.approx(7_350_000)


def test_band_recovery_half_complete_checkpoint():
    """完成度 50% 時，預付款 9,000,000 應已扣回一半。
    手算：(45,000,000 − 18,000,000) × 1/6 = 4,500,000
    """
    items, progress, sc = template_case()
    lg = simulate(items, progress, sc).set_index("month")
    assert lg.loc[:6, "advance_recovered"].sum() == pytest.approx(4_500_000)
    assert lg.loc[6, "advance_unrecovered"] == pytest.approx(4_500_000)


def test_band_recovery_stops_at_band_end():
    """累計估驗：第 8 月底 67,500,000（75%），第 9 月 78,750,000（87.5%）。
    第 9 月只有 72,000,000 − 67,500,000 = 4,500,000 落在區間內 → 扣回 750,000，之後不再扣回，合計 9,000,000。
    """
    items, progress, sc = template_case()
    lg = simulate(items, progress, sc).set_index("month")
    assert lg.loc[9, "advance_recovered"] == pytest.approx(750_000)
    assert lg.loc[10, "advance_recovered"] == pytest.approx(0)
    assert lg["advance_recovered"].sum() == pytest.approx(9_000_000)
    assert check_identities(items, lg.reset_index(), sc) == []


@pytest.mark.parametrize("kwargs", [{"advance_recovery_method": "linear"},
                                    {"recovery_band_start": 0.8, "recovery_band_end": 0.2}])
def test_invalid_recovery_settings_rejected(kwargs):
    with pytest.raises(ValueError):
        Scenario("t", **kwargs)


def test_cost_pay_lag_shifts_payment():
    """工項 2 支付延遲 1 個月：第 2 月完成的成本 2,000 改在第 3 月月初支付。"""
    items, progress = small_case(lag2=1)
    incurred, paid, _ = item_monthly(items, progress)
    assert incurred.sum().to_dict() == {1: 1000, 2: 2000}
    assert paid.sum().to_dict() == {1: 1000, 2: 0, 3: 2000}


def test_retention_release_before_last_receipt_rejected():
    items, progress = small_case()
    with pytest.raises(ValueError):
        simulate(items, progress, Scenario("t", **{**BASE, "retention_release_month": 2}))


def test_progress_rows_must_sum_to_one(tmp_path):
    items, progress = small_case()
    progress.loc[2, "M2"] = 0.9
    items.to_csv(tmp_path / "items.csv", index=False, encoding="utf-8-sig")
    progress.to_csv(tmp_path / "progress.csv", encoding="utf-8-sig")
    pd.DataFrame([{"scenario": "t", **BASE}]).to_csv(tmp_path / "scenarios.csv", index=False)
    with pytest.raises(ValueError, match="2"):
        load_case(tmp_path)


# ---------------------------------------------------------------- 正式案例
@pytest.fixture(scope="module")
def case():
    return load_case(ROOT / "data")


def test_case_meets_minimum_size(case):
    items, _, _ = case
    assert len(items) >= 30
    assert items["cost"].sum() == 9_000_000
    assert items["contract_price"].sum() == 10_000_000


def test_case_identities_hold_for_every_scenario(case):
    """守恆：收款總額 = 合約價；期末淨現金 = 期初現金 + 合約價 − 成本 − 利息；保留款、預付款都結清。"""
    items, progress, scenarios = case
    for sc in scenarios:
        assert check_identities(items, simulate(items, progress, sc), sc) == [], sc.scenario


def test_shorter_delay_and_advance_reduce_financing(case):
    """方向性檢查：第一個方案是基準（延遲 2 月、無預付款），其餘方案縮短收款延遲或加入預付款，
    最高借款與總利息都應該低於基準。"""
    items, progress, scenarios = case
    base, *others = [summarize(simulate(items, progress, sc), sc) for sc in scenarios]
    assert others, "範例資料至少要有兩個方案"
    for other in others:
        assert other["max_loan"] < base["max_loan"], other["scenario"]
        assert other["total_interest"] < base["total_interest"], other["scenario"]
