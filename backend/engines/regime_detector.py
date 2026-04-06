"""
시장 레짐 감지 엔진 (Hidden Markov Model 기반)
- Bull(강세) / Bear(약세) / Sideways(횡보) 레짐 자동 식별
- 레짐 전환 확률 계산
- 전략 파라미터 동적 조정
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class RegimeState:
    current_regime: str = "unknown"          # bull / bear / sideways
    regime_probability: Dict[str, float] = None
    regime_duration_days: int = 0
    transition_probability: float = 0        # 레짐 전환 확률
    volatility_regime: str = "normal"        # low / normal / high / extreme
    risk_multiplier: float = 1.0             # 전략 리스크 조정 배수

    def __post_init__(self):
        if self.regime_probability is None:
            self.regime_probability = {"bull": 0.33, "bear": 0.33, "sideways": 0.34}

class RegimeDetector:
    """
    시장 레짐 감지 - 간이 HMM + 통계적 방법 조합
    hmmlearn 없이도 동작하도록 설계
    """

    # 레짐별 파라미터 (한국 시장 기준)
    REGIME_PARAMS = {
        "bull": {
            "mean_return": 0.08,    # 일평균 0.08% 수준
            "std_return": 0.012,
            "vol_low": 0.10,
            "vol_high": 0.22,
        },
        "bear": {
            "mean_return": -0.06,
            "std_return": 0.018,
            "vol_low": 0.18,
            "vol_high": 0.45,
        },
        "sideways": {
            "mean_return": 0.001,
            "std_return": 0.008,
            "vol_low": 0.12,
            "vol_high": 0.25,
        },
    }

    # 전이 확률 행렬 (사전 추정)
    TRANSITION_MATRIX = np.array([
        #       bull   bear   side
        [0.92,  0.03,  0.05],  # from bull
        [0.05,  0.90,  0.05],  # from bear
        [0.08,  0.07,  0.85],  # from sideways
    ])

    def __init__(self):
        self._current_state: Optional[RegimeState] = None
        self._history: list = []

    def detect(self, kospi_df: pd.DataFrame = None,
               returns: pd.Series = None,
               vix: float = None,
               macro_data: dict = None) -> RegimeState:
        """
        복합 시그널 기반 레짐 감지
        """
        signals = {}

        # 1. 수익률 기반 판단
        if returns is not None and len(returns) >= 60:
            signals['return'] = self._return_signal(returns)
        elif kospi_df is not None and len(kospi_df) >= 60:
            ret = kospi_df['close'].pct_change().dropna()
            signals['return'] = self._return_signal(ret)

        # 2. 추세 기반 판단
        if kospi_df is not None and len(kospi_df) >= 120:
            signals['trend'] = self._trend_signal(kospi_df)

        # 3. 변동성 기반 판단
        if returns is not None and len(returns) >= 20:
            signals['volatility'] = self._volatility_signal(returns)

        # 4. VIX / Fear 기반
        if vix is not None:
            signals['vix'] = self._vix_signal(vix)

        # 5. 매크로 기반
        if macro_data:
            signals['macro'] = self._macro_signal(macro_data)

        # 종합 판단
        return self._combine_signals(signals)

    def _return_signal(self, returns: pd.Series) -> Dict[str, float]:
        """수익률 분포 기반"""
        r20 = returns.tail(20)
        r60 = returns.tail(60)

        mean_20 = r20.mean()
        mean_60 = r60.mean()
        vol_20 = r20.std()

        # 단순 경계값 기반 확률 추정
        if mean_20 > 0.003 and mean_60 > 0.001:
            return {"bull": 0.7, "bear": 0.05, "sideways": 0.25}
        elif mean_20 < -0.003 and mean_60 < -0.001:
            return {"bull": 0.05, "bear": 0.7, "sideways": 0.25}
        elif abs(mean_20) < 0.001 and vol_20 < 0.015:
            return {"bull": 0.15, "bear": 0.15, "sideways": 0.7}
        else:
            return {"bull": 0.3, "bear": 0.3, "sideways": 0.4}

    def _trend_signal(self, df: pd.DataFrame) -> Dict[str, float]:
        """이동평균 크로스 기반"""
        c = df['close']
        ma20 = c.rolling(20).mean().iloc[-1]
        ma60 = c.rolling(60).mean().iloc[-1]
        ma120 = c.rolling(120).mean().iloc[-1]
        price = c.iloc[-1]

        score = 0
        if price > ma20: score += 1
        if price > ma60: score += 1
        if price > ma120: score += 1
        if ma20 > ma60: score += 1
        if ma60 > ma120: score += 1

        if score >= 4:
            return {"bull": 0.75, "bear": 0.05, "sideways": 0.2}
        elif score <= 1:
            return {"bull": 0.05, "bear": 0.75, "sideways": 0.2}
        else:
            return {"bull": 0.25, "bear": 0.25, "sideways": 0.5}

    def _volatility_signal(self, returns: pd.Series) -> Dict[str, float]:
        """변동성 레짐"""
        vol = returns.tail(20).std() * np.sqrt(252)

        if vol < 0.12:
            return {"bull": 0.4, "bear": 0.1, "sideways": 0.5}
        elif vol > 0.35:
            return {"bull": 0.15, "bear": 0.65, "sideways": 0.2}
        else:
            return {"bull": 0.3, "bear": 0.3, "sideways": 0.4}

    def _vix_signal(self, vix: float) -> Dict[str, float]:
        """VIX 기반"""
        if vix < 15:
            return {"bull": 0.6, "bear": 0.05, "sideways": 0.35}
        elif vix > 30:
            return {"bull": 0.05, "bear": 0.75, "sideways": 0.2}
        elif vix > 20:
            return {"bull": 0.2, "bear": 0.4, "sideways": 0.4}
        else:
            return {"bull": 0.35, "bear": 0.2, "sideways": 0.45}

    def _macro_signal(self, macro: dict) -> Dict[str, float]:
        """매크로 데이터 기반"""
        yield_spread = macro.get("yield_spread", 0)
        fear_greed = macro.get("fear_greed_index", 50)

        bull_prob = 0.33
        if yield_spread > 0: bull_prob += 0.15
        if fear_greed > 60: bull_prob += 0.1

        bear_prob = 0.33
        if yield_spread < -0.5: bear_prob += 0.2
        if fear_greed < 25: bear_prob += 0.15

        side_prob = max(0, 1 - bull_prob - bear_prob)
        total = bull_prob + bear_prob + side_prob
        return {
            "bull": bull_prob / total,
            "bear": bear_prob / total,
            "sideways": side_prob / total,
        }

    def _combine_signals(self, signals: Dict[str, Dict[str, float]]) -> RegimeState:
        """다중 시그널 종합"""
        if not signals:
            return RegimeState()

        # 가중 평균 (각 시그널 동등 가중)
        combined = {"bull": 0, "bear": 0, "sideways": 0}
        for probs in signals.values():
            for regime, prob in probs.items():
                combined[regime] += prob
        total = sum(combined.values())
        for k in combined:
            combined[k] /= total

        # 최고 확률 레짐
        current = max(combined, key=combined.get)
        confidence = combined[current]

        # 변동성 레짐
        vol_regime = "normal"
        vol_probs = signals.get("volatility", {})
        if vol_probs.get("bear", 0) > 0.5:
            vol_regime = "high"
        elif vol_probs.get("bull", 0) > 0.5 and vol_probs.get("sideways", 0) > 0.3:
            vol_regime = "low"

        # 리스크 배수 결정
        risk_mult = {
            "bull": 1.2,   # 강세 → 포지션 확대
            "bear": 0.5,   # 약세 → 포지션 축소
            "sideways": 0.8,
        }.get(current, 1.0)

        if vol_regime == "high":
            risk_mult *= 0.7
        elif vol_regime == "extreme":
            risk_mult *= 0.3

        state = RegimeState(
            current_regime=current,
            regime_probability=combined,
            volatility_regime=vol_regime,
            risk_multiplier=round(risk_mult, 2),
            transition_probability=round(1 - confidence, 3),
        )

        self._current_state = state
        self._history.append(state)
        return state

    def get_strategy_params(self) -> dict:
        """현재 레짐에 맞는 전략 파라미터"""
        if not self._current_state:
            return {}

        regime = self._current_state.current_regime
        params = {
            "bull": {
                "entry_threshold": 55, "exit_trailing_pct": 5.0,
                "max_position_pct": 25, "prefer_momentum": True,
                "avg_down_allowed": True, "factor_weights": "momentum_heavy",
            },
            "bear": {
                "entry_threshold": 75, "exit_trailing_pct": 2.0,
                "max_position_pct": 10, "prefer_momentum": False,
                "avg_down_allowed": False, "factor_weights": "quality_defensive",
            },
            "sideways": {
                "entry_threshold": 65, "exit_trailing_pct": 3.0,
                "max_position_pct": 15, "prefer_momentum": False,
                "avg_down_allowed": True, "factor_weights": "balanced",
            },
        }
        return params.get(regime, params["sideways"])
