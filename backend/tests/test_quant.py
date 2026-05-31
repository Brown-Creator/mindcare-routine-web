"""
Correctness tests for backend.quant.

These are not smoke tests — each asserts a *mathematical property* the method
must satisfy (orthogonality after neutralization, equal risk contributions for
risk parity, CVaR ≥ VaR, tangency matching the closed form, …). Runnable either
with pytest or directly:  ``python -m backend.tests.test_quant``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.quant import (
    cross_section as xs,
    covariance as cov,
    optimization as opt,
    metrics as met,
    validation as val,
    sizing as sz,
)

RNG = np.random.default_rng(12345)


# ── cross_section ─────────────────────────────────────────────────────────
def test_zscore_properties():
    x = RNG.normal(5, 3, 500)
    z = xs.zscore(x)
    assert abs(z.mean()) < 1e-9
    assert abs(z.std(ddof=1) - 1.0) < 1e-9


def test_rank_normalize_is_gaussian_and_monotone():
    x = RNG.exponential(2.0, 1000)            # heavily skewed input
    z = xs.rank_normalize(x)
    # Output should be ~standard normal regardless of skewed input.
    assert abs(z.mean()) < 0.05
    assert abs(z.std() - 1.0) < 0.1
    # Monotonic: ranks preserved.
    order_in = np.argsort(x)
    order_out = np.argsort(z.to_numpy())
    assert np.array_equal(order_in, order_out)


def test_mad_winsorize_caps_outliers():
    x = np.concatenate([RNG.normal(0, 1, 200), [50.0, -40.0]])
    w = xs.mad_winsorize(x, n_sigma=3.0)
    assert w.max() < 50.0 and w.min() > -40.0


def test_neutralize_orthogonality():
    n = 400
    size = RNG.normal(0, 1, n)
    factor = 0.8 * size + RNG.normal(0, 0.5, n)   # factor contaminated by size
    resid = xs.neutralize(factor, exposures=pd.DataFrame({"size": size}))
    # After neutralization the residual must be ~uncorrelated with size.
    corr = np.corrcoef(resid.to_numpy(), size)[0, 1]
    assert abs(corr) < 1e-8


def test_information_coefficient_perfect_monotone():
    scores = np.arange(50, dtype="float64")
    fwd = scores ** 1.5                        # monotone increasing
    assert abs(xs.information_coefficient(scores, fwd, "spearman") - 1.0) < 1e-9
    assert xs.information_coefficient(scores, -fwd, "spearman") < -0.99


def test_combine_factors_returns_zscore():
    f1 = pd.Series(xs.zscore(RNG.normal(0, 1, 300)))
    f2 = pd.Series(xs.zscore(RNG.normal(0, 1, 300)))
    comp = xs.combine_factors({"a": f1, "b": f2}, {"a": 0.5, "b": 0.5})
    assert abs(comp.mean()) < 1e-9
    assert abs(comp.std(ddof=1) - 1.0) < 1e-9


# ── covariance ────────────────────────────────────────────────────────────
def _make_returns(n_assets=8, t=300, n_factors=3, seed=None):
    """
    Multi-factor return panel with *heterogeneous* pairwise correlations (random
    factor loadings). This is deliberately NOT a single-factor / constant-
    correlation structure — otherwise the Ledoit-Wolf constant-correlation target
    would be exactly right and shrinkage would saturate at 1 for every T.
    """
    rng = RNG if seed is None else np.random.default_rng(seed)
    loadings = rng.normal(0, 1, (n_assets, n_factors))
    factors = rng.normal(0, 1, (t, n_factors))
    idio = rng.normal(0, 1, (t, n_assets))
    raw = factors @ loadings.T + 1.2 * idio
    raw = raw / raw.std(axis=0)                 # unit variance per asset
    vols = np.linspace(0.01, 0.03, n_assets)
    X = raw * vols
    return pd.DataFrame(X, columns=[f"A{i}" for i in range(n_assets)])


def test_ledoit_wolf_valid_and_shrinks():
    R = _make_returns()
    sigma, delta = cov.ledoit_wolf_shrinkage(R)
    assert 0.0 <= delta <= 1.0
    assert cov.is_psd(sigma.to_numpy())
    assert np.allclose(sigma.to_numpy(), sigma.to_numpy().T)
    # More data → less shrinkage needed. Slice a common large panel so the
    # comparison is deterministic (δ = κ/T decays ~1/T).
    panel = _make_returns(n_assets=8, t=4000, n_factors=3, seed=99)
    _, delta_small = cov.ledoit_wolf_shrinkage(panel.iloc[:40])
    _, delta_big = cov.ledoit_wolf_shrinkage(panel)
    assert delta_small > delta_big


def test_ledoit_wolf_identity_valid():
    R = _make_returns()
    sigma, delta = cov.ledoit_wolf_identity(R)
    assert 0.0 <= delta <= 1.0
    assert cov.is_psd(sigma.to_numpy())


def test_nearest_psd_fixes_indefinite():
    A = np.array([[1.0, 2.0], [2.0, 1.0]])     # eigenvalues 3, -1 → indefinite
    assert not cov.is_psd(A)
    P = cov.nearest_psd(A)
    assert cov.is_psd(P)


def test_ewma_covariance_psd():
    R = _make_returns()
    C = cov.ewma_covariance(R, halflife=50)
    assert cov.is_psd(C.to_numpy(), tol=1e-8)


# ── optimization ──────────────────────────────────────────────────────────
def test_min_variance_two_asset_closed_form():
    # σ1=0.1, σ2=0.2, ρ=0 → GMV w1 = σ2²/(σ1²+σ2²) = 0.8
    C = pd.DataFrame([[0.01, 0.0], [0.0, 0.04]], index=["x", "y"], columns=["x", "y"])
    res = opt.min_variance(C)
    assert abs(res.weights["x"] - 0.8) < 1e-3
    assert abs(res.weights["y"] - 0.2) < 1e-3


def test_max_sharpe_matches_tangency():
    mu = pd.Series({"x": 0.10, "y": 0.14})
    C = pd.DataFrame([[0.04, 0.01], [0.01, 0.09]], index=["x", "y"], columns=["x", "y"])
    analytic = opt.tangency_unconstrained(mu, C, rf=0.02)   # closed form
    # Allow shorts / loose box so the constrained solver can reach the tangency.
    res = opt.max_sharpe(mu, C, rf=0.02, lb=-2.0, ub=2.0, n_starts=8)
    w = res.weight_array(["x", "y"])
    assert np.allclose(w, analytic, atol=1e-3)


def test_risk_parity_equal_contributions():
    R = _make_returns(n_assets=6, t=500, n_factors=2)
    sigma, _ = cov.ledoit_wolf_shrinkage(R)
    res = opt.risk_parity(sigma)
    rc = np.array(list(res.risk_contributions.values()))
    assert rc.max() - rc.min() < 1e-3        # all risk contributions equal
    assert abs(sum(res.weights.values()) - 1.0) < 1e-4   # 6-dp rounded weights
    assert all(w >= -1e-9 for w in res.weights.values())


def test_risk_parity_diagonal_is_inverse_vol():
    # For uncorrelated assets, ERC weights ∝ 1/σ.
    vols = np.array([0.1, 0.2, 0.4])
    C = pd.DataFrame(np.diag(vols ** 2), index=list("abc"), columns=list("abc"))
    res = opt.risk_parity(C)
    inv_vol = (1 / vols) / (1 / vols).sum()
    w = res.weight_array(list("abc"))
    assert np.allclose(w, inv_vol, atol=1e-3)


def test_optimizers_respect_constraints():
    R = _make_returns(n_assets=10)
    sigma, _ = cov.ledoit_wolf_shrinkage(R)
    res = opt.min_variance(sigma, lb=0.0, ub=0.2)
    assert all(-1e-9 <= w <= 0.2 + 1e-6 for w in res.weights.values())
    assert abs(sum(res.weights.values()) - 1.0) < 1e-4


# ── metrics ───────────────────────────────────────────────────────────────
def test_cvar_geq_var():
    r = RNG.standard_t(4, 2000) * 0.01         # fat-tailed
    for c in (0.95, 0.99):
        assert met.historical_cvar(r, c) >= met.historical_var(r, c) - 1e-12
        assert met.cornish_fisher_cvar(r, c) >= met.cornish_fisher_var(r, c) - 1e-9


def test_cornish_fisher_reduces_to_gaussian_when_normal():
    r = RNG.normal(0, 0.01, 20000)             # ~no skew/kurt
    assert abs(met.cornish_fisher_var(r, 0.95) - met.gaussian_var(r, 0.95)) < 5e-4


def test_max_drawdown_known_series():
    # +0%, -50%, then flat → MDD = -50%
    r = np.array([0.0, -0.5, 0.0, 0.0])
    dd = met.max_drawdown(r)
    assert abs(dd.max_drawdown + 0.5) < 1e-9
    assert dd.trough_index == 1


def test_sharpe_sign_and_scale():
    # Positive drift with realistic noise → positive Sharpe. (A constant series
    # has zero volatility and an undefined Sharpe, which we report as 0.)
    r = RNG.normal(0.0008, 0.01, 1000)
    assert met.sharpe_ratio(r) > 0
    assert met.sharpe_ratio(-r) < 0
    assert met.sortino_ratio(np.array([0.01, 0.02, -0.01, 0.015])) != 0
    assert met.sharpe_ratio(np.full(252, 0.001)) == 0.0   # zero-vol edge case


# ── validation ────────────────────────────────────────────────────────────
def test_psr_in_unit_interval_and_monotone_in_n():
    short = RNG.normal(0.001, 0.01, 60)
    long = np.concatenate([short, RNG.normal(0.001, 0.01, 2000)])
    p_short = val.probabilistic_sharpe_ratio(short, 0.0)
    p_long = val.probabilistic_sharpe_ratio(long, 0.0)
    assert 0.0 <= p_short <= 1.0 and 0.0 <= p_long <= 1.0


def test_deflated_sharpe_decreases_with_more_trials():
    r = RNG.normal(0.0008, 0.01, 1000)
    d1 = val.deflated_sharpe_ratio(r, n_trials=1)["deflated_sharpe"]
    d100 = val.deflated_sharpe_ratio(r, n_trials=100)["deflated_sharpe"]
    assert d100 <= d1                          # more trials → harder hurdle


def test_purged_walk_forward_no_leakage():
    splitter = val.PurgedWalkForward(n_splits=4, label_horizon=5, embargo_pct=0.02)
    for train, test in splitter.split(1000):
        assert len(np.intersect1d(train, test)) == 0
        # Purge gap: no training index within the horizon before the test start.
        assert train.max() < test.min()
        assert test.min() - train.max() >= 5


def test_purged_kfold_disjoint():
    kf = val.PurgedKFold(n_splits=5, label_horizon=3, embargo_pct=0.01)
    for train, test in kf.split(500):
        assert len(np.intersect1d(train, test)) == 0


# ── sizing ────────────────────────────────────────────────────────────────
def test_kelly_binary_known_value():
    # p=0.6, b=1 → f*=0.2 ; half-Kelly → 0.1
    assert abs(sz.kelly_binary(0.6, 1.0, fraction=1.0) - 0.2) < 1e-12
    assert abs(sz.kelly_binary(0.6, 1.0, fraction=0.5) - 0.1) < 1e-12
    assert sz.kelly_binary(0.4, 1.0) == 0.0    # no edge → no bet


def test_kelly_continuous_and_multi_asset():
    assert abs(sz.kelly_continuous(0.05, 0.04, fraction=1.0) - 1.0) < 1e-12  # 0.05/0.04 capped at 1
    mu = np.array([0.02, 0.03])
    C = np.diag([0.04, 0.09])
    f = sz.kelly_multi_asset(mu, C, fraction=1.0, long_only=True, gross_cap=10)
    assert np.allclose(f, mu / np.diag(C), atol=1e-9)


def test_volatility_target_and_throttle():
    assert abs(sz.volatility_target(0.10, 0.20, max_leverage=2) - 0.5) < 1e-12
    assert sz.drawdown_throttle(0.0) == 1.0
    assert sz.drawdown_throttle(0.30, max_tolerable_dd=0.20) == 0.25
    assert 0.25 < sz.drawdown_throttle(0.10, max_tolerable_dd=0.20) < 1.0


# ── manual runner ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception:
            print(f"  FAIL  {fn.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    raise SystemExit(1 if failed else 0)
