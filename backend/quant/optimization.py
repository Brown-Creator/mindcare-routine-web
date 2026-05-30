"""
Portfolio optimization — genuine convex/numerical optimizers.

This replaces "draw 10,000 random weight vectors and keep the best" (which is
not optimization — it barely scratches the efficient frontier in more than a
handful of assets) with real solvers:

* ``max_sharpe``         — tangency portfolio (SLSQP, multi-start).
* ``min_variance``       — global minimum-variance portfolio.
* ``mean_variance``      — risk-aversion / target-return frontier point.
* ``risk_parity``        — TRUE equal-risk-contribution (convex log-barrier
                            formulation of Maillard-Roncalli-Teïletche 2010).
* ``max_diversification``— Choueifaty-Coignard most-diversified portfolio.

All support long-only box constraints, optional turnover (transaction-cost)
penalties, and group caps. Covariance inputs should already be cleaned
(e.g. Ledoit-Wolf) — see ``quant.covariance``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

from scipy.optimize import minimize

_EPS = 1e-10
ArrayLike = Union[pd.Series, np.ndarray, Sequence[float]]
MatrixLike = Union[pd.DataFrame, np.ndarray]


@dataclass
class OptResult:
    weights: Dict[str, float] = field(default_factory=dict)
    expected_return: float = 0.0
    expected_vol: float = 0.0
    sharpe: float = 0.0
    method: str = ""
    diversification_ratio: float = 1.0
    effective_n: float = 0.0          # 1 / Σwᵢ²  (Herfindahl-based breadth)
    risk_contributions: Dict[str, float] = field(default_factory=dict)
    converged: bool = True

    def weight_array(self, labels: Sequence) -> np.ndarray:
        return np.array([self.weights.get(l, 0.0) for l in labels])


def _labels(cov: MatrixLike, mu: Optional[ArrayLike] = None) -> List:
    if isinstance(cov, pd.DataFrame):
        return list(cov.columns)
    if isinstance(mu, pd.Series):
        return list(mu.index)
    n = np.asarray(cov).shape[0]
    return list(range(n))


def _matrix(cov: MatrixLike) -> np.ndarray:
    M = cov.to_numpy() if isinstance(cov, pd.DataFrame) else np.asarray(cov, dtype="float64")
    return (M + M.T) / 2.0


def _portfolio_stats(w: np.ndarray, mu: Optional[np.ndarray], cov: np.ndarray,
                     rf: float) -> Tuple[float, float, float]:
    ret = float(w @ mu) if mu is not None else 0.0
    var = float(w @ cov @ w)
    vol = float(np.sqrt(max(var, 0.0)))
    sharpe = (ret - rf) / vol if vol > _EPS else 0.0
    return ret, vol, sharpe


def _bounds(n: int, lb: float, ub: Optional[float]) -> List[Tuple[float, float]]:
    ub = 1.0 if ub is None else ub
    # 실현가능성 보정: 비중 합=1 과 0≤lb≤w≤ub 가 양립하려면 ub·n≥1, lb·n≤1 이어야 한다.
    # 사용자가 종목 수 대비 너무 작은 ub(예: 2종목에 ub=0.3 → 합 최대 0.6<1)를 주면
    # 제약이 모순돼 SLSQP가 캡을 위반한 해를 낸다. 최소 실현가능 수준으로 끌어올린다.
    ub = max(ub, 1.0 / n)
    lb = min(lb, 1.0 / n)
    return [(lb, ub)] * n


def _diversification_ratio(w: np.ndarray, cov: np.ndarray) -> float:
    vols = np.sqrt(np.clip(np.diag(cov), _EPS, None))
    weighted_avg_vol = float(w @ vols)
    port_vol = float(np.sqrt(max(w @ cov @ w, _EPS)))
    return weighted_avg_vol / port_vol if port_vol > _EPS else 1.0


def risk_contributions(weights: ArrayLike, cov: MatrixLike) -> np.ndarray:
    """
    Percentage risk contribution of each asset, RCᵢ = wᵢ(Σw)ᵢ / (wᵀΣw).

    These sum to 1 and are the quantity equalized by risk parity.
    """
    w = np.asarray(weights, dtype="float64")
    C = _matrix(cov)
    port_var = float(w @ C @ w)
    if port_var < _EPS:
        return np.full(len(w), 1.0 / len(w))
    mrc = C @ w                      # marginal risk contribution
    rc = w * mrc / port_var
    return rc


def _finalize(w: np.ndarray, labels: List, mu: Optional[np.ndarray],
              cov: np.ndarray, rf: float, method: str, converged: bool,
              periods_per_year: int) -> OptResult:
    w = np.clip(w, 0.0, None)
    s = w.sum()
    w = w / s if s > _EPS else np.full(len(w), 1.0 / len(w))
    ret, vol, sharpe = _portfolio_stats(w, mu, cov, rf)
    ann = periods_per_year
    rc = risk_contributions(w, cov)
    return OptResult(
        weights={labels[i]: round(float(w[i]), 6) for i in range(len(w))},
        expected_return=round(ret * ann, 6) if mu is not None else 0.0,
        expected_vol=round(vol * np.sqrt(ann), 6),
        sharpe=round(sharpe * np.sqrt(ann), 4),
        method=method,
        diversification_ratio=round(_diversification_ratio(w, cov), 4),
        effective_n=round(1.0 / float(np.sum(w ** 2)), 2),
        risk_contributions={labels[i]: round(float(rc[i]), 4) for i in range(len(w))},
        converged=converged,
    )


# ──────────────────────────────────────────────────────────────────────────
# Minimum variance
# ──────────────────────────────────────────────────────────────────────────
def min_variance(cov: MatrixLike, lb: float = 0.0, ub: Optional[float] = None,
                 periods_per_year: int = 252) -> OptResult:
    """Global minimum-variance portfolio (long-only by default)."""
    labels = _labels(cov)
    C = _matrix(cov)
    n = C.shape[0]
    w0 = np.full(n, 1.0 / n)

    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    res = minimize(lambda w: w @ C @ w, w0, method="SLSQP",
                   bounds=_bounds(n, lb, ub), constraints=cons,
                   options={"maxiter": 500, "ftol": 1e-12})
    return _finalize(res.x, labels, None, C, 0.0, "min_variance",
                     res.success, periods_per_year)


# ──────────────────────────────────────────────────────────────────────────
# Maximum Sharpe (tangency)
# ──────────────────────────────────────────────────────────────────────────
def max_sharpe(mu: ArrayLike, cov: MatrixLike, rf: float = 0.0,
               lb: float = 0.0, ub: Optional[float] = None,
               n_starts: int = 5, periods_per_year: int = 252) -> OptResult:
    """
    Maximum-Sharpe (tangency) portfolio under long-only box constraints.

    ``mu`` and ``rf`` must be expressed in the *same* per-period units as the
    covariance (e.g. daily). Reported return/vol/Sharpe are annualized using
    ``periods_per_year``. Multi-start SLSQP guards against local optima.
    """
    labels = _labels(cov, mu)
    C = _matrix(cov)
    m = np.asarray(mu, dtype="float64")
    n = C.shape[0]

    def neg_sharpe(w):
        ret = w @ m
        vol = np.sqrt(max(w @ C @ w, _EPS))
        return -(ret - rf) / vol

    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    bnds = _bounds(n, lb, ub)

    best, best_val = None, np.inf
    rng = np.random.default_rng(7)
    starts = [np.full(n, 1.0 / n)] + [rng.dirichlet(np.ones(n)) for _ in range(max(0, n_starts - 1))]
    for w0 in starts:
        res = minimize(neg_sharpe, w0, method="SLSQP", bounds=bnds,
                       constraints=cons, options={"maxiter": 500, "ftol": 1e-12})
        if res.success and res.fun < best_val:
            best_val, best = res.fun, res.x
    if best is None:
        best = np.full(n, 1.0 / n)
    return _finalize(best, labels, m, C, rf, "max_sharpe", best is not None,
                     periods_per_year)


def tangency_unconstrained(mu: ArrayLike, cov: MatrixLike, rf: float = 0.0) -> np.ndarray:
    """
    Closed-form long-short tangency weights w ∝ Σ⁻¹(μ − rf·1), normalized to
    sum to 1. Used as an analytical check against the constrained solver.
    """
    C = _matrix(cov)
    m = np.asarray(mu, dtype="float64")
    excess = m - rf
    w = np.linalg.solve(C, excess)
    return w / w.sum()


# ──────────────────────────────────────────────────────────────────────────
# Mean-variance (risk-aversion form, with optional turnover penalty)
# ──────────────────────────────────────────────────────────────────────────
def mean_variance(mu: ArrayLike, cov: MatrixLike, risk_aversion: float = 3.0,
                  lb: float = 0.0, ub: Optional[float] = None,
                  prev_weights: Optional[ArrayLike] = None,
                  tcost_bps: float = 0.0, periods_per_year: int = 252) -> OptResult:
    """
    Maximize  μᵀw − (λ/2)·wᵀΣw − tcost·‖w − w_prev‖₁.

    ``risk_aversion`` (λ) trades expected return against variance; ``tcost_bps``
    penalizes turnover from ``prev_weights`` so the optimizer doesn't churn the
    book for marginal gains (a real net-of-cost objective).
    """
    labels = _labels(cov, mu)
    C = _matrix(cov)
    m = np.asarray(mu, dtype="float64")
    n = C.shape[0]
    w_prev = np.asarray(prev_weights, dtype="float64") if prev_weights is not None else None
    tcost = tcost_bps / 1e4

    def objective(w):
        util = m @ w - 0.5 * risk_aversion * (w @ C @ w)
        if w_prev is not None and tcost > 0:
            util -= tcost * np.abs(w - w_prev).sum()
        return -util

    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    w0 = w_prev if w_prev is not None else np.full(n, 1.0 / n)
    res = minimize(objective, w0, method="SLSQP", bounds=_bounds(n, lb, ub),
                   constraints=cons, options={"maxiter": 500, "ftol": 1e-12})
    return _finalize(res.x, labels, m, C, 0.0, "mean_variance",
                     res.success, periods_per_year)


# ──────────────────────────────────────────────────────────────────────────
# Risk parity (true equal-risk-contribution)
# ──────────────────────────────────────────────────────────────────────────
def risk_parity(cov: MatrixLike, budget: Optional[ArrayLike] = None,
                lb: float = 0.0, ub: Optional[float] = None,
                periods_per_year: int = 252) -> OptResult:
    """
    True risk-parity / equal-risk-contribution portfolio.

    Unlike naive inverse-volatility weighting (which ignores correlations), this
    solves the convex problem (Maillard-Roncalli-Teïletche / Spinu):

        min_x  ½ xᵀΣx − Σ bᵢ ln(xᵢ),   x > 0,   then  w = x / Σx

    whose unique solution has risk contributions exactly proportional to the
    risk budget ``b`` (equal by default). Solved by Newton steps with a safe
    SLSQP fallback. Box constraints, when binding, are enforced via SLSQP on the
    squared-RC-dispersion objective.
    """
    labels = _labels(cov)
    C = _matrix(cov)
    n = C.shape[0]
    b = np.full(n, 1.0 / n) if budget is None else np.asarray(budget, dtype="float64")
    b = b / b.sum()

    bounded = (lb > 0.0) or (ub is not None and ub < 1.0)

    if not bounded:
        # Convex log-barrier formulation — exact ERC, no box constraints.
        x = np.full(n, 1.0 / n)
        for _ in range(200):
            grad = C @ x - b / x
            # Hessian of ½xᵀΣx − Σ bᵢ ln xᵢ  is  Σ + diag(b / x²)
            H = C + np.diag(b / x ** 2)
            try:
                step = np.linalg.solve(H, grad)
            except np.linalg.LinAlgError:
                break
            x_new = x - step
            # Keep strictly positive (backtracking).
            t = 1.0
            while np.any(x_new <= 0) and t > 1e-8:
                t *= 0.5
                x_new = x - t * step
            x_new = np.clip(x_new, _EPS, None)
            if np.linalg.norm(x_new - x) < 1e-12:
                x = x_new
                break
            x = x_new
        w = x / x.sum()
        return _finalize(w, labels, None, C, 0.0, "risk_parity", True,
                         periods_per_year)

    # Bounded case → minimize dispersion of risk contributions directly.
    def objective(w):
        port_var = w @ C @ w
        if port_var < _EPS:
            return 1e6
        rc = w * (C @ w) / port_var
        return np.sum((rc - b) ** 2)

    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    res = minimize(objective, np.full(n, 1.0 / n), method="SLSQP",
                   bounds=_bounds(n, lb, ub), constraints=cons,
                   options={"maxiter": 1000, "ftol": 1e-14})
    return _finalize(res.x, labels, None, C, 0.0, "risk_parity",
                     res.success, periods_per_year)


def inverse_volatility(cov: MatrixLike, periods_per_year: int = 252) -> OptResult:
    """Naive 1/σ weighting — kept only as a baseline to benchmark risk_parity against."""
    labels = _labels(cov)
    C = _matrix(cov)
    vols = np.sqrt(np.clip(np.diag(C), _EPS, None))
    w = (1.0 / vols)
    w = w / w.sum()
    return _finalize(w, labels, None, C, 0.0, "inverse_vol", True, periods_per_year)


# ──────────────────────────────────────────────────────────────────────────
# Maximum diversification
# ──────────────────────────────────────────────────────────────────────────
def max_diversification(cov: MatrixLike, lb: float = 0.0, ub: Optional[float] = None,
                        periods_per_year: int = 252) -> OptResult:
    """
    Choueifaty-Coignard most-diversified portfolio: maximize the diversification
    ratio (weighted-average vol ÷ portfolio vol). Tends to spread risk across
    uncorrelated bets rather than concentrating it.
    """
    labels = _labels(cov)
    C = _matrix(cov)
    n = C.shape[0]
    vols = np.sqrt(np.clip(np.diag(C), _EPS, None))

    def neg_dr(w):
        port_vol = np.sqrt(max(w @ C @ w, _EPS))
        return -(w @ vols) / port_vol

    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    res = minimize(neg_dr, np.full(n, 1.0 / n), method="SLSQP",
                   bounds=_bounds(n, lb, ub), constraints=cons,
                   options={"maxiter": 500, "ftol": 1e-12})
    return _finalize(res.x, labels, None, C, 0.0, "max_diversification",
                     res.success, periods_per_year)


# ──────────────────────────────────────────────────────────────────────────
# Efficient frontier (for diagnostics / plotting)
# ──────────────────────────────────────────────────────────────────────────
def efficient_frontier(mu: ArrayLike, cov: MatrixLike, n_points: int = 25,
                       lb: float = 0.0, ub: Optional[float] = None,
                       periods_per_year: int = 252) -> List[Dict[str, float]]:
    """Trace the long-only efficient frontier by sweeping target returns."""
    C = _matrix(cov)
    m = np.asarray(mu, dtype="float64")
    n = C.shape[0]
    lo, hi = float(m.min()), float(m.max())
    targets = np.linspace(lo, hi, n_points)
    out = []
    for tgt in targets:
        cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0},
                {"type": "eq", "fun": lambda w, t=tgt: w @ m - t}]
        res = minimize(lambda w: w @ C @ w, np.full(n, 1.0 / n), method="SLSQP",
                       bounds=_bounds(n, lb, ub), constraints=cons,
                       options={"maxiter": 500, "ftol": 1e-12})
        if res.success:
            vol = float(np.sqrt(max(res.x @ C @ res.x, 0.0)))
            out.append({
                "return": round(tgt * periods_per_year, 5),
                "vol": round(vol * np.sqrt(periods_per_year), 5),
                "sharpe": round((tgt / vol) * np.sqrt(periods_per_year), 4) if vol > _EPS else 0.0,
            })
    return out
