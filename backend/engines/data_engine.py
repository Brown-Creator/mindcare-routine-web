"""
데이터 엔진 인터페이스
시장 데이터 수집, 가공, 기술적 지표 계산
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from backend.models.stock import StockInfo, OHLCV


class BaseDataEngine(ABC):
    """데이터 엔진 추상 인터페이스"""

    @abstractmethod
    async def get_stock_info(self, ticker: str) -> StockInfo:
        """종목 기본 정보 조회"""
        pass

    @abstractmethod
    async def get_price_history(self, ticker: str, days: int = 120) -> List[OHLCV]:
        """분봉/일봉 OHLCV 조회"""
        pass

    @abstractmethod
    async def get_current_price(self, ticker: str) -> float:
        """실시간 현재가"""
        pass

    @abstractmethod
    async def get_orderbook(self, ticker: str) -> dict:
        """호가 조회"""
        pass

    @abstractmethod
    async def get_indicators(self, ticker: str) -> dict:
        """
        기술적 지표 계산/조회
        - MA(5/20/60/120)
        - RSI(14)
        - MACD
        - 볼린저밴드
        - ATR
        - 거래량 비율
        - 변동성 급등 여부
        """
        pass

    @abstractmethod
    async def get_market_context(self) -> dict:
        """
        시장 전체 맥락
        - 코스피/코스닥 지수
        - 업종별 강도
        - 외국인/기관 수급
        - 금리/환율
        - 시장 스트레스 점수
        """
        pass

    @abstractmethod
    async def get_sector_strength(self, sector: str) -> float:
        """업종 강도 (0~100)"""
        pass

    @abstractmethod
    async def get_supply_demand(self, ticker: str) -> dict:
        """외국인/기관 수급 데이터"""
        pass


class MockDataEngine(BaseDataEngine):
    """Mock 데이터 엔진"""

    async def get_stock_info(self, ticker):
        from backend.mock_data import MOCK_STOCKS
        return MOCK_STOCKS.get(ticker, StockInfo(ticker=ticker, name="Unknown"))

    async def get_price_history(self, ticker, days=120):
        from backend.mock_data import generate_price_history
        return generate_price_history(ticker)

    async def get_current_price(self, ticker):
        from backend.mock_data import MOCK_STOCKS
        stock = MOCK_STOCKS.get(ticker)
        return stock.current_price if stock else 0

    async def get_orderbook(self, ticker):
        from backend.mock_data import MOCK_STOCKS
        stock = MOCK_STOCKS.get(ticker)
        if not stock:
            return {}
        p = stock.current_price
        return {
            "asks": [{"price": p + i * 100, "volume": 500 - i * 30} for i in range(5)],
            "bids": [{"price": p - i * 100, "volume": 450 - i * 25} for i in range(5)],
        }

    async def get_indicators(self, ticker):
        import pandas as pd
        from backend.indicators import calculate_all_indicators
        
        history = await self.get_price_history(ticker, days=120)
        if not history:
            return {}
            
        df = pd.DataFrame(history)
        df = df.sort_values(by='date').reset_index(drop=True)
        
        # 기술적 지표 계산
        df_ind = calculate_all_indicators(df)
        latest = df_ind.iloc[-1]
        
        return {
            "ma5": float(latest.get('MA5', 0)),
            "ma20": float(latest.get('MA20', 0)),
            "ma60": float(latest.get('MA60', 0)),
            "ma120": float(latest.get('MA120', 0)),
            "rsi14": float(latest.get('RSI', 0)),
            "macd": float(latest.get('MACD', 0)),
            "macd_signal": float(latest.get('MACD_Signal', 0)),
            "macd_histogram": float(latest.get('MACD_Hist', 0)),
            "bb_upper": float(latest.get('BB_Upper', 0)),
            "bb_middle": float(latest.get('BB_Middle', 0)),
            "bb_lower": float(latest.get('BB_Lower', 0)),
            "atr14": float(latest.get('ATR', 0)),
            "volume_ratio": float(latest.get('Volume_Ratio', 0)),
            "gap_pct": float(latest.get('Gap_Pct', 0)),
            "volatility_surge": bool(latest.get('Volatility_Pct', 0) > 5.0),
        }

    async def get_market_context(self):
        return {
            "kospi": {"index": 2580.5, "change_pct": -0.8},
            "kosdaq": {"index": 725.3, "change_pct": -1.2},
            "usd_krw": 1385.5,
            "market_stress_score": 35,
            "sector_strength": {
                "반도체": 62, "철강": 38, "인터넷": 45, "화학": 30, "자동차": 55,
            },
            "foreign_flow": {"net_buy": -125000000000},
            "institutional_flow": {"net_buy": 85000000000},
        }

    async def get_sector_strength(self, sector):
        sectors = {"반도체": 62, "철강": 38, "인터넷": 45, "화학": 30}
        return sectors.get(sector, 50)

    async def get_supply_demand(self, ticker):
        supply_data = {
            "005490": {"foreign_net": 15000, "institutional_net": -5000, "trend": "외국인 순매수 전환"},
            "005930": {"foreign_net": -85000, "institutional_net": 42000, "trend": "혼조"},
            "000660": {"foreign_net": 32000, "institutional_net": 28000, "trend": "쌍방 순매수"},
            "035420": {"foreign_net": 8000, "institutional_net": -12000, "trend": "혼조"},
            "051910": {"foreign_net": -25000, "institutional_net": -18000, "trend": "쌍방 순매도"},
        }
        return supply_data.get(ticker, {})
