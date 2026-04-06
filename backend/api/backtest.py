"""
백테스트 결과를 요청하고 시뮬레이션을 수행하는 백엔드 라우터
"""
from fastapi import APIRouter
from pydantic import BaseModel
import pandas as pd
from backend.engines.backtest_engine import BacktestEngine
from backend.mock_data.stocks import _generate_ohlcv, MOCK_STOCKS

router = APIRouter(tags=["백테스트"])

class BacktestRequest(BaseModel):
    ticker: str
    initial_capital: float
    days: int = 250 # 기본 1년 (영업일 기준 약 250일)

@router.post("/api/backtest/run")
async def run_backtest(req: BacktestRequest):
    ticker = req.ticker
    
    # 전략적 변동성을 위해 ticker에 따라 기본값과 변동률을 다르게 적용
    stock = MOCK_STOCKS.get(ticker)
    if not stock:
        return {"error": "해당 종목을 찾을 수 없습니다."}
        
    base_price = stock.current_price
    
    # 과거 모의 OHLCV 데이터 생성 (백테스트 기간 + 60일(지표 웜업용))
    total_days = req.days + 60
    
    # 각 종목의 특성에 맞는 변동성 파라미터 부여
    volatility_map = {
        "005490": 0.018,
        "005930": 0.012,
        "000660": 0.022,
        "035420": 0.020,
        "051910": 0.025
    }
    vol = volatility_map.get(ticker, 0.02)
    
    # 웜업 포함 데이터 생성 (mock 생성기가 최신일자를 맨 앞에 두는지 역순인지 확인 필요)
    # mock_data의 _generate_ohlcv는 리스트를 반환하며, 마지막 원소가 가장 과거임 (history 역순)
    # 하지만 백테스트는 과거부터 미래로 흘러야 하므로, df 반전 처리 필요.
    raw_data = _generate_ohlcv(base_price, days=total_days, volatility=vol)
    
    df_history = pd.DataFrame(raw_data)
    
    # 백테스트 엔진 수행
    engine = BacktestEngine(initial_capital=req.initial_capital)
    result = engine.run(df_history, ticker)
    
    return result
