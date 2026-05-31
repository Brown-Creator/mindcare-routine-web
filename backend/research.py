"""
재현 가능한 퀀트 리서치 진입점.

전체 워크플로를 하나의 명령으로 묶는다:
    유니버스 → 다기간 팩터 IC 백테스트 → ICIR 가중치 보정 →
    공분산 수축 + 볼록 최적화 → 리포트.

사용:
    python -m backend.research                 # 합성 유니버스(네트워크 불필요)
    python -m backend.research --live --n 10   # 실 KRX 데이터(pykrx)
    python -m backend.research --apply          # 보정 가중치를 영속화(다음 부팅 반영)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from backend.ml.factor_model import MultiFactorModel
from backend.engines.portfolio_engine import PortfolioOptimizer
from backend.data.factor_backtest import (
    fetch_price_history, run_factor_ic_backtest, calibrate_factor_model)


def _synthetic_universe(n=10, days=440, seed=7):
    rng = np.random.default_rng(seed)
    drifts = np.linspace(-0.0015, 0.0025, n)
    hist, meta = {}, {}
    for i in range(n):
        tk = f"{i:06d}"
        r = rng.normal(drifts[i], 0.012, days)
        c = 10000 * np.cumprod(1 + r)
        hist[tk] = pd.DataFrame({
            "date": pd.date_range("2022-06-01", periods=days).astype(str),
            "open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
            "volume": rng.integers(1e5, 1e6, days)})
        meta[tk] = {"name": f"종목{i}", "sector": ["반도체", "금융", "바이오", "자동차", "화학"][i % 5],
                    "market_cap": float((i + 1) * 1e12),
                    "fundamentals": {"per": 20 - i, "pbr": 2.0 - 0.1 * i, "roe": 5 + i,
                                     "debt_ratio": 80 - 3 * i, "revenue_growth": -5 + 2 * i,
                                     "eps_growth": -5 + 2 * i, "operating_margin": 5 + i}}
    return hist, meta


def _live_universe(n, days):
    from backend.data.krx_loader import KRXDataLoader
    from backend.api.quant import _LIVE_UNIVERSE
    loader = KRXDataLoader()
    if not loader.available():
        print("pykrx 미설치 — 합성 데이터로 대체합니다.", file=sys.stderr)
        return None, None
    universe = _LIVE_UNIVERSE[:n]
    now = datetime.now()
    end = now.strftime("%Y%m%d")
    start = (now - timedelta(days=int(days * 1.5))).strftime("%Y%m%d")
    hist = fetch_price_history(loader, universe, start, end)
    meta = {u["ticker"]: {"name": u["name"], "sector": u.get("sector", ""),
                          "market_cap": 0, "fundamentals": {}} for u in universe}
    return hist, meta


def _bar(label, value, width=28):
    filled = int(max(0.0, min(1.0, value)) * width)
    return f"{label:<10} {'█' * filled}{'·' * (width - filled)} {value:.3f}"


def main(argv=None):
    ap = argparse.ArgumentParser(description="퀀트 리서치 워크플로")
    ap.add_argument("--live", action="store_true", help="실 KRX 데이터(pykrx) 사용")
    ap.add_argument("--n", type=int, default=10, help="유니버스 종목 수")
    ap.add_argument("--days", type=int, default=440, help="조회 기간(일)")
    ap.add_argument("--apply", action="store_true", help="보정 가중치 영속화")
    args = ap.parse_args(argv)

    print("=" * 64)
    print(" KRX AutoTrader — 퀀트 리서치 리포트")
    print("=" * 64)

    if args.live:
        hist, meta = _live_universe(args.n, args.days)
        if hist is None:
            hist, meta = _synthetic_universe(args.n, args.days)
            source = "synthetic (fallback)"
        else:
            source = "live KRX (pykrx)"
    else:
        hist, meta = _synthetic_universe(args.n, args.days)
        source = "synthetic"
    print(f" 데이터: {source} | 종목: {len(hist)}")

    fm = MultiFactorModel(load_calibrated=False)

    # ── 1) 다기간 팩터 IC 백테스트 ──
    print("\n[1] 다기간 팩터 IC 백테스트")
    res = run_factor_ic_backtest(hist, meta, fm, rebalance_every=20,
                                 lookback=min(250, args.days - 60), forward=20)
    if "error" in res:
        print("   →", res["error"])
        return 1
    print(f"   기간 수={res['n_periods']}  종목={res['n_stocks']}")
    print("   팩터별 평균 IC / ICIR:")
    for f, rep in res["ic_report"].items():
        ic = rep.get("mean_ic") or 0.0
        icir = rep.get("icir")
        icir_s = f"{icir:+.2f}" if isinstance(icir, (int, float)) and np.isfinite(icir) else "  -"
        print(f"     {f:<9} IC={ic:+.3f}  ICIR={icir_s}  적중률={rep.get('hit_rate')}")

    # ── 2) 가중치 보정 ──
    print("\n[2] 데이터기반 팩터 가중치 (ICIR 비례, 수축)")
    weights = calibrate_factor_model(fm, res, apply=True)
    if args.apply:
        from backend.jobs.recalibration import persist_weights
        persist_weights(weights, meta={"source": source,
                                       "calibrated_at": datetime.now().isoformat()})
        print("   (영속화됨 → data/factor_weights.json)")
    for f, w in sorted(weights.items(), key=lambda x: -x[1]):
        print("   " + _bar(f, w))

    # ── 3) 횡단면 스코어 + 포트폴리오 최적화 ──
    print("\n[3] 횡단면 종합 스코어 상위 종목")
    recs = [{"ticker": t, "name": meta[t]["name"], "sector": meta[t]["sector"],
             "market_cap": meta[t]["market_cap"], "fundamentals": meta[t]["fundamentals"],
             "price_data": hist[t]} for t in hist]
    scores = fm.score_universe(recs)
    for s in scores[:5]:
        print(f"   {s.rank:>2}. {s.name:<8} z={s.composite_z:+.2f}  pct={s.percentile:>5.1f}")

    print("\n[4] 포트폴리오 최적화 (Ledoit-Wolf 수축 + 볼록 max-Sharpe)")
    returns = pd.DataFrame({t: hist[t]["close"].pct_change().dropna().reset_index(drop=True)
                            for t in hist})
    po = PortfolioOptimizer()
    opt = po.optimize(returns, method="max_sharpe", max_weight=0.30)
    print(f"   기대샤프(연율)={opt.sharpe_ratio}  분산화비율={opt.diversification_ratio}"
          f"  유효종목수={opt.effective_n}  수축강도={opt.shrinkage}")
    print("   목표 비중:")
    for a in sorted(opt.allocations, key=lambda x: -x.weight)[:6]:
        if a.weight > 0.001:
            print("   " + _bar(meta.get(a.ticker, {}).get("name", a.ticker), a.weight))

    print("\n" + "=" * 64)
    print(" 완료 — 모든 단계가 검증된 퀀트 코어(backend.quant)로 계산됨")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
