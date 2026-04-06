"""
KRX AutoTrader 데이터 모델 - 주문
"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


class OrderSide(str, Enum):
    BUY = "매수"
    SELL = "매도"


class OrderType(str, Enum):
    MARKET = "시장가"
    LIMIT = "지정가"


class OrderStatus(str, Enum):
    PENDING = "대기"
    SUBMITTED = "접수"
    PARTIAL = "부분체결"
    FILLED = "체결"
    CANCELLED = "취소"
    REJECTED = "거부"
    FAILED = "실패"


class OrderReason(str, Enum):
    NEW_ENTRY = "신규진입"
    AVG_DOWN_1 = "1차 물타기"
    AVG_DOWN_2 = "2차 물타기"
    EXIT_1 = "1차 분할매도"
    EXIT_2 = "2차 분할매도"
    TRAILING_STOP = "트레일링 스탑"
    HARD_STOP = "손절"
    RISK_CUTOFF = "리스크 강제청산"
    KILL_SWITCH = "킬스위치 청산"
    MANUAL = "수동주문"


class Order(BaseModel):
    order_id: str = ""
    ticker: str
    name: str = ""
    side: OrderSide
    order_type: OrderType = OrderType.LIMIT
    price: float
    quantity: int
    filled_quantity: int = 0
    avg_filled_price: float = 0
    status: OrderStatus = OrderStatus.PENDING
    reason: OrderReason = OrderReason.MANUAL
    strategy_version: str = ""
    risk_approved: bool = False
    risk_rejection_reason: str = ""
    broker_order_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    filled_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
