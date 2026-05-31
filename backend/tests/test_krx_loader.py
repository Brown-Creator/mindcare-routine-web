"""
Tests for backend.data.krx_loader.

Uses an injected fake pykrx ``stock`` API so the record-assembly logic is tested
deterministically without any network. (A live-network sanity check lives in the
__main__ block and is not part of the offline suite.)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import asyncio
from dataclasses import dataclass

from backend.data.krx_loader import (KRXDataLoader, run_factor_research,
                                     dart_fundamentals_to_dict, _merge_fundamentals)
from backend.ml.factor_model import MultiFactorModel

RNG = np.random.default_rng(11)


class FakeStock:
    """pykrx.stock 의 최소 모형 — 한글 컬럼/인덱스 형태를 그대로 흉내."""

    def __init__(self, drift_by_ticker):
        self.drift = drift_by_ticker

    def get_market_ohlcv(self, start, end, ticker):
        n = 300
        idx = pd.date_range("2023-01-01", periods=n)
        r = RNG.normal(self.drift.get(ticker, 0.0), 0.02, n)
        c = 10000 * np.cumprod(1 + r)
        return pd.DataFrame({
            "시가": c, "고가": c * 1.01, "저가": c * 0.99,
            "종가": c, "거래량": RNG.integers(1e5, 1e6, n),
        }, index=idx)

    def get_market_fundamental(self, start, end, ticker):
        idx = pd.date_range(end, periods=1)
        return pd.DataFrame({"PER": [10.0], "PBR": [1.2], "EPS": [1500.0],
                             "BPS": [12000.0], "DIV": [2.5]}, index=idx)

    def get_market_cap(self, start, end, ticker):
        idx = pd.date_range(end, periods=1)
        return pd.DataFrame({"시가총액": [5e12]}, index=idx)


def _universe(n=12):
    return [{"ticker": f"{i:06d}", "name": f"S{i}",
             "sector": ["반도체", "금융", "바이오"][i % 3], "market": "KOSPI"}
            for i in range(n)]


def test_fetch_ohlcv_renames_columns():
    loader = KRXDataLoader(stock_api=FakeStock({}))
    df = loader.fetch_ohlcv("005930", "20230101", "20231231")
    assert set(["open", "high", "low", "close", "volume", "date"]).issubset(df.columns)
    assert len(df) == 300


def test_fetch_fundamentals_maps_keys():
    loader = KRXDataLoader(stock_api=FakeStock({}))
    f = loader.fetch_fundamentals("005930", "20231229")
    assert f["per"] == 10.0 and f["pbr"] == 1.2
    assert "roe" in f and f["roe"] > 0          # EPS/BPS 근사


def test_build_records_shape():
    loader = KRXDataLoader(stock_api=FakeStock({}))
    recs = loader.build_records(_universe(8), "20230101", "20231231")
    assert len(recs) == 8
    r = recs[0]
    for k in ("ticker", "name", "sector", "market_cap", "fundamentals", "price_data"):
        assert k in r
    assert r["market_cap"] == 5e12
    assert not r["price_data"].empty


def test_research_runner_detects_momentum_signal():
    # 드리프트가 높은 종목일수록 전방수익률이 높음 → IC 양수여야 함
    drift = {f"{i:06d}": 0.002 * (i - 6) for i in range(12)}
    loader = KRXDataLoader(stock_api=FakeStock(drift))
    recs = loader.build_records(_universe(12), "20230101", "20231231")
    res = run_factor_research(recs, MultiFactorModel(), forward_horizon=20)
    assert "error" not in res
    assert res["n_stocks"] >= 5
    assert res["cross_sectional_ic"] is not None


def test_fundamentals_empty_safe():
    class EmptyFundStock(FakeStock):
        def get_market_fundamental(self, start, end, ticker):
            return pd.DataFrame()                # KRX 엔드포인트가 빈 값 줄 때
    loader = KRXDataLoader(stock_api=EmptyFundStock({}))
    assert loader.fetch_fundamentals("005930", "20231229") == {}
    recs = loader.build_records(_universe(6), "20230101", "20231231")
    assert len(recs) == 6                        # 펀더멘털 없어도 조립 성공


@dataclass
class _FakeFund:
    per: float = 9.0
    pbr: float = 1.1
    roe: float = 15.0
    roa: float = 7.0
    debt_ratio: float = 40.0
    operating_margin: float = 12.0
    dividend_yield: float = 2.0
    revenue_growth: float = 18.0
    eps_growth: float = 22.0
    free_cash_flow: float = 3000.0
    market_cap: float = 50000.0    # 억원


class _FakeDart:
    async def get_fundamentals(self, ticker):
        return _FakeFund()


def test_dart_converter_drops_zeros():
    d = dart_fundamentals_to_dict(_FakeFund(per=0.0, pbr=1.1))
    assert "per" not in d          # 0 은 결측으로 제거
    assert d["pbr"] == 1.1 and d["roe"] == 15.0


def test_merge_prefers_primary():
    merged = _merge_fundamentals({"per": 8.0}, {"per": 9.0, "roe": 15.0})
    assert merged["per"] == 8.0    # primary(pykrx) 우선
    assert merged["roe"] == 15.0   # secondary(DART) 보강


def test_build_records_async_enriches_with_dart():
    class EmptyFundStock(FakeStock):
        def get_market_fundamental(self, start, end, ticker):
            return pd.DataFrame()                # pykrx 펀더멘털 결측 상황
    loader = KRXDataLoader(stock_api=EmptyFundStock({}), dart_client=_FakeDart())
    recs = asyncio.run(loader.build_records_async(_universe(6), "20230101", "20231231"))
    assert len(recs) == 6
    # DART 로 PER/ROE 가 채워져야 한다.
    assert recs[0]["fundamentals"].get("roe") == 15.0
    assert recs[0]["fundamentals"].get("per") == 9.0


if __name__ == "__main__":
    import sys, traceback
    # 오프라인 테스트
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}"); passed += 1
        except Exception:
            print(f"  FAIL  {fn.__name__}"); traceback.print_exc(); failed += 1
    print(f"\n{passed} passed, {failed} failed (offline)")

    # 라이브 네트워크 sanity (실패해도 무방)
    if "--live" in sys.argv:
        print("\n[LIVE] 실제 KRX 페치 시도...")
        try:
            loader = KRXDataLoader()
            if loader.available():
                df = loader.fetch_ohlcv("005930", "20240102", "20240131")
                print(f"[LIVE] 삼성전자 {len(df)}일 OHLCV, 최근 종가={df['close'].iloc[-1]:,.0f}")
        except Exception as e:
            print(f"[LIVE] skip: {e}")
    raise SystemExit(1 if failed else 0)
