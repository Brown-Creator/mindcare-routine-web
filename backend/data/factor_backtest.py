"""
다기간(multi-period) 팩터 IC 백테스트 + 팩터 가중치 자동 보정.

`MultiFactorModel.DEFAULT_WEIGHTS` 는 원래 직관으로 박아둔 값이었다. 진짜 퀀트 데스크는
팩터 가중치를 '데이터로' 정한다: 여러 리밸런싱 시점에 걸쳐 각 팩터의 횡단면 점수가
전방수익률을 얼마나 일관되게 예측했는지(IC/ICIR)를 측정하고, 그에 비례해 가중치를
부여한다.

이 모듈은 종목별 가격 히스토리를 1회만 받아 인메모리로 시점을 슬라이싱하므로(네트워크
호출 최소화) 실데이터/합성데이터 모두에서 효율적이고 결정론적으로 동작한다.

파이프라인
----------
    가격 히스토리(종목×전체기간)
        → 각 리밸런싱 시점에서 직전 lookback 구간으로 횡단면 팩터점수 산출
        → 그 시점의 forward(=다음 forward일) 수익률과 매칭
        → 팩터별 per-date IC 시계열  (quant.factor_research.rolling_factor_ic)
        → ICIR 비례 가중치 추정       (quant.factor_research.estimate_factor_weights)
        → MultiFactorModel.weights 보정
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from backend.quant import factor_research as fr

logger = logging.getLogger(__name__)

# score_universe 가 채우는 팩터별 0-100 점수 속성명
_FACTOR_ATTRS = {
    "value": "value_score", "quality": "quality_score", "momentum": "momentum_score",
    "low_vol": "low_vol_score", "size": "size_score", "growth": "growth_score",
}


def fetch_price_history(loader, universe: List[dict], start: str, end: str) -> Dict[str, pd.DataFrame]:
    """유니버스 전체의 OHLCV 를 1회씩 받아 {ticker: DataFrame} 로 반환."""
    out = {}
    for u in universe:
        df = loader.fetch_ohlcv(u["ticker"], start, end)
        if not df.empty:
            out[u["ticker"]] = df.reset_index(drop=True)
    return out


def run_factor_ic_backtest(
    price_history: Dict[str, pd.DataFrame],
    meta: Dict[str, dict],
    factor_model,
    rebalance_every: int = 20,
    lookback: int = 120,
    forward: int = 20,
    min_names: int = 5,
) -> dict:
    """
    다기간 팩터 IC 백테스트.

    price_history : {ticker: OHLCV DataFrame(정렬된 'close' 포함)}
    meta          : {ticker: {"sector","market_cap","fundamentals","name"}}
    rebalance_every : 리밸런싱 간격(거래일)
    lookback      : 팩터 산출에 쓰는 직전 구간 길이
    forward       : 전방수익률 horizon

    반환: ic_report(팩터별 mean IC/ICIR/t-stat), calibrated_weights, n_periods 등.
    """
    tickers = [t for t, df in price_history.items() if len(df) >= lookback + forward + 5]
    if len(tickers) < min_names:
        return {"error": f"유효 종목 부족 ({len(tickers)} < {min_names})"}

    # 공통 길이(가장 짧은 종목 기준)
    min_len = min(len(price_history[t]) for t in tickers)
    closes = pd.DataFrame({t: price_history[t]["close"].iloc[-min_len:].reset_index(drop=True)
                           for t in tickers})

    factor_panels: Dict[str, Dict[int, Dict[str, float]]] = {f: {} for f in _FACTOR_ATTRS}
    fwd_panel: Dict[int, Dict[str, float]] = {}

    # 리밸런싱 시점 순회 (lookback 확보 ~ forward 여유까지)
    t0, t1 = lookback, min_len - forward
    rebal_points = list(range(t0, t1, rebalance_every))
    for t in rebal_points:
        records = []
        for tk in tickers:
            sub = price_history[tk]
            window = sub.iloc[max(0, len(sub) - min_len + t - lookback): len(sub) - min_len + t]
            if len(window) < 60:
                continue
            m = meta.get(tk, {})
            records.append({
                "ticker": tk, "name": m.get("name", ""),
                "sector": m.get("sector", ""), "market_cap": m.get("market_cap", 0),
                "fundamentals": m.get("fundamentals", {}),
                "price_data": window.reset_index(drop=True),
            })
        if len(records) < min_names:
            continue

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            scores = factor_model.score_universe(records)

        # 팩터별 점수 패널 적재
        for s in scores:
            for fname, attr in _FACTOR_ATTRS.items():
                factor_panels[fname].setdefault(t, {})[s.ticker] = float(getattr(s, attr, 50.0))

        # 전방수익률
        fwd_panel[t] = {}
        for tk in tickers:
            c = closes[tk]
            if t + forward < len(c):
                fwd_panel[t][tk] = float(c.iloc[t + forward] / c.iloc[t] - 1.0)

    if len(fwd_panel) < 2:
        return {"error": "리밸런싱 시점 부족 (데이터/구간 확인)"}

    # dict → DataFrame[date×ticker]
    panels_df = {f: pd.DataFrame.from_dict(factor_panels[f], orient="index") for f in _FACTOR_ATTRS}
    fwd_df = pd.DataFrame.from_dict(fwd_panel, orient="index")

    ic_panel = fr.rolling_factor_ic(panels_df, fwd_df, method="spearman")
    ic_report = fr.factor_ic_report(ic_panel)
    weights = fr.estimate_factor_weights(ic_panel, shrinkage=0.6)

    return {
        "n_periods": len(fwd_panel),
        "n_stocks": len(tickers),
        "rebalance_every": rebalance_every,
        "lookback": lookback,
        "forward": forward,
        "ic_report": {f: {k: ic_report[f][k] for k in ("mean_ic", "icir", "t_stat", "hit_rate")}
                      for f in ic_report},
        "calibrated_weights": weights,
        "default_weights": dict(factor_model.weights),
    }


async def run_fundamental_factor_backtest(
    loader, universe: List[dict], factor_model,
    start: str, end: str,
    rebalance_every: int = 20, lookback: int = 250, forward: int = 20,
) -> dict:
    """
    ★ 펀더멘털 포함 다기간 IC 백테스트 (DART 연동).

    loader.build_records_async() 로 가격 + DART 펀더멘털(PER/PBR/ROE/부채/성장)을
    함께 받아, value/quality/growth 팩터까지 IC 백테스트에 진입시킨다. 가격기반
    팩터만 쓰던 run_factor_ic_backtest 의 상위 호환.

    주의(look-ahead): DART 는 '현재 시점' 펀더멘털을 주므로 과거 구간에 동일 적용된다.
    엄밀한 PIT(point-in-time) 백테스트를 하려면 분기별 과거 재무를 적재해야 한다
    (현 구현은 펀더멘털 팩터의 '횡단면 순위 안정성'을 가정한 근사).
    """
    records = await loader.build_records_async(universe, start, end)
    if len(records) < 5:
        return {"error": f"records 부족 ({len(records)})"}

    price_history = {r["ticker"]: r["price_data"] for r in records}
    meta = {r["ticker"]: {"name": r.get("name", ""), "sector": r.get("sector", ""),
                          "market_cap": r.get("market_cap", 0),
                          "fundamentals": r.get("fundamentals", {})}
            for r in records}
    result = run_factor_ic_backtest(price_history, meta, factor_model,
                                    rebalance_every=rebalance_every,
                                    lookback=lookback, forward=forward)
    if isinstance(result, dict) and "error" not in result:
        result["fundamentals_source"] = "DART (async)"
        result["pit_caveat"] = "현재 시점 펀더멘털을 과거에 동일 적용(근사)"
    return result


def calibrate_factor_model(factor_model, backtest_result: dict,
                           apply: bool = True) -> Dict[str, float]:
    """
    백테스트 결과의 데이터기반 가중치를 MultiFactorModel 에 적용.
    apply=False 면 가중치만 반환(적용 안 함).
    """
    weights = backtest_result.get("calibrated_weights")
    if not weights:
        return dict(factor_model.weights)
    # MultiFactorModel.weights 키와 정렬(누락 팩터는 기존값 유지)
    new_w = dict(factor_model.weights)
    for k, v in weights.items():
        if k in new_w:
            new_w[k] = v
    # 정규화
    tot = sum(new_w.values()) or 1.0
    new_w = {k: round(v / tot, 4) for k, v in new_w.items()}
    if apply:
        factor_model.weights = new_w
        logger.info(f"팩터 가중치 보정 적용: {new_w}")
    return new_w
