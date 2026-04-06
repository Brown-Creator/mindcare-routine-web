"""
리스크 엔진 인터페이스
모든 주문은 반드시 리스크 엔진을 통과해야 한다.
리스크 엔진이 거부하면 어떤 경우에도 주문하지 않는다.
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from backend.models.stock import StockSignal, Position, PortfolioSummary
from backend.models.order import Order
from backend.models.risk import RiskCheckResult, RiskStatus, RiskLevel


class BaseRiskEngine(ABC):
    """리스크 엔진 추상 인터페이스"""

    @abstractmethod
    async def check_order(self, order: Order, signal: StockSignal,
                          portfolio: PortfolioSummary,
                          positions: List[Position]) -> RiskCheckResult:
        """
        주문 리스크 검사 - 통과하지 못하면 주문 불가
        
        검사 항목:
        1. 일일 최대 손실 제한
        2. 종목별 최대 비중 제한
        3. 계좌 전체 최대 드로다운 제한
        4. 주문당 최대 손실 허용치
        5. 슬리피지 한도
        6. 장 시작 직후 과열 구간 필터
        7. 물타기 횟수 제한 (최대 2회)
        8. 하락 추세 중 물타기 금지
        9. 악재 이벤트 지속 시 추가매수 금지
        10. API 오류, 데이터 누락 시 주문 중단
        11. 중복 주문 감지
        12. 킬스위치 상태 확인
        """
        pass

    @abstractmethod
    async def check_avg_down_allowed(self, ticker: str, signal: StockSignal,
                                     position: Position) -> RiskCheckResult:
        """
        물타기 허용 여부 전용 검사
        
        조건:
        - 종목당 최대 2회까지만 허용
        - 단순 하락 추세에서는 금지
        - 1차: 소액
        - 2차: 추세 개선 확인 시에만
        - 바닥확률, 거래량, 지지구간, 시장위험 점수 모두 기준 이상
        - 악재 이벤트 지속, 시장 급락, 추세 붕괴 시 금지
        """
        pass

    @abstractmethod
    async def get_status(self) -> RiskStatus:
        """현재 리스크 상태 조회"""
        pass

    @abstractmethod
    async def activate_kill_switch(self, reason: str) -> bool:
        """킬스위치 활성화 → 모든 자동주문 즉시 중단"""
        pass

    @abstractmethod
    async def deactivate_kill_switch(self) -> bool:
        """킬스위치 해제"""
        pass

    @abstractmethod
    async def is_kill_switch_active(self) -> bool:
        """킬스위치 상태 확인"""
        pass

    @abstractmethod
    async def check_data_health(self) -> dict:
        """
        데이터 건전성 검사
        - API 연결 상태
        - WebSocket 연결 상태
        - 데이터 지연/누락 여부
        """
        pass

    @abstractmethod
    async def check_market_hours_filter(self) -> bool:
        """장 시작 직후 과열 구간 필터"""
        pass


class MockRiskEngine(BaseRiskEngine):
    """Mock 리스크 엔진"""
    
    def __init__(self):
        self._kill_switch = False

    async def check_order(self, order, signal, portfolio, positions):
        if self._kill_switch:
            return RiskCheckResult(
                approved=False,
                level=RiskLevel.BLOCKED,
                checks_failed=["킬스위치 활성화됨"],
                reason="킬스위치가 활성화되어 모든 주문이 차단됩니다."
            )
        
        checks_passed = [
            "일일 손실 제한 통과",
            "종목 비중 제한 통과",
            "드로다운 제한 통과",
            "중복 주문 없음",
        ]
        
        # Mock: 매매금지 종목이면 거부
        if signal.state.value == "매매금지":
            return RiskCheckResult(
                approved=False,
                level=RiskLevel.BLOCKED,
                checks_passed=checks_passed[:2],
                checks_failed=["매매금지 종목"],
                reason="리스크 엔진이 해당 종목의 매매를 차단했습니다."
            )
        
        return RiskCheckResult(
            approved=True,
            level=RiskLevel.LOW,
            checks_passed=checks_passed,
            checks_failed=[],
            reason="모든 리스크 검사 통과",
            daily_loss_pct=0.05,
            position_weight_pct=2.5,
            drawdown_pct=1.8,
            order_risk_pct=0.8,
        )

    async def check_avg_down_allowed(self, ticker, signal, position):
        if position.avg_down_count >= 2:
            return RiskCheckResult(
                approved=False,
                level=RiskLevel.HIGH,
                checks_failed=["물타기 횟수 초과 (최대 2회)"],
                reason="해당 종목은 이미 최대 물타기 횟수에 도달했습니다."
            )
        
        if signal.trend_score < 40:
            return RiskCheckResult(
                approved=False,
                level=RiskLevel.HIGH,
                checks_failed=["하락 추세 중 물타기 금지"],
                reason="추세 점수가 기준 미달입니다. 추세 개선 후 재검토하세요."
            )
        
        return RiskCheckResult(
            approved=True,
            level=RiskLevel.MODERATE,
            checks_passed=["물타기 횟수 확인", "추세 점수 확인", "바닥확률 확인"],
            reason="물타기 조건 충족"
        )

    async def get_status(self):
        from backend.mock_data import MOCK_RISK_STATUS
        status = MOCK_RISK_STATUS.model_copy()
        status.kill_switch_active = self._kill_switch
        return status

    async def activate_kill_switch(self, reason):
        self._kill_switch = True
        return True

    async def deactivate_kill_switch(self):
        self._kill_switch = False
        return True

    async def is_kill_switch_active(self):
        return self._kill_switch

    async def check_data_health(self):
        return {"api": "정상", "websocket": "정상", "data_lag_ms": 120}

    async def check_market_hours_filter(self):
        return True
