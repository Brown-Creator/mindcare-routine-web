"""
프로덕션 전략 엔진 - 모든 모듈 통합
BaseStrategyEngine의 실제 구현체
"""
import pandas as pd
import numpy as np
import logging
from typing import List, Optional, Dict

from backend.engines.strategy_engine import BaseStrategyEngine
from backend.models.stock import StockSignal, StockState, StockInfo, OHLCV
from backend.indicators import calculate_all_indicators
from backend.strategies import evaluate_all_strategies
from backend.ml.feature_engineering import FeatureEngineer
from backend.engines.alpha_engine import AlphaEngine
from backend.strategies.deep_recovery import DeepRecoveryStrategy

logger = logging.getLogger(__name__)


class LiveStrategyEngine(BaseStrategyEngine):
    """프로덕션 전략 엔진 - 전체 파이프라인 통합"""

    def __init__(self):
        self.alpha_engine = AlphaEngine()
        self.feature_engineer = FeatureEngineer()
        self._ml_ensemble = None
        self._deep_predictor = None
        self._factor_model = None
        self._regime_detector = None
        self._sentiment_engine = None
        self._flow_analyzer = None
        self._current_regime = "sideways"
        # 단기 고점 회복 전담 분리 엔진
        self.recovery_strategy = DeepRecoveryStrategy(self.alpha_engine, None)

    def set_components(self, ml_ensemble=None, deep_predictor=None,
                       factor_model=None, regime_detector=None,
                       sentiment_engine=None, flow_analyzer=None):
        """외부 컴포넌트 주입"""
        self._ml_ensemble = ml_ensemble
        self._deep_predictor = deep_predictor
        self._factor_model = factor_model
        self._regime_detector = regime_detector
        self._sentiment_engine = sentiment_engine
        self._flow_analyzer = flow_analyzer

    async def evaluate(self, ticker: str, stock_info: StockInfo,
                       price_history: List[OHLCV], indicators: dict,
                       market_context: dict) -> StockSignal:
        """종합 평가 → StockSignal 생성"""

        # 1. DataFrame 구성 + 지표 계산
        df = pd.DataFrame([vars(p) if hasattr(p, '__dict__') else p for p in price_history])
        if df.empty:
            return self._empty_signal(ticker, stock_info)

        df = df.sort_values('date').reset_index(drop=True)
        df = calculate_all_indicators(df)

        # 1.5 Deep Recovery Strategy 트리거 (분리된 태스크로 동작해야하지만, 편의상 평가 사이클 중 호출)
        if ticker in self.recovery_strategy.targets:
            current_market_data = {ticker: {"close": df.iloc[-1]['close'] if not df.empty else 0}}
            import asyncio
            asyncio.create_task(self.recovery_strategy.evaluate_targets(current_market_data))

        # 2. 기존 기술적 분석
        tech_eval = evaluate_all_strategies(df, market_context)

        # 3. 피처 엔지니어링
        feat_df = self.feature_engineer.build_features(
            df,
            macro=market_context,
            sentiment=market_context.get("sentiment"),
            flow=market_context.get("flow"),
        )

        # 4. ML 앙상블 예측
        ml_pred = None
        if self._ml_ensemble:
            try:
                feature_cols = [c for c in FeatureEngineer.get_feature_names()
                               if c in feat_df.columns]
                X = feat_df[feature_cols].fillna(0)
                pred = self._ml_ensemble.predict(X, ticker)
                ml_pred = {
                    "probability": pred.probability,
                    "confidence": pred.confidence,
                    "direction": pred.direction,
                }
            except Exception as e:
                logger.warning(f"ML 예측 실패 [{ticker}]: {e}")

        # 5. 딥러닝 예측
        deep_pred = None
        if self._deep_predictor:
            try:
                seq_cols = ['close', 'volume']
                seq_cols = [c for c in seq_cols if c in feat_df.columns]
                if seq_cols:
                    X_seq, _ = self._deep_predictor.prepare_sequences(feat_df, seq_cols)
                    if X_seq is not None and len(X_seq) > 0:
                        pred = self._deep_predictor.predict(X_seq, ticker)
                        deep_pred = {
                            "predicted_return_pct": pred.predicted_return_pct,
                            "confidence": pred.confidence,
                            "pattern": pred.sequence_pattern,
                        }
            except Exception as e:
                logger.warning(f"딥러닝 예측 실패 [{ticker}]: {e}")

        # 6. 팩터 모델 점수
        factor_score = None
        if self._factor_model:
            try:
                fundamentals = market_context.get("fundamentals", {})
                fs = self._factor_model.score_stock(
                    ticker, fundamentals, df,
                    market_cap=stock_info.market_cap if stock_info else 0
                )
                factor_score = fs.composite_score
            except Exception as e:
                logger.warning(f"팩터 모델 실패 [{ticker}]: {e}")

        # 7. 센티먼트
        sentiment = market_context.get("sentiment")

        # 8. 수급
        flow = market_context.get("flow")

        # 9. 레짐
        regime = self._current_regime

        # 10. 알파 엔진 종합
        alpha = self.alpha_engine.generate_alpha(
            ticker=ticker,
            name=stock_info.name if stock_info else "",
            technical=tech_eval,
            factor_score=factor_score,
            ml_prediction=ml_pred,
            deep_prediction=deep_pred,
            sentiment=sentiment,
            flow=flow,
            macro=market_context,
            event_risk=market_context.get("event_risk"),
            regime=regime,
        )

        # 11. 상태 결정
        state = await self.classify_state_from_alpha(alpha, None)

        # 12. StockSignal 구성
        signal = StockSignal(
            ticker=ticker,
            name=stock_info.name if stock_info else ticker,
            state=state,
            confidence=int(alpha.confidence * 100),
            bottom_probability_score=tech_eval.get("bottom_probability_score", 0),
            trend_score=tech_eval.get("trend_score", 0),
            momentum_score=tech_eval.get("momentum_score", 0),
            supply_demand_score=alpha.flow_score,
            event_risk_score=alpha.event_risk_score,
            market_risk_score=alpha.macro_score,
            risk_score=100 - alpha.alpha_score,
            reason=alpha.catalysts + tech_eval.get("reasons", []),
            risk_flags=alpha.risk_factors,
        )

        # 매매 계획 첨부
        if stock_info:
            signal = await self.generate_trade_plan(signal, stock_info)

        return signal

    async def classify_state_from_alpha(self, alpha, position) -> StockState:
        """알파 시그널 기반 상태 분류"""
        score = alpha.alpha_score
        conf = alpha.confidence
        direction = alpha.direction

        if "매수" in direction and score >= 70 and conf >= 0.5:
            return StockState.NEW_ENTRY_CANDIDATE
        elif "매수" in direction and score >= 60:
            return StockState.WATCH  # 관찰 후 진입
        elif "매도" in direction and score <= 30:
            return StockState.FULL_EXIT
        elif alpha.risk_factors and len(alpha.risk_factors) >= 3:
            return StockState.TRADE_BLOCKED
        else:
            return StockState.WATCH

    # ─── BaseStrategyEngine 추상 메서드 구현 ───

    async def calculate_bottom_score(self, ticker, price_history, indicators):
        df = pd.DataFrame(price_history)
        if df.empty:
            return 0
        df = calculate_all_indicators(df)
        from backend.strategies.bottom_detector import analyze_bottom
        return analyze_bottom(df)["score"]

    async def calculate_trend_score(self, price_history, indicators):
        df = pd.DataFrame(price_history)
        if df.empty:
            return 50
        df = calculate_all_indicators(df)
        from backend.strategies.trend_analyzer import analyze_trend
        return analyze_trend(df)["score"]

    async def calculate_momentum_score(self, price_history, indicators):
        df = pd.DataFrame(price_history)
        if df.empty:
            return 50
        df = calculate_all_indicators(df)
        from backend.strategies.momentum_scorer import analyze_momentum
        return analyze_momentum(df)["score"]

    async def calculate_supply_demand_score(self, ticker, market_context):
        flow = market_context.get("flow")
        return flow.get("score", 50) if flow else 50

    async def calculate_event_risk_score(self, ticker, market_context):
        event = market_context.get("event_risk")
        return event.get("event_risk_score", 0) * 100 if event else 30

    async def calculate_market_risk_score(self, market_context):
        vix = market_context.get("vix", 20)
        if vix > 35: return 80
        elif vix > 25: return 60
        elif vix > 18: return 40
        return 20

    async def classify_state(self, signal, current_position):
        return signal.state

    async def generate_trade_plan(self, signal, stock_info):
        """ATR 기반 매매 계획"""
        price = stock_info.current_price if stock_info else 0
        if price <= 0:
            return signal

        # ATR 기반 동적 스탑/타겟 (2ATR 스탑, 3ATR 타겟)
        atr_pct = 2.0  # 기본값

        signal.buy_price_1 = price
        signal.buy_price_2 = round(price * 0.95)  # 5% 하락 시 물타기
        signal.exit_price_1 = round(price * (1 + atr_pct * 1.5 / 100))
        signal.exit_price_2 = round(price * (1 + atr_pct * 3 / 100))
        signal.exit_trailing_stop = round(price * (1 - atr_pct / 100))
        signal.hard_stop = round(price * (1 - atr_pct * 2 / 100))

        return signal

    def _empty_signal(self, ticker, stock_info):
        return StockSignal(
            ticker=ticker,
            name=stock_info.name if stock_info else ticker,
            state=StockState.WATCH,
            confidence=0,
        )
