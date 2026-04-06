"""종목 API 라우터 - 엔진 기반 실시간 계산"""
from fastapi import APIRouter, HTTPException
from backend.engines.data_engine import MockDataEngine
from backend.engines.strategy_engine import MockStrategyEngine
from backend.mock_data import MOCK_STOCKS, MOCK_SIGNALS

router = APIRouter(prefix="/api/stocks", tags=["종목"])

data_engine = MockDataEngine()
strategy_engine = MockStrategyEngine()


@router.get("/")
async def get_stock_list():
    """감시 종목 목록 - 실시간 신호 포함"""
    result = []
    market_ctx = await data_engine.get_market_context()

    for ticker, stock in MOCK_STOCKS.items():
        try:
            price_history = await data_engine.get_price_history(ticker)
            indicators = await data_engine.get_indicators(ticker)
            signal = await strategy_engine.evaluate(
                ticker, stock, price_history, indicators, market_ctx
            )
            result.append({
                **stock.model_dump(),
                "signal": signal.model_dump(),
            })
        except Exception:
            sig = MOCK_SIGNALS.get(ticker)
            result.append({
                **stock.model_dump(),
                "signal": sig.model_dump() if sig else None,
            })
    return result


@router.get("/{ticker}")
async def get_stock_detail(ticker: str):
    """종목 상세 정보 - 실시간 지표 및 전략 신호"""
    stock = MOCK_STOCKS.get(ticker)
    if not stock:
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다.")

    try:
        price_history = await data_engine.get_price_history(ticker)
        indicators = await data_engine.get_indicators(ticker)
        market_ctx = await data_engine.get_market_context()
        signal = await strategy_engine.evaluate(
            ticker, stock, price_history, indicators, market_ctx
        )
    except Exception:
        from backend.mock_data import get_indicators, generate_price_history
        price_history = generate_price_history(ticker)
        indicators = get_indicators(ticker)
        signal = MOCK_SIGNALS.get(ticker)

    return {
        "stock": stock.model_dump(),
        "signal": signal.model_dump() if signal else None,
        "indicators": indicators,
        "price_history": price_history[-60:],
    }


@router.get("/{ticker}/signal")
async def get_stock_signal(ticker: str):
    """종목 전략 신호 - 실시간 계산"""
    stock = MOCK_STOCKS.get(ticker)
    if not stock:
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다.")

    try:
        price_history = await data_engine.get_price_history(ticker)
        indicators = await data_engine.get_indicators(ticker)
        market_ctx = await data_engine.get_market_context()
        signal = await strategy_engine.evaluate(
            ticker, stock, price_history, indicators, market_ctx
        )
        return signal.model_dump()
    except Exception:
        sig = MOCK_SIGNALS.get(ticker)
        if not sig:
            raise HTTPException(status_code=404, detail="신호 데이터가 없습니다.")
        return sig.model_dump()


@router.get("/{ticker}/indicators")
async def get_stock_indicators(ticker: str):
    """종목 기술적 지표 - pandas 기반 실시간 계산"""
    try:
        return await data_engine.get_indicators(ticker)
    except Exception:
        from backend.mock_data import get_indicators
        return get_indicators(ticker)


@router.get("/{ticker}/history")
async def get_stock_history(ticker: str, days: int = 60):
    """종목 가격 히스토리"""
    try:
        history = await data_engine.get_price_history(ticker, days=max(days, 120))
        return history[-days:]
    except Exception:
        from backend.mock_data import generate_price_history
        return generate_price_history(ticker)[-days:]
