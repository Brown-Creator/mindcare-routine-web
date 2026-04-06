"""전략 API 라우터 - 엔진 기반 실시간 계산"""
from fastapi import APIRouter
from backend.engines.data_engine import MockDataEngine
from backend.engines.strategy_engine import MockStrategyEngine
from backend.mock_data import MOCK_STOCKS, MOCK_SIGNALS, MOCK_STRATEGY_LOGS

router = APIRouter(prefix="/api/strategy", tags=["전략"])

data_engine = MockDataEngine()
strategy_engine = MockStrategyEngine()


@router.get("/signals")
async def get_all_signals():
    """전체 종목 전략 신호 - 실시간 엔진 계산"""
    signals = {}
    market_ctx = await data_engine.get_market_context()

    for ticker, stock in MOCK_STOCKS.items():
        try:
            price_history = await data_engine.get_price_history(ticker)
            indicators = await data_engine.get_indicators(ticker)
            signal = await strategy_engine.evaluate(
                ticker, stock, price_history, indicators, market_ctx
            )
            signals[ticker] = signal.model_dump()
        except Exception:
            sig = MOCK_SIGNALS.get(ticker)
            if sig:
                signals[ticker] = sig.model_dump()

    return signals


@router.get("/logs")
async def get_strategy_logs():
    """전략 로그"""
    return MOCK_STRATEGY_LOGS
