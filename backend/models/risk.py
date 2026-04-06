"""
KRX AutoTrader 데이터 모델 - 리스크
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "낮음"
    MODERATE = "보통"
    HIGH = "높음"
    CRITICAL = "위험"
    BLOCKED = "차단"


class RiskCheckResult(BaseModel):
    approved: bool = False
    level: RiskLevel = RiskLevel.MODERATE
    checks_passed: List[str] = []
    checks_failed: List[str] = []
    reason: str = ""
    daily_loss_pct: float = 0
    position_weight_pct: float = 0
    drawdown_pct: float = 0
    order_risk_pct: float = 0


class RiskStatus(BaseModel):
    overall_level: RiskLevel = RiskLevel.LOW
    kill_switch_active: bool = False
    daily_loss_pct: float = 0
    max_daily_loss_pct: float = 3.0
    current_drawdown_pct: float = 0
    max_drawdown_pct: float = 10.0
    total_exposure_pct: float = 0
    largest_position_pct: float = 0
    api_health: str = "정상"
    data_health: str = "정상"
    websocket_status: str = "연결됨"
    last_check_time: str = ""
    blocked_tickers: List[str] = []
    active_alerts: List[str] = []
