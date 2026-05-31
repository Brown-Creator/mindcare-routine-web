"""
Factor research — turn a backtest of factor scores into *evidence*.

This is how a desk decides which factors to trust and how to weight them, rather
than hard-coding weights by intuition (as the original DEFAULT_WEIGHTS did):

* ``rolling_factor_ic``      — per-date Information Coefficient for each factor.
* ``estimate_factor_weights``— ICIR-proportional weights, shrunk to equal weight
                               (the standard robust factor-blending rule).
* ``factor_decay``           — IC as the forward horizon lengthens (how fast the
                               signal goes stale → sets the rebalance frequency).
* ``quantile_spread``        — the classic long-top / short-bottom quantile
                               backtest with a t-stat on the spread.

Everything is computed from panels you already produce in backtesting; no market
data dependency. Unit-tested in ``backend/tests/test_factor_research.py``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from scipy import stats

from .cross_section import information_coefficient, ic_summary

_EPS = 1e-12


def rolling_factor_ic(
    factor_panels: Dict[str, pd.DataFrame],
    forward_returns: pd.DataFrame,
    method: str = "spearman",
) -> pd.DataFrame:
    """
    Per-date IC for each factor.

    Parameters
    ----------
    factor_panels : {factor_name: DataFrame[date × asset]} of standardized scores.
    forward_returns : DataFrame[date × asset] of subsequent returns aligned to the
        same dates (already shifted so row t holds the return *earned after* t).

    Returns a DataFrame[date × factor] of ICs.
    """
    out: Dict[str, pd.Series] = {}
    for fname, panel in factor_panels.items():
        dates = panel.index.intersection(forward_returns.index)
        ics = {}
        for dt in dates:
            ics[dt] = information_coefficient(
                panel.loc[dt], forward_returns.loc[dt], method=method)
        out[fname] = pd.Series(ics, dtype="float64")
    return pd.DataFrame(out)


def factor_ic_report(ic_panel: pd.DataFrame, periods_per_year: int = 252) -> Dict[str, dict]:
    """Summarize each factor's IC time series (mean IC, ICIR, t-stat, hit rate)."""
    return {f: ic_summary(ic_panel[f], periods_per_year) for f in ic_panel.columns}


def estimate_factor_weights(
    ic_panel: pd.DataFrame,
    shrinkage: float = 0.5,
    long_only_signal: bool = True,
    periods_per_year: int = 252,
) -> Dict[str, float]:
    """
    Data-driven factor weights ∝ ICIR, shrunk toward equal weight.

        w_f ∝ shrinkage · max(ICIR_f, 0) + (1 − shrinkage) · equal

    Tilting by ICIR allocates to factors that are *consistently* predictive (high
    mean IC relative to its volatility), while the shrinkage guards against
    over-fitting the weights to a particular sample.
    """
    factors = list(ic_panel.columns)
    if not factors:
        return {}
    report = factor_ic_report(ic_panel, periods_per_year)
    icir = np.array([
        (report[f]["icir"] if report[f]["icir"] is not None
         and np.isfinite(report[f]["icir"]) else 0.0)
        for f in factors
    ])
    if long_only_signal:
        icir = np.clip(icir, 0.0, None)
    if icir.sum() < _EPS:
        ic_w = np.ones(len(factors)) / len(factors)
    else:
        ic_w = icir / icir.sum()
    eq = np.ones(len(factors)) / len(factors)
    w = shrinkage * ic_w + (1 - shrinkage) * eq
    w = w / w.sum()
    return {factors[i]: round(float(w[i]), 4) for i in range(len(factors))}


def factor_decay(
    scores: pd.DataFrame,
    returns: pd.DataFrame,
    horizons: List[int] = (1, 5, 10, 20, 60),
    method: str = "spearman",
) -> Dict[int, float]:
    """
    Mean IC of a factor against forward returns of increasing horizon.

    ``scores`` and ``returns`` are DataFrame[date × asset] of *simple per-period
    returns* (not forward). For each horizon h the forward return is compounded
    over the next h periods and the cross-sectional IC is averaged across dates.
    A factor whose IC decays slowly can be rebalanced less often.
    """
    out: Dict[int, float] = {}
    fwd_log = np.log1p(returns)
    for h in horizons:
        # forward h-period return at date t = product of returns t+1..t+h
        fwd = np.expm1(fwd_log.shift(-1).rolling(h).sum().shift(-(h - 1)))
        ics = []
        common = scores.index.intersection(fwd.index)
        for dt in common:
            ic = information_coefficient(scores.loc[dt], fwd.loc[dt], method=method)
            if np.isfinite(ic):
                ics.append(ic)
        out[h] = round(float(np.mean(ics)), 4) if ics else float("nan")
    return out


@dataclass
class QuantileBacktest:
    n_quantiles: int = 5
    quantile_returns: List[float] = field(default_factory=list)  # 평균 분위 수익(저→고)
    long_short_mean: float = 0.0     # 최고분위 − 최저분위 평균 스프레드(per period)
    long_short_t: float = 0.0        # 스프레드 t-통계량
    long_short_ir: float = 0.0       # 스프레드 정보비율(연율)
    monotonicity: float = 0.0        # 분위-수익 단조성(Spearman)
    n_periods: int = 0


def quantile_spread(
    scores: pd.DataFrame,
    forward_returns: pd.DataFrame,
    n_quantiles: int = 5,
    periods_per_year: int = 252,
) -> QuantileBacktest:
    """
    Classic factor backtest: each date, sort names into quantiles by score and
    measure the average forward return per quantile, plus the top-minus-bottom
    long-short spread with a t-stat and an annualized information ratio.

    A genuine factor shows a (near) monotonic increase in return across quantiles
    and a long-short spread that is statistically distinguishable from zero.
    """
    dates = scores.index.intersection(forward_returns.index)
    q_rets = {q: [] for q in range(n_quantiles)}
    ls_series: List[float] = []

    for dt in dates:
        s = scores.loc[dt]
        r = forward_returns.loc[dt]
        df = pd.concat([s, r], axis=1, keys=["score", "ret"]).dropna()
        if len(df) < n_quantiles * 2:
            continue
        try:
            df["q"] = pd.qcut(df["score"].rank(method="first"),
                              n_quantiles, labels=False)
        except ValueError:
            continue
        means = df.groupby("q")["ret"].mean()
        for q in range(n_quantiles):
            if q in means.index:
                q_rets[q].append(float(means[q]))
        if (n_quantiles - 1) in means.index and 0 in means.index:
            ls_series.append(float(means[n_quantiles - 1] - means[0]))

    quantile_means = [round(float(np.mean(q_rets[q])), 5) if q_rets[q] else float("nan")
                      for q in range(n_quantiles)]
    ls = np.array(ls_series, dtype="float64")
    n = len(ls)
    res = QuantileBacktest(n_quantiles=n_quantiles, quantile_returns=quantile_means,
                           n_periods=n)
    if n >= 2:
        mean_ls = float(ls.mean())
        sd_ls = float(ls.std(ddof=1))
        res.long_short_mean = round(mean_ls, 5)
        res.long_short_t = round(mean_ls / (sd_ls / np.sqrt(n)), 3) if sd_ls > _EPS else 0.0
        res.long_short_ir = round((mean_ls / sd_ls) * np.sqrt(periods_per_year), 3) \
            if sd_ls > _EPS else 0.0
    valid = [m for m in quantile_means if np.isfinite(m)]
    if len(valid) >= 3:
        res.monotonicity = round(float(
            stats.spearmanr(range(len(valid)), valid).statistic), 3)
    return res
