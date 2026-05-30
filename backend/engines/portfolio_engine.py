"""
포트폴리오 최적화 엔진 (★ 퀀트 코어 연동 버전 ★)

이전 구현은 "마코위츠 최적화"라는 이름으로 디리클레 난수 1만 개를 뽑아 그중
샤프가 가장 높은 것을 고르는 방식이었다. 이는 최적화가 아니라 무작위 탐색이며,
자산이 몇 개만 넘어가도 효율적 프론티어 근처에도 가지 못한다. 또 표본 공분산을
그대로 사용해 추정오차가 최적해를 지배한다("error maximization").

본 버전은 ``backend.quant`` 의 institutional-grade 모듈에 위임한다:
  - 공분산: Ledoit-Wolf 수축 추정(표본 공분산의 추정오차 제거)
  - 최적화: scipy SLSQP 기반 진짜 볼록 최적화(max-Sharpe / min-var / mean-var)
  - 리스크 패리티: 단순 역변동성이 아닌 진짜 ERC(등위험기여)
  - Kelly / 성과지표: 검증된 quant.sizing / quant.metrics

공개 API(메서드 시그니처, 반환 형식)는 기존과 동일하게 유지하여 호출부 호환성을 보장.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

from backend.quant import covariance as qcov
from backend.quant import optimization as qopt
from backend.quant import sizing as qsize
from backend.quant import metrics as qmet

logger = logging.getLogger(__name__)


@dataclass
class PortfolioAllocation:
    ticker: str
    name: str = ""
    weight: float = 0              # 목표 비중 (0~1)
    amount: float = 0             # 투자 금액
    shares: int = 0               # 목표 주수
    current_weight: float = 0     # 현재 비중
    rebalance_action: str = ""    # 매수/매도/유지
    rebalance_amount: float = 0   # 리밸런싱 금액


@dataclass
class OptimizationResult:
    allocations: List[PortfolioAllocation] = field(default_factory=list)
    expected_return: float = 0
    expected_risk: float = 0
    sharpe_ratio: float = 0
    method: str = ""
    diversification_ratio: float = 0
    effective_n: float = 0
    shrinkage: float = 0          # Ledoit-Wolf 수축 강도(진단용)


class PortfolioOptimizer:
    """포트폴리오 최적화 — 볼록 최적화 + 공분산 수축."""

    def __init__(self, risk_free_rate: float = 0.035, periods_per_year: int = 252,
                 covariance_method: str = "ledoit_wolf"):
        self.rf = risk_free_rate
        self.ppy = periods_per_year
        self.cov_method = covariance_method

    # ─── 공분산 추정 (수축) ───
    def estimate_covariance(self, returns: pd.DataFrame):
        """
        일별 수익률로부터 (연율화된) 공분산 행렬을 추정.
        기본은 Ledoit-Wolf 상수상관 수축 — 표본 공분산의 작은 고유값 편향을 교정해
        최적화기가 추정오차에 베팅하는 것을 막는다.
        반환: (annualized_cov_df, shrinkage_delta)
        """
        if returns is None or returns.empty or returns.shape[1] == 0:
            return pd.DataFrame(), 0.0
        clean = returns.dropna(how="all").fillna(0.0)
        if self.cov_method == "ewma":
            cov = qcov.ewma_covariance(clean, halflife=60)
            delta = float("nan")
        elif self.cov_method == "sample":
            cov = qcov.sample_covariance(clean)
            delta = 0.0
        else:
            cov, delta = qcov.ledoit_wolf_shrinkage(clean)
        # PSD 보정 후 연율화
        psd = qcov.nearest_psd(cov.to_numpy())
        cov = pd.DataFrame(psd, index=cov.index, columns=cov.columns) * self.ppy
        return cov, delta

    # ─── 마코위츠(최대 샤프 / 목표수익) ───
    def optimize_mean_variance(self, returns: pd.DataFrame,
                               target_return: float = None,
                               max_weight: float = 1.0) -> Dict[str, float]:
        """
        평균-분산 최적화 (진짜 볼록 최적화).
        target_return 미지정 시 최대 샤프(접점 포트폴리오)를 반환.
        """
        if returns is None or returns.empty or len(returns) < 30:
            return self._equal_weight(list(returns.columns) if returns is not None else [])
        if returns.shape[1] == 1:
            return {returns.columns[0]: 1.0}

        cov, _ = self.estimate_covariance(returns)
        mu_annual = returns.mean() * self.ppy        # 연율화 기대수익
        labels = list(returns.columns)

        try:
            if target_return is not None:
                res = qopt.mean_variance(
                    mu_annual.values, cov, risk_aversion=3.0,
                    lb=0.0, ub=max_weight, periods_per_year=1,
                )
            else:
                res = qopt.max_sharpe(
                    mu_annual.values, cov, rf=self.rf,
                    lb=0.0, ub=max_weight, periods_per_year=1,
                )
            return {labels[i]: res.weights.get(cov.columns[i], 0.0)
                    for i in range(len(labels))}
        except Exception as e:
            logger.warning(f"평균-분산 최적화 실패, 동일가중 대체: {e}")
            return self._equal_weight(labels)

    # ─── 리스크 패리티(진짜 ERC) ───
    def optimize_risk_parity(self, returns: pd.DataFrame,
                             max_weight: float = 1.0) -> Dict[str, float]:
        """
        진짜 등위험기여(ERC) 포트폴리오.
        각 자산의 '위험 기여도'를 균등화 — 상관관계를 반영하므로 단순 역변동성과 다르다.
        """
        if returns is None or returns.empty or len(returns) < 30:
            return self._equal_weight(list(returns.columns) if returns is not None else [])
        cov, _ = self.estimate_covariance(returns)
        try:
            ub = None if max_weight >= 1.0 else max_weight
            res = qopt.risk_parity(cov, lb=0.0, ub=ub, periods_per_year=1)
            return dict(res.weights)
        except Exception as e:
            logger.warning(f"리스크 패리티 실패, 역변동성 대체: {e}")
            res = qopt.inverse_volatility(cov, periods_per_year=1)
            return dict(res.weights)

    def optimize_min_variance(self, returns: pd.DataFrame,
                              max_weight: float = 1.0) -> Dict[str, float]:
        """글로벌 최소분산 포트폴리오."""
        if returns is None or returns.empty or len(returns) < 30:
            return self._equal_weight(list(returns.columns) if returns is not None else [])
        cov, _ = self.estimate_covariance(returns)
        ub = None if max_weight >= 1.0 else max_weight
        res = qopt.min_variance(cov, lb=0.0, ub=ub, periods_per_year=1)
        return dict(res.weights)

    # ─── Black-Litterman ───
    def optimize_black_litterman(self, returns: pd.DataFrame,
                                 views: Dict[str, float],
                                 view_confidences: Dict[str, float] = None,
                                 market_caps: Dict[str, float] = None) -> Dict[str, float]:
        """
        Black-Litterman 모델 (수축 공분산 사용).
        views: {ticker: 연율 기대수익(절대 전망)}
        시장 균형 수익률(역최적화)에서 출발해 투자자 뷰를 베이지안 결합한다.
        """
        if returns is None or returns.empty or len(returns) < 30:
            return self._equal_weight(list(returns.columns) if returns is not None else [])

        tickers = list(returns.columns)
        n = len(tickers)
        cov_df, _ = self.estimate_covariance(returns)
        sigma = cov_df.to_numpy()

        if market_caps:
            caps = np.array([market_caps.get(t, 1) for t in tickers], dtype=float)
            w_mkt = caps / caps.sum()
        else:
            w_mkt = np.ones(n) / n

        delta = 2.5  # 시장 리스크 회피
        pi = delta * sigma @ w_mkt  # 균형(내재) 수익률

        view_tickers = [t for t in tickers if t in views]
        if not view_tickers:
            return dict(zip(tickers, np.round(w_mkt, 4)))

        k = len(view_tickers)
        P = np.zeros((k, n))
        Q = np.zeros(k)
        for i, t in enumerate(view_tickers):
            P[i, tickers.index(t)] = 1
            Q[i] = views[t]

        tau = 0.05
        if view_confidences:
            omega_diag = [max(1e-6, (1 / max(view_confidences.get(t, 0.5), 0.01) - 1)
                              * tau * (P[i] @ sigma @ P[i].T))
                          for i, t in enumerate(view_tickers)]
        else:
            omega_diag = [tau * P[i] @ sigma @ P[i].T for i in range(k)]
        omega = np.diag(np.maximum(omega_diag, 1e-10))

        tau_sigma = tau * sigma
        try:
            inv_tau_sigma = np.linalg.inv(tau_sigma)
            inv_omega = np.linalg.inv(omega)
            bl_cov = np.linalg.inv(inv_tau_sigma + P.T @ inv_omega @ P)
            bl_mu = bl_cov @ (inv_tau_sigma @ pi + P.T @ inv_omega @ Q)
        except np.linalg.LinAlgError:
            return dict(zip(tickers, np.round(w_mkt, 4)))

        # BL 사후 기대수익으로 최대샤프 재최적화(롱온리)
        res = qopt.max_sharpe(bl_mu, cov_df, rf=self.rf, lb=0.0, ub=1.0,
                              periods_per_year=1)
        return dict(res.weights)

    # ─── Kelly 포지션 사이징 ───
    def kelly_position_size(self, win_rate: float, avg_win: float,
                            avg_loss: float, kelly_fraction: float = 0.25) -> float:
        """
        Kelly 기준 포지션 비중. Full Kelly의 1/4(보수적)이 기본.
        검증된 quant.sizing.kelly_binary 에 위임.
        """
        b = avg_win / abs(avg_loss) if avg_loss else 0.0
        return qsize.kelly_binary(win_rate, b, fraction=kelly_fraction)

    # ─── 리밸런싱 ───
    def calculate_rebalance(self, current_positions: Dict[str, float],
                            target_weights: Dict[str, float],
                            total_value: float,
                            prices: Dict[str, float],
                            rebalance_band: float = 0.01) -> List[PortfolioAllocation]:
        """리밸런싱 계산 (밴드 밖에서만 거래해 회전율/비용 절감)."""
        allocations = []
        for ticker, target_w in target_weights.items():
            current_w = current_positions.get(ticker, 0)
            target_amount = total_value * target_w
            diff = target_amount - total_value * current_w
            price = prices.get(ticker, 1)
            shares = int(abs(diff) / price) if price > 0 else 0

            action = "유지"
            if diff > total_value * rebalance_band:
                action = "매수"
            elif diff < -total_value * rebalance_band:
                action = "매도"

            allocations.append(PortfolioAllocation(
                ticker=ticker, weight=target_w, amount=target_amount,
                shares=shares, current_weight=current_w,
                rebalance_action=action, rebalance_amount=abs(diff),
            ))
        return allocations

    @staticmethod
    def _equal_weight(tickers: list) -> Dict[str, float]:
        n = max(len(tickers), 1)
        return {t: round(1 / n, 4) for t in tickers}

    # ─── 성과 지표 ───
    def calculate_metrics(self, returns: pd.DataFrame,
                          weights: Dict[str, float]) -> dict:
        """포트폴리오 성과 지표 (검증된 quant.metrics 사용)."""
        if returns is None or returns.empty:
            return {}
        w = np.array([weights.get(c, 0) for c in returns.columns])
        port_ret = returns.fillna(0.0).to_numpy() @ w
        summary = qmet.performance_summary(port_ret, rf=self.rf,
                                           periods_per_year=self.ppy)
        # 기존 키 호환 유지
        return {
            "annual_return": summary["ann_return_pct"],
            "annual_volatility": summary["ann_vol_pct"],
            "sharpe_ratio": summary["sharpe"],
            "sortino_ratio": summary["sortino"],
            "max_drawdown": summary["max_drawdown_pct"],
            "calmar_ratio": summary["calmar"],
            "omega_ratio": summary["omega"],
            "var_95_pct": summary["var_95_hist_pct"],
            "cvar_95_pct": summary["cvar_95_hist_pct"],
            "cvar_99_cornish_fisher_pct": summary["cvar_99_cornish_fisher_pct"],
        }

    # ─── 종합 최적화 (진단 포함) ───
    def optimize(self, returns: pd.DataFrame, method: str = "max_sharpe",
                 max_weight: float = 0.25, **kwargs) -> OptimizationResult:
        """
        통합 최적화 진입점 — 비중 + 진단지표(샤프/분산화비율/유효종목수/수축강도)를 반환.
        method: max_sharpe / min_variance / risk_parity / mean_variance / max_diversification
        """
        labels = list(returns.columns) if returns is not None else []
        if not labels or len(returns) < 30:
            w = self._equal_weight(labels)
            return OptimizationResult(method="equal_weight",
                                      allocations=[PortfolioAllocation(t, weight=wv)
                                                   for t, wv in w.items()])
        cov, delta = self.estimate_covariance(returns)
        mu_annual = returns.mean() * self.ppy
        ub = None if max_weight >= 1.0 else max_weight
        if method == "min_variance":
            res = qopt.min_variance(cov, lb=0.0, ub=ub, periods_per_year=1)
        elif method == "risk_parity":
            res = qopt.risk_parity(cov, lb=0.0, ub=ub, periods_per_year=1)
        elif method == "max_diversification":
            res = qopt.max_diversification(cov, lb=0.0, ub=ub, periods_per_year=1)
        elif method == "mean_variance":
            res = qopt.mean_variance(mu_annual.values, cov,
                                     risk_aversion=kwargs.get("risk_aversion", 3.0),
                                     lb=0.0, ub=max_weight, periods_per_year=1)
        else:
            res = qopt.max_sharpe(mu_annual.values, cov, rf=self.rf,
                                  lb=0.0, ub=max_weight, periods_per_year=1)
        return OptimizationResult(
            allocations=[PortfolioAllocation(ticker=t, weight=round(wv, 4))
                         for t, wv in res.weights.items()],
            expected_return=res.expected_return if res.expected_return else
            float(mu_annual.values @ res.weight_array(labels)),
            expected_risk=res.expected_vol,
            sharpe_ratio=res.sharpe,
            method=res.method,
            diversification_ratio=res.diversification_ratio,
            effective_n=res.effective_n,
            shrinkage=round(float(delta), 4) if np.isfinite(delta) else 0.0,
        )
