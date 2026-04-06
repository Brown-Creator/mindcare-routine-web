"""
실시간 투자자별 수급 분석 엔진
- 외국인/기관/개인 순매수 추이
- 프로그램 매매 분석
- 신용잔고 추적
- 공매도 잔고 모니터링
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class InvestorFlow:
    ticker: str
    date: str
    foreign_net: int = 0       # 외국인 순매수 (주)
    institutional_net: int = 0  # 기관 순매수
    retail_net: int = 0         # 개인 순매수
    program_net: int = 0        # 프로그램 순매수
    foreign_holding_pct: float = 0  # 외국인 보유비율
    short_ratio: float = 0     # 공매도 잔고비율
    margin_ratio: float = 0    # 신용잔고율

@dataclass
class FlowAnalysis:
    score: float = 50           # 0-100 수급점수
    trend: str = "중립"         # 강세/약세/중립
    foreign_trend: str = "중립"
    institutional_trend: str = "중립"
    smart_money_signal: str = "없음"  # 스마트머니 신호
    factors: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)

class SupplyDemandAnalyzer:
    """투자자별 수급 분석 엔진"""

    def __init__(self, kiwoom_broker=None):
        self.broker = kiwoom_broker
        self._flow_history: Dict[str, List[InvestorFlow]] = {}
        self._market_flow: Dict[str, InvestorFlow] = {}

    async def fetch_investor_flow(self, ticker: str, days: int = 20) -> List[InvestorFlow]:
        """키움 API를 통해 투자자별 매매동향 수집"""
        try:
            if self.broker:
                # 키움 OPT10059 (투자자별 매매동향) 호출
                data = await self.broker._request(
                    "POST", "/api/dostk/invst", "ka10010",
                    data={"stk_cd": ticker, "cnt": str(days)}
                )
                flows = []
                for item in data.get("list", []):
                    flows.append(InvestorFlow(
                        ticker=ticker,
                        date=item.get("date", ""),
                        foreign_net=int(item.get("frgn_net", 0)),
                        institutional_net=int(item.get("inst_net", 0)),
                        retail_net=int(item.get("indv_net", 0)),
                        program_net=int(item.get("prgm_net", 0)),
                        foreign_holding_pct=float(item.get("frgn_hold_rt", 0)),
                    ))
                self._flow_history[ticker] = flows
                return flows
        except Exception as e:
            logger.warning(f"수급 데이터 수집 실패 [{ticker}]: {e}")

        return self._flow_history.get(ticker, [])

    def analyze(self, ticker: str, flows: List[InvestorFlow] = None) -> FlowAnalysis:
        """종합 수급 분석"""
        flows = flows or self._flow_history.get(ticker, [])
        if not flows:
            return FlowAnalysis(score=50, factors=["수급 데이터 없음"])

        analysis = FlowAnalysis()
        score = 50
        factors = []
        risk_flags = []

        # ─── 1. 외국인 순매수 추이 (5일/20일) ───
        recent_5 = flows[:5] if len(flows) >= 5 else flows
        recent_20 = flows[:20] if len(flows) >= 20 else flows

        foreign_5d = sum(f.foreign_net for f in recent_5)
        foreign_20d = sum(f.foreign_net for f in recent_20)

        if foreign_5d > 0 and foreign_20d > 0:
            score += 20
            analysis.foreign_trend = "강한매수"
            factors.append(f"외국인 5일/20일 연속 순매수 ({foreign_5d:,}주)")
        elif foreign_5d > 0:
            score += 10
            analysis.foreign_trend = "단기매수"
            factors.append("외국인 단기 순매수 전환")
        elif foreign_5d < 0 and foreign_20d < 0:
            score -= 15
            analysis.foreign_trend = "강한매도"
            factors.append(f"외국인 지속 순매도 ({foreign_5d:,}주)")
            risk_flags.append("외국인 이탈")

        # ─── 2. 기관 순매수 추이 ───
        inst_5d = sum(f.institutional_net for f in recent_5)
        inst_20d = sum(f.institutional_net for f in recent_20)

        if inst_5d > 0 and inst_20d > 0:
            score += 15
            analysis.institutional_trend = "강한매수"
            factors.append(f"기관 연속 순매수 ({inst_5d:,}주)")
        elif inst_5d < 0 and inst_20d < 0:
            score -= 10
            analysis.institutional_trend = "강한매도"

        # ─── 3. 스마트머니 시그널 (외인+기관 동시 매수) ───
        if foreign_5d > 0 and inst_5d > 0:
            score += 15
            analysis.smart_money_signal = "쌍끌이 매수"
            factors.append("🔥 외국인+기관 쌍끌이 매수 (스마트머니 유입)")

        if foreign_5d < 0 and inst_5d < 0:
            score -= 20
            analysis.smart_money_signal = "쌍끌이 매도"
            risk_flags.append("⚠️ 외국인+기관 동시 이탈")

        # ─── 4. 프로그램 매매 ───
        prog_5d = sum(f.program_net for f in recent_5)
        if prog_5d > 0:
            score += 5
            factors.append("프로그램 순매수")
        elif prog_5d < -10000:
            score -= 10
            risk_flags.append("프로그램 대량 매도")

        # ─── 5. 공매도/신용잔고 위험 ───
        if recent_5 and recent_5[0].short_ratio > 5:
            score -= 10
            risk_flags.append(f"공매도 잔고비율 높음 ({recent_5[0].short_ratio:.1f}%)")

        if recent_5 and recent_5[0].margin_ratio > 3:
            risk_flags.append(f"신용잔고율 높음 ({recent_5[0].margin_ratio:.1f}%) - 반대매매 위험")
            score -= 5

        # ─── 6. 외국인 보유비율 변화 ───
        if len(flows) >= 20:
            frgn_now = flows[0].foreign_holding_pct
            frgn_before = flows[-1].foreign_holding_pct
            change = frgn_now - frgn_before
            if change > 1.0:
                score += 10
                factors.append(f"외국인 보유비율 {change:+.1f}%p 증가")
            elif change < -2.0:
                score -= 10
                risk_flags.append(f"외국인 보유비율 {change:+.1f}%p 급감")

        # 스코어 클램프
        analysis.score = max(0, min(100, score))
        analysis.factors = factors
        analysis.risk_flags = risk_flags
        analysis.trend = "강세" if score >= 65 else ("약세" if score <= 35 else "중립")

        return analysis

    async def get_market_wide_flow(self) -> dict:
        """시장 전체 수급 개요"""
        return {
            "foreign_net_buy": 0,
            "institutional_net_buy": 0,
            "program_net_buy": 0,
            "market_trend": "데이터 수집중",
        }
