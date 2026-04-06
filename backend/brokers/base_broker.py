"""
브로커 추상 인터페이스
키움 전용으로 먼저 구현하되, 추후 다른 증권사로 확장 가능한 구조.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from enum import Enum


class BrokerMode(str, Enum):
    MOCK = "mock"
    PAPER = "paper"       # 모의투자
    LIVE = "live"         # 실전투자


class BaseBroker(ABC):
    """브로커 추상 인터페이스"""

    def __init__(self, mode: BrokerMode = BrokerMode.MOCK):
        self.mode = mode
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """브로커 연결 (인증 토큰 발급 등)"""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """연결 해제"""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """연결 상태 확인"""
        pass

    # ─── 시세 조회 ───
    @abstractmethod
    async def get_stock_price(self, ticker: str) -> dict:
        """주식 현재가 조회"""
        pass

    @abstractmethod
    async def get_stock_history(self, ticker: str, period: str = "D",
                                count: int = 120) -> List[dict]:
        """주식 일/주/월/시/분 조회"""
        pass

    @abstractmethod
    async def get_orderbook(self, ticker: str) -> dict:
        """호가 조회"""
        pass

    # ─── 주문 ───
    @abstractmethod
    async def place_buy_order(self, ticker: str, price: float,
                              quantity: int, order_type: str = "limit") -> dict:
        """매수 주문"""
        pass

    @abstractmethod
    async def place_sell_order(self, ticker: str, price: float,
                               quantity: int, order_type: str = "limit") -> dict:
        """매도 주문"""
        pass

    @abstractmethod
    async def modify_order(self, order_id: str, price: float,
                           quantity: int) -> dict:
        """주문 정정"""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> dict:
        """주문 취소"""
        pass

    # ─── 계좌 ───
    @abstractmethod
    async def get_account_balance(self) -> dict:
        """계좌 잔고 조회"""
        pass

    @abstractmethod
    async def get_positions(self) -> List[dict]:
        """보유 종목 조회"""
        pass

    @abstractmethod
    async def get_order_history(self, date: Optional[str] = None) -> List[dict]:
        """체결 내역 조회"""
        pass

    # ─── 상태 ───
    @abstractmethod
    async def get_api_health(self) -> dict:
        """API 상태 확인"""
        pass

    def _ensure_not_live_without_confirmation(self):
        """실전 모드 안전장치"""
        if self.mode == BrokerMode.LIVE:
            raise RuntimeError(
                "실전 모드 주문은 명시적 승인 없이 실행할 수 없습니다. "
                "config에서 live_trading_confirmed=True를 설정하세요."
            )
