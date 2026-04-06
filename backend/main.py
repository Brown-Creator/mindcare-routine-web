"""
KRX AutoTrader - FastAPI 메인 애플리케이션
월스트리트급 자동매매 시스템 - 전체 엔진 통합
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import (
    dashboard_router, stocks_router, orders_router,
    strategy_router, settings_router, killswitch_router, ws_router,
    backtest_router
)
from backend.config import config

from contextlib import asynccontextmanager
import asyncio
import logging

logger = logging.getLogger(__name__)

# ─── 글로벌 엔진 인스턴스 ───
_engines = {}

def get_engine(name: str):
    """엔진 인스턴스 접근"""
    return _engines.get(name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 - 전체 엔진 초기화"""
    logger.info("🚀 KRX AutoTrader 시작 - 엔진 초기화 중...")

    # DB 초기화
    from backend.db.database import setup_database
    await setup_database()

    # ─── Phase 1: 데이터 파이프라인 ───
    from backend.data.market_feed import MarketDataFeed
    from backend.data.news_sentiment import NewsSentimentEngine
    from backend.data.economic_calendar import EconomicCalendar
    from backend.data.supply_demand_live import SupplyDemandAnalyzer

    market_feed = MarketDataFeed()
    news_engine = NewsSentimentEngine()
    calendar = EconomicCalendar()
    flow_analyzer = SupplyDemandAnalyzer()

    _engines['market_feed'] = market_feed
    _engines['news'] = news_engine
    _engines['calendar'] = calendar
    _engines['flow'] = flow_analyzer
    logger.info("✅ Phase 1: 데이터 파이프라인 초기화 완료")

    # ─── Phase 2: 매크로/레짐 감지 ───
    from backend.engines.regime_detector import RegimeDetector
    regime_detector = RegimeDetector()
    _engines['regime'] = regime_detector
    logger.info("✅ Phase 2: 레짐 감지 엔진 초기화 완료")

    # ─── Phase 3: AI/ML 엔진 ───
    from backend.ml.ml_ensemble import MLEnsemble
    from backend.ml.deep_predictor import DeepPredictor
    from backend.ml.factor_model import MultiFactorModel

    ml_ensemble = MLEnsemble(model_dir="data/models")
    deep_predictor = DeepPredictor(model_dir="data/models")
    factor_model = MultiFactorModel()

    _engines['ml'] = ml_ensemble
    _engines['deep'] = deep_predictor
    _engines['factor'] = factor_model

    # 알파 엔진
    from backend.engines.alpha_engine import AlphaEngine
    alpha_engine = AlphaEngine()
    _engines['alpha'] = alpha_engine

    # 포트폴리오 최적화
    from backend.engines.portfolio_engine import PortfolioOptimizer
    portfolio_engine = PortfolioOptimizer()
    _engines['portfolio'] = portfolio_engine

    # 유니버스 스크리닝
    from backend.engines.universe_engine import UniverseScreener
    screener = UniverseScreener()
    _engines['screener'] = screener

    logger.info("✅ Phase 3: AI/ML 엔진 초기화 완료")

    # ─── Phase 4: 프로덕션 전략/리스크/실행 엔진 ───
    from backend.engines.live_strategy_engine import LiveStrategyEngine
    from backend.engines.live_risk_engine import LiveRiskEngine
    from backend.engines.execution_engine import SmartExecutionEngine
    from backend.engines.advanced_backtest import AdvancedBacktestEngine

    strategy_engine = LiveStrategyEngine()
    strategy_engine.set_components(
        ml_ensemble=ml_ensemble,
        deep_predictor=deep_predictor,
        factor_model=factor_model,
        regime_detector=regime_detector,
        sentiment_engine=news_engine,
        flow_analyzer=flow_analyzer,
    )
    risk_engine = LiveRiskEngine()
    execution_engine = SmartExecutionEngine()
    backtest_engine = AdvancedBacktestEngine()

    _engines['strategy'] = strategy_engine
    _engines['risk'] = risk_engine
    _engines['execution'] = execution_engine
    _engines['backtest_adv'] = backtest_engine

    logger.info("✅ Phase 4: 프로덕션 엔진 초기화 완료")

    # ─── 백그라운드 태스크 ───
    task = asyncio.create_task(system_heartbeat())
    logger.info("🏦 KRX AutoTrader 준비 완료 - 모든 엔진 가동 중")

    yield

    task.cancel()
    logger.info("🛑 KRX AutoTrader 종료")


async def system_heartbeat():
    """시스템 하트비트 - 주기적 데이터 갱신 및 상태 체크"""
    from backend.api.ws import manager
    from backend.mock_data import MOCK_STOCKS
    import random

    while True:
        await asyncio.sleep(2.0)

        # Mock 가격 변동 (실전에서는 키움 WebSocket 대체)
        for ticker, stock in MOCK_STOCKS.items():
            if random.random() > 0.5:
                change = stock.current_price * random.uniform(-0.001, 0.001)
                new_price = round(stock.current_price + change)
                stock.current_price = new_price
                stock.volume += random.randint(10, 500)

                await manager.broadcast_market_data({
                    "ticker": ticker,
                    "price": new_price,
                    "change_pct": round((new_price - stock.prev_close) / stock.prev_close * 100, 2),
                    "volume": stock.volume
                })

        # 매크로 데이터 주기적 갱신 (5분마다)
        # market_feed = _engines.get('market_feed')
        # if market_feed: await market_feed.get_macro_data()


app = FastAPI(
    title="KRX AutoTrader",
    description="한국 주식 자동매매 시스템 - 월스트리트급 AI 트레이딩",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.get("server", "cors_origins", default=["http://localhost:5173"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(dashboard_router)
app.include_router(stocks_router)
app.include_router(orders_router)
app.include_router(strategy_router)
app.include_router(settings_router)
app.include_router(killswitch_router)
app.include_router(ws_router)
app.include_router(backtest_router)


@app.get("/")
async def root():
    return {
        "name": "KRX AutoTrader",
        "version": "2.0.0",
        "mode": config.mode.value,
        "status": "running",
        "grade": "Wall Street Level",
    }


@app.get("/api/health")
async def health_check():
    engine_status = {}
    for name in ['market_feed', 'news', 'calendar', 'flow', 'regime',
                  'ml', 'deep', 'factor', 'alpha', 'portfolio', 'screener',
                  'strategy', 'risk', 'execution', 'backtest_adv']:
        engine_status[name] = "활성" if _engines.get(name) else "미초기화"

    return {
        "status": "정상",
        "version": "2.0.0",
        "mode": config.mode.value,
        "engines": engine_status,
        "architecture": {
            "phase1_data_pipeline": "✅",
            "phase2_macro_regime": "✅",
            "phase3_ai_alpha": "✅",
            "phase4_execution": "✅",
        }
    }


@app.get("/api/system/engines")
async def get_system_engines():
    """모든 엔진 상태 상세 조회"""
    details = {}
    for name, engine in _engines.items():
        info = {"status": "활성", "type": type(engine).__name__}
        if hasattr(engine, 'get_health'):
            info["health"] = engine.get_health()
        details[name] = info
    return {"engines": details, "total": len(_engines)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=config.get("server", "host", default="0.0.0.0"),
        port=config.get("server", "port", default=8000),
        reload=True,
    )
