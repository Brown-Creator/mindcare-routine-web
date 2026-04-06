"""
멀티팩터 모델 (Fama-French 확장)
- Value (PBR, PER 역수)
- Quality (ROE, 부채비율, 이익안정성)
- Momentum (3M/6M/12M 수익률)
- Low Volatility (실현변동성 역수)
- Size (시가총액)
- 팩터 점수 → 종합 랭킹 → 종목 선정
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class FactorScore:
    ticker: str
    name: str = ""
    value_score: float = 0        # 가치 팩터
    quality_score: float = 0      # 퀄리티 팩터
    momentum_score: float = 0     # 모멘텀 팩터
    low_vol_score: float = 0      # 저변동성 팩터
    size_score: float = 0         # 사이즈 팩터
    growth_score: float = 0       # 성장성 팩터
    composite_score: float = 0    # 종합 점수
    rank: int = 0
    factors_detail: Dict = field(default_factory=dict)

class MultiFactorModel:
    """
    멀티팩터 모델 - 월스트리트 퀀트 표준
    Barra 리스크 모델 기반 한국시장 커스텀
    """

    # 팩터 가중치 (시장 레짐에 따라 동적 조정)
    DEFAULT_WEIGHTS = {
        "value": 0.20,
        "quality": 0.25,
        "momentum": 0.20,
        "low_vol": 0.15,
        "size": 0.05,
        "growth": 0.15,
    }

    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._universe_scores: List[FactorScore] = []

    def score_stock(self, ticker: str, fundamentals: dict,
                    price_data: pd.DataFrame, market_cap: float = 0) -> FactorScore:
        """개별 종목 팩터 스코어링"""
        fs = FactorScore(ticker=ticker, name=fundamentals.get("name", ""))

        # 1. Value Factor
        fs.value_score = self._calc_value(fundamentals)

        # 2. Quality Factor
        fs.quality_score = self._calc_quality(fundamentals)

        # 3. Momentum Factor
        fs.momentum_score = self._calc_momentum(price_data)

        # 4. Low Volatility Factor
        fs.low_vol_score = self._calc_low_vol(price_data)

        # 5. Size Factor
        fs.size_score = self._calc_size(market_cap)

        # 6. Growth Factor
        fs.growth_score = self._calc_growth(fundamentals)

        # Composite (가중 평균)
        fs.composite_score = (
            fs.value_score * self.weights["value"] +
            fs.quality_score * self.weights["quality"] +
            fs.momentum_score * self.weights["momentum"] +
            fs.low_vol_score * self.weights["low_vol"] +
            fs.size_score * self.weights["size"] +
            fs.growth_score * self.weights["growth"]
        )

        fs.factors_detail = {
            "value": round(fs.value_score, 1),
            "quality": round(fs.quality_score, 1),
            "momentum": round(fs.momentum_score, 1),
            "low_vol": round(fs.low_vol_score, 1),
            "size": round(fs.size_score, 1),
            "growth": round(fs.growth_score, 1),
        }

        return fs

    def rank_universe(self, stocks: List[FactorScore]) -> List[FactorScore]:
        """유니버스 전체 랭킹"""
        sorted_stocks = sorted(stocks, key=lambda s: s.composite_score, reverse=True)
        for i, s in enumerate(sorted_stocks):
            s.rank = i + 1
        self._universe_scores = sorted_stocks
        return sorted_stocks

    def get_top_picks(self, n: int = 20) -> List[FactorScore]:
        """상위 N개 종목 반환"""
        return self._universe_scores[:n] if self._universe_scores else []

    def adjust_weights_for_regime(self, regime: str):
        """시장 레짐에 따른 팩터 가중치 동적 조정"""
        if regime == "bull":
            self.weights = {
                "value": 0.10, "quality": 0.15, "momentum": 0.35,
                "low_vol": 0.05, "size": 0.10, "growth": 0.25,
            }
        elif regime == "bear":
            self.weights = {
                "value": 0.25, "quality": 0.30, "momentum": 0.05,
                "low_vol": 0.25, "size": 0.05, "growth": 0.10,
            }
        elif regime == "sideways":
            self.weights = {
                "value": 0.25, "quality": 0.25, "momentum": 0.15,
                "low_vol": 0.20, "size": 0.05, "growth": 0.10,
            }
        else:
            self.weights = self.DEFAULT_WEIGHTS.copy()

    # ─── 개별 팩터 계산 ───

    def _calc_value(self, fund: dict) -> float:
        """가치 팩터 (0-100)"""
        score = 50
        per = fund.get("per", 0)
        pbr = fund.get("pbr", 0)
        div_yield = fund.get("dividend_yield", 0)
        ev_ebitda = fund.get("ev_ebitda", 0)

        # PER (낮을수록 좋음, 0 이하 제외)
        if 0 < per < 8: score += 25
        elif 8 <= per < 12: score += 15
        elif 12 <= per < 20: score += 5
        elif per >= 30: score -= 15

        # PBR (낮을수록 좋음)
        if 0 < pbr < 0.7: score += 20
        elif 0.7 <= pbr < 1.0: score += 10
        elif pbr > 3.0: score -= 10

        # 배당수익률
        if div_yield > 5: score += 15
        elif div_yield > 3: score += 10
        elif div_yield > 1.5: score += 5

        # EV/EBITDA (낮을수록 좋음)
        if 0 < ev_ebitda < 6: score += 10
        elif ev_ebitda > 20: score -= 10

        return max(0, min(100, score))

    def _calc_quality(self, fund: dict) -> float:
        """퀄리티 팩터 (0-100)"""
        score = 50
        roe = fund.get("roe", 0)
        roa = fund.get("roa", 0)
        debt_ratio = fund.get("debt_ratio", 0)
        margin = fund.get("operating_margin", 0)
        fcf = fund.get("free_cash_flow", 0)

        # ROE
        if roe > 20: score += 25
        elif roe > 12: score += 15
        elif roe > 8: score += 5
        elif roe < 0: score -= 20

        # 부채비율 (낮을수록 좋음)
        if debt_ratio < 30: score += 15
        elif debt_ratio < 60: score += 5
        elif debt_ratio > 150: score -= 15
        elif debt_ratio > 300: score -= 25

        # 영업이익률
        if margin > 20: score += 10
        elif margin > 10: score += 5
        elif margin < 0: score -= 15

        # FCF 양수
        if fcf > 0: score += 5

        return max(0, min(100, score))

    def _calc_momentum(self, df: pd.DataFrame) -> float:
        """모멘텀 팩터 (0-100)"""
        if df.empty or len(df) < 60:
            return 50

        c = df['close']
        score = 50

        # 3개월 수익률
        if len(c) >= 60:
            ret_3m = (c.iloc[-1] / c.iloc[-60] - 1) * 100
            if ret_3m > 20: score += 20
            elif ret_3m > 10: score += 15
            elif ret_3m > 5: score += 8
            elif ret_3m < -20: score -= 15
            elif ret_3m < -10: score -= 10

        # 6개월 수익률
        if len(c) >= 120:
            ret_6m = (c.iloc[-1] / c.iloc[-120] - 1) * 100
            if ret_6m > 30: score += 15
            elif ret_6m > 15: score += 10
            elif ret_6m < -30: score -= 15

        # 최근 1개월 모멘텀 가속도
        if len(c) >= 20:
            ret_1m = (c.iloc[-1] / c.iloc[-20] - 1) * 100
            ret_prev_1m = (c.iloc[-20] / c.iloc[-40] - 1) * 100 if len(c) >= 40 else 0
            accel = ret_1m - ret_prev_1m
            if accel > 5: score += 10
            elif accel < -5: score -= 10

        # 52주 고점 대비 (산타클로스 효과: 고점 근접할수록 모멘텀)
        if len(c) >= 240:
            from_high = (c.iloc[-1] / c.rolling(240).max().iloc[-1]) * 100
            if from_high > 90: score += 10  # 고점 근처
            elif from_high < 50: score -= 10

        return max(0, min(100, score))

    def _calc_low_vol(self, df: pd.DataFrame) -> float:
        """저변동성 팩터 (0-100) - 변동성 낮을수록 높은 점수"""
        if df.empty or len(df) < 20:
            return 50

        ret = df['close'].pct_change().dropna()
        vol_20d = ret.tail(20).std() * np.sqrt(252) * 100  # 연환산 %

        if vol_20d < 15: return 90
        elif vol_20d < 25: return 70
        elif vol_20d < 35: return 50
        elif vol_20d < 50: return 30
        else: return 10

    def _calc_size(self, market_cap: float) -> float:
        """사이즈 팩터 (소형주 프리미엄)"""
        if market_cap <= 0:
            return 50
        # 한국 시장 기준 (억원)
        cap_billion = market_cap / 1e8
        if cap_billion > 100000: return 30      # 대형주
        elif cap_billion > 10000: return 50     # 중형주
        elif cap_billion > 3000: return 70      # 중소형주
        elif cap_billion > 1000: return 80      # 소형주
        else: return 40                          # 초소형 (유동성 리스크)

    def _calc_growth(self, fund: dict) -> float:
        """성장성 팩터 (0-100)"""
        score = 50
        rev_growth = fund.get("revenue_growth", 0)
        eps_growth = fund.get("eps_growth", 0)
        guidance = fund.get("guidance", "")

        if rev_growth > 30: score += 20
        elif rev_growth > 15: score += 10
        elif rev_growth > 5: score += 5
        elif rev_growth < -10: score -= 15

        if eps_growth > 30: score += 20
        elif eps_growth > 15: score += 10
        elif eps_growth < -20: score -= 15

        if "상향" in guidance: score += 10
        elif "하향" in guidance: score -= 10

        return max(0, min(100, score))
