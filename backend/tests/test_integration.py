"""
End-to-end integration test — proves the upgraded quant pipeline *composes*.

Unit tests verify each module in isolation; this test runs the full chain the
live system uses and asserts the pieces fit together and produce coherent output:

    universe → cross-sectional factor scores → alpha signals → ranking
             → portfolio optimization → risk analytics → position sizing
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.ml.factor_model import MultiFactorModel
from backend.engines.alpha_engine import AlphaEngine
from backend.engines.portfolio_engine import PortfolioOptimizer
from backend.engines.live_risk_engine import LiveRiskEngine
from backend.engines.universe_engine import UniverseScreener
from backend.models.stock import Position
from backend.quant import sizing as qsize

RNG = np.random.default_rng(31)


def _build_universe(n=10, days=300):
    """합성 가격 + 펀더멘털을 가진 records[] (드리프트가 매력도와 상관)."""
    recs, rets = [], {}
    drifts = np.linspace(-0.0008, 0.0012, n)
    for i in range(n):
        tk = f"{i:06d}"
        r = RNG.normal(drifts[i], 0.018, days)
        c = 100 * np.cumprod(1 + r)
        px = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=days).astype(str),
                           "open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
                           "volume": RNG.integers(1e5, 1e6, days)})
        recs.append({
            "ticker": tk, "name": f"종목{i}",
            "sector": ["반도체", "금융", "바이오", "자동차", "화학"][i % 5],
            "market_cap": float((i + 1) * 1e12),
            "fundamentals": {"per": 20 - i, "pbr": 2.0 - 0.1 * i, "roe": 5 + i,
                             "debt_ratio": 80 - 3 * i, "operating_margin": 5 + i,
                             "revenue_growth": -5 + 2 * i, "eps_growth": -5 + 2 * i,
                             "dividend_yield": 1 + 0.2 * i},
            "price_data": px,
        })
        rets[tk] = px["close"].pct_change().dropna().reset_index(drop=True)
    returns = pd.DataFrame(rets)
    return recs, returns


def test_full_pipeline_composes():
    recs, returns = _build_universe()

    # 1) 횡단면 팩터 스코어링 (퀀트 표준 경로)
    fm = MultiFactorModel(load_calibrated=False)
    scores = fm.score_universe(recs)
    assert len(scores) == len(recs)
    assert abs(np.mean([s.composite_z for s in scores])) < 0.5    # ~표준화됨
    score_map = {s.ticker: s for s in scores}

    # 2) 스크리너 멀티팩터 랭킹이 동일 점수와 일관
    screener = UniverseScreener()
    ranked = screener.rank_by_factors(recs, fm)
    assert ranked[0].score >= ranked[-1].score                    # 내림차순

    # 3) 알파 시그널 — 횡단면 팩터점수를 입력으로
    alpha_engine = AlphaEngine()
    signals = []
    for s in scores:
        sig = alpha_engine.generate_alpha(
            ticker=s.ticker, name=s.name,
            technical={"bottom_probability_score": 55, "trend_score": 55,
                       "momentum_score": 55},
            factor_score=s.composite_score,
            regime="sideways")
        assert 0 <= sig.alpha_score <= 100
        assert 0 <= sig.confidence <= 1
        signals.append(sig)
    picks = alpha_engine.get_top_picks(signals, n=3)
    assert isinstance(picks, list)

    # 4) 포트폴리오 최적화 (볼록 + 수축)
    po = PortfolioOptimizer()
    opt = po.optimize(returns, method="max_sharpe", max_weight=0.30)
    w = {a.ticker: a.weight for a in opt.allocations}
    assert abs(sum(w.values()) - 1.0) < 1e-3
    assert all(v <= 0.3001 for v in w.values())                   # 상한 준수
    assert opt.effective_n > 1                                     # 분산됨

    # 5) 리스크 분석 — 포지션 + 누적 수익률로 CVaR/스트레스
    risk = LiveRiskEngine()
    positions = []
    for s in scores[:5]:
        px = next(r["price_data"] for r in recs if r["ticker"] == s.ticker)
        last = float(px["close"].iloc[-1])
        positions.append(Position(ticker=s.ticker, name=s.name, avg_price=last,
                                  quantity=100, current_price=last,
                                  market_value=last * 100))
        for ret in returns[s.ticker].tail(120):
            risk.update_returns_history(s.ticker, float(ret))
    port_ret = (returns[[p.ticker for p in positions]].mean(axis=1)).tail(120)
    for r in port_ret:
        risk.update_portfolio_return(float(r))
    summary = risk.get_advanced_risk_summary(positions, portfolio_value=sum(p.market_value for p in positions))
    assert "cvar" in summary and "stress_tests" in summary
    assert summary["cvar"]["cvar_99_pct"] >= 0                     # CVaR 산출
    assert 0.1 <= summary["dynamic_position_scale"] <= 1.5
    # 섹터 충격이 실제 반영되는지(이전 버그: 미사용)
    sector_map = {p.ticker: next(r["sector"] for r in recs if r["ticker"] == p.ticker)
                  for p in positions}
    stress = risk.run_stress_tests(positions, sum(p.market_value for p in positions),
                                   sector_map=sector_map)
    assert len(stress) >= 4

    # 6) 포지션 사이징 — 상위 픽
    top = max(scores, key=lambda s: s.composite_z)
    vol = float(returns[top.ticker].std() * np.sqrt(252))
    size = qsize.size_position(alpha_score=score_map[top.ticker].composite_score,
                               expected_vol=vol, confidence=0.6, max_weight=0.20)
    assert 0 <= size["weight"] <= 0.20


def test_pipeline_handles_tiny_universe():
    """종목 4개(횡단면 통계 불안정) → 폴백 경로가 깨지지 않아야."""
    recs, returns = _build_universe(n=4, days=300)
    fm = MultiFactorModel(load_calibrated=False)
    scores = fm.score_universe(recs)                              # <5 → 절대스코어 폴백
    assert len(scores) == 4
    po = PortfolioOptimizer()
    opt = po.optimize(returns, method="risk_parity", max_weight=0.5)
    assert abs(sum(a.weight for a in opt.allocations) - 1.0) < 1e-3


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}"); passed += 1
        except Exception:
            print(f"  FAIL  {fn.__name__}"); traceback.print_exc(); failed += 1
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
