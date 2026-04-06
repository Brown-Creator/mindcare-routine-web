"""
포트폴리오 최적화 엔진
- Mean-Variance (Markowitz)
- Risk Parity
- Black-Litterman
- Kelly Criterion 포지션 사이징
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
import logging

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

class PortfolioOptimizer:
    """포트폴리오 최적화"""

    def __init__(self, risk_free_rate: float = 0.035):
        self.rf = risk_free_rate

    def optimize_mean_variance(self, returns: pd.DataFrame,
                                target_return: float = None) -> Dict[str, float]:
        """마코위츠 평균-분산 최적화"""
        if returns.empty or len(returns) < 30:
            return self._equal_weight(returns.columns.tolist())

        mu = returns.mean() * 252
        sigma = returns.cov() * 252
        n = len(mu)

        if n == 1:
            return {returns.columns[0]: 1.0}

        # 최대 샤프 비율 포트폴리오 (수치적 근사)
        best_sharpe = -np.inf
        best_weights = np.ones(n) / n

        np.random.seed(42)
        for _ in range(10000):
            w = np.random.dirichlet(np.ones(n))
            port_ret = np.dot(w, mu)
            port_vol = np.sqrt(np.dot(w.T, np.dot(sigma, w)))
            sharpe = (port_ret - self.rf) / port_vol if port_vol > 0 else 0

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_weights = w

        return dict(zip(returns.columns, np.round(best_weights, 4)))

    def optimize_risk_parity(self, returns: pd.DataFrame) -> Dict[str, float]:
        """리스크 패리티 (각 자산의 리스크 기여도 균등화)"""
        if returns.empty or len(returns) < 30:
            return self._equal_weight(returns.columns.tolist())

        sigma = returns.cov() * 252
        n = len(sigma)

        # 역변동성 가중 (Risk Parity 근사)
        vols = np.sqrt(np.diag(sigma))
        if np.any(vols == 0):
            return self._equal_weight(returns.columns.tolist())

        inv_vols = 1 / vols
        weights = inv_vols / inv_vols.sum()

        # 상관관계 고려한 보정
        corr = returns.corr()
        avg_corr = (corr.values.sum() - n) / (n * (n - 1)) if n > 1 else 0

        # 높은 상관관계이면 집중도 줄임
        if avg_corr > 0.7:
            weights = weights * 0.7 + np.ones(n) / n * 0.3

        weights = weights / weights.sum()
        return dict(zip(returns.columns, np.round(weights, 4)))

    def optimize_black_litterman(self, returns: pd.DataFrame,
                                  views: Dict[str, float],
                                  view_confidences: Dict[str, float] = None,
                                  market_caps: Dict[str, float] = None) -> Dict[str, float]:
        """
        Black-Litterman 모델
        views: {ticker: expected_return} (절대 전망)
        """
        if returns.empty or len(returns) < 30:
            return self._equal_weight(returns.columns.tolist())

        tickers = returns.columns.tolist()
        n = len(tickers)
        sigma = returns.cov().values * 252

        # 시장 균형 수익률 (CAPM 기반)
        if market_caps:
            caps = np.array([market_caps.get(t, 1) for t in tickers], dtype=float)
            market_weights = caps / caps.sum()
        else:
            market_weights = np.ones(n) / n

        # 리스크 회피 계수
        delta = 2.5
        pi = delta * sigma @ market_weights  # 균형 수익률

        # 뷰 행렬 구성
        view_tickers = [t for t in tickers if t in views]
        if not view_tickers:
            return dict(zip(tickers, np.round(market_weights, 4)))

        k = len(view_tickers)
        P = np.zeros((k, n))
        Q = np.zeros(k)
        for i, t in enumerate(view_tickers):
            j = tickers.index(t)
            P[i, j] = 1
            Q[i] = views[t]

        # 불확실성 행렬
        tau = 0.05
        if view_confidences:
            omega_diag = [1 / max(view_confidences.get(t, 0.5), 0.01) * 0.01 for t in view_tickers]
        else:
            omega_diag = [tau * P[i] @ sigma @ P[i].T for i in range(k)]
        omega = np.diag(omega_diag)

        # BL 수정 수익률
        tau_sigma = tau * sigma
        inv_tau_sigma = np.linalg.inv(tau_sigma)
        inv_omega = np.linalg.inv(omega)

        bl_mu = np.linalg.inv(inv_tau_sigma + P.T @ inv_omega @ P) @ \
                (inv_tau_sigma @ pi + P.T @ inv_omega @ Q)

        # 최적 가중치
        weights = np.linalg.inv(delta * sigma) @ bl_mu
        weights = np.maximum(weights, 0)  # 공매도 불가
        if weights.sum() > 0:
            weights = weights / weights.sum()

        return dict(zip(tickers, np.round(weights, 4)))

    def kelly_position_size(self, win_rate: float, avg_win: float,
                            avg_loss: float, kelly_fraction: float = 0.25) -> float:
        """
        Kelly Criterion 포지션 사이징
        kelly_fraction: Full Kelly의 1/4 사용 (보수적)
        """
        if avg_loss == 0 or win_rate <= 0:
            return 0

        b = avg_win / abs(avg_loss)  # 승/패 비율
        p = win_rate
        q = 1 - p

        kelly = (b * p - q) / b
        return max(0, kelly * kelly_fraction)

    def calculate_rebalance(self, current_positions: Dict[str, float],
                            target_weights: Dict[str, float],
                            total_value: float,
                            prices: Dict[str, float]) -> List[PortfolioAllocation]:
        """리밸런싱 계산"""
        allocations = []
        for ticker, target_w in target_weights.items():
            current_w = current_positions.get(ticker, 0)
            target_amount = total_value * target_w
            current_amount = total_value * current_w
            diff = target_amount - current_amount
            price = prices.get(ticker, 1)
            shares = int(abs(diff) / price) if price > 0 else 0

            action = "유지"
            if diff > total_value * 0.01:
                action = "매수"
            elif diff < -total_value * 0.01:
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
        return {t: round(1/n, 4) for t in tickers}

    def calculate_metrics(self, returns: pd.DataFrame,
                          weights: Dict[str, float]) -> dict:
        """포트폴리오 성과 지표 계산"""
        w = np.array([weights.get(c, 0) for c in returns.columns])
        port_ret = returns @ w

        ann_ret = port_ret.mean() * 252
        ann_vol = port_ret.std() * np.sqrt(252)
        sharpe = (ann_ret - self.rf) / ann_vol if ann_vol > 0 else 0

        # 소르티노 (하방 변동성만)
        downside = port_ret[port_ret < 0].std() * np.sqrt(252)
        sortino = (ann_ret - self.rf) / downside if downside > 0 else 0

        # MDD
        cumulative = (1 + port_ret).cumprod()
        drawdown = cumulative / cumulative.cummax() - 1
        mdd = drawdown.min()

        # Calmar
        calmar = ann_ret / abs(mdd) if mdd != 0 else 0

        return {
            "annual_return": round(ann_ret * 100, 2),
            "annual_volatility": round(ann_vol * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "max_drawdown": round(mdd * 100, 2),
            "calmar_ratio": round(calmar, 3),
        }
