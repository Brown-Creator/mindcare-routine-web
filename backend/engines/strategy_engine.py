"""
전략 엔진 인터페이스
데이터 엔진의 출력을 받아 종목별 점수를 계산하고 상태를 분류한다.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from backend.models.stock import StockSignal, StockState, StockInfo, OHLCV


class BaseStrategyEngine(ABC):
    """전략 엔진 추상 인터페이스"""

    @abstractmethod
    async def evaluate(self, ticker: str, stock_info: StockInfo,
                       price_history: List[OHLCV], indicators: dict,
                       market_context: dict) -> StockSignal:
        """
        종목 종합 평가 → StockSignal 반환
        
        Args:
            ticker: 종목코드
            stock_info: 종목 기본정보
            price_history: OHLCV 히스토리
            indicators: 기술적 지표 (MA, RSI, MACD, BB, ATR 등)
            market_context: 시장 전체 맥락 (코스피 지수, 업종 강도, 수급, 뉴스 등)
        
        Returns:
            StockSignal: 종합 점수 + 상태 분류 + 매매 계획
        """
        pass

    @abstractmethod
    async def calculate_bottom_score(self, ticker: str, price_history: List[OHLCV],
                                     indicators: dict) -> float:
        """
        저점 확률 점수 계산 (0~100)
        
        판단 요소:
        - 최근 N일 최저가 대비 거리
        - 20/60/120일 이동평균 괴리율
        - RSI 과매도 여부
        - 거래량 감소 후 바닥 형성 여부
        - 급락 후 하락속도 둔화 여부
        - 지지선 근접 여부
        """
        pass

    @abstractmethod
    async def calculate_trend_score(self, price_history: List[OHLCV],
                                    indicators: dict) -> float:
        """추세 점수 (0~100) - 상승추세일수록 높음"""
        pass

    @abstractmethod
    async def calculate_momentum_score(self, price_history: List[OHLCV],
                                       indicators: dict) -> float:
        """반등 모멘텀 점수 (0~100)"""
        pass

    @abstractmethod
    async def calculate_supply_demand_score(self, ticker: str,
                                            market_context: dict) -> float:
        """수급 점수 (0~100) - 외국인/기관 매수세"""
        pass

    @abstractmethod
    async def calculate_event_risk_score(self, ticker: str,
                                         market_context: dict) -> float:
        """이벤트 리스크 점수 (0~100) - 높을수록 위험"""
        pass

    @abstractmethod
    async def calculate_market_risk_score(self, market_context: dict) -> float:
        """시장 전체 위험도 (0~100) - 높을수록 위험"""
        pass

    @abstractmethod
    async def classify_state(self, signal: StockSignal,
                             current_position: Optional[dict]) -> StockState:
        """
        종합 점수 기반 상태 분류
        
        상태:
        - 관찰: 진입 조건 미충족
        - 신규진입 후보: 저점 점수 충족 + 리스크 낮음
        - 1차 물타기 후보: 보유 중 + 추가 하락 + 바닥 확인
        - 2차 물타기 후보: 1차 물타기 후 + 추세 개선 확인
        - 보유: 진입 후 대기
        - 1차 분할매도: 평균단가 회복 또는 단기 저항선
        - 2차 분할매도: 중기 저항선
        - 전량매도: 트레일링 스탑 또는 강제청산
        - 매매금지: 리스크 초과
        """
        pass

    @abstractmethod
    async def generate_trade_plan(self, signal: StockSignal,
                                  stock_info: StockInfo) -> StockSignal:
        """
        매매 계획 생성 (진입가, 물타기가, 매도가, 스탑)
        """
        pass


class MockStrategyEngine(BaseStrategyEngine):
    """Mock 전략 엔진 - Mock 데이터 기반"""

    async def evaluate(self, ticker, stock_info, price_history, indicators, market_context):
        import pandas as pd
        from backend.strategies import evaluate_all_strategies
        from backend.models.stock import StockState
        
        df = pd.DataFrame(price_history)
        if not df.empty:
            df = df.sort_values(by='date').reset_index(drop=True)
            from backend.indicators import calculate_all_indicators
            df = calculate_all_indicators(df)
            
        evaluation = evaluate_all_strategies(df, market_context)
        
        score_bottom = int(evaluation['bottom_probability_score'])
        score_trend = int(evaluation['trend_score'])
        score_momentum = int(evaluation['momentum_score'])
        score_supply = int(evaluation['supply_demand_score'])
        
        state = StockState.WATCH
        if score_bottom > 50 and score_trend > 40:
            state = StockState.NEW_ENTRY_CANDIDATE
        if score_bottom > 65 and score_trend < 40 and score_momentum > 40:
            state = StockState.AVG_DOWN_1_CANDIDATE
            
        return StockSignal(
            ticker=ticker,
            name=stock_info.name if stock_info else ticker,
            state=state,
            confidence=int((score_bottom + score_trend + score_momentum) / 3),
            bottom_probability_score=score_bottom,
            trend_score=score_trend,
            momentum_score=score_momentum,
            supply_demand_score=score_supply,
            event_risk_score=30,
            market_risk_score=35,
            risk_score=30,
            reason=evaluation.get('reasons', []),
            risk_flags=[]
        )

    async def calculate_bottom_score(self, ticker, price_history, indicators):
        from backend.mock_data import MOCK_SIGNALS
        sig = MOCK_SIGNALS.get(ticker)
        return sig.bottom_probability_score if sig else 0

    async def calculate_trend_score(self, price_history, indicators):
        return 50.0

    async def calculate_momentum_score(self, price_history, indicators):
        return 50.0

    async def calculate_supply_demand_score(self, ticker, market_context):
        return 50.0

    async def calculate_event_risk_score(self, ticker, market_context):
        return 30.0

    async def calculate_market_risk_score(self, market_context):
        return 35.0

    async def classify_state(self, signal, current_position):
        return signal.state

    async def generate_trade_plan(self, signal, stock_info):
        return signal
