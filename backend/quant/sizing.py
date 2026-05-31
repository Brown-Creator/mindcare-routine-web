"""
Position sizing — turning an edge into a bet size without blowing up.

Implements the family of Kelly sizing rules plus volatility targeting:

* ``kelly_binary``      — classic p·b form for win/loss bets.
* ``kelly_continuous``  — μ/σ² for a continuously-distributed edge.
* ``kelly_multi_asset`` — Σ⁻¹μ, the multivariate generalization.
* ``volatility_target`` — scale exposure to hit a target portfolio volatility.

Full Kelly maximizes long-run log-growth but is famously too aggressive for real
capital (its drawdowns are brutal and it assumes parameters are known exactly).
Every function therefore exposes a ``fraction`` (½- or ¼-Kelly are standard) and
the helpers add a drawdown-aware de-risking overlay.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Optional, Sequence, Union

_EPS = 1e-12
ArrayLike = Union[pd.Series, np.ndarray, Sequence[float]]
MatrixLike = Union[pd.DataFrame, np.ndarray]


def kelly_binary(win_prob: float, win_loss_ratio: float,
                 fraction: float = 0.5) -> float:
    """
    Kelly fraction for a binary bet.

        f* = (b·p − q) / b ,   q = 1 − p,   b = win/loss payoff ratio

    Returns ``fraction · f*`` clipped to [0, 1]. ``fraction`` defaults to ½-Kelly.
    """
    p = float(np.clip(win_prob, 0.0, 1.0))
    b = float(win_loss_ratio)
    if b <= _EPS:
        return 0.0
    f_star = (b * p - (1 - p)) / b
    return float(np.clip(f_star * fraction, 0.0, 1.0))


def kelly_continuous(expected_return: float, variance: float,
                     fraction: float = 0.5, cap: float = 1.0) -> float:
    """
    Kelly fraction for a continuous edge: f* = μ / σ².

    ``expected_return`` and ``variance`` are per-period (same horizon). The
    result is the fraction of capital to allocate, scaled by ``fraction`` and
    capped at ``cap``. Negative edges return 0 (no short here).
    """
    if variance <= _EPS:
        return 0.0
    f_star = expected_return / variance
    return float(np.clip(f_star * fraction, 0.0, cap))


def kelly_multi_asset(mu: ArrayLike, cov: MatrixLike, fraction: float = 0.5,
                      long_only: bool = True, gross_cap: float = 1.0) -> np.ndarray:
    """
    Multivariate Kelly: f* = Σ⁻¹μ (per-period μ and covariance).

    This is the growth-optimal *vector* of fractional exposures and correctly
    accounts for correlations — adding a position that is redundant with the book
    gets a smaller bet. ``fraction`` shrinks toward cash; ``long_only`` projects
    out shorts and ``gross_cap`` caps total gross exposure.
    """
    m = np.asarray(mu, dtype="float64")
    C = cov.to_numpy() if isinstance(cov, pd.DataFrame) else np.asarray(cov, dtype="float64")
    C = (C + C.T) / 2.0
    try:
        f = np.linalg.solve(C, m)
    except np.linalg.LinAlgError:
        f = np.linalg.lstsq(C, m, rcond=None)[0]
    f = f * fraction
    if long_only:
        f = np.clip(f, 0.0, None)
    gross = np.abs(f).sum()
    if gross > gross_cap and gross > _EPS:
        f = f * (gross_cap / gross)
    return f


def volatility_target(target_vol: float, asset_vol: float,
                      max_leverage: float = 1.0) -> float:
    """
    Exposure multiplier that scales a position to a target volatility.

        scale = target_vol / realized_vol   (capped at ``max_leverage``)

    Volatility targeting is the backbone of risk-managed futures/CTA books: it
    cuts size when markets get wild and adds when they calm down, stabilizing the
    realized risk of the strategy.
    """
    if asset_vol <= _EPS:
        return 0.0
    return float(np.clip(target_vol / asset_vol, 0.0, max_leverage))


def drawdown_throttle(current_drawdown: float, max_tolerable_dd: float = 0.20,
                      floor: float = 0.25) -> float:
    """
    De-risking multiplier as drawdown deepens (a soft, continuous "kill switch").

    Returns 1.0 at no drawdown and decays linearly to ``floor`` as the current
    drawdown approaches ``max_tolerable_dd``. Multiply your target exposure by
    this to systematically shed risk into a losing streak.
    """
    dd = abs(current_drawdown)
    if dd <= 0:
        return 1.0
    if dd >= max_tolerable_dd:
        return float(floor)
    scale = 1.0 - (1.0 - floor) * (dd / max_tolerable_dd)
    return float(np.clip(scale, floor, 1.0))


def size_position(alpha_score: float, expected_vol: float, confidence: float,
                  target_vol: float = 0.15, kelly_fraction: float = 0.5,
                  current_drawdown: float = 0.0, max_weight: float = 0.20,
                  periods_per_year: int = 252) -> Dict[str, float]:
    """
    End-to-end sizing used by the live engine: map an alpha score (0-100) and a
    volatility forecast into a portfolio weight, combining a Kelly edge, a
    volatility-target cap, a confidence haircut and a drawdown throttle.

    Returns the recommended weight plus its components for transparency.
    """
    # Alpha 50 = neutral. Convert the 0-100 score to an expected annual edge,
    # very conservatively (a 100-score implies a ~10% annual excess assumption).
    edge_annual = max(0.0, (alpha_score - 50.0) / 50.0) * 0.10
    var_annual = max(expected_vol, _EPS) ** 2

    f_kelly = kelly_continuous(edge_annual, var_annual, fraction=kelly_fraction,
                               cap=max_weight)
    vt_cap = volatility_target(target_vol, expected_vol, max_leverage=max_weight)
    throttle = drawdown_throttle(current_drawdown)
    conf = float(np.clip(confidence, 0.0, 1.0))

    weight = min(f_kelly, vt_cap) * conf * throttle
    weight = float(np.clip(weight, 0.0, max_weight))
    return {
        "weight": round(weight, 4),
        "kelly_weight": round(f_kelly, 4),
        "vol_target_cap": round(vt_cap, 4),
        "confidence_mult": round(conf, 3),
        "drawdown_throttle": round(throttle, 3),
        "implied_edge_annual_pct": round(edge_annual * 100, 2),
    }
