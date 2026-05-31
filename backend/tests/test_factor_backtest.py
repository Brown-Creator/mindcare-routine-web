"""
Tests for backend.data.factor_backtest (multi-period factor IC backtest).

Builds synthetic price history with *persistent per-stock drift* so that the
momentum factor genuinely predicts forward returns. Asserts the backtest detects
positive momentum IC and the data-driven calibration tilts weight toward it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import asyncio

from backend.data.factor_backtest import (
    run_factor_ic_backtest, calibrate_factor_model, run_fundamental_factor_backtest)
from backend.ml.factor_model import MultiFactorModel

RNG = np.random.default_rng(2025)


def _price_history(n_tickers=12, days=440):
    """
    지속적 드리프트가 노이즈를 '지배'하는 합성 가격 — 과거 추세(모멘텀)가 전방수익률을
    실제로 예측하도록. (드리프트가 노이즈에 묻히면 모멘텀은 예측력이 없다 — 상수 드리프트
    + iid 노이즈는 진짜 모멘텀이 아니라는 점이 핵심.)
    """
    hist, meta = {}, {}
    drifts = np.linspace(-0.004, 0.004, n_tickers)     # 지배적 추세
    for i in range(n_tickers):
        tk = f"{i:06d}"
        r = RNG.normal(drifts[i], 0.006, days)          # 노이즈 < 드리프트 스프레드
        c = 10000 * np.cumprod(1 + r)
        hist[tk] = pd.DataFrame({
            "date": pd.date_range("2022-01-01", periods=days).astype(str),
            "open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
            "volume": RNG.integers(1e5, 1e6, days),
        })
        meta[tk] = {"name": f"S{i}", "sector": ["반도체", "금융", "바이오", "자동차"][i % 4],
                    "market_cap": float(RNG.uniform(1e12, 1e13)), "fundamentals": {}}
    return hist, meta


def test_backtest_detects_momentum_ic():
    hist, meta = _price_history()
    res = run_factor_ic_backtest(hist, meta, MultiFactorModel(),
                                 rebalance_every=20, lookback=250, forward=20)
    assert "error" not in res, res
    assert res["n_periods"] >= 3
    # 지속 드리프트 → 모멘텀 팩터의 평균 IC 가 양수여야 한다.
    assert res["ic_report"]["momentum"]["mean_ic"] > 0.1


def test_calibrated_weights_valid_and_applied():
    hist, meta = _price_history()
    fm = MultiFactorModel()
    res = run_factor_ic_backtest(hist, meta, fm, rebalance_every=20, lookback=250, forward=20)
    w = res["calibrated_weights"]
    assert abs(sum(w.values()) - 1.0) < 1e-3      # 4자리 반올림 허용
    assert all(v >= 0 for v in w.values())
    # 데이터기반 가중치는 예측력 있는 모멘텀에 동일가중(1/6)보다 더 실어야 한다.
    assert w["momentum"] > 1.0 / 6
    # 적용
    applied = calibrate_factor_model(fm, res, apply=True)
    assert abs(sum(applied.values()) - 1.0) < 1e-3
    assert fm.weights == applied


def test_insufficient_data_returns_error():
    hist, meta = _price_history(n_tickers=12, days=120)   # lookback+forward 못 채움
    res = run_factor_ic_backtest(hist, meta, MultiFactorModel(),
                                 rebalance_every=20, lookback=250, forward=20)
    assert "error" in res


class _FundLoader:
    """build_records_async 를 제공하는 모의 로더 — 저PER(value)일수록 고수익 드리프트."""
    def __init__(self, n=12, days=440):
        self.n, self.days = n, days

    async def build_records_async(self, universe, start, end):
        recs = []
        for i, u in enumerate(universe):
            drift = np.linspace(-0.004, 0.004, self.n)[i]
            per = 30 - 25 * (i / (self.n - 1))      # 고드리프트 = 저PER(싸다)
            r = RNG.normal(drift, 0.006, self.days)
            c = 10000 * np.cumprod(1 + r)
            px = pd.DataFrame({
                "date": pd.date_range("2022-01-01", periods=self.days).astype(str),
                "open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
                "volume": RNG.integers(1e5, 1e6, self.days)})
            recs.append({"ticker": u["ticker"], "name": u["name"],
                         "sector": u.get("sector", ""), "market_cap": 1e12 * (i + 1),
                         "fundamentals": {"per": per, "pbr": per / 10,
                                          "roe": 5 + i, "debt_ratio": 50},
                         "price_data": px})
        return recs


def test_fundamental_backtest_detects_value_ic():
    uni = [{"ticker": f"{i:06d}", "name": f"S{i}", "sector": ["반도체", "금융", "바이오"][i % 3]}
           for i in range(12)]
    res = asyncio.run(run_fundamental_factor_backtest(
        _FundLoader(), uni, MultiFactorModel(load_calibrated=False),
        "20220101", "20231231", rebalance_every=20, lookback=250, forward=20))
    assert "error" not in res, res
    assert res.get("fundamentals_source") == "DART (async)"
    # 저PER(=고value)일수록 고수익 → value 팩터 IC 가 양수여야 한다.
    assert res["ic_report"]["value"]["mean_ic"] > 0.1


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
