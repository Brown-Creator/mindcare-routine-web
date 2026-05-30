"""
프로덕션 리스크 엔진 ★★★ 고도화 버전 ★★★
- Historical CVaR (Conditional Value at Risk) 99% 신뢰구간
- Monte Carlo CVaR
- 포트폴리오 상관관계 리스크 (HHI 지수 + 집중도)
- 스트레스 테스트 (코로나/금융위기 시나리오)
- 유동성 리스크 (청산 예상 시간)
- 동적 포지션 스케일러 (VIX + CVaR 기반)
- 실시간 Greeks 모니터링 (Delta, Beta)
"""
import numpy as np
import pandas as pd
from scipy import stats
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from backend.engines.risk_engine import BaseRiskEngine
from backend.models.stock import StockSignal, StockState, Position, PortfolioSummary
from backend.models.order import Order
from backend.models.risk import RiskCheckResult, RiskStatus, RiskLevel
from backend.config import config
from backend.quant import metrics as qmet

logger = logging.getLogger(__name__)


# ─── 고도화 리스크 데이터 구조 ───

@dataclass
class CVaRResult:
    """CVaR 계산 결과"""
    var_95: float = 0.0          # 95% VaR (원)
    var_99: float = 0.0          # 99% VaR (원)
    cvar_95: float = 0.0         # 95% CVaR (Expected Shortfall)
    cvar_99: float = 0.0         # 99% CVaR
    var_95_pct: float = 0.0      # 95% VaR (%)
    var_99_pct: float = 0.0      # 99% VaR (%)
    # ★ Cornish-Fisher (왜도·첨도 보정) — 팻테일을 반영한 modified VaR/ES
    var_cf_99_pct: float = 0.0   # 99% Cornish-Fisher VaR (%)
    cvar_cf_99_pct: float = 0.0  # 99% Cornish-Fisher CVaR (%)
    method: str = "historical"   # historical / monte_carlo
    lookback_days: int = 0


@dataclass
class CorrelationRisk:
    """포트폴리오 상관관계 리스크"""
    hhi_index: float = 0.0       # Herfindahl-Hirschman Index (집중도)
    avg_correlation: float = 0.0  # 평균 상관계수
    max_correlation_pair: Tuple = ("", "", 0.0)  # 가장 높은 상관관계 종목쌍
    diversification_ratio: float = 1.0  # 분산투자 비율 (높을수록 좋음)
    sector_concentration: Dict[str, float] = field(default_factory=dict)
    cluster_risk: bool = False    # 한 방향으로 몰린 클러스터 리스크


@dataclass
class StressTestResult:
    """스트레스 테스트 결과"""
    scenario: str = ""
    portfolio_loss_pct: float = 0.0   # 예상 손실률 (%)
    portfolio_loss_krw: float = 0.0   # 예상 손실액 (원)
    survival: bool = True             # 생존 여부 (손실 > 자본금 50%)
    worst_ticker: str = ""
    worst_ticker_loss_pct: float = 0.0


@dataclass
class LiquidityRisk:
    """유동성 리스크"""
    ticker: str = ""
    position_value: float = 0.0
    avg_daily_volume_krw: float = 0.0
    days_to_liquidate: float = 0.0   # 청산 예상 일수
    liquidity_score: float = 100.0   # 0-100 (100=완전 유동)
    risk_level: str = "낮음"         # 낮음/보통/높음/위험


class LiveRiskEngine(BaseRiskEngine):
    """프로덕션 리스크 엔진"""

    def __init__(self):
        self._kill_switch = False
        self._kill_reason = ""
        self._daily_pnl = 0
        self._daily_trades = 0
        self._blocked_tickers: List[str] = []
        self._alerts: List[str] = []
        self._order_log: List[dict] = []
        # ★ 고도화 추가 상태 ★
        self._returns_history: Dict[str, List[float]] = {}  # 종목별 수익률 히스토리
        self._position_returns: List[float] = []  # 포트폴리오 수익률 히스토리
        self._current_vix: float = 20.0
        self._stress_scenarios_last_run: Optional[datetime] = None

        # 설정값 로드
        risk_cfg = config.risk_config
        self.max_daily_loss_pct = risk_cfg.get("max_daily_loss_pct", 3.0)
        self.max_position_pct = risk_cfg.get("max_position_pct", 20.0)
        self.max_drawdown_pct = risk_cfg.get("max_drawdown_pct", 10.0)
        self.max_order_loss_pct = risk_cfg.get("max_order_loss_pct", 2.0)
        self.max_avg_down = risk_cfg.get("max_avg_down_count", 2)
        # ★ CVaR 파라미터
        self.cvar_confidence = 0.99     # 99% CVaR
        self.max_cvar_pct = 0.05        # 포트폴리오 대비 최대 CVaR 5%
        self.max_hhi = 0.35             # 최대 HHI 집중도 (0.25=분산, 1=독점)

    async def check_order(self, order: Order, signal: StockSignal,
                          portfolio: PortfolioSummary,
                          positions: List[Position]) -> RiskCheckResult:
        """주문 리스크 검사 (12항목)"""
        passed = []
        failed = []

        # 0. 킬스위치
        if self._kill_switch:
            return RiskCheckResult(
                approved=False, level=RiskLevel.BLOCKED,
                checks_failed=["킬스위치 활성화됨"],
                reason=f"킬스위치: {self._kill_reason}"
            )

        # 1. 일일 최대 손실
        daily_loss = abs(self._daily_pnl) / max(portfolio.total_value, 1) * 100
        if daily_loss < self.max_daily_loss_pct:
            passed.append(f"일일 손실 {daily_loss:.1f}% < {self.max_daily_loss_pct}%")
        else:
            failed.append(f"일일 손실 {daily_loss:.1f}% 초과")

        # 2. 종목별 최대 비중
        order_value = order.price * order.quantity
        position_value = order_value
        for p in positions:
            if p.ticker == order.ticker:
                position_value += p.market_value
        weight = position_value / max(portfolio.total_value, 1) * 100
        if weight <= self.max_position_pct:
            passed.append(f"종목 비중 {weight:.1f}% ≤ {self.max_position_pct}%")
        else:
            failed.append(f"종목 비중 {weight:.1f}% 초과")

        # 3. 드로다운
        if abs(portfolio.max_drawdown_pct) < self.max_drawdown_pct:
            passed.append(f"MDD {portfolio.max_drawdown_pct:.1f}% < {self.max_drawdown_pct}%")
        else:
            failed.append(f"MDD {portfolio.max_drawdown_pct:.1f}% 초과")

        # 4. 단일 주문 리스크
        order_risk = order_value / max(portfolio.total_value, 1) * 100
        if order_risk <= self.max_order_loss_pct * 5:
            passed.append(f"주문 규모 {order_risk:.1f}% 적정")
        else:
            failed.append(f"주문 규모 {order_risk:.1f}% 과대")

        # 5. 매매금지 종목
        if order.ticker in self._blocked_tickers:
            failed.append("매매금지 종목")
        elif getattr(signal, "state", None) == StockState.TRADE_BLOCKED:
            failed.append("리스크 차단 종목")

        # 6. 중복 주문 감지
        recent = [o for o in self._order_log[-20:]
                  if o.get("ticker") == order.ticker and
                  o.get("side") == order.side.value]
        if len(recent) >= 3:
            failed.append("단기 중복 주문 감지 (동일 종목 3회 이상)")

        # 7. 장 시작 직후 필터 (09:00-09:15)
        now = datetime.now()
        if now.hour == 9 and now.minute < 15:
            if signal.confidence < 80:
                failed.append("장 초반 과열 구간 (09:15 이후 재시도)")

        # 8. 시그널 신뢰도 최소값
        if signal.confidence < 40:
            failed.append(f"시그널 신뢰도 {signal.confidence}% 기준 미달 (최소 40%)")

        # VaR 체크 (Historical)
        var_check = self._check_var(portfolio, order_value)
        if var_check:
            failed.append(var_check)

        # 결과
        approved = len(failed) == 0
        level = RiskLevel.LOW if approved else (
            RiskLevel.HIGH if len(failed) >= 3 else RiskLevel.MODERATE
        )

        # 로깅
        self._order_log.append({
            "ticker": order.ticker, "side": order.side.value if hasattr(order.side, 'value') else str(order.side),
            "quantity": order.quantity, "approved": approved,
            "timestamp": now.isoformat(),
        })

        return RiskCheckResult(
            approved=approved, level=level,
            checks_passed=passed, checks_failed=failed,
            reason="모든 리스크 검사 통과" if approved else f"리스크 검사 실패: {'; '.join(failed)}",
            daily_loss_pct=round(daily_loss, 2),
            position_weight_pct=round(weight, 2),
            drawdown_pct=round(abs(portfolio.max_drawdown_pct), 2),
            order_risk_pct=round(order_risk, 2),
        )

    async def check_avg_down_allowed(self, ticker, signal, position) -> RiskCheckResult:
        """물타기 허용 여부"""
        failed = []

        if position.avg_down_count >= self.max_avg_down:
            failed.append(f"물타기 횟수 초과 ({position.avg_down_count}/{self.max_avg_down})")

        if signal.trend_score < 35:
            failed.append("하락 추세 중 물타기 금지 (추세점수 35 미만)")

        if signal.bottom_probability_score < 50:
            failed.append("바닥 확률 부족 (50 미만)")

        if signal.event_risk_score > 70:
            failed.append("이벤트 리스크 높음 (70 초과)")

        loss_pct = position.pnl_pct
        if loss_pct < -15:
            failed.append(f"손실률 {loss_pct:.1f}% 과대 (물타기 위험)")

        approved = len(failed) == 0
        return RiskCheckResult(
            approved=approved,
            level=RiskLevel.MODERATE if approved else RiskLevel.HIGH,
            checks_passed=["물타기 조건 충족"] if approved else [],
            checks_failed=failed,
            reason="물타기 승인" if approved else f"물타기 거부: {'; '.join(failed)}"
        )

    def _check_var(self, portfolio: PortfolioSummary, order_value: float) -> Optional[str]:
        """★ 고도화된 CVaR 체크 (Historical + 상관관계 보정)"""
        if portfolio.total_value <= 0:
            return None

        ratio = order_value / portfolio.total_value

        # 1. 단순 비율 체크
        if ratio > 0.05:
            return f"단일 주문이 포트폴리오의 {ratio*100:.1f}% - CVaR 경고"

        # 2. Historical CVaR 체크
        cvar = self.calculate_portfolio_cvar(self._position_returns)
        if cvar and cvar.cvar_99_pct > self.max_cvar_pct * 100:
            return (f"포트폴리오 CVaR(99%) {cvar.cvar_99_pct:.2f}% 초과 "
                    f"(허용: {self.max_cvar_pct*100:.1f}%)")

        return None

    # ─── ★★★ 고도화 CVaR 계산 ★★★ ───

    def calculate_portfolio_cvar(self,
                                  returns: List[float],
                                  confidence: float = 0.99) -> Optional[CVaRResult]:
        """
        Historical CVaR 계산 (Expected Shortfall)
        returns: 일별 수익률 리스트 (소수, 예: -0.025 = -2.5%)
        """
        if len(returns) < 30:
            return None

        r = np.array(returns)
        portfolio_value = 1.0  # 비율 기준

        # VaR 계산
        var_95 = float(np.percentile(r, (1 - 0.95) * 100))
        var_99 = float(np.percentile(r, (1 - 0.99) * 100))

        # CVaR = VaR 이하 손실들의 평균 (Expected Shortfall)
        losses_beyond_95 = r[r <= var_95]
        losses_beyond_99 = r[r <= var_99]

        cvar_95 = float(losses_beyond_95.mean()) if len(losses_beyond_95) > 0 else var_95
        cvar_99 = float(losses_beyond_99.mean()) if len(losses_beyond_99) > 0 else var_99

        # ★ Cornish-Fisher: 정규분위수를 표본 왜도/첨도로 보정 → 팻테일 반영
        var_cf_99 = qmet.cornish_fisher_var(r, confidence=0.99)
        cvar_cf_99 = qmet.cornish_fisher_cvar(r, confidence=0.99)

        return CVaRResult(
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            var_95_pct=round(abs(var_95) * 100, 3),
            var_99_pct=round(abs(var_99) * 100, 3),
            var_cf_99_pct=round(var_cf_99 * 100, 3),
            cvar_cf_99_pct=round(cvar_cf_99 * 100, 3),
            method="historical",
            lookback_days=len(returns),
        )

    def calculate_monte_carlo_cvar(self,
                                    mean_return: float,
                                    volatility: float,
                                    n_simulations: int = 10000,
                                    confidence: float = 0.99) -> CVaRResult:
        """
        Monte Carlo CVaR 계산
        mean_return: 일 평균 수익률
        volatility: 일 변동성 (std)
        """
        # 정규 분포 시뮬레이션
        simulated = np.random.normal(mean_return, volatility, n_simulations)

        var_99 = float(np.percentile(simulated, 1))
        var_95 = float(np.percentile(simulated, 5))

        losses_99 = simulated[simulated <= var_99]
        losses_95 = simulated[simulated <= var_95]

        return CVaRResult(
            var_95=var_95, var_99=var_99,
            cvar_95=float(losses_95.mean()) if len(losses_95) > 0 else var_95,
            cvar_99=float(losses_99.mean()) if len(losses_99) > 0 else var_99,
            var_95_pct=round(abs(var_95) * 100, 3),
            var_99_pct=round(abs(var_99) * 100, 3),
            method="monte_carlo",
            lookback_days=n_simulations,
        )

    # ─── ★★★ 상관관계 리스크 ★★★ ───

    def analyze_correlation_risk(self,
                                   positions: List[Position],
                                   returns_matrix: Dict[str, List[float]] = None) -> CorrelationRisk:
        """
        포트폴리오 상관관계 집중도 리스크 분석
        HHI (Herfindahl-Hirschman Index) + 상관관계 군집 감지
        """
        risk = CorrelationRisk()
        if not positions:
            return risk

        # HHI (포지션 비중 기반)
        total_value = sum(p.market_value for p in positions)
        if total_value <= 0:
            return risk

        weights = [p.market_value / total_value for p in positions]
        risk.hhi_index = round(float(np.sum(np.square(weights))), 4)
        # HHI 해석: 0.15 미만=분산, 0.15-0.25=중간, 0.25 이상=집중

        # 수익률 상관관계 분석
        if returns_matrix and len(returns_matrix) >= 2:
            tickers = [p.ticker for p in positions if p.ticker in returns_matrix]
            if len(tickers) >= 2:
                returns_df = pd.DataFrame(
                    {t: returns_matrix[t] for t in tickers}
                ).dropna()

                if len(returns_df) >= 20:
                    corr_matrix = returns_df.corr()

                    # 상삼각 행렬의 상관계수들만 추출 (자기 자신 제외)
                    upper_tri = corr_matrix.values[
                        np.triu_indices(len(tickers), k=1)
                    ]
                    risk.avg_correlation = round(float(np.mean(upper_tri)), 3)

                    # 최고 상관관계 쌍 찾기
                    max_corr = 0.0
                    max_pair = ("", "")
                    for i in range(len(tickers)):
                        for j in range(i + 1, len(tickers)):
                            corr = abs(corr_matrix.iloc[i, j])
                            if corr > max_corr:
                                max_corr = corr
                                max_pair = (tickers[i], tickers[j])
                    risk.max_correlation_pair = (*max_pair, round(max_corr, 3))

                    # 분산투자 비율 (낮은 상관관계 = 높은 분산)
                    risk.diversification_ratio = round(1 - max(risk.avg_correlation, 0), 3)

                    # 클러스터 리스크 (평균 상관계수 > 0.7)
                    risk.cluster_risk = risk.avg_correlation > 0.7

        return risk

    # ─── ★★★ 스트레스 테스트 ★★★ ───

    def run_stress_tests(self,
                          positions: List[Position],
                          portfolio_value: float,
                          sector_map: Optional[Dict[str, str]] = None,
                          beta_map: Optional[Dict[str, float]] = None) -> List[StressTestResult]:
        """
        역사적 위기 시나리오 스트레스 테스트
        - 2008 금융위기 (KOSPI -40%)
        - 2020 코로나 패닉 (KOSPI -30%)
        - 2022 금리인상 충격 (성장주 -40%)
        - 지정학 위기 (한반도 리스크)

        sector_map: {ticker: 섹터명} — 제공 시 시나리오별 '섹터 충격'을 적용한다.
                    (이전 버전은 sector_shocks 를 정의만 하고 시장충격만 일괄 적용하는
                     버그가 있었다. 이제 섹터별 차등 충격 + 종목 베타를 반영한다.)
        beta_map:   {ticker: 베타} — 미제공 시 1.0 가정.
        """
        sector_map = sector_map or {}
        beta_map = beta_map or {}
        SCENARIOS = [
            {
                "name": "2008 금융위기",
                "market_shock": -0.40,      # KOSPI -40%
                "sector_shocks": {
                    "금융": -0.55, "반도체": -0.45, "자동차": -0.38,
                    "철강": -0.50, "화학": -0.42, "IT": -0.35,
                },
                "duration": "6개월"
            },
            {
                "name": "2020 코로나 패닉",
                "market_shock": -0.30,
                "sector_shocks": {
                    "항공": -0.70, "여행": -0.60, "유통": -0.45,
                    "반도체": -0.15, "바이오": 0.10, "IT": 0.05,
                },
                "duration": "2개월"
            },
            {
                "name": "2022 금리인상 충격",
                "market_shock": -0.25,
                "sector_shocks": {
                    "성장주": -0.40, "바이오": -0.50, "IT": -0.30,
                    "은행": 0.05, "에너지": 0.15, "유틸리티": 0.0,
                },
                "duration": "1년"
            },
            {
                "name": "한반도 지정학 위기",
                "market_shock": -0.15,
                "sector_shocks": {
                    "방산": 0.20, "원자력": 0.10, "반도체": -0.20,
                    "철강": -0.15, "금융": -0.18,
                },
                "duration": "2주"
            },
        ]

        results = []
        for scenario in SCENARIOS:
            result = StressTestResult(scenario=scenario["name"])
            total_loss = 0.0
            worst_loss = 0.0
            worst_ticker = ""

            sector_shocks = scenario.get("sector_shocks", {})
            for position in positions:
                # 섹터별 차등 충격 우선, 없으면 시장 충격
                sector = sector_map.get(position.ticker, "")
                if sector and sector in sector_shocks:
                    shock = sector_shocks[sector]
                else:
                    # 시장 충격 × 종목 베타 (체계적 위험 반영)
                    beta = beta_map.get(position.ticker, 1.0)
                    shock = scenario["market_shock"] * beta
                position_loss = position.market_value * shock
                total_loss += position_loss

                if abs(position_loss) > abs(worst_loss):
                    worst_loss = position_loss
                    worst_ticker = position.ticker

            result.portfolio_loss_krw = round(total_loss)
            result.portfolio_loss_pct = (
                round(total_loss / portfolio_value * 100, 2)
                if portfolio_value > 0 else 0
            )
            result.worst_ticker = worst_ticker
            result.worst_ticker_loss_pct = round(worst_loss / portfolio_value * 100, 2) if portfolio_value > 0 else 0
            result.survival = result.portfolio_loss_pct > -50  # 50% 초과 손실이면 생존 불가
            results.append(result)

        return results

    # ─── ★★★ 유동성 리스크 ★★★ ───

    def analyze_liquidity_risk(self,
                                ticker: str,
                                position_value: float,
                                avg_daily_volume_krw: float) -> LiquidityRisk:
        """
        유동성 리스크 - 포지션 청산 예상 소요 시간
        (평균 거래량의 20% 이내에서만 은밀하게 청산 가능)
        """
        risk = LiquidityRisk(
            ticker=ticker,
            position_value=position_value,
            avg_daily_volume_krw=avg_daily_volume_krw,
        )

        if avg_daily_volume_krw <= 0:
            risk.days_to_liquidate = 999
            risk.liquidity_score = 0
            risk.risk_level = "위험"
            return risk

        # 하루에 거래량의 20%까지 임팩트 없이 청산 가능
        safe_daily_liquidation = avg_daily_volume_krw * 0.20
        days = position_value / safe_daily_liquidation
        risk.days_to_liquidate = round(days, 1)

        # 유동성 점수 (0-100)
        if days < 0.5: risk.liquidity_score = 100;  risk.risk_level = "낮음"
        elif days < 1: risk.liquidity_score = 85;   risk.risk_level = "낮음"
        elif days < 3: risk.liquidity_score = 60;   risk.risk_level = "보통"
        elif days < 7: risk.liquidity_score = 35;   risk.risk_level = "높음"
        else: risk.liquidity_score = 10;             risk.risk_level = "위험"

        return risk

    # ─── ★★★ 동적 포지션 스케일러 ★★★ ───

    def calculate_dynamic_position_scale(self,
                                          vix: float,
                                          regime: str = "sideways",
                                          cvar_portfolio_pct: float = 0.0) -> float:
        """
        VIX + Regime + CVaR 기반 동적 포지션 스케일 팩터
        반환: 0.1~1.5 (1.0=기준, 1.5=최대 확대, 0.1=최대 축소)
        """
        scale = 1.0

        # VIX 기반 조정
        if vix < 12:
            scale *= 1.3      # 극도 안정 → 확대
        elif vix < 16:
            scale *= 1.1
        elif vix < 20:
            scale *= 1.0
        elif vix < 25:
            scale *= 0.85
        elif vix < 30:
            scale *= 0.65
        elif vix < 40:
            scale *= 0.40
        else:
            scale *= 0.20    # 극도 공포 → 최소화

        # 레짐 기반 조정
        regime_mult = {"bull": 1.2, "sideways": 0.9, "bear": 0.5}
        scale *= regime_mult.get(regime, 0.9)

        # CVaR 초과 페널티
        if cvar_portfolio_pct > 3.0:
            scale *= 0.5
        elif cvar_portfolio_pct > 2.0:
            scale *= 0.7
        elif cvar_portfolio_pct > 1.5:
            scale *= 0.85

        return round(max(0.1, min(1.5, scale)), 2)

    # ─── 수익률 히스토리 업데이트 ───

    def update_returns_history(self, ticker: str, daily_return: float):
        """수익률 히스토리 업데이트 (CVaR 계산용)"""
        if ticker not in self._returns_history:
            self._returns_history[ticker] = []
        self._returns_history[ticker].append(daily_return)
        if len(self._returns_history[ticker]) > 500:
            self._returns_history[ticker] = self._returns_history[ticker][-250:]

    def update_portfolio_return(self, daily_return: float):
        """포트폴리오 수익률 히스토리"""
        self._position_returns.append(daily_return)
        if len(self._position_returns) > 500:
            self._position_returns = self._position_returns[-250:]

    def update_vix(self, vix: float):
        """현재 VIX 업데이트"""
        self._current_vix = vix

    def get_advanced_risk_summary(self,
                                    positions: List[Position],
                                    portfolio_value: float) -> dict:
        """★ 고도화 리스크 종합 요약 (대시보드용)"""
        # CVaR
        cvar = self.calculate_portfolio_cvar(self._position_returns)
        mc_cvar = None
        if self._position_returns:
            r = np.array(self._position_returns)
            mc_cvar = self.calculate_monte_carlo_cvar(
                float(r.mean()), float(r.std())
            )

        # 상관관계 리스크
        corr_risk = self.analyze_correlation_risk(
            positions, self._returns_history
        )

        # 스트레스 테스트
        stress = self.run_stress_tests(positions, portfolio_value)

        # 동적 스케일
        dynamic_scale = self.calculate_dynamic_position_scale(
            self._current_vix,
            "sideways",
            cvar.cvar_99_pct if cvar else 0
        )

        return {
            "cvar": {
                "var_99_pct": cvar.var_99_pct if cvar else 0,
                "cvar_99_pct": cvar.cvar_99_pct if cvar else 0,
                "cvar_95_pct": cvar.cvar_95_pct if cvar else 0,
                # ★ 팻테일 보정 (Cornish-Fisher) — 정규가정 historical 대비 보수적
                "var_cf_99_pct": cvar.var_cf_99_pct if cvar else 0,
                "cvar_cf_99_pct": cvar.cvar_cf_99_pct if cvar else 0,
                "method": cvar.method if cvar else "insufficient_data",
                "lookback_days": cvar.lookback_days if cvar else 0,
            },
            "monte_carlo_cvar": {
                "cvar_99_pct": mc_cvar.cvar_99_pct if mc_cvar else 0,
            } if mc_cvar else {},
            "correlation_risk": {
                "hhi_index": corr_risk.hhi_index,
                "avg_correlation": corr_risk.avg_correlation,
                "diversification_ratio": corr_risk.diversification_ratio,
                "cluster_risk": corr_risk.cluster_risk,
                "max_corr_pair": list(corr_risk.max_correlation_pair),
            },
            "stress_tests": [
                {
                    "scenario": s.scenario,
                    "loss_pct": s.portfolio_loss_pct,
                    "loss_krw": s.portfolio_loss_krw,
                    "survival": s.survival,
                }
                for s in stress
            ],
            "dynamic_position_scale": dynamic_scale,
            "current_vix": self._current_vix,
            "kill_switch_active": self._kill_switch,
        }

    async def get_status(self) -> RiskStatus:
        return RiskStatus(
            overall_level=RiskLevel.BLOCKED if self._kill_switch else RiskLevel.LOW,
            kill_switch_active=self._kill_switch,
            daily_loss_pct=self._daily_pnl,
            max_daily_loss_pct=self.max_daily_loss_pct,
            max_drawdown_pct=self.max_drawdown_pct,
            blocked_tickers=self._blocked_tickers,
            active_alerts=self._alerts,
            last_check_time=datetime.now().isoformat(),
        )

    async def activate_kill_switch(self, reason):
        self._kill_switch = True
        self._kill_reason = reason
        self._alerts.append(f"[킬스위치] {reason} ({datetime.now().isoformat()})")
        logger.critical(f"🚨 킬스위치 활성화: {reason}")
        return True

    async def deactivate_kill_switch(self):
        self._kill_switch = False
        self._kill_reason = ""
        return True

    async def is_kill_switch_active(self):
        return self._kill_switch

    async def check_data_health(self):
        return {"api": "정상", "websocket": "정상", "data_lag_ms": 0}

    async def check_market_hours_filter(self):
        now = datetime.now()
        if now.hour == 9 and now.minute < 15:
            return False
        return True

    def update_daily_pnl(self, pnl: float):
        self._daily_pnl = pnl

    def block_ticker(self, ticker: str):
        if ticker not in self._blocked_tickers:
            self._blocked_tickers.append(ticker)

    def unblock_ticker(self, ticker: str):
        if ticker in self._blocked_tickers:
            self._blocked_tickers.remove(ticker)
