"""
Backtest validation — the part most amateur systems get catastrophically wrong.

Two failure modes dominate quant research and both are addressed here:

1. **Leakage in cross-validation.** When labels are forward returns over h
   periods, a naive train/test split lets the model peek at overlapping
   information. ``PurgedWalkForward`` and ``PurgedKFold`` remove (purge) training
   samples whose label horizon overlaps the test set and add an embargo after it
   (López de Prado, *Advances in Financial Machine Learning*, ch. 7).

2. **Selection bias from many trials.** Try 100 strategies and the best one looks
   great by luck. The **Deflated Sharpe Ratio** and **Probabilistic Sharpe
   Ratio** (Bailey & López de Prado, 2012/2014) discount an observed Sharpe for
   the number of trials, the sample length, and the non-normality of returns.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Iterator, List, Optional, Sequence, Tuple, Union

from scipy import stats

_EPS = 1e-12
_EULER = 0.5772156649015329          # Euler-Mascheroni constant
ArrayLike = Union[pd.Series, np.ndarray, Sequence[float]]


# ──────────────────────────────────────────────────────────────────────────
# Purged / embargoed splits
# ──────────────────────────────────────────────────────────────────────────
class PurgedWalkForward:
    """
    Expanding (or rolling) walk-forward splitter with purge + embargo.

    For each fold the test block immediately follows the train block. Training
    samples within ``label_horizon`` of the test block are purged, and an
    ``embargo`` of samples right after the test block is excluded from any later
    training to prevent serial-correlation leakage.

    Parameters
    ----------
    n_splits : number of sequential test folds.
    label_horizon : h, the forward-return horizon of the label (purge width).
    embargo_pct : embargo length as a fraction of the sample.
    expanding : True for an expanding train window, False for a rolling window.
    """

    def __init__(self, n_splits: int = 5, label_horizon: int = 1,
                 embargo_pct: float = 0.01, expanding: bool = True):
        self.n_splits = n_splits
        self.label_horizon = max(int(label_horizon), 0)
        self.embargo_pct = embargo_pct
        self.expanding = expanding

    def split(self, n_samples: int) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        idx = np.arange(n_samples)
        fold = n_samples // (self.n_splits + 1)
        if fold < 1:
            return
        embargo = int(n_samples * self.embargo_pct)
        for k in range(1, self.n_splits + 1):
            train_end = fold * k
            test_start = train_end + self.label_horizon + embargo
            test_end = min(test_start + fold, n_samples)
            if test_start >= n_samples or test_end - test_start < 1:
                continue
            train_start = 0 if self.expanding else max(0, train_end - fold)
            train_idx = idx[train_start:train_end]
            test_idx = idx[test_start:test_end]
            yield train_idx, test_idx


class PurgedKFold:
    """
    K-fold cross-validation with purging and embargo for overlapping labels.

    Each contiguous fold serves as the test set; training observations whose
    label window (``label_horizon``) overlaps the test fold — on either side —
    are purged, and an embargo is applied after the test fold.
    """

    def __init__(self, n_splits: int = 5, label_horizon: int = 1,
                 embargo_pct: float = 0.01):
        self.n_splits = n_splits
        self.label_horizon = max(int(label_horizon), 0)
        self.embargo_pct = embargo_pct

    def split(self, n_samples: int) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        idx = np.arange(n_samples)
        fold_bounds = np.linspace(0, n_samples, self.n_splits + 1).astype(int)
        embargo = int(n_samples * self.embargo_pct)
        h = self.label_horizon
        for k in range(self.n_splits):
            test_start, test_end = fold_bounds[k], fold_bounds[k + 1]
            test_idx = idx[test_start:test_end]
            # Purge: drop training points whose label window touches the test fold.
            left = max(0, test_start - h)
            right = min(n_samples, test_end + h + embargo)
            train_mask = np.ones(n_samples, dtype=bool)
            train_mask[left:right] = False
            train_idx = idx[train_mask]
            if test_idx.size and train_idx.size:
                yield train_idx, test_idx


# ──────────────────────────────────────────────────────────────────────────
# Sharpe-ratio statistics that account for non-normality & multiple testing
# ──────────────────────────────────────────────────────────────────────────
def _sr_moments(returns: ArrayLike) -> Tuple[float, int, float, float]:
    r = pd.Series(returns, dtype="float64").replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
    n = r.size
    if n < 3:
        return 0.0, n, 0.0, 3.0
    mu, sd = r.mean(), r.std(ddof=1)
    sr = mu / sd if sd > _EPS else 0.0
    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r, fisher=False))   # non-excess kurtosis
    return float(sr), n, skew, kurt


def probabilistic_sharpe_ratio(returns: ArrayLike, benchmark_sr: float = 0.0) -> float:
    """
    Probability that the *true* (per-period) Sharpe exceeds ``benchmark_sr``,
    accounting for sample length, skewness and kurtosis.

        PSR = Φ( (SR − SR*)·√(n−1) / √(1 − γ₃·SR + ((γ₄−1)/4)·SR²) )

    ``benchmark_sr`` is in the same per-period units as the returns (use 0 to
    test "is the strategy better than nothing?").
    """
    sr, n, skew, kurt = _sr_moments(returns)
    if n < 3:
        return float("nan")
    denom = np.sqrt(max(1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2, _EPS))
    z = (sr - benchmark_sr) * np.sqrt(n - 1) / denom
    return float(stats.norm.cdf(z))


def deflated_sharpe_ratio(returns: ArrayLike, n_trials: int,
                          trial_sr_variance: Optional[float] = None) -> dict:
    """
    Deflated Sharpe Ratio: PSR evaluated against the Sharpe you'd *expect* the
    best of ``n_trials`` independent strategies to show under the null of zero
    skill. Clearing the DSR means the result survives the multiple-testing the
    researcher actually performed.

        SR₀ = √V · [ (1−γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)) ]
        DSR = PSR(SR₀)

    where V is the variance of the Sharpe estimates across trials (defaults to
    1/(n−1), the asymptotic variance of a single Sharpe under normality), γ is
    the Euler-Mascheroni constant and N = ``n_trials``.
    """
    sr, n, skew, kurt = _sr_moments(returns)
    if n < 3 or n_trials < 1:
        return {"deflated_sharpe": float("nan"), "expected_max_sr": float("nan"),
                "observed_sr": sr, "n_trials": n_trials}
    V = trial_sr_variance if trial_sr_variance is not None else 1.0 / (n - 1)
    V = max(V, _EPS)
    N = max(int(n_trials), 1)
    if N == 1:
        sr0 = 0.0
    else:
        q1 = stats.norm.ppf(1.0 - 1.0 / N)
        q2 = stats.norm.ppf(1.0 - 1.0 / (N * np.e))
        sr0 = np.sqrt(V) * ((1 - _EULER) * q1 + _EULER * q2)
    dsr = probabilistic_sharpe_ratio(returns, benchmark_sr=sr0)
    return {
        "deflated_sharpe": round(float(dsr), 4),
        "expected_max_sr": round(float(sr0), 5),
        "observed_sr": round(float(sr), 5),
        "psr_vs_zero": round(probabilistic_sharpe_ratio(returns, 0.0), 4),
        "n_trials": N,
        "n_obs": n,
        "skew": round(skew, 3),
        "kurtosis": round(kurt, 3),
        "passes": bool(dsr > 0.95),     # 95% confidence the skill is real
    }


def min_track_record_length(returns: ArrayLike, benchmark_sr: float = 0.0,
                            confidence: float = 0.95) -> float:
    """
    Minimum number of observations needed for the observed Sharpe to be
    statistically greater than ``benchmark_sr`` at the given confidence.
    """
    sr, n, skew, kurt = _sr_moments(returns)
    if n < 3 or abs(sr - benchmark_sr) < _EPS:
        return float("inf")
    z = stats.norm.ppf(confidence)
    factor = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2
    return float(1.0 + factor * (z / (sr - benchmark_sr)) ** 2)


# ──────────────────────────────────────────────────────────────────────────
# Information Coefficient evaluation across time
# ──────────────────────────────────────────────────────────────────────────
def rolling_ic(scores_panel: pd.DataFrame, forward_returns_panel: pd.DataFrame,
               method: str = "spearman") -> pd.Series:
    """
    Per-date IC time series given a (dates × assets) panel of scores and the
    corresponding forward returns. Feed the result to ``cross_section.ic_summary``
    for mean IC, ICIR and a t-stat.
    """
    common = scores_panel.index.intersection(forward_returns_panel.index)
    out = {}
    for dt in common:
        a = scores_panel.loc[dt]
        b = forward_returns_panel.loc[dt]
        df = pd.concat([a, b], axis=1).dropna()
        if len(df) < 3 or df.iloc[:, 0].std() < _EPS or df.iloc[:, 1].std() < _EPS:
            continue
        if method == "pearson":
            ic = float(np.corrcoef(df.iloc[:, 0], df.iloc[:, 1])[0, 1])
        else:
            ic = float(stats.spearmanr(df.iloc[:, 0], df.iloc[:, 1]).statistic)
        out[dt] = ic
    return pd.Series(out, dtype="float64")
