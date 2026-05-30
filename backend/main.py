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
    backtest_router, quant_router
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

    # ★ 고도화: DART API 클라이언트 (재무데이터 + 공시)
    from backend.data.dart_client import get_dart_client
    dart_api_key = config.get("api", "dart_api_key", default="")
    dart_client = get_dart_client(api_key=dart_api_key)
    _engines['dart'] = dart_client

    # ★ 고도화: LLM 뉴스 심층 분석
    from backend.data.llm_news_analyzer import get_llm_analyzer
    openai_key = config.get("api", "openai_api_key", default="")
    llm_analyzer = get_llm_analyzer(openai_api_key=openai_key)
    _engines['llm'] = llm_analyzer

    # ★ 고도화: ML 모델 드리프트 모니터
    from backend.ml.model_monitor import get_monitor
    for model_name in ['xgboost', 'lightgbm', 'lstm']:
        _engines[f'monitor_{model_name}'] = get_monitor(model_name)

    logger.info("✅ Phase 1: 데이터 파이프라인 초기화 완료 (★DART+LLM+드리프트 모니터 포함)")

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

    # ─── 스케줄러: 팩터 가중치 주기 재보정 (config 플래그로 가드, 기본 OFF) ───
    scheduler = None
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        if config.get("jobs", "auto_recalibrate", default=False):
            day = config.get("jobs", "recalibrate_day_of_week", default="sun")
            hour = config.get("jobs", "recalibrate_hour", default=6)
            scheduler.add_job(scheduled_recalibration, "cron",
                              day_of_week=day, hour=hour, id="factor_recalibration")
            logger.info(f"📅 팩터 재보정 스케줄 등록: 매주 {day} {hour}시")
        scheduler.start()
        _engines["scheduler"] = scheduler
    except Exception as e:
        logger.warning(f"스케줄러 초기화 건너뜀: {e}")

    logger.info("🏦 KRX AutoTrader 준비 완료 - 모든 엔진 가동 중")

    yield

    task.cancel()
    if scheduler:
        scheduler.shutdown(wait=False)
    logger.info("🛑 KRX AutoTrader 종료")


async def scheduled_recalibration():
    """주기 팩터 재보정 — 실 KRX 데이터로 가중치 갱신 후 factor 엔진에 반영."""
    from datetime import datetime, timedelta
    from backend.data.krx_loader import KRXDataLoader
    from backend.jobs.recalibration import recalibrate_factor_weights
    from backend.api.quant import _LIVE_UNIVERSE

    logger.info("🔁 팩터 가중치 재보정 시작…")
    loader = KRXDataLoader()
    if not loader.available():
        logger.warning("pykrx 미설치 — 재보정 건너뜀")
        return
    now = datetime.now()
    end = now.strftime("%Y%m%d")
    start = (now - timedelta(days=750)).strftime("%Y%m%d")
    factor_model = _engines.get("factor")
    if factor_model is None:
        return
    try:
        res = await asyncio.to_thread(
            recalibrate_factor_weights, loader, _LIVE_UNIVERSE, factor_model,
            start, end, 20, 250, 20, True, True,
        )
        logger.info(f"✅ 팩터 재보정 완료: {res.get('applied_weights')}")
    except Exception as e:
        logger.error(f"팩터 재보정 실패: {e}")


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
app.include_router(quant_router)


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
