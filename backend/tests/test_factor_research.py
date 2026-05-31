"""
Correctness tests for backend.quant.factor_research.

Builds a synthetic panel where one factor genuinely predicts forward returns and
another is pure noise, then asserts the research tools can tell them apart:
positive IC, higher data-driven weight on the real factor, a positive & monotone
quantile spread. Runnable with pytest or directly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.quant import factor_research as fr

RNG = np.random.default_rng(2024)
N_DATES, N_ASSETS = 120, 40
ASSETS = [f"A{i}" for i in range(N_ASSETS)]
DATES = pd.RangeIndex(N_DATES)


def _panels():
    """A predictive factor (IC>0), a noise factor, and aligned forward returns."""
    signal = pd.DataFrame(RNG.normal(0, 1, (N_DATES, N_ASSETS)), index=DATES, columns=ASSETS)
    noise = pd.DataFrame(RNG.normal(0, 1, (N_DATES, N_ASSETS)), index=DATES, columns=ASSETS)
    # forward return = 0.04 * signal (cross-sectionally) + idiosyncratic noise
    fwd = 0.04 * signal + pd.DataFrame(RNG.normal(0, 0.04, (N_DATES, N_ASSETS)),
                                       index=DATES, columns=ASSETS)
    return signal, noise, fwd


def test_rolling_ic_detects_signal_vs_noise():
    signal, noise, fwd = _panels()
    ic = fr.rolling_factor_ic({"signal": signal, "noise": noise}, fwd)
    assert ic["signal"].mean() > 0.15        # real factor has clear positive IC
    assert abs(ic["noise"].mean()) < 0.05     # noise factor ~ zero IC


def test_estimate_weights_favors_predictive_factor():
    signal, noise, fwd = _panels()
    ic = fr.rolling_factor_ic({"signal": signal, "noise": noise}, fwd)
    w = fr.estimate_factor_weights(ic, shrinkage=0.8)
    assert w["signal"] > w["noise"]
    assert abs(sum(w.values()) - 1.0) < 1e-6


def test_ic_report_fields():
    signal, _, fwd = _panels()
    ic = fr.rolling_factor_ic({"signal": signal}, fwd)
    rep = fr.factor_ic_report(ic)["signal"]
    for k in ("mean_ic", "icir", "t_stat", "hit_rate", "n"):
        assert k in rep
    assert rep["hit_rate"] > 0.6              # IC positive most dates


def test_quantile_spread_positive_and_monotone():
    signal, _, fwd = _panels()
    qb = fr.quantile_spread(signal, fwd, n_quantiles=5)
    assert qb.long_short_mean > 0             # top quantile beats bottom
    assert qb.long_short_t > 2.0              # statistically significant
    assert qb.monotonicity > 0.8              # returns increase across quantiles
    # quantile returns should be (weakly) increasing low→high
    qr = [q for q in qb.quantile_returns if np.isfinite(q)]
    assert qr[-1] > qr[0]


def test_factor_decay_runs():
    signal, _, fwd = _panels()
    # interpret fwd as per-period returns for the decay helper
    decay = fr.factor_decay(signal, fwd, horizons=[1, 5, 10])
    assert set(decay.keys()) == {1, 5, 10}
    assert np.isfinite(decay[1])


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
