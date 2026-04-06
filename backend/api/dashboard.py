"""대시보드 API 라우터 - 엔진 기반 실시간 연산"""
from fastapi import APIRouter
from backend.engines.data_engine import MockDataEngine
from backend.engines.strategy_engine import MockStrategyEngine
from backend.mock_data import (
    MOCK_POSITIONS, MOCK_ORDERS,
    MOCK_PORTFOLIO, MOCK_RISK_STATUS, MOCK_ALERTS, MOCK_STRATEGY_LOGS,
    MOCK_STOCKS,
)

router = APIRouter(prefix="/api/dashboard", tags=["대시보드"])

data_engine = MockDataEngine()
strategy_engine = MockStrategyEngine()


@router.get("/summary")
async def get_dashboard_summary():
    """대시보드 요약 데이터 - 전략 신호는 엔진에서 실시간 계산"""
    # 실시간 전략 신호 계산
    signals = {}
    market_ctx = await data_engine.get_market_context()

    for ticker, stock_info in MOCK_STOCKS.items():
        try:
            price_history = await data_engine.get_price_history(ticker)
            indicators = await data_engine.get_indicators(ticker)
            signal = await strategy_engine.evaluate(
                ticker, stock_info, price_history, indicators, market_ctx
            )
            signals[ticker] = signal.model_dump()
        except Exception as e:
            # 계산 실패 시 기본 Mock 데이터 사용
            from backend.mock_data import MOCK_SIGNALS
            sig = MOCK_SIGNALS.get(ticker)
            if sig:
                signals[ticker] = sig.model_dump()

    return {
        "portfolio": MOCK_PORTFOLIO.model_dump(),
        "risk_status": MOCK_RISK_STATUS.model_dump(),
        "positions": [p.model_dump() for p in MOCK_POSITIONS],
        "signals": signals,
        "recent_orders": MOCK_ORDERS[:5],
        "alerts": MOCK_ALERTS,
        "mode": "mock",
    }


@router.get("/portfolio")
async def get_portfolio():
    return MOCK_PORTFOLIO.model_dump()


@router.get("/positions")
async def get_positions():
    return [p.model_dump() for p in MOCK_POSITIONS]


@router.get("/alerts")
async def get_alerts():
    return MOCK_ALERTS


@router.get("/strategy-logs")
async def get_strategy_logs():
    return MOCK_STRATEGY_LOGS
