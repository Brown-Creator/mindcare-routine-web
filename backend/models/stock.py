"""
KRX AutoTrader 데이터 모델 - 종목 정보
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class StockState(str, Enum):
    WATCH = "관찰"
    NEW_ENTRY_CANDIDATE = "신규진입 후보"
    AVG_DOWN_1_CANDIDATE = "1차 물타기 후보"
    AVG_DOWN_2_CANDIDATE = "2차 물타기 후보"
    HOLDING = "보유"
    PARTIAL_EXIT_1 = "1차 분할매도"
    PARTIAL_EXIT_2 = "2차 분할매도"
    FULL_EXIT = "전량매도"
    TRADE_BLOCKED = "매매금지"


class OHLCV(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockInfo(BaseModel):
    ticker: str
    name: str
    market: str = "KOSPI"
    sector: str = ""
    current_price: float = 0
    prev_close: float = 0
    change_pct: float = 0
    volume: int = 0
    market_cap: int = 0
    high_52w: float = 0
    low_52w: float = 0


class StockSignal(BaseModel):
    ticker: str
    name: str = ""
    state: StockState = StockState.WATCH
    confidence: float = Field(0, ge=0, le=100)
    bottom_probability_score: float = Field(0, ge=0, le=100)
    trend_score: float = Field(0, ge=0, le=100)
    momentum_score: float = Field(0, ge=0, le=100)
    mean_reversion_score: float = Field(0, ge=0, le=100)
    supply_demand_score: float = Field(0, ge=0, le=100)
    event_risk_score: float = Field(0, ge=0, le=100)
    market_risk_score: float = Field(0, ge=0, le=100)
    risk_score: float = Field(0, ge=0, le=100)
    buy_price_1: Optional[float] = None
    buy_amount_1: Optional[float] = None
    buy_price_2: Optional[float] = None
    buy_amount_2: Optional[float] = None
    exit_price_1: Optional[float] = None
    exit_price_2: Optional[float] = None
    exit_trailing_stop: Optional[float] = None
    hard_stop: Optional[float] = None
    reason: List[str] = []
    risk_flags: List[str] = []
    updated_at: str = ""


class PortfolioSummary(BaseModel):
    total_value: float = 0
    invested_amount: float = 0
    cash: float = 0
    total_pnl: float = 0
    total_pnl_pct: float = 0
    daily_pnl: float = 0
    daily_pnl_pct: float = 0
    position_count: int = 0
    watchlist_count: int = 0
    max_drawdown_pct: float = 0
    win_rate: float = 0


class Position(BaseModel):
    ticker: str
    name: str
    avg_price: float
    quantity: int
    current_price: float
    market_value: float = 0
    pnl: float = 0
    pnl_pct: float = 0
    weight_pct: float = 0
    avg_down_count: int = 0
    entry_date: str = ""
    holding_days: int = 0
