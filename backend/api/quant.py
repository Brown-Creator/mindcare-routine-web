"""
퀀트 분석 API — 새 계량 코어(backend.quant)의 산출물을 프론트로 노출.

대시보드가 "그럴듯한" 숫자가 아니라 실제로 계산된 퀀트 진단지표를 보여주도록:
  - 포트폴리오 최적화(볼록 max-Sharpe / 진짜 ERC) + 공분산 수축 강도
  - 위험분석(Historical + Cornish-Fisher VaR/CVaR, MDD)
  - 횡단면 팩터 점수(유니버스 상대)
  - 거래비용·시장충격 곡선(참여율 vs bp)
  - 백테스트 유의성(PSR/DSR)

데이터: 응답성을 위해 포지션 종목에 대해 '결정론적(시드 고정) 합성 수익률'을 생성해
실제 최적화기/지표를 돌린다. KRX 로더로 실수익률을 꽂으려면 한 줄 교체면 된다
(data_source 필드에 명시).
"""
from fastapi import APIRouter, Query
import asyncio
import logging
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from backend.quant import (
    optimization as qopt, covariance as qcov, metrics as qmet,
    validation as qval, cross_section as xs,
)
from backend.quant.costs import CostModel
from backend.engines.portfolio_engine import PortfolioOptimizer
from backend.ml.factor_model import MultiFactorModel

router = APIRouter(prefix="/api/quant", tags=["퀀트분석"])

_PPY = 252


def _fallback_tickers():
    return [("005930", "삼성전자"), ("000660", "SK하이닉스"), ("005490", "포스코홀딩스"),
            ("035420", "NAVER"), ("051910", "LG화학"), ("005380", "현대차"),
            ("105560", "KB금융"), ("068270", "셀트리온")]


def _position_tickers():
    """
    퀀트 데모용 바스켓. 현재 보유 포지션을 우선 사용하되, 포트폴리오 최적화가
    의미를 가지려면 최소 종목 수가 필요하므로(2종목 + 비중상한이면 제약 모순)
    대표 종목으로 보강해 최소 6종목을 보장한다.
    """
    tickers = []
    try:
        from backend.mock_data import MOCK_POSITIONS
        tickers = [(p.ticker, p.name) for p in MOCK_POSITIONS]
    except Exception:
        pass
    have = {t for t, _ in tickers}
    for t, n in _fallback_tickers():
        if len(tickers) >= 8:
            break
        if t not in have:
            tickers.append((t, n))
    return tickers if len(tickers) >= 6 else _fallback_tickers()


def _synthetic_returns(tickers, t=252, seed=20240101):
    """결정론적 다인자 수익률 패널(시드 고정) — 실제 최적화기 입력용."""
    rng = np.random.default_rng(seed)
    n = len(tickers)
    n_factors = 2
    loadings = rng.normal(0, 1, (n, n_factors))
    factors = rng.normal(0, 1, (t, n_factors))
    idio = rng.normal(0, 1, (t, n))
    raw = factors @ loadings.T + 1.3 * idio
    raw = raw / raw.std(axis=0)
    vols = np.linspace(0.012, 0.028, n)          # 종목별 일변동성 1.2%~2.8%
    drifts = np.linspace(0.0002, 0.0007, n)
    X = raw * vols + drifts
    return pd.DataFrame(X, columns=[tk for tk, _ in tickers])


def _compute_portfolio(method: str = "max_sharpe", max_weight: float = 0.30):
    """포트폴리오 최적화 결과 + 진단지표 (순수 함수 — 라우트/summary 공용)."""
    tickers = _position_tickers()
    rets = _synthetic_returns(tickers)
    name_map = {tk: nm for tk, nm in tickers}
    po = PortfolioOptimizer()
    res = po.optimize(rets, method=method, max_weight=max_weight)

    # 비교: naive 동일가중 vs 최적화
    eq_w = {c: 1 / len(rets.columns) for c in rets.columns}
    eq_metrics = po.calculate_metrics(rets, eq_w)
    opt_w = {a.ticker: a.weight for a in res.allocations}
    opt_metrics = po.calculate_metrics(rets, opt_w)

    return {
        "method": res.method,
        "data_source": "illustrative (deterministic synthetic returns)",
        "allocations": [
            {"ticker": a.ticker, "name": name_map.get(a.ticker, a.ticker),
             "weight": a.weight,
             "risk_contribution": None}
            for a in sorted(res.allocations, key=lambda x: -x.weight)
        ],
        "diagnostics": {
            "expected_return_pct": round(res.expected_return * 100, 2),
            "expected_vol_pct": round(res.expected_risk * 100, 2),
            "sharpe": res.sharpe_ratio,
            "diversification_ratio": res.diversification_ratio,
            "effective_n": res.effective_n,
            "ledoit_wolf_shrinkage": res.shrinkage,
        },
        "vs_equal_weight": {
            "optimized_sharpe": opt_metrics.get("sharpe_ratio"),
            "equal_weight_sharpe": eq_metrics.get("sharpe_ratio"),
        },
    }


def _compute_risk():
    """위험분석: Historical + Cornish-Fisher VaR/CVaR, 드로다운, 꼬리지표."""
    tickers = _position_tickers()
    rets = _synthetic_returns(tickers)
    # 동일가중 포트폴리오 수익률
    w = np.ones(len(rets.columns)) / len(rets.columns)
    port = rets.to_numpy() @ w
    summ = qmet.performance_summary(port, rf=0.035, periods_per_year=_PPY)
    return {
        "data_source": "illustrative (deterministic synthetic returns)",
        "var_cvar": {
            "var_95_historical_pct": summ["var_95_hist_pct"],
            "cvar_95_historical_pct": summ["cvar_95_hist_pct"],
            "var_99_cornish_fisher_pct": summ["var_99_cornish_fisher_pct"],
            "cvar_99_cornish_fisher_pct": summ["cvar_99_cornish_fisher_pct"],
        },
        "drawdown": {
            "max_drawdown_pct": summ["max_drawdown_pct"],
            "drawdown_duration": summ["drawdown_duration"],
            "recovery_duration": summ["recovery_duration"],
        },
        "distribution": {
            "skew": summ["skew"], "excess_kurtosis": summ["excess_kurtosis"],
            "tail_ratio": summ["tail_ratio"], "hit_rate": summ["hit_rate"],
        },
        "ratios": {
            "sharpe": summ["sharpe"], "sortino": summ["sortino"],
            "calmar": summ["calmar"], "omega": summ["omega"],
            "ann_return_pct": summ["ann_return_pct"], "ann_vol_pct": summ["ann_vol_pct"],
        },
    }


def _compute_costs(price: float = 70000, daily_vol: float = 0.022,
                   adv_shares: float = 1_000_000):
    """제곱근 시장충격 비용 곡선(참여율 vs 비용 bp)."""
    cm = CostModel()
    curve = []
    for part_pct in [0.5, 1, 2, 5, 10, 20, 30]:
        qty = adv_shares * part_pct / 100
        c = cm.trade_cost(price, qty, "buy", adv_shares=adv_shares, daily_vol=daily_vol)
        curve.append({
            "participation_pct": part_pct,
            "impact_bps": round(cm.market_impact_bps(qty, adv_shares, daily_vol), 2),
            "total_cost_bps": c["cost_bps"],
        })
    return {
        "model": "square-root market impact: η·σ·√(Q/ADV)",
        "params": {"commission_bps": cm.commission_bps, "sell_tax_bps": cm.sell_tax_bps,
                   "half_spread_bps": cm.half_spread_bps, "impact_coef": cm.impact_coef},
        "curve": curve,
    }


def _compute_significance(n_trials: int = 50):
    """백테스트 유의성: 동일 전략을 n_trials회 탐색했다고 가정한 PSR/DSR."""
    rng = np.random.default_rng(7)
    # 약한 양의 엣지를 가진 일수익률(예시)
    r = rng.normal(0.0006, 0.011, 504)
    psr = qval.probabilistic_sharpe_ratio(r, 0.0)
    dsr = qval.deflated_sharpe_ratio(r, n_trials=n_trials)
    return {
        "observed_annual_sharpe": round(qmet.sharpe_ratio(r, periods_per_year=_PPY), 3),
        "probabilistic_sharpe": round(float(psr), 4),
        "deflated_sharpe": dsr["deflated_sharpe"],
        "expected_max_sharpe_under_null": dsr["expected_max_sr"],
        "n_trials": dsr["n_trials"],
        "passes_at_95pct": dsr["passes"],
        "note": "DSR는 다중검정(여러 구성 시도)을 보정한 샤프 — 95% 미만이면 '운'일 수 있음",
    }


# ─── 라우트(얇은 래퍼) ───
@router.get("/portfolio")
async def quant_portfolio(method: str = Query("max_sharpe"),
                          max_weight: float = Query(0.30)):
    return _compute_portfolio(method, max_weight)


@router.get("/risk")
async def quant_risk():
    return _compute_risk()


@router.get("/costs")
async def quant_costs(price: float = Query(70000), daily_vol: float = Query(0.022),
                      adv_shares: float = Query(1_000_000)):
    return _compute_costs(price, daily_vol, adv_shares)


@router.get("/significance")
async def quant_significance(n_trials: int = Query(50)):
    return _compute_significance(n_trials)


@router.get("/summary")
async def quant_summary():
    """대시보드용 통합 응답(한 번에 모든 패널)."""
    return {
        "portfolio": _compute_portfolio(),
        "risk": _compute_risk(),
        "costs": _compute_costs(),
        "significance": _compute_significance(),
    }


# ─── 실데이터 팩터 리서치 (pykrx 라이브) ───
_LIVE_CACHE = {"data": None, "time": None, "ttl": timedelta(minutes=30)}

_LIVE_UNIVERSE = [
    {"ticker": "005930", "name": "삼성전자", "sector": "반도체"},
    {"ticker": "000660", "name": "SK하이닉스", "sector": "반도체"},
    {"ticker": "005380", "name": "현대차", "sector": "자동차"},
    {"ticker": "000270", "name": "기아", "sector": "자동차"},
    {"ticker": "105560", "name": "KB금융", "sector": "금융"},
    {"ticker": "055550", "name": "신한지주", "sector": "금융"},
    {"ticker": "035420", "name": "NAVER", "sector": "인터넷"},
    {"ticker": "051910", "name": "LG화학", "sector": "화학"},
    {"ticker": "006400", "name": "삼성SDI", "sector": "배터리"},
    {"ticker": "068270", "name": "셀트리온", "sector": "바이오"},
]


def _run_live_research(start: str, end: str, n: int) -> dict:
    """블로킹 pykrx 페치 + 횡단면 리서치 (스레드에서 실행)."""
    from backend.data.krx_loader import KRXDataLoader, run_factor_research
    loader = KRXDataLoader()
    if not loader.available():
        return {"error": "pykrx 미설치 — 실데이터 사용 불가", "data_source": "unavailable"}
    universe = _LIVE_UNIVERSE[:max(5, n)]
    records = loader.build_records(universe, start, end)
    if len(records) < 5:
        return {"error": f"실데이터 종목 부족 ({len(records)})", "fetched": len(records)}
    res = run_factor_research(records, MultiFactorModel(), forward_horizon=20)
    res["data_source"] = "live KRX (pykrx)"
    res["universe_size"] = len(records)
    res["window"] = f"{start}~{end}"
    # 종목별 점수 요약 첨부
    scores = MultiFactorModel().score_universe(records)
    res["scores"] = [
        {"ticker": s.ticker, "name": s.name, "composite_z": s.composite_z,
         "percentile": s.percentile, "momentum": s.momentum_score,
         "low_vol": s.low_vol_score, "value": s.value_score, "quality": s.quality_score}
        for s in scores
    ]
    return res


@router.get("/live-research")
async def quant_live_research(n: int = Query(8, ge=5, le=10),
                              days: int = Query(300, ge=120, le=500),
                              force: bool = Query(False)):
    """
    ★ 실제 KRX 데이터로 횡단면 팩터 리서치 (pykrx 라이브).

    네트워크 페치가 수초 걸리므로 30분 캐시. force=true 로 강제 갱신.
    펀더멘털은 pykrx-KRX 엔드포인트 이슈로 결측될 수 있어 가격기반 팩터로 폴백
    (DART 키 설정 시 build_records_async 로 보강 가능).
    """
    now = datetime.now()
    cache = _LIVE_CACHE
    if (not force and cache["data"] is not None and cache["time"]
            and now - cache["time"] < cache["ttl"]):
        return {**cache["data"], "cached": True}

    end = now.strftime("%Y%m%d")
    start = (now - timedelta(days=int(days * 1.5))).strftime("%Y%m%d")  # 거래일 여유
    try:
        res = await asyncio.to_thread(_run_live_research, start, end, n)
    except Exception as e:
        logger.warning(f"live-research 실패: {e}")
        return {"error": str(e), "data_source": "error"}
    cache["data"] = res
    cache["time"] = now
    return {**res, "cached": False}


def _run_recalibration(start: str, end: str, ts: str) -> dict:
    """블로킹 재보정(스레드 실행) — 실 KRX 데이터로 팩터 가중치 갱신."""
    from backend.data.krx_loader import KRXDataLoader
    from backend.jobs.recalibration import recalibrate_factor_weights
    loader = KRXDataLoader()
    if not loader.available():
        return {"error": "pykrx 미설치 — 재보정 불가"}
    fm = MultiFactorModel(load_calibrated=False)
    res = recalibrate_factor_weights(
        loader, _LIVE_UNIVERSE, fm, start, end,
        rebalance_every=20, lookback=250, forward=20,
        apply=True, persist=True, timestamp=ts)
    return res


@router.post("/recalibrate")
async def quant_recalibrate(days: int = Query(500, ge=350, le=900)):
    """
    ★ 실 KRX 데이터로 팩터 가중치 재보정(수동 트리거).

    다기간 IC 백테스트 → ICIR 비례 가중치 → data/factor_weights.json 저장.
    이후 생성되는 MultiFactorModel 은 이 가중치를 자동 로드한다.
    네트워크 페치가 오래 걸리므로(수~수십 초) 평소엔 스케줄러/수동으로만 실행.
    """
    now = datetime.now()
    end = now.strftime("%Y%m%d")
    start = (now - timedelta(days=int(days * 1.5))).strftime("%Y%m%d")
    try:
        res = await asyncio.to_thread(_run_recalibration, start, end, now.isoformat())
        return res
    except Exception as e:
        logger.warning(f"재보정 실패: {e}")
        return {"error": str(e)}
