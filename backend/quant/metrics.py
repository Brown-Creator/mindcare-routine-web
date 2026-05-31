"""
Performance & risk analytics — the metrics a quant actually reports.

Everything here operates on a series of *periodic returns* (decimals, e.g.
0.012 = +1.2%). Annualization uses ``periods_per_year`` (252 for daily KRX).

Highlights beyond the usual Sharpe/MDD:
* Cornish-Fisher (modified) VaR/CVaR that corrects the Gaussian quantile for
  skew and kurtosis — fat tails are the whole point of tail risk.
* Drawdown analytics with peak/trough dates and recovery duration.
* Omega, tail ratio, gain-to-pain, downside deviation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Union, Sequence

from scipy import stats

_EPS = 1e-12
ArrayLike = Union[pd.Series, np.ndarray, Sequence[float]]


def _clean(returns: ArrayLike) -> np.ndarray:
    r = pd.Series(returns, dtype="float64").replace([np.inf, -np.inf], np.nan).dropna()
    return r.to_numpy()


# ──────────────────────────────────────────────────────────────────────────
# Return / risk-adjusted ratios
# ──────────────────────────────────────────────────────────────────────────
def annualized_return(returns: ArrayLike, periods_per_year: int = 252,
                      geometric: bool = True) -> float:
    r = _clean(returns)
    if r.size == 0:
        return 0.0
    if geometric:
        growth = np.prod(1.0 + r)
        if growth <= 0:
            return -1.0
        return float(growth ** (periods_per_year / r.size) - 1.0)
    return float(np.mean(r) * periods_per_year)


def annualized_volatility(returns: ArrayLike, periods_per_year: int = 252) -> float:
    r = _clean(returns)
    if r.size < 2:
        return 0.0
    return float(np.std(r, ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(returns: ArrayLike, rf: float = 0.0, periods_per_year: int = 252) -> float:
    """Annualized Sharpe ratio. ``rf`` is the *annual* risk-free rate."""
    r = _clean(returns)
    if r.size < 2:
        return 0.0
    excess = r - rf / periods_per_year
    sd = np.std(excess, ddof=1)
    if sd < _EPS:
        return 0.0
    return float(np.mean(excess) / sd * np.sqrt(periods_per_year))


def sortino_ratio(returns: ArrayLike, rf: float = 0.0, periods_per_year: int = 252) -> float:
    """Annualized Sortino ratio (penalizes only downside deviation)."""
    r = _clean(returns)
    if r.size < 2:
        return 0.0
    excess = r - rf / periods_per_year
    downside = excess[excess < 0]
    if downside.size == 0:
        return float("inf") if np.mean(excess) > 0 else 0.0
    dd = np.sqrt(np.mean(downside ** 2))
    if dd < _EPS:
        return 0.0
    return float(np.mean(excess) / dd * np.sqrt(periods_per_year))


def downside_deviation(returns: ArrayLike, mar: float = 0.0,
                       periods_per_year: int = 252) -> float:
    """Annualized downside deviation below a minimum acceptable return (per period)."""
    r = _clean(returns)
    if r.size == 0:
        return 0.0
    shortfall = np.minimum(r - mar, 0.0)
    return float(np.sqrt(np.mean(shortfall ** 2)) * np.sqrt(periods_per_year))


def omega_ratio(returns: ArrayLike, threshold: float = 0.0) -> float:
    """Ω = Σ gains above threshold / Σ losses below threshold (per period)."""
    r = _clean(returns)
    if r.size == 0:
        return 0.0
    gains = np.sum(np.maximum(r - threshold, 0.0))
    losses = -np.sum(np.minimum(r - threshold, 0.0))
    if losses < _EPS:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def tail_ratio(returns: ArrayLike) -> float:
    """|95th percentile| / |5th percentile| — >1 means a fatter right tail."""
    r = _clean(returns)
    if r.size < 20:
        return float("nan")
    left = abs(np.percentile(r, 5))
    right = abs(np.percentile(r, 95))
    return float(right / left) if left > _EPS else float("inf")


def gain_to_pain(returns: ArrayLike) -> float:
    """Sum of returns ÷ sum of absolute losses (Schwager's gain-to-pain)."""
    r = _clean(returns)
    pain = -np.sum(r[r < 0])
    return float(np.sum(r) / pain) if pain > _EPS else float("inf")


# ──────────────────────────────────────────────────────────────────────────
# Drawdown
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class DrawdownInfo:
    max_drawdown: float = 0.0       # negative number, e.g. -0.23
    peak_index: int = 0
    trough_index: int = 0
    recovery_index: int = -1        # -1 if not yet recovered
    drawdown_duration: int = 0      # peak → trough (periods)
    recovery_duration: int = 0      # trough → recovery (periods)


def equity_curve(returns: ArrayLike, initial: float = 1.0) -> np.ndarray:
    r = _clean(returns)
    return initial * np.cumprod(1.0 + r)


def max_drawdown(returns: ArrayLike) -> DrawdownInfo:
    """Maximum drawdown with peak/trough/recovery indices and durations."""
    r = _clean(returns)
    if r.size == 0:
        return DrawdownInfo()
    eq = np.cumprod(1.0 + r)
    running_max = np.maximum.accumulate(eq)
    dd = eq / running_max - 1.0
    trough = int(np.argmin(dd))
    mdd = float(dd[trough])
    peak = int(np.argmax(eq[: trough + 1])) if trough > 0 else 0
    recovery = -1
    after = np.where(eq[trough:] >= eq[peak])[0]
    if after.size > 0:
        recovery = int(trough + after[0])
    return DrawdownInfo(
        max_drawdown=mdd,
        peak_index=peak,
        trough_index=trough,
        recovery_index=recovery,
        drawdown_duration=trough - peak,
        recovery_duration=(recovery - trough) if recovery >= 0 else 0,
    )


def calmar_ratio(returns: ArrayLike, periods_per_year: int = 252) -> float:
    """Annualized return ÷ |max drawdown|."""
    mdd = max_drawdown(returns).max_drawdown
    if abs(mdd) < _EPS:
        return 0.0
    return float(annualized_return(returns, periods_per_year) / abs(mdd))


# ──────────────────────────────────────────────────────────────────────────
# Value-at-Risk / Expected Shortfall
# ──────────────────────────────────────────────────────────────────────────
def historical_var(returns: ArrayLike, confidence: float = 0.95) -> float:
    """Historical VaR as a positive loss fraction at the given confidence."""
    r = _clean(returns)
    if r.size < 2:
        return 0.0
    q = np.percentile(r, (1 - confidence) * 100)
    return float(-q)


def historical_cvar(returns: ArrayLike, confidence: float = 0.95) -> float:
    """Historical CVaR / Expected Shortfall (mean loss in the tail beyond VaR)."""
    r = _clean(returns)
    if r.size < 2:
        return 0.0
    q = np.percentile(r, (1 - confidence) * 100)
    tail = r[r <= q]
    if tail.size == 0:
        return float(-q)
    return float(-tail.mean())


def gaussian_var(returns: ArrayLike, confidence: float = 0.95) -> float:
    """Parametric (Gaussian) VaR — assumes normality; included for comparison."""
    r = _clean(returns)
    if r.size < 2:
        return 0.0
    mu, sd = np.mean(r), np.std(r, ddof=1)
    z = stats.norm.ppf(1 - confidence)
    return float(-(mu + z * sd))


def cornish_fisher_var(returns: ArrayLike, confidence: float = 0.95) -> float:
    """
    Modified (Cornish-Fisher) VaR that adjusts the Gaussian quantile for the
    sample skewness and excess kurtosis:

        z_cf = z + (z²−1)S/6 + (z³−3z)K/24 − (2z³−5z)S²/36

    For the typically left-skewed, fat-tailed return distributions of equities
    this is materially more accurate than Gaussian VaR without needing a long
    history for a purely empirical estimate.
    """
    r = _clean(returns)
    if r.size < 4:
        return gaussian_var(returns, confidence)
    mu, sd = np.mean(r), np.std(r, ddof=1)
    if sd < _EPS:
        return 0.0
    S = float(stats.skew(r))
    K = float(stats.kurtosis(r))          # excess kurtosis (Fisher)
    z = stats.norm.ppf(1 - confidence)
    z_cf = (z
            + (z ** 2 - 1) * S / 6.0
            + (z ** 3 - 3 * z) * K / 24.0
            - (2 * z ** 3 - 5 * z) * S ** 2 / 36.0)
    return float(-(mu + z_cf * sd))


def cornish_fisher_cvar(returns: ArrayLike, confidence: float = 0.95) -> float:
    """Cornish-Fisher Expected Shortfall (tail mean using the CF quantile)."""
    r = _clean(returns)
    if r.size < 4:
        return historical_cvar(returns, confidence)
    var_cf = cornish_fisher_var(returns, confidence)
    tail = r[r <= -var_cf]
    if tail.size == 0:
        return var_cf
    return float(-tail.mean())


# ──────────────────────────────────────────────────────────────────────────
# One-shot summary
# ──────────────────────────────────────────────────────────────────────────
def performance_summary(returns: ArrayLike, rf: float = 0.0,
                        periods_per_year: int = 252) -> dict:
    """Full tear-sheet of metrics from a return series."""
    r = _clean(returns)
    dd = max_drawdown(r)
    return {
        "n_periods": int(r.size),
        "ann_return_pct": round(annualized_return(r, periods_per_year) * 100, 3),
        "ann_vol_pct": round(annualized_volatility(r, periods_per_year) * 100, 3),
        "sharpe": round(sharpe_ratio(r, rf, periods_per_year), 3),
        "sortino": round(sortino_ratio(r, rf, periods_per_year), 3),
        "calmar": round(calmar_ratio(r, periods_per_year), 3),
        "omega": round(omega_ratio(r), 3),
        "max_drawdown_pct": round(dd.max_drawdown * 100, 3),
        "drawdown_duration": dd.drawdown_duration,
        "recovery_duration": dd.recovery_duration,
        "skew": round(float(stats.skew(r)), 3) if r.size > 2 else 0.0,
        "excess_kurtosis": round(float(stats.kurtosis(r)), 3) if r.size > 3 else 0.0,
        "var_95_hist_pct": round(historical_var(r, 0.95) * 100, 3),
        "cvar_95_hist_pct": round(historical_cvar(r, 0.95) * 100, 3),
        "var_99_cornish_fisher_pct": round(cornish_fisher_var(r, 0.99) * 100, 3),
        "cvar_99_cornish_fisher_pct": round(cornish_fisher_cvar(r, 0.99) * 100, 3),
        "tail_ratio": round(tail_ratio(r), 3) if r.size >= 20 else None,
        "hit_rate": round(float(np.mean(r > 0)), 3) if r.size else 0.0,
    }
