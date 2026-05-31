"""
Tests for backend.jobs.recalibration + MultiFactorModel persisted-weight load.

Uses a mock loader producing momentum-predictive prices, persists to a temp path,
and verifies the calibrated weights tilt to momentum, round-trip through JSON, and
are auto-loaded by a fresh MultiFactorModel.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from backend.jobs.recalibration import (
    recalibrate_factor_weights, persist_weights, load_persisted_weights,
    DEFAULT_WEIGHTS_PATH,
)
from backend.ml.factor_model import MultiFactorModel

RNG = np.random.default_rng(77)


class _MockLoader:
    """fetch_ohlcv 를 제공하는 최소 로더 (모멘텀 예측형 합성 가격)."""
    def available(self):
        return True

    def fetch_ohlcv(self, ticker, start, end):
        i = int(ticker)
        drift = np.linspace(-0.004, 0.004, 12)[i]
        r = RNG.normal(drift, 0.006, 440)
        c = 10000 * np.cumprod(1 + r)
        return pd.DataFrame({
            "date": pd.date_range("2022-01-01", periods=440).astype(str),
            "open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
            "volume": RNG.integers(1e5, 1e6, 440),
        })


def _universe():
    return [{"ticker": f"{i:06d}", "name": f"S{i}",
             "sector": ["반도체", "금융", "바이오", "자동차"][i % 4],
             "market_cap": 1e12 * (i + 1), "fundamentals": {}}
            for i in range(12)]


def test_recalibration_tilts_to_momentum_and_persists(tmp_path=None):
    path = Path(tmp_path) / "fw.json" if tmp_path else Path("data/_test_fw.json")
    fm = MultiFactorModel(load_calibrated=False)
    res = recalibrate_factor_weights(
        _MockLoader(), _universe(), fm,
        start="20220101", end="20231231",
        rebalance_every=20, lookback=250, forward=20,
        apply=True, persist=True, path=path, timestamp="2026-05-31T00:00:00",
    )
    assert "error" not in res, res
    w = res["applied_weights"]
    assert w["momentum"] > 1.0 / 6                  # 데이터기반: 모멘텀 우대
    assert fm.weights["momentum"] == w["momentum"]   # 모델에 적용됨
    # 영속화 라운드트립
    loaded = load_persisted_weights(path)
    assert loaded is not None and abs(loaded["momentum"] - w["momentum"]) < 1e-9
    if not tmp_path:
        path.unlink(missing_ok=True)


def test_model_autoloads_persisted_weights():
    # 기본 경로에 임시로 저장 → 새 모델이 자동 로드하는지 확인 후 정리.
    backup = None
    p = DEFAULT_WEIGHTS_PATH
    try:
        if p.exists():
            backup = p.read_text(encoding="utf-8")
        persist_weights({"value": 0.05, "quality": 0.05, "momentum": 0.6,
                         "low_vol": 0.1, "size": 0.1, "growth": 0.1},
                        meta={"test": True}, path=p)
        fm = MultiFactorModel(load_calibrated=True)
        assert abs(fm.weights["momentum"] - 0.6) < 1e-6
        # 정규화로 합은 1
        assert abs(sum(fm.weights.values()) - 1.0) < 1e-6
    finally:
        if backup is not None:
            p.write_text(backup, encoding="utf-8")
        else:
            p.unlink(missing_ok=True)


def test_insufficient_data_returns_error():
    class ShortLoader(_MockLoader):
        def fetch_ohlcv(self, ticker, start, end):
            return super().fetch_ohlcv(ticker, start, end).iloc[:100]
    fm = MultiFactorModel(load_calibrated=False)
    res = recalibrate_factor_weights(ShortLoader(), _universe(), fm,
                                     "20220101", "20231231",
                                     lookback=250, forward=20, persist=False)
    assert "error" in res


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
