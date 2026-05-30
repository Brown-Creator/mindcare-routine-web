"""
Correctness tests for backend.quant.costs (transaction & market-impact model).
"""
from __future__ import annotations

import numpy as np

from backend.quant.costs import CostModel, apply_cost_to_return, break_even_holding_days


def test_zero_quantity_zero_cost():
    cm = CostModel()
    c = cm.trade_cost(price=10000, quantity=0, side="buy")
    assert c["total"] == 0.0


def test_sell_costs_more_than_buy_due_to_tax():
    cm = CostModel()
    buy = cm.trade_cost(10000, 1000, "buy")["total"]
    sell = cm.trade_cost(10000, 1000, "sell")["total"]
    assert sell > buy
    # difference ≈ tax on the notional
    assert abs((sell - buy) - 10000 * 1000 * cm.sell_tax_bps / 1e4) < 1e-6


def test_square_root_impact_scaling():
    cm = CostModel(impact_coef=0.5, impact_exponent=0.5)
    # Doubling participation should raise impact by exactly sqrt(2).
    i1 = cm.market_impact_fraction(quantity=1000, adv_shares=100000, daily_vol=0.02)
    i2 = cm.market_impact_fraction(quantity=2000, adv_shares=100000, daily_vol=0.02)
    assert abs(i2 / i1 - np.sqrt(2)) < 1e-9
    # Impact scales linearly with volatility.
    iv = cm.market_impact_fraction(1000, 100000, 0.04)
    assert abs(iv / i1 - 2.0) < 1e-9


def test_impact_grows_with_participation():
    cm = CostModel()
    small = cm.trade_cost(10000, 500, "buy", adv_shares=1_000_000, daily_vol=0.02)
    large = cm.trade_cost(10000, 200_000, "buy", adv_shares=1_000_000, daily_vol=0.02)
    # Bigger order → higher per-share cost in bps (impact term dominates).
    assert large["cost_bps"] > small["cost_bps"]
    assert large["impact"] > small["impact"]


def test_cost_decomposition_sums():
    cm = CostModel()
    c = cm.trade_cost(10000, 5000, "sell", adv_shares=500_000, daily_vol=0.03)
    assert abs(c["total"] - (c["commission"] + c["tax"] + c["spread"] + c["impact"])) < 1e-6


def test_apply_cost_to_return():
    # 2% gross, 50% one-way turnover, 20bps one-way → net = 0.02 - 0.5*0.0020 = 0.019
    assert abs(apply_cost_to_return(0.02, 0.5, 20.0) - 0.019) < 1e-12


def test_break_even_infinite_when_edge_below_cost():
    cm = CostModel()
    rt = cm.round_trip_bps(participation=0.01, daily_vol=0.02)
    assert break_even_holding_days(rt - 1, cm, 0.01, 0.02, daily_alpha_decay_bps=5) == float("inf")
    assert break_even_holding_days(rt + 50, cm, 0.01, 0.02, daily_alpha_decay_bps=5) < float("inf")


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}"); passed += 1
        except Exception:
            print(f"  FAIL  {fn.__name__}"); traceback.print_exc(); failed += 1
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
