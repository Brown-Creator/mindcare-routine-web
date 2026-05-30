"""
KRX 실데이터 어댑터 + 팩터 리서치 러너.

목적: 퀀트 코어(score_universe / quantile_spread / IC)가 소비하는 records[] 포맷을
실제 KRX 데이터로 채운다. pykrx 가 있으면 실 OHLCV/시총/펀더멘털을 가져오고,
없거나 네트워크가 막히면 기본 유니버스로 graceful 폴백한다.

설계 노트
---------
- pykrx 의 ``stock`` 모듈을 주입 가능(``KRXDataLoader(stock_api=...)``)하게 해서
  네트워크 없이도 단위 테스트가 가능하다.
- ``get_market_fundamental`` 은 KRX 사이트 변경으로 종종 빈 값을 반환한다. 이때는
  펀더멘털 팩터(value/quality/growth)를 NaN 으로 두고 — 가격기반 팩터(momentum/
  low_vol/size)는 실데이터로 — 횡단면 점수를 계속 산출한다(코어가 NaN 을 중립 처리).
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# pykrx OHLCV 한글 컬럼 → 표준 영문
_OHLCV_MAP = {"시가": "open", "고가": "high", "저가": "low",
              "종가": "close", "거래량": "volume"}


def dart_fundamentals_to_dict(f) -> dict:
    """
    DART 클라이언트의 Fundamentals 데이터클래스 → score_universe 가 쓰는 dict.
    (duck-typing: f 의 속성만 읽으므로 DARTClient 에 대한 하드 의존 없음.)
    """
    if f is None:
        return {}
    g = lambda k, d=0.0: float(getattr(f, k, d) or d)
    out = {
        "per": g("per"), "pbr": g("pbr"), "psr": g("psr"),
        "ev_ebitda": g("ev_ebitda"), "dividend_yield": g("dividend_yield"),
        "roe": g("roe"), "roa": g("roa"),
        "operating_margin": g("operating_margin"), "net_margin": g("net_margin"),
        "debt_ratio": g("debt_ratio"), "current_ratio": g("current_ratio"),
        "revenue_growth": g("revenue_growth"), "eps_growth": g("eps_growth"),
        "free_cash_flow": g("free_cash_flow"),
    }
    # 0 값은 '결측'으로 보고 제거(횡단면 표준화에서 0이 가짜 신호가 되지 않도록)
    return {k: v for k, v in out.items() if v != 0.0}


def _merge_fundamentals(primary: dict, secondary: dict) -> dict:
    """primary(예: pykrx) 우선, 결측 필드는 secondary(예: DART)로 보강."""
    merged = dict(secondary or {})
    merged.update({k: v for k, v in (primary or {}).items() if v not in (None, 0, 0.0)})
    return merged


class KRXDataLoader:
    """KRX 데이터 로더 (pykrx 래퍼, 주입 가능)."""

    def __init__(self, stock_api=None, dart_client=None):
        self._stock = stock_api
        self._dart = dart_client          # DARTClient (선택) — 펀더멘털 보강용
        self._available: Optional[bool] = None

    def _api(self):
        if self._stock is None:
            from pykrx import stock          # 지연 임포트
            self._stock = stock
        return self._stock

    def available(self) -> bool:
        """pykrx 사용 가능 여부(미설치면 False)."""
        if self._available is None:
            try:
                self._api()
                self._available = True
            except Exception:
                self._available = False
        return self._available

    # ── 개별 페치 ──
    def fetch_ohlcv(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """일봉 OHLCV → 표준 컬럼 DataFrame(date,open,high,low,close,volume)."""
        try:
            raw = self._api().get_market_ohlcv(start, end, ticker)
            if raw is None or len(raw) == 0:
                return pd.DataFrame()
            df = raw.rename(columns=_OHLCV_MAP)
            df = df[[c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]].copy()
            df["date"] = pd.to_datetime(df.index).strftime("%Y-%m-%d")
            return df.reset_index(drop=True)
        except Exception as e:
            logger.warning(f"OHLCV 페치 실패 [{ticker}]: {e}")
            return pd.DataFrame()

    def fetch_fundamentals(self, ticker: str, date: str) -> dict:
        """
        펀더멘털(PER/PBR/EPS/BPS/DIV) → score_universe 가 쓰는 키로 매핑.
        KRX 엔드포인트가 빈 값을 주면 {} 반환(가격기반 팩터만으로 진행).
        """
        try:
            raw = self._api().get_market_fundamental(date, date, ticker)
            if raw is None or len(raw) == 0:
                return {}
            row = raw.iloc[-1]
            out = {
                "per": float(row.get("PER", 0) or 0),
                "pbr": float(row.get("PBR", 0) or 0),
                "eps": float(row.get("EPS", 0) or 0),
                "bps": float(row.get("BPS", 0) or 0),
                "dividend_yield": float(row.get("DIV", 0) or 0),
            }
            # ROE 근사: EPS/BPS (펀더멘털이 부분적으로만 올 때의 보강)
            if out["bps"] > 0 and out["eps"]:
                out["roe"] = round(out["eps"] / out["bps"] * 100, 2)
            return out
        except Exception as e:
            logger.warning(f"펀더멘털 페치 실패 [{ticker}]: {e}")
            return {}

    def fetch_market_cap(self, ticker: str, date: str) -> float:
        try:
            raw = self._api().get_market_cap(date, date, ticker)
            if raw is None or len(raw) == 0:
                return 0.0
            return float(raw.iloc[-1].get("시가총액", 0) or 0)
        except Exception as e:
            logger.warning(f"시총 페치 실패 [{ticker}]: {e}")
            return 0.0

    # ── records[] 조립 ──
    def build_records(self, universe: List[dict], start: str, end: str,
                      as_of: Optional[str] = None) -> List[dict]:
        """
        유니버스(메타) → score_universe/rank_by_factors 가 소비하는 records[] 조립.

        universe : [{"ticker","name","sector","market"}, ...]
        start,end: OHLCV 조회 구간 ('YYYYMMDD').
        as_of    : 펀더멘털/시총 기준일(미지정 시 end).
        """
        as_of = as_of or end
        records = []
        for u in universe:
            tk = u["ticker"]
            px = self.fetch_ohlcv(tk, start, end)
            if px.empty:
                continue
            fund = self.fetch_fundamentals(tk, as_of)
            mcap = self.fetch_market_cap(tk, as_of)
            if mcap <= 0:
                # 시총 폴백: 메타에 있으면 사용
                mcap = u.get("market_cap", 0)
            records.append({
                "ticker": tk, "name": u.get("name", ""),
                "sector": u.get("sector", ""), "market": u.get("market", "KOSPI"),
                "market_cap": mcap, "fundamentals": fund, "price_data": px,
            })
        logger.info(f"records 조립 완료: {len(records)}/{len(universe)} 종목")
        return records

    async def build_records_async(self, universe: List[dict], start: str, end: str,
                                  as_of: Optional[str] = None) -> List[dict]:
        """
        ★ DART 펀더멘털 보강 버전(비동기).

        pykrx 의 get_market_fundamental 이 빈 값을 줄 때(KRX 엔드포인트 이슈) DART
        클라이언트로 PER/PBR/ROE/ROA/부채비율/성장률 등을 채운다. DART 키가 없으면
        DARTClient 가 업종 기본값을 반환하므로 최소한의 펀더멘털은 확보된다.
        """
        as_of = as_of or end
        records = []
        for u in universe:
            tk = u["ticker"]
            px = self.fetch_ohlcv(tk, start, end)
            if px.empty:
                continue
            pykrx_fund = self.fetch_fundamentals(tk, as_of)
            dart_fund = {}
            if self._dart is not None:
                try:
                    f = await self._dart.get_fundamentals(tk)
                    dart_fund = dart_fundamentals_to_dict(f)
                except Exception as e:
                    logger.warning(f"DART 펀더멘털 실패 [{tk}]: {e}")
            fund = _merge_fundamentals(pykrx_fund, dart_fund)

            mcap = self.fetch_market_cap(tk, as_of)
            if mcap <= 0:
                # DART market_cap(억원) → 원 환산, 없으면 메타
                dmc = float(getattr(f, "market_cap", 0) or 0) if dart_fund else 0
                mcap = dmc * 1e8 if dmc else u.get("market_cap", 0)
            records.append({
                "ticker": tk, "name": u.get("name", ""),
                "sector": u.get("sector", ""), "market": u.get("market", "KOSPI"),
                "market_cap": mcap, "fundamentals": fund, "price_data": px,
            })
        logger.info(f"records(+DART) 조립 완료: {len(records)}/{len(universe)} 종목")
        return records


def run_factor_research(records: List[dict], factor_model,
                        forward_horizon: int = 20,
                        n_quantiles: int = 5) -> dict:
    """
    실데이터 records 로 횡단면 팩터 점수 → 분위 스프레드/IC 백테스트(단일 시점).

    각 종목의 price_data 마지막 ``forward_horizon`` 구간을 '전방수익률'로 떼어내,
    그 이전 데이터로 매긴 횡단면 composite 점수가 실제 전방수익률을 예측했는지
    (IC, 분위 스프레드 단조성)를 측정한다. 진짜 팩터라면 IC>0, 분위수익이 단조 증가.
    """
    from backend.quant import factor_research as fr

    # 전방수익률: 각 종목 마지막 h일 수익률
    fwd_ret = {}
    sliced = []
    for r in records:
        px = r["price_data"]
        if px is None or len(px) <= forward_horizon + 60:
            continue
        c = px["close"]
        fwd = float(c.iloc[-1] / c.iloc[-1 - forward_horizon] - 1.0)
        fwd_ret[r["ticker"]] = fwd
        r2 = dict(r)
        r2["price_data"] = px.iloc[:-forward_horizon].reset_index(drop=True)  # 룩어헤드 방지
        sliced.append(r2)

    if len(sliced) < 5:
        return {"error": "유효 종목 부족 (최소 5)"}

    # 펀더멘털이 전부 결측이면(KRX 엔드포인트 이슈 등) value/quality/growth 그룹이
    # all-NaN 이 되어 numpy 가 'Mean of empty slice' 경고를 낸다 — 가격기반 팩터로
    # 폴백하는 정상 동작이므로 이 경계에서만 조용히 처리한다.
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        scores = factor_model.score_universe(sliced)
    score_map = {s.ticker: s.composite_z for s in scores}

    common = [t for t in score_map if t in fwd_ret]
    s_vec = pd.Series({t: score_map[t] for t in common})
    r_vec = pd.Series({t: fwd_ret[t] for t in common})

    from backend.quant.cross_section import information_coefficient
    ic = information_coefficient(s_vec.values, r_vec.values, method="spearman")

    # 단일 시점 분위 스프레드
    panel_scores = pd.DataFrame([s_vec])
    panel_fwd = pd.DataFrame([r_vec])
    qb = fr.quantile_spread(panel_scores, panel_fwd,
                            n_quantiles=min(n_quantiles, max(2, len(common) // 3)))

    return {
        "n_stocks": len(common),
        "forward_horizon": forward_horizon,
        "cross_sectional_ic": round(float(ic), 4) if np.isfinite(ic) else None,
        "quantile_returns": qb.quantile_returns,
        "long_short_spread": qb.long_short_mean,
        "monotonicity": qb.monotonicity,
        "top_picks": [s.ticker for s in scores[:5]],
    }
