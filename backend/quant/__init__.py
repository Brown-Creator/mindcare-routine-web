"""
backend.quant — institutional-grade quantitative core.

A self-contained, dependency-light (numpy / pandas / scipy only) library of the
methods that separate a real quant book from a dashboard that merely *looks*
quantitative:

    cross_section   cross-sectional standardization, neutralization, IC/ICIR
    covariance      Ledoit-Wolf shrinkage, EWMA covariance, nearest-PSD
    optimization    convex max-Sharpe / min-var / mean-var / true ERC risk parity
    metrics         Cornish-Fisher VaR/CVaR, drawdown, Sortino/Calmar/Omega
    validation      purged/embargoed CV, Deflated & Probabilistic Sharpe Ratio
    sizing          discrete / continuous / multi-asset Kelly, vol targeting

Everything is unit-tested in ``backend/tests/test_quant.py``.
"""
from . import (cross_section, covariance, optimization, metrics, validation,
               sizing, factor_research, costs)

# Most-used helpers re-exported for convenience.
from .cross_section import (
    standardize_factor, combine_factors, mad_winsorize, robust_zscore,
    rank_normalize, neutralize, information_coefficient, ic_summary,
)
from .covariance import (
    ledoit_wolf_shrinkage, ledoit_wolf_identity, ewma_covariance,
    sample_covariance, nearest_psd, is_psd,
)
from .optimization import (
    OptResult, max_sharpe, min_variance, mean_variance, risk_parity,
    max_diversification, inverse_volatility, risk_contributions,
)
from .metrics import (
    sharpe_ratio, sortino_ratio, calmar_ratio, omega_ratio, max_drawdown,
    historical_var, historical_cvar, cornish_fisher_var, cornish_fisher_cvar,
    performance_summary,
)
from .validation import (
    PurgedWalkForward, PurgedKFold, probabilistic_sharpe_ratio,
    deflated_sharpe_ratio, min_track_record_length,
)
from .sizing import (
    kelly_binary, kelly_continuous, kelly_multi_asset, volatility_target,
    drawdown_throttle, size_position,
)
from .factor_research import (
    rolling_factor_ic, factor_ic_report, estimate_factor_weights,
    factor_decay, quantile_spread,
)
from .costs import CostModel, apply_cost_to_return, break_even_holding_days

__all__ = [
    "cross_section", "covariance", "optimization", "metrics", "validation",
    "sizing", "factor_research",
    "standardize_factor", "combine_factors", "mad_winsorize", "robust_zscore",
    "rank_normalize", "neutralize", "information_coefficient", "ic_summary",
    "ledoit_wolf_shrinkage", "ledoit_wolf_identity", "ewma_covariance",
    "sample_covariance", "nearest_psd", "is_psd",
    "OptResult", "max_sharpe", "min_variance", "mean_variance", "risk_parity",
    "max_diversification", "inverse_volatility", "risk_contributions",
    "sharpe_ratio", "sortino_ratio", "calmar_ratio", "omega_ratio", "max_drawdown",
    "historical_var", "historical_cvar", "cornish_fisher_var", "cornish_fisher_cvar",
    "performance_summary",
    "PurgedWalkForward", "PurgedKFold", "probabilistic_sharpe_ratio",
    "deflated_sharpe_ratio", "min_track_record_length",
    "kelly_binary", "kelly_continuous", "kelly_multi_asset", "volatility_target",
    "drawdown_throttle", "size_position",
    "rolling_factor_ic", "factor_ic_report", "estimate_factor_weights",
    "factor_decay", "quantile_spread",
    "CostModel", "apply_cost_to_return", "break_even_holding_days",
]
