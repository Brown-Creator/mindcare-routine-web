"""
Cross-sectional factor engineering — institutional-grade.

The single biggest gap between an "impressive-looking" factor model and a real
quant factor model is *cross-sectional standardization*. A real model never uses
absolute thresholds (e.g. "if PER < 8 add 25 points"); instead it ranks each
name against its peers on the same date, neutralizes unwanted exposures
(sector, size), and combines orthogonalized z-scores. This module provides that
machinery using only numpy/pandas/scipy.

References
----------
- Grinold & Kahn, *Active Portfolio Management* (information ratio, IC).
- Qian, Hua & Sorensen, *Quantitative Equity Portfolio Management*.
- Blom (1958) for the rank→normal score transform constant.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Sequence, Union

from scipy import stats

ArrayLike = Union[pd.Series, np.ndarray, Sequence[float]]

_EPS = 1e-12


# ──────────────────────────────────────────────────────────────────────────
# Robust outlier handling
# ──────────────────────────────────────────────────────────────────────────
def winsorize(x: ArrayLike, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """Clip a cross-section at the given quantiles (percentile winsorization)."""
    s = pd.Series(x, dtype="float64")
    if s.notna().sum() < 2:
        return s
    lo, hi = s.quantile(lower), s.quantile(upper)
    return s.clip(lower=lo, upper=hi)


def mad_winsorize(x: ArrayLike, n_sigma: float = 3.0) -> pd.Series:
    """
    Median-Absolute-Deviation winsorization (robust to fat tails).

    Caps values to median ± n_sigma * 1.4826 * MAD. The 1.4826 factor makes the
    MAD a consistent estimator of the standard deviation under normality. This is
    the standard de-extreming step in equity factor pipelines (e.g. Axioma/Barra).
    """
    s = pd.Series(x, dtype="float64")
    med = s.median()
    mad = (s - med).abs().median()
    if not np.isfinite(mad) or mad < _EPS:
        # Degenerate dispersion → fall back to quantile winsorization.
        return winsorize(s, 0.01, 0.99)
    scale = 1.4826 * mad
    return s.clip(lower=med - n_sigma * scale, upper=med + n_sigma * scale)


# ──────────────────────────────────────────────────────────────────────────
# Standardization
# ──────────────────────────────────────────────────────────────────────────
def zscore(x: ArrayLike, ddof: int = 1) -> pd.Series:
    """Standard cross-sectional z-score (mean 0, std 1), NaN-safe."""
    s = pd.Series(x, dtype="float64")
    mu = s.mean()
    sd = s.std(ddof=ddof)
    if not np.isfinite(sd) or sd < _EPS:
        return pd.Series(0.0, index=s.index)
    return (s - mu) / sd


def robust_zscore(x: ArrayLike) -> pd.Series:
    """
    Robust z-score using median and scaled MAD instead of mean/std.

    Far less sensitive to a handful of extreme names than the classical z-score,
    which matters because equity factors (PER, growth, …) are heavy-tailed.
    """
    s = pd.Series(x, dtype="float64")
    med = s.median()
    mad = (s - med).abs().median()
    if not np.isfinite(mad) or mad < _EPS:
        return zscore(s)
    return (s - med) / (1.4826 * mad)


def rank_normalize(x: ArrayLike) -> pd.Series:
    """
    Map a cross-section to standard-normal scores via its ranks (Blom 1958).

    score_i = Φ⁻¹((rank_i − 3/8) / (n + 1/4))

    This produces a perfectly Gaussian-shaped factor regardless of the raw
    distribution, which stabilizes downstream linear combinations and is the
    de-facto transform for noisy fundamental factors.
    """
    s = pd.Series(x, dtype="float64")
    valid = s.notna()
    n = int(valid.sum())
    out = pd.Series(np.nan, index=s.index, dtype="float64")
    if n == 0:
        return out
    if n == 1:
        out[valid] = 0.0
        return out
    ranks = s[valid].rank(method="average")
    quantiles = (ranks - 0.375) / (n + 0.25)
    out[valid] = stats.norm.ppf(quantiles.clip(_EPS, 1 - _EPS))
    return out


# ──────────────────────────────────────────────────────────────────────────
# Neutralization (residualize a factor against unwanted exposures)
# ──────────────────────────────────────────────────────────────────────────
def neutralize(
    factor: ArrayLike,
    exposures: Optional[pd.DataFrame] = None,
    groups: Optional[ArrayLike] = None,
    add_intercept: bool = True,
) -> pd.Series:
    """
    Remove unwanted exposures from a factor via cross-sectional OLS.

    The returned series is the residual of regressing ``factor`` on the supplied
    ``exposures`` (continuous, e.g. log market-cap, beta) and ``groups``
    (categorical, e.g. GICS sector → dummy variables). After neutralization the
    factor is, by construction, orthogonal to those exposures — so a "value" bet
    is not secretly a "small-cap" or "banks" bet.

    Solved with ``numpy.linalg.lstsq`` (SVD), so it is robust to rank-deficient
    or collinear design matrices.
    """
    y = pd.Series(factor, dtype="float64")
    idx = y.index

    design_cols: List[np.ndarray] = []
    if add_intercept:
        design_cols.append(np.ones(len(y)))

    if exposures is not None and len(exposures) == len(y):
        X = exposures.copy()
        # Standardize continuous exposures so the intercept stays interpretable.
        for col in X.columns:
            X[col] = zscore(X[col]).fillna(0.0)
        design_cols.extend(X[c].to_numpy() for c in X.columns)

    if groups is not None:
        g = pd.Series(groups, index=idx).astype("object").fillna("__NA__")
        dummies = pd.get_dummies(g, drop_first=True, dtype="float64")
        design_cols.extend(dummies[c].to_numpy() for c in dummies.columns)

    if len(design_cols) <= (1 if add_intercept else 0):
        # Nothing to neutralize against → just demean.
        return y - y.mean()

    A = np.column_stack(design_cols)
    mask = np.isfinite(y.to_numpy()) & np.all(np.isfinite(A), axis=1)
    resid = pd.Series(np.nan, index=idx, dtype="float64")
    if mask.sum() <= A.shape[1]:
        return y - y.mean()

    beta, *_ = np.linalg.lstsq(A[mask], y.to_numpy()[mask], rcond=None)
    fitted = A[mask] @ beta
    resid.loc[idx[mask]] = y.to_numpy()[mask] - fitted
    return resid


# ──────────────────────────────────────────────────────────────────────────
# End-to-end factor standardization
# ──────────────────────────────────────────────────────────────────────────
def standardize_factor(
    raw: ArrayLike,
    method: str = "rank",
    winsor: str = "mad",
    n_sigma: float = 3.0,
    exposures: Optional[pd.DataFrame] = None,
    groups: Optional[ArrayLike] = None,
    higher_is_better: bool = True,
) -> pd.Series:
    """
    Full single-factor pipeline: winsorize → standardize → neutralize → re-z.

    Parameters
    ----------
    method : {"rank", "robust", "zscore"}
        Standardization style. "rank" (Blom rank→normal) is the most robust.
    winsor : {"mad", "quantile", "none"}
        Outlier treatment applied first.
    higher_is_better : bool
        Set False for factors where small is good (PER, PBR, debt, volatility);
        the sign is flipped so a high standardized score is always "attractive".
    """
    s = pd.Series(raw, dtype="float64")

    if winsor == "mad":
        s = mad_winsorize(s, n_sigma)
    elif winsor == "quantile":
        s = winsorize(s)

    if method == "rank":
        std = rank_normalize(s)
    elif method == "robust":
        std = robust_zscore(s)
    else:
        std = zscore(s)

    if not higher_is_better:
        std = -std

    if exposures is not None or groups is not None:
        std = neutralize(std, exposures=exposures, groups=groups)
        std = zscore(std)  # re-standardize residual to unit variance

    return std


def combine_factors(
    factor_scores: Dict[str, pd.Series],
    weights: Optional[Dict[str, float]] = None,
) -> pd.Series:
    """
    Combine several already-standardized factors into one composite z-score.

    Each input should be a standardized factor (mean ~0, std ~1) aligned by
    index. Missing factor values for a name are treated as neutral (0) rather
    than dropping the name, then the composite is re-standardized so it remains
    a clean z-score for downstream sizing.
    """
    if not factor_scores:
        return pd.Series(dtype="float64")

    df = pd.DataFrame(factor_scores)
    if weights:
        w = pd.Series({k: weights.get(k, 0.0) for k in df.columns}, dtype="float64")
    else:
        w = pd.Series(1.0, index=df.columns)
    total = w.abs().sum()
    if total < _EPS:
        w = pd.Series(1.0, index=df.columns)
        total = float(len(df.columns))
    w = w / total

    composite = df.fillna(0.0).mul(w, axis=1).sum(axis=1)
    return zscore(composite)


# ──────────────────────────────────────────────────────────────────────────
# Information Coefficient — the core measure of factor predictive power
# ──────────────────────────────────────────────────────────────────────────
def information_coefficient(
    scores: ArrayLike,
    forward_returns: ArrayLike,
    method: str = "spearman",
) -> float:
    """
    Cross-sectional Information Coefficient between scores and forward returns.

    IC is the correlation, on a single date, between today's factor scores and
    the subsequent realized returns. "spearman" (rank IC) is the industry
    default because it is robust to outliers and monotone-but-nonlinear payoffs.

    Alignment: if both inputs are labelled Series (e.g. indexed by ticker), they
    are matched on their shared labels — NOT by position. This matters because a
    caller may hand in scores sorted differently from the returns (e.g. ranked
    top-to-bottom); aligning positionally there would silently scramble the pairs
    and invert the IC.
    """
    a = pd.Series(scores, dtype="float64")
    b = pd.Series(forward_returns, dtype="float64")
    if a.index.equals(b.index):
        pass                                  # already aligned (incl. plain arrays)
    else:
        common = a.index.intersection(b.index)
        if len(common) >= 3:
            a, b = a.loc[common], b.loc[common]    # align by label (ticker)
        else:
            a = a.reset_index(drop=True)           # fall back to positional
            b = b.reset_index(drop=True)
    mask = a.notna() & b.notna()
    if mask.sum() < 3:
        return float("nan")
    a, b = a[mask], b[mask]
    if a.std() < _EPS or b.std() < _EPS:
        return 0.0
    if method == "pearson":
        return float(np.corrcoef(a, b)[0, 1])
    return float(stats.spearmanr(a, b).statistic)


def ic_summary(ic_series: ArrayLike, periods_per_year: int = 252) -> Dict[str, float]:
    """
    Summarize a time series of per-date ICs.

    Returns the mean IC, IC volatility, ICIR ( = mean / std, the information
    ratio of the signal itself), an annualized ICIR, and a t-stat for "mean IC
    is zero". A standalone equity factor with |ICIR| ≳ 0.5 is already strong.
    """
    ic = pd.Series(ic_series, dtype="float64").dropna()
    n = len(ic)
    if n < 2:
        return {"mean_ic": float("nan"), "ic_std": float("nan"),
                "icir": float("nan"), "icir_annual": float("nan"),
                "t_stat": float("nan"), "hit_rate": float("nan"), "n": n}
    mean_ic = float(ic.mean())
    ic_std = float(ic.std(ddof=1))
    icir = mean_ic / ic_std if ic_std > _EPS else float("nan")
    return {
        "mean_ic": round(mean_ic, 4),
        "ic_std": round(ic_std, 4),
        "icir": round(icir, 3) if np.isfinite(icir) else float("nan"),
        "icir_annual": round(icir * np.sqrt(periods_per_year), 3)
        if np.isfinite(icir) else float("nan"),
        "t_stat": round(icir * np.sqrt(n), 3) if np.isfinite(icir) else float("nan"),
        "hit_rate": round(float((ic > 0).mean()), 3),
        "n": n,
    }


def ic_weighted_combination(
    factor_panel: pd.DataFrame,
    ic_history: Dict[str, ArrayLike],
    shrinkage: float = 0.5,
) -> "tuple[pd.Series, Dict[str, float]]":
    """
    Combine factors weighting each by its historical ICIR (signal quality),
    shrunk toward equal weight to avoid over-fitting the weights themselves.

    weight_f ∝ shrinkage · ICIR_f  +  (1 − shrinkage) · equal_weight

    This is a simple, robust alternative to full mean-variance signal blending
    and is exactly how multi-factor desks tilt toward their best signals.

    Returns ``(composite_score, weights_used)``.
    """
    cols = list(factor_panel.columns)
    if not cols:
        return pd.Series(dtype="float64")

    icirs = {}
    for f in cols:
        summ = ic_summary(ic_history.get(f, []))
        icir = summ["icir"]
        icirs[f] = icir if (icir is not None and np.isfinite(icir)) else 0.0

    icir_vec = np.array([max(icirs[f], 0.0) for f in cols])  # long-only on signal quality
    if icir_vec.sum() < _EPS:
        ic_w = np.ones(len(cols)) / len(cols)
    else:
        ic_w = icir_vec / icir_vec.sum()
    eq_w = np.ones(len(cols)) / len(cols)
    w = shrinkage * ic_w + (1 - shrinkage) * eq_w
    w = w / w.sum()

    weights = {f: float(w[i]) for i, f in enumerate(cols)}
    return combine_factors({c: factor_panel[c] for c in cols}, weights), weights
