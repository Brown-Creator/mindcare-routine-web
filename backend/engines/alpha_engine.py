"""
종합 알파 엔진 - 모든 시그널을 통합하여 최종 매매 결정
- 멀티팩터 + ML 앙상블 + 딥러닝 + 기술적 분석 + 센티먼트 + 수급 + 매크로
- 동적 가중치 (시장 레짐 기반)
- 신뢰도 기반 필터링
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class AlphaSignal:
    ticker: str
    name: str = ""
    # 개별 시그널 점수 (0-100)
    technical_score: float = 50
    factor_score: float = 50
    ml_score: float = 50
    deep_score: float = 50
    sentiment_score: float = 50
    flow_score: float = 50
    macro_score: float = 50
    event_risk_score: float = 50
    # 종합
    alpha_score: float = 50        # 최종 알파 점수 (0-100)
    confidence: float = 0          # 신뢰도 (0-1)
    direction: str = "중립"        # 매수/매도/중립
    strength: str = "약"           # 강/중/약
    position_size_pct: float = 0   # 권장 포지션 크기 (%)
    # 상세
    signal_details: Dict = field(default_factory=dict)
    risk_factors: List[str] = field(default_factory=list)
    catalysts: List[str] = field(default_factory=list)

class AlphaEngine:
    """
    종합 알파 생성 엔진 - 월스트리트급 의사결정 시스템
    모든 시그널 소스를 가중 통합하여 최종 alpha 산출
    """

    # 기본 시그널 가중치 (레짐에 따라 동적 변경)
    DEFAULT_WEIGHTS = {
        "technical": 0.15,
        "factor": 0.20,
        "ml": 0.20,
        "deep": 0.10,
        "sentiment": 0.10,
        "flow": 0.15,
        "macro": 0.10,
    }

    REGIME_WEIGHTS = {
        "bull": {
            "technical": 0.10, "factor": 0.15, "ml": 0.25,
            "deep": 0.15, "sentiment": 0.10, "flow": 0.15, "macro": 0.10,
        },
        "bear": {
            "technical": 0.15, "factor": 0.25, "ml": 0.15,
            "deep": 0.05, "sentiment": 0.15, "flow": 0.15, "macro": 0.10,
        },
        "sideways": {
            "technical": 0.20, "factor": 0.20, "ml": 0.15,
            "deep": 0.10, "sentiment": 0.10, "flow": 0.15, "macro": 0.10,
        },
    }

    def __init__(self):
        self._weights = self.DEFAULT_WEIGHTS.copy()

    def set_regime(self, regime: str):
        """시장 레짐에 따른 가중치 조정 (하위호환용 — generate_alpha는 지역 가중치 사용)"""
        self._weights = self.REGIME_WEIGHTS.get(regime, self.DEFAULT_WEIGHTS).copy()

    def _regime_weights(self, regime: str) -> dict:
        """레짐별 가중치의 '새 복사본'을 반환 — 인스턴스 상태를 건드리지 않아 동시 호출에 안전."""
        return dict(self.REGIME_WEIGHTS.get(regime, self.DEFAULT_WEIGHTS))

    def generate_alpha(self, ticker: str, name: str = "",
                       technical: dict = None,
                       factor_score: float = None,
                       ml_prediction: dict = None,
                       deep_prediction: dict = None,
                       sentiment: dict = None,
                       flow: dict = None,
                       macro: dict = None,
                       event_risk: dict = None,
                       regime: str = "sideways") -> AlphaSignal:
        """종합 알파 시그널 생성"""

        # 인스턴스 상태가 아닌 '지역 가중치'를 사용 → async 동시 평가 시 상호 간섭 없음
        weights = self._regime_weights(regime)
        signal = AlphaSignal(ticker=ticker, name=name)

        # ─── 1. 기술적 점수 (기존 strategy 결과 활용) ───
        if technical:
            bottom = technical.get("bottom_probability_score", 50)
            trend = technical.get("trend_score", 50)
            momentum = technical.get("momentum_score", 50)
            signal.technical_score = (bottom * 0.35 + trend * 0.35 + momentum * 0.30)

        # ─── 2. 팩터 점수 ───
        if factor_score is not None:
            signal.factor_score = factor_score

        # ─── 3. ML 앙상블 점수 ───
        if ml_prediction:
            prob = ml_prediction.get("probability", 0.5)
            conf = ml_prediction.get("confidence", 0)
            signal.ml_score = prob * 100
            # ML 신뢰도가 낮으면 가중치 축소 (지역 가중치만 수정)
            if conf < 0.3:
                weights["ml"] *= 0.5

        # ─── 4. 딥러닝 점수 ───
        if deep_prediction:
            prob = (deep_prediction.get("predicted_return_pct", 0) + 5) / 10 * 100
            signal.deep_score = max(0, min(100, prob))

        # ─── 5. 센티먼트 점수 ───
        if sentiment:
            sent_score = sentiment.get("score", 0)
            signal.sentiment_score = (sent_score + 1) / 2 * 100  # -1~1 → 0~100
            if sentiment.get("high_impact_events"):
                signal.catalysts.extend(sentiment["high_impact_events"][:3])

        # ─── 6. 수급 점수 ───
        if flow:
            signal.flow_score = flow.get("score", 50)
            if flow.get("smart_money_signal") == "쌍끌이 매수":
                signal.catalysts.append("외국인+기관 쌍끌이 매수")
            if flow.get("risk_flags"):
                signal.risk_factors.extend(flow["risk_flags"])

        # ─── 7. 매크로 점수 ───
        if macro:
            vix = macro.get("vix", 20)
            fear = macro.get("fear_greed_index", 50)
            # VIX 낮고 Fear&Greed 높으면 매크로 호조
            macro_score = 50
            if vix < 15: macro_score += 15
            elif vix > 30: macro_score -= 20
            macro_score += (fear - 50) * 0.3
            signal.macro_score = max(0, min(100, macro_score))

        # ─── 8. 이벤트 리스크 ───
        if event_risk:
            signal.event_risk_score = event_risk.get("event_risk_score", 0) * 100
            if event_risk.get("risk_factors"):
                signal.risk_factors.extend(event_risk["risk_factors"])

        # ─── 가중 합산 ───
        scores = {
            "technical": signal.technical_score,
            "factor": signal.factor_score,
            "ml": signal.ml_score,
            "deep": signal.deep_score,
            "sentiment": signal.sentiment_score,
            "flow": signal.flow_score,
            "macro": signal.macro_score,
        }

        weighted_sum = sum(scores[k] * weights[k] for k in scores)
        total_weight = sum(weights[k] for k in scores)
        signal.alpha_score = weighted_sum / total_weight if total_weight > 0 else 50

        # 이벤트 리스크 감산
        event_penalty = signal.event_risk_score * 0.15
        signal.alpha_score = max(0, signal.alpha_score - event_penalty)

        # ─── 방향/강도/신뢰도 결정 ───
        if signal.alpha_score >= 70:
            signal.direction = "강력 매수"
            signal.strength = "강"
        elif signal.alpha_score >= 60:
            signal.direction = "매수"
            signal.strength = "중"
        elif signal.alpha_score <= 30:
            signal.direction = "매도"
            signal.strength = "중"
        elif signal.alpha_score <= 20:
            signal.direction = "강력 매도"
            signal.strength = "강"
        else:
            signal.direction = "중립"
            signal.strength = "약"

        # 신뢰도 = 방향 일치도 × 확신도(중립 이탈)의 기하평균.
        # 기존 (1 - std/50) 은 모든 시그널이 50(중립)일 때 신뢰도 1을 주는 결함이 있었다.
        # 진짜 확신은 (a) 시그널들이 같은 방향을 가리키고 (b) 합성점수가 중립에서
        # 충분히 떨어져 있을 때만 높아야 한다.
        signs = {k: np.sign(scores[k] - 50) for k in scores}
        agree_den = sum(weights[k] for k in scores)
        agreement = (abs(sum(weights[k] * signs[k] for k in scores)) / agree_den
                     if agree_den > 0 else 0.0)
        conviction = min(1.0, abs(signal.alpha_score - 50) / 25.0)
        signal.confidence = round(float(np.sqrt(max(agreement, 0.0) * conviction)), 3)

        # 포지션 크기 제안 (알파 * 신뢰도 * 레짐 리스크)
        regime_mult = {"bull": 1.2, "bear": 0.5, "sideways": 0.8}.get(regime, 1.0)
        base_size = max(0, (signal.alpha_score - 50) / 50) * 10  # 최대 10%
        signal.position_size_pct = round(base_size * signal.confidence * regime_mult, 1)

        signal.signal_details = {k: round(v, 1) for k, v in scores.items()}

        return signal

    def rank_candidates(self, signals: List[AlphaSignal]) -> List[AlphaSignal]:
        """알파 시그널 기반 후보군 랭킹"""
        # 알파 * 신뢰도 → 최종 랭킹
        for s in signals:
            s._rank_score = s.alpha_score * s.confidence

        ranked = sorted(signals, key=lambda s: s._rank_score, reverse=True)

        # 상위 20% 만 매수 후보
        cutoff = max(int(len(ranked) * 0.2), 1)
        for i, s in enumerate(ranked):
            if i < cutoff and s.alpha_score >= 60:
                s.direction = "매수" if s.direction == "중립" else s.direction
        return ranked

    def get_top_picks(self, signals: List[AlphaSignal], n: int = 10) -> List[AlphaSignal]:
        """상위 N개 추천 종목"""
        ranked = self.rank_candidates(signals)
        return [s for s in ranked[:n] if s.alpha_score >= 55]
