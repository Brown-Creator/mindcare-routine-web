"""
주문 엔진 인터페이스
브로커 어댑터를 통해 실제 주문을 실행한다.
반드시 리스크 엔진 승인 후에만 주문을 실행한다.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from backend.models.order import Order, OrderStatus
from backend.models.stock import StockSignal
from backend.models.risk import RiskCheckResult


class BaseOrderEngine(ABC):
    """주문 엔진 추상 인터페이스"""

    @abstractmethod
    async def submit_order(self, order: Order, risk_result: RiskCheckResult) -> Order:
        """
        주문 제출
        - 리스크 승인 확인 후 브로커에 전달
        - risk_result.approved가 False이면 거부
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """주문 취소"""
        pass

    @abstractmethod
    async def modify_order(self, order_id: str, new_price: float,
                           new_quantity: int) -> Order:
        """주문 정정"""
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> Order:
        """주문 상태 조회"""
        pass

    @abstractmethod
    async def get_pending_orders(self) -> List[Order]:
        """미체결 주문 목록"""
        pass

    @abstractmethod
    async def get_order_history(self, limit: int = 50) -> List[Order]:
        """주문 히스토리"""
        pass

    @abstractmethod
    async def check_duplicate(self, order: Order) -> bool:
        """중복 주문 검사"""
        pass

    @abstractmethod
    async def cancel_all_orders(self, reason: str) -> int:
        """
        전체 주문 취소 (킬스위치 또는 긴급 상황)
        Returns: 취소된 주문 수
        """
        pass


class MockOrderEngine(BaseOrderEngine):
    """Mock 주문 엔진"""

    def __init__(self):
        self._orders: List[dict] = []
        self._order_counter = 0

    async def submit_order(self, order, risk_result):
        if not risk_result.approved:
            order.status = OrderStatus.REJECTED
            order.risk_rejection_reason = risk_result.reason
            return order
        
        self._order_counter += 1
        order.order_id = f"MOCK-{self._order_counter:06d}"
        order.status = OrderStatus.SUBMITTED
        order.risk_approved = True
        self._orders.append(order.model_dump())
        return order

    async def cancel_order(self, order_id):
        return True

    async def modify_order(self, order_id, new_price, new_quantity):
        return Order(ticker="", side="매수", price=new_price, quantity=new_quantity)

    async def get_order_status(self, order_id):
        for o in self._orders:
            if o.get("order_id") == order_id:
                return Order(**o)
        return None

    async def get_pending_orders(self):
        return [Order(**o) for o in self._orders if o.get("status") == "대기"]

    async def get_order_history(self, limit=50):
        from backend.mock_data import MOCK_ORDERS
        return MOCK_ORDERS[:limit]

    async def check_duplicate(self, order):
        return False

    async def cancel_all_orders(self, reason):
        count = len([o for o in self._orders if o.get("status") in ("대기", "접수")])
        return count
