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

from backend.quant import cross_section as xs

logger = logging.getLogger(__name__)


def _to100(z) -> float:
    """횡단면 z-score를 0-100 점수로 환산(정규 CDF). z=0 → 50점."""
    from scipy import stats as _st
    if z is None or not np.isfinite(z):
        return 50.0
    return float(_st.norm.cdf(z) * 100)

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
    composite_score: float = 0    # 종합 점수 (0-100, 호환 유지)
    composite_z: float = 0        # 횡단면 종합 z-score (퀀트 표준)
    percentile: float = 0         # 유니버스 내 백분위 (0-100)
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

    def __init__(self, weights: Dict[str, float] = None,
                 load_calibrated: bool = True):
        if weights:
            self.weights = dict(weights)
        else:
            # 재보정 잡이 저장한 데이터기반 가중치가 있으면 우선 사용.
            calibrated = None
            if load_calibrated:
                try:
                    from backend.jobs.recalibration import load_persisted_weights
                    persisted = load_persisted_weights()
                    if persisted:
                        # DEFAULT 키에 맞춰 병합(누락 팩터는 기본값 유지)
                        calibrated = self.DEFAULT_WEIGHTS.copy()
                        for k, v in persisted.items():
                            if k in calibrated:
                                calibrated[k] = v
                        tot = sum(calibrated.values()) or 1.0
                        calibrated = {k: v / tot for k, v in calibrated.items()}
                        logger.info(f"보정된 팩터 가중치 로드: {calibrated}")
                except Exception as e:
                    logger.debug(f"보정 가중치 로드 건너뜀: {e}")
            self.weights = calibrated or self.DEFAULT_WEIGHTS.copy()
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

    # ──────────────────────────────────────────────────────────────────
    # ★★★ 횡단면 팩터 스코어링 (퀀트 표준) ★★★
    #
    # score_stock() 은 절대 임계값(PER<8 → +25점)을 쓴다. 이는 시장 전체가
    # 싸지거나 비싸질 때 무력하고, 팩터 간 스케일이 달라 비교 불가능하다.
    # 진짜 퀀트 팩터 모델은 매 시점 '동종 유니버스 내 상대 순위'로 표준화한다:
    #     winsorize → rank/z-score → 섹터·사이즈 중립화 → 가중 결합
    # 아래 score_universe() 가 그 정석 파이프라인이다.
    # ──────────────────────────────────────────────────────────────────
    def _raw_factor_panel(self, records: List[dict]) -> pd.DataFrame:
        """레코드 리스트에서 원시(raw) 팩터값 패널(종목×팩터)을 추출."""
        rows = {}
        for r in records:
            tk = r["ticker"]
            fund = r.get("fundamentals", {}) or {}
            px = r.get("price_data")
            mcap = r.get("market_cap", 0) or 0

            per = fund.get("per", 0) or 0
            pbr = fund.get("pbr", 0) or 0
            row = {
                # Value: 수익률(yield) 형태로 — 높을수록 저평가(=매력)
                "earnings_yield": (1.0 / per) if per > 0 else np.nan,
                "book_yield": (1.0 / pbr) if pbr > 0 else np.nan,
                "dividend_yield": fund.get("dividend_yield", np.nan),
                # Quality
                "roe": fund.get("roe", np.nan),
                "roa": fund.get("roa", np.nan),
                "operating_margin": fund.get("operating_margin", np.nan),
                "debt_ratio": fund.get("debt_ratio", np.nan),   # 낮을수록 좋음 → 부호 반전
                # Growth
                "revenue_growth": fund.get("revenue_growth", np.nan),
                "eps_growth": fund.get("eps_growth", np.nan),
                # Size: log 시총 (소형주 프리미엄 → 부호 반전)
                "log_mktcap": np.log(mcap) if mcap > 0 else np.nan,
            }
            # 가격 기반 팩터
            row["momentum_12_1"] = self._momentum_12_1(px)
            row["realized_vol"] = self._realized_vol(px)
            rows[tk] = row
        return pd.DataFrame.from_dict(rows, orient="index")

    @staticmethod
    def _momentum_12_1(px) -> float:
        """12-1 모멘텀: 최근 1개월을 제외한 12개월 수익률(단기 반전 회피)."""
        if px is None or len(px) < 240:
            return np.nan
        c = px["close"]
        return float(c.iloc[-21] / c.iloc[-240] - 1.0)

    @staticmethod
    def _realized_vol(px) -> float:
        """최근 60일 실현변동성(연율)."""
        if px is None or len(px) < 20:
            return np.nan
        ret = px["close"].pct_change().dropna().tail(60)
        if len(ret) < 5:
            return np.nan
        return float(ret.std() * np.sqrt(252))

    def score_universe(self, records: List[dict],
                       sector_neutralize: bool = True,
                       size_neutralize: bool = True) -> List[FactorScore]:
        """
        유니버스 전체를 횡단면 표준화해 종합 팩터 점수를 산출(퀀트 표준 경로).

        records: [{"ticker","name","fundamentals":{...},"price_data":DataFrame,
                   "market_cap":float,"sector":str}, ...]

        반환: composite_z(횡단면 z), percentile(0-100), composite_score(0-100 환산)을
        채운 FactorScore 리스트(종합점수 내림차순).
        """
        if not records:
            return []
        if len(records) < 5:
            # 횡단면 통계가 불안정 → 종목별 절대 스코어로 폴백
            return self._fallback_absolute(records)

        panel = self._raw_factor_panel(records)
        tickers = list(panel.index)
        sectors = pd.Series({r["ticker"]: r.get("sector", "") for r in records})
        log_mcap = panel["log_mktcap"]

        groups = sectors if sector_neutralize else None
        exposures = (pd.DataFrame({"size": log_mcap})
                     if size_neutralize and log_mcap.notna().any() else None)

        def std(col, higher_is_better=True, neutral=True):
            return xs.standardize_factor(
                panel[col], method="rank", winsor="mad",
                exposures=exposures if neutral else None,
                groups=groups if neutral else None,
                higher_is_better=higher_is_better,
            )

        # ─ 그룹별 횡단면 z (구성요소 평균 후 재표준화) ─
        value_z = xs.zscore(pd.concat([std("earnings_yield"), std("book_yield"),
                                       std("dividend_yield")], axis=1).mean(axis=1))
        quality_z = xs.zscore(pd.concat([std("roe"), std("roa"),
                                         std("operating_margin"),
                                         std("debt_ratio", higher_is_better=False)],
                                        axis=1).mean(axis=1))
        momentum_z = std("momentum_12_1")
        lowvol_z = std("realized_vol", higher_is_better=False)
        growth_z = xs.zscore(pd.concat([std("revenue_growth"), std("eps_growth")],
                                       axis=1).mean(axis=1))
        # 사이즈는 자기 자신을 중립화하지 않음
        size_z = xs.standardize_factor(panel["log_mktcap"], method="rank",
                                       winsor="mad", higher_is_better=False)

        factor_zs = {
            "value": value_z, "quality": quality_z, "momentum": momentum_z,
            "low_vol": lowvol_z, "size": size_z, "growth": growth_z,
        }
        composite = xs.combine_factors(factor_zs, self.weights)

        # 0-100 환산(정규 CDF) + 백분위
        from scipy import stats as _st
        pct = composite.rank(pct=True) * 100
        score_100 = pd.Series(_st.norm.cdf(composite) * 100, index=composite.index)

        results = []
        name_map = {r["ticker"]: r.get("name", "") for r in records}
        for tk in tickers:
            fs = FactorScore(
                ticker=tk, name=name_map.get(tk, ""),
                value_score=round(float(_to100(value_z.get(tk))), 1),
                quality_score=round(float(_to100(quality_z.get(tk))), 1),
                momentum_score=round(float(_to100(momentum_z.get(tk))), 1),
                low_vol_score=round(float(_to100(lowvol_z.get(tk))), 1),
                size_score=round(float(_to100(size_z.get(tk))), 1),
                growth_score=round(float(_to100(growth_z.get(tk))), 1),
                composite_z=round(float(composite.get(tk, 0.0)), 3),
                composite_score=round(float(score_100.get(tk, 50.0)), 1),
                percentile=round(float(pct.get(tk, 50.0)), 1),
            )
            fs.factors_detail = {
                "value_z": fs.value_score, "quality_z": fs.quality_score,
                "momentum_z": fs.momentum_score, "low_vol_z": fs.low_vol_score,
                "size_z": fs.size_score, "growth_z": fs.growth_score,
            }
            results.append(fs)

        results.sort(key=lambda s: s.composite_z, reverse=True)
        for i, s in enumerate(results):
            s.rank = i + 1
        self._universe_scores = results
        return results

    def compute_factor_ic(self, scores: List[FactorScore],
                          forward_returns: Dict[str, float]) -> Dict[str, float]:
        """
        직전 리밸런싱의 팩터 점수와 실현 전방수익률 간 IC(정보계수)를 계산.
        팩터가 실제로 수익을 예측하는지에 대한 핵심 진단지표.
        """
        tickers = [s.ticker for s in scores if s.ticker in forward_returns]
        if len(tickers) < 3:
            return {}
        sc = [next(s.composite_z for s in scores if s.ticker == t) for t in tickers]
        fr = [forward_returns[t] for t in tickers]
        ic = xs.information_coefficient(sc, fr, method="spearman")
        return {"composite_ic": round(ic, 4), "n": len(tickers)}

    def _fallback_absolute(self, records: List[dict]) -> List[FactorScore]:
        """유니버스가 작을 때 종목별 절대 스코어로 폴백."""
        out = []
        for r in records:
            fs = self.score_stock(r["ticker"], r.get("fundamentals", {}),
                                  r.get("price_data", pd.DataFrame()),
                                  market_cap=r.get("market_cap", 0))
            fs.composite_z = round((fs.composite_score - 50) / 15.0, 3)
            fs.percentile = fs.composite_score
            out.append(fs)
        out.sort(key=lambda s: s.composite_score, reverse=True)
        for i, s in enumerate(out):
            s.rank = i + 1
        return out

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
