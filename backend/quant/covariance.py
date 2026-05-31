"""
Covariance estimation — shrinkage and exponential weighting.

The sample covariance matrix is a notoriously bad input to a portfolio
optimizer: with N assets you must estimate N(N+1)/2 parameters, so the smallest
eigenvalues are biased downward and the optimizer piles risk into them. Real
desks never feed the raw sample covariance to an optimizer. This module
implements the two standard fixes:

1. Ledoit-Wolf (2004) shrinkage toward a constant-correlation target, with the
   analytically optimal shrinkage intensity (no cross-validation needed).
2. Exponentially-weighted (RiskMetrics-style) covariance for regime adaptivity.

Plus a nearest-PSD projection so any matrix we hand to the optimizer is a valid
covariance matrix.

Reference
---------
Ledoit, O. & Wolf, M. (2004). "Honey, I Shrunk the Sample Covariance Matrix."
*Journal of Portfolio Management* 30(4), 110-119.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Tuple, Union

_EPS = 1e-12
ArrayLike = Union[pd.DataFrame, np.ndarray]


def _as_matrix(returns: ArrayLike) -> Tuple[np.ndarray, list]:
    """Return a (T, N) float array of returns and the asset labels."""
    if isinstance(returns, pd.DataFrame):
        cols = list(returns.columns)
        X = returns.to_numpy(dtype="float64")
    else:
        X = np.asarray(returns, dtype="float64")
        cols = list(range(X.shape[1])) if X.ndim == 2 else [0]
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    return X, cols


def sample_covariance(returns: ArrayLike, ddof: int = 1) -> pd.DataFrame:
    """Plain sample covariance (annualize separately if desired)."""
    X, cols = _as_matrix(returns)
    cov = np.cov(X, rowvar=False, ddof=ddof)
    cov = np.atleast_2d(cov)
    return pd.DataFrame(cov, index=cols, columns=cols)


def ledoit_wolf_shrinkage(returns: ArrayLike) -> Tuple[pd.DataFrame, float]:
    """
    Ledoit-Wolf shrinkage of the sample covariance toward a constant-correlation
    target, with the closed-form optimal shrinkage intensity.

    Σ̂ = δ · F + (1 − δ) · S

    where S is the sample covariance, F is the constant-correlation target
    (same variances as S, all pairwise correlations replaced by their average),
    and δ ∈ [0, 1] minimizes the expected Frobenius loss E‖Σ̂ − Σ‖².

    Returns ``(shrunk_covariance, delta)``. Input returns are *not* annualized;
    multiply the result by the periods-per-year if you need annual covariance.
    """
    X, cols = _as_matrix(returns)
    t, n = X.shape
    if t < 2 or n < 1:
        S = sample_covariance(returns)
        return S, 0.0
    if n == 1:
        S = sample_covariance(returns)
        return S, 0.0

    # Demean (the estimator is defined on the centered data).
    mean = X.mean(axis=0)
    Xc = X - mean

    # Sample covariance (MLE / divide by t, matching the LW derivation).
    S = (Xc.T @ Xc) / t

    var = np.diag(S)
    std = np.sqrt(np.clip(var, _EPS, None))
    outer_std = np.outer(std, std)

    # Average pairwise sample correlation r̄.
    corr = S / outer_std
    mask_off = ~np.eye(n, dtype=bool)
    r_bar = corr[mask_off].mean()

    # Constant-correlation target F.
    F = r_bar * outer_std
    np.fill_diagonal(F, var)

    # π : sum of asymptotic variances of the entries of S.
    Xc2 = Xc ** 2
    pi_mat = (Xc2.T @ Xc2) / t - S ** 2
    pi_hat = pi_mat.sum()

    # ρ : asymptotic covariance between the target and the sample.
    # Diagonal entries of the target equal S, so they contribute π_ii directly.
    rho_diag = np.trace(pi_mat)
    # Off-diagonal term (the "theta" terms from the LW paper).
    term1 = (Xc ** 3).T @ Xc / t            # E[x_i^3 x_j]
    theta_ij = term1 - var[:, None] * S     # ϑ_{ii,ij} = AsyCov(s_ii, s_ij)
    # ratio[i, j] = std_j / std_i = sqrt(s_jj / s_ii).  Note np.outer(std, std)
    # is symmetric, so dividing it by its transpose would give all-ones — the
    # correct ratio is the outer product of (1/std) with std.
    ratio = np.outer(1.0 / std, std)
    rho_off = (r_bar / 2.0) * (ratio * theta_ij + ratio.T * theta_ij.T)
    np.fill_diagonal(rho_off, 0.0)
    rho_hat = rho_diag + rho_off[mask_off].sum()

    # γ : squared Frobenius distance between sample and target.
    gamma_hat = np.sum((F - S) ** 2)

    # Optimal shrinkage intensity κ/t, clipped to [0, 1].
    if gamma_hat < _EPS:
        delta = 0.0
    else:
        kappa = (pi_hat - rho_hat) / gamma_hat
        delta = float(np.clip(kappa / t, 0.0, 1.0))

    sigma = delta * F + (1 - delta) * S

    # Re-scale to an unbiased (ddof=1) covariance for downstream use.
    sigma = sigma * (t / (t - 1))
    return pd.DataFrame(sigma, index=cols, columns=cols), delta


def ledoit_wolf_identity(returns: ArrayLike) -> Tuple[pd.DataFrame, float]:
    """
    Ledoit-Wolf (2004 JMVA) shrinkage toward a scaled identity target.

    Simpler cousin of the constant-correlation estimator: the target is
    μ·I where μ is the average sample variance. Handy when N ≫ T and even the
    constant-correlation target is unstable.
    """
    X, cols = _as_matrix(returns)
    t, n = X.shape
    if t < 2 or n < 1:
        return sample_covariance(returns), 0.0
    Xc = X - X.mean(axis=0)
    S = (Xc.T @ Xc) / t
    mu = np.trace(S) / n
    target = mu * np.eye(n)

    d2 = np.sum((S - target) ** 2)              # ‖S − μI‖²
    b_bar2 = 0.0
    for k in range(t):
        xk = Xc[k][:, None]
        b_bar2 += np.sum((xk @ xk.T - S) ** 2)
    b_bar2 /= t ** 2
    b2 = min(b_bar2, d2)                          # b² ≤ d²
    delta = float(b2 / d2) if d2 > _EPS else 0.0

    sigma = delta * target + (1 - delta) * S
    sigma = sigma * (t / (t - 1))
    return pd.DataFrame(sigma, index=cols, columns=cols), delta


def ewma_covariance(returns: ArrayLike, halflife: float = 60.0) -> pd.DataFrame:
    """
    Exponentially-weighted covariance (RiskMetrics style).

    Recent observations get more weight (decay set by ``halflife`` in periods),
    so the estimate adapts to volatility regimes far faster than an equal-weight
    window — important during crises when correlations spike.
    """
    X, cols = _as_matrix(returns)
    t, n = X.shape
    if t < 2:
        return sample_covariance(returns)
    lam = 0.5 ** (1.0 / max(halflife, _EPS))
    weights = lam ** np.arange(t - 1, -1, -1)     # oldest → newest
    weights = weights / weights.sum()
    mean = np.average(X, axis=0, weights=weights)
    Xc = X - mean
    cov = (Xc * weights[:, None]).T @ Xc
    # Normalize for the effective sample size (bias correction).
    cov = cov / (1.0 - np.sum(weights ** 2))
    return pd.DataFrame(cov, index=cols, columns=cols)


def nearest_psd(matrix: ArrayLike, epsilon: float = 0.0) -> np.ndarray:
    """
    Project a symmetric matrix onto the nearest positive-semidefinite matrix by
    clipping negative eigenvalues. Guarantees a valid covariance input for the
    optimizer even after shrinkage/EWMA numerical noise.
    """
    A = np.asarray(matrix, dtype="float64")
    A = (A + A.T) / 2.0
    vals, vecs = np.linalg.eigh(A)
    vals = np.clip(vals, epsilon, None)
    return (vecs * vals) @ vecs.T


def is_psd(matrix: ArrayLike, tol: float = 1e-10) -> bool:
    """True if ``matrix`` is symmetric positive-semidefinite within tolerance."""
    A = np.asarray(matrix, dtype="float64")
    if not np.allclose(A, A.T, atol=1e-8):
        return False
    return bool(np.linalg.eigvalsh((A + A.T) / 2.0).min() >= -tol)


def cov_to_corr(cov: ArrayLike) -> np.ndarray:
    """Convert a covariance matrix to a correlation matrix."""
    C = np.asarray(cov, dtype="float64")
    d = np.sqrt(np.clip(np.diag(C), _EPS, None))
    corr = C / np.outer(d, d)
    np.fill_diagonal(corr, 1.0)
    return corr


def condition_number(matrix: ArrayLike) -> float:
    """λ_max / λ_min — a quick diagnostic for optimizer-destabilizing ill-conditioning."""
    vals = np.linalg.eigvalsh((np.asarray(matrix) + np.asarray(matrix).T) / 2.0)
    lo = vals.min()
    if lo <= _EPS:
        return float("inf")
    return float(vals.max() / lo)
