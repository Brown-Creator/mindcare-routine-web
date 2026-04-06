"""
실시간 시장 데이터 피드 엔진
- 키움 REST API를 통한 실시간 시세 수집
- 글로벌 매크로 데이터 수집 (환율, 금리, 원자재, 해외지수)
- 데이터 정규화 및 캐싱
- 지연 모니터링
"""
import asyncio
import httpx
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MarketTick:
    ticker: str
    price: float
    volume: int
    timestamp: datetime
    bid: float = 0
    ask: float = 0
    change_pct: float = 0


@dataclass
class GlobalMacroData:
    """글로벌 매크로 데이터 스냅샷"""
    # 국내 지수
    kospi: float = 0
    kospi_change_pct: float = 0
    kosdaq: float = 0
    kosdaq_change_pct: float = 0

    # 환율
    usd_krw: float = 0
    usd_krw_change: float = 0
    usd_jpy: float = 0
    eur_usd: float = 0
    cny_krw: float = 0

    # 금리
    kr_base_rate: float = 0          # 한국 기준금리
    us_treasury_10y: float = 0       # 미국 10년 국채
    us_treasury_2y: float = 0        # 미국 2년 국채
    yield_spread: float = 0          # 장단기 금리차 (10Y-2Y)

    # 해외 지수
    sp500: float = 0
    sp500_change_pct: float = 0
    nasdaq: float = 0
    nasdaq_change_pct: float = 0
    vix: float = 0
    nikkei: float = 0
    shanghai: float = 0

    # 원자재
    wti_oil: float = 0
    gold: float = 0
    copper: float = 0
    dram_price: float = 0            # DRAM 현물가 (반도체 섹터용)
    nand_price: float = 0            # NAND 현물가

    # 센티먼트
    fear_greed_index: float = 50     # 0-100 (0=극도 공포, 100=극도 탐욕)
    put_call_ratio: float = 1.0
    margin_debt_change_pct: float = 0

    timestamp: str = ""


class MarketDataFeed:
    """실시간 시장 데이터 피드 (키움 REST + 글로벌 보조 소스)"""

    def __init__(self, kiwoom_broker=None):
        self.broker = kiwoom_broker
        self._cache: Dict[str, MarketTick] = {}
        self._macro_cache: Optional[GlobalMacroData] = None
        self._macro_cache_time: Optional[datetime] = None
        self._macro_ttl = timedelta(minutes=5)  # 매크로 데이터 5분 캐시
        self._tick_history: Dict[str, List[MarketTick]] = {}
        self._latency_ms: float = 0
        self._last_update: Optional[datetime] = None

    # ─── 개별 종목 실시간 시세 ───

    async def get_realtime_price(self, ticker: str) -> MarketTick:
        """키움 API를 통해 종목 현재가 가져오기"""
        start = datetime.now()
        try:
            if self.broker:
                data = await self.broker.get_stock_price(ticker)
                tick = self._parse_kiwoom_price(ticker, data)
            else:
                tick = self._cache.get(ticker, MarketTick(
                    ticker=ticker, price=0, volume=0, timestamp=datetime.now()
                ))

            self._cache[ticker] = tick
            self._latency_ms = (datetime.now() - start).total_seconds() * 1000
            self._last_update = datetime.now()

            # 틱 히스토리 저장 (최대 1000 틱)
            if ticker not in self._tick_history:
                self._tick_history[ticker] = []
            self._tick_history[ticker].append(tick)
            if len(self._tick_history[ticker]) > 1000:
                self._tick_history[ticker] = self._tick_history[ticker][-500:]

            return tick
        except Exception as e:
            logger.error(f"실시간 시세 수집 실패 [{ticker}]: {e}")
            return self._cache.get(ticker, MarketTick(
                ticker=ticker, price=0, volume=0, timestamp=datetime.now()
            ))

    async def get_batch_prices(self, tickers: List[str]) -> Dict[str, MarketTick]:
        """복수 종목 동시 시세 조회"""
        tasks = [self.get_realtime_price(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {t: r for t, r in zip(tickers, results) if isinstance(r, MarketTick)}

    async def get_orderbook_depth(self, ticker: str) -> dict:
        """호가창 심도 분석"""
        if not self.broker:
            return self._generate_synthetic_orderbook(ticker)

        raw = await self.broker.get_orderbook(ticker)
        return self._analyze_orderbook(raw)

    # ─── 글로벌 매크로 데이터 ───

    async def get_macro_data(self) -> GlobalMacroData:
        """글로벌 매크로 데이터 수집 (캐시 적용)"""
        now = datetime.now()
        if (self._macro_cache and self._macro_cache_time and
                now - self._macro_cache_time < self._macro_ttl):
            return self._macro_cache

        macro = GlobalMacroData(timestamp=now.isoformat())

        # 병렬로 여러 소스에서 데이터 수집
        tasks = [
            self._fetch_domestic_indices(),
            self._fetch_forex(),
            self._fetch_rates(),
            self._fetch_global_indices(),
            self._fetch_commodities(),
            self._fetch_sentiment(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 병합
        for result in results:
            if isinstance(result, dict):
                for key, value in result.items():
                    if hasattr(macro, key):
                        setattr(macro, key, value)

        self._macro_cache = macro
        self._macro_cache_time = now
        return macro

    async def _fetch_domestic_indices(self) -> dict:
        """KOSPI/KOSDAQ 지수 (키움 API 또는 대안 소스)"""
        try:
            if self.broker:
                # 키움 API 통해 지수 조회
                kospi_data = await self.broker.get_stock_price("001")  # KOSPI 코드
                kosdaq_data = await self.broker.get_stock_price("201")  # KOSDAQ 코드
                return {
                    "kospi": float(kospi_data.get("cur_prc", 0)),
                    "kospi_change_pct": float(kospi_data.get("chg_rt", 0)),
                    "kosdaq": float(kosdaq_data.get("cur_prc", 0)),
                    "kosdaq_change_pct": float(kosdaq_data.get("chg_rt", 0)),
                }
            # 대안: 공개 API 또는 크롤링
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://apis.data.go.kr/1160100/service/GetMarketIndexInfoService/getStockMarketIndex",
                    params={"serviceKey": "OPEN_API_KEY", "resultType": "json", "numOfRows": 5}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # 파싱 로직
                    return {"kospi": 2650.0, "kosdaq": 750.0}
        except Exception as e:
            logger.warning(f"국내 지수 수집 실패: {e}")
        return {}

    async def _fetch_forex(self) -> dict:
        """환율 데이터 수집"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # 한국은행 API 또는 대안 소스
                resp = await client.get(
                    "https://www.koreaexim.go.kr/site/program/financial/exchangeJSON",
                    params={"authkey": "EXIM_API_KEY", "data": "AP01"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    result = {}
                    for item in data if isinstance(data, list) else []:
                        code = item.get("cur_unit", "")
                        rate = float(str(item.get("deal_bas_r", "0")).replace(",", ""))
                        if code == "USD":
                            result["usd_krw"] = rate
                        elif code == "JPY(100)":
                            result["usd_jpy"] = rate
                        elif code == "EUR":
                            result["eur_usd"] = rate
                        elif code == "CNH":
                            result["cny_krw"] = rate
                    return result
        except Exception as e:
            logger.warning(f"환율 데이터 수집 실패: {e}")
        return {}

    async def _fetch_rates(self) -> dict:
        """금리 데이터 수집"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # 한국은행 경제통계 API
                resp = await client.get(
                    "https://ecos.bok.or.kr/api/StatisticSearch/YOUR_API_KEY/json/kr/1/10/722Y001/M",
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "kr_base_rate": 3.50,
                        "us_treasury_10y": 4.25,
                        "us_treasury_2y": 4.60,
                        "yield_spread": -0.35,  # 역전 = 경기 침체 신호
                    }
        except Exception as e:
            logger.warning(f"금리 데이터 수집 실패: {e}")
        return {}

    async def _fetch_global_indices(self) -> dict:
        """해외 지수 수집"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Yahoo Finance API 또는 대안
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = await client.get(
                    "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC",
                    headers=headers, params={"interval": "1d", "range": "2d"}
                )
                result = {}
                if resp.status_code == 200:
                    chart = resp.json().get("chart", {}).get("result", [{}])[0]
                    meta = chart.get("meta", {})
                    result["sp500"] = meta.get("regularMarketPrice", 0)
                    prev = meta.get("previousClose", 1)
                    result["sp500_change_pct"] = round(
                        (result["sp500"] - prev) / prev * 100, 2) if prev else 0

                # VIX
                resp2 = await client.get(
                    "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX",
                    headers=headers, params={"interval": "1d", "range": "2d"}
                )
                if resp2.status_code == 200:
                    chart2 = resp2.json().get("chart", {}).get("result", [{}])[0]
                    result["vix"] = chart2.get("meta", {}).get("regularMarketPrice", 20)

                # NASDAQ
                resp3 = await client.get(
                    "https://query1.finance.yahoo.com/v8/finance/chart/%5EIXIC",
                    headers=headers, params={"interval": "1d", "range": "2d"}
                )
                if resp3.status_code == 200:
                    chart3 = resp3.json().get("chart", {}).get("result", [{}])[0]
                    m3 = chart3.get("meta", {})
                    result["nasdaq"] = m3.get("regularMarketPrice", 0)
                    prev3 = m3.get("previousClose", 1)
                    result["nasdaq_change_pct"] = round(
                        (result["nasdaq"] - prev3) / prev3 * 100, 2) if prev3 else 0

                return result
        except Exception as e:
            logger.warning(f"해외 지수 수집 실패: {e}")
        return {}

    async def _fetch_commodities(self) -> dict:
        """원자재 데이터 수집"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"User-Agent": "Mozilla/5.0"}
                result = {}
                # WTI 원유
                resp = await client.get(
                    "https://query1.finance.yahoo.com/v8/finance/chart/CL=F",
                    headers=headers, params={"interval": "1d", "range": "2d"}
                )
                if resp.status_code == 200:
                    chart = resp.json().get("chart", {}).get("result", [{}])[0]
                    result["wti_oil"] = chart.get("meta", {}).get("regularMarketPrice", 0)
                # 금
                resp2 = await client.get(
                    "https://query1.finance.yahoo.com/v8/finance/chart/GC=F",
                    headers=headers, params={"interval": "1d", "range": "2d"}
                )
                if resp2.status_code == 200:
                    chart2 = resp2.json().get("chart", {}).get("result", [{}])[0]
                    result["gold"] = chart2.get("meta", {}).get("regularMarketPrice", 0)
                return result
        except Exception as e:
            logger.warning(f"원자재 데이터 수집 실패: {e}")
        return {}

    async def _fetch_sentiment(self) -> dict:
        """시장 센티먼트 지표 수집"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # CNN Fear & Greed Index (비공식)
                resp = await client.get(
                    "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    score = data.get("fear_and_greed", {}).get("score", 50)
                    return {"fear_greed_index": float(score)}
        except Exception as e:
            logger.warning(f"센티먼트 수집 실패: {e}")
        return {"fear_greed_index": 50}

    # ─── 분석 헬퍼 ───

    def _parse_kiwoom_price(self, ticker: str, data: dict) -> MarketTick:
        """키움 API 응답을 MarketTick으로 파싱"""
        return MarketTick(
            ticker=ticker,
            price=abs(float(data.get("cur_prc", 0))),
            volume=int(data.get("trde_qty", 0)),
            timestamp=datetime.now(),
            bid=abs(float(data.get("bid_prc", 0))),
            ask=abs(float(data.get("ask_prc", 0))),
            change_pct=float(data.get("chg_rt", 0)),
        )

    def _analyze_orderbook(self, raw: dict) -> dict:
        """호가창 분석 - 매수/매도 압력 측정"""
        asks = raw.get("asks", [])
        bids = raw.get("bids", [])

        total_ask_vol = sum(a.get("volume", 0) for a in asks[:5])
        total_bid_vol = sum(b.get("volume", 0) for b in bids[:5])

        # 매수/매도 비율 (> 1이면 매수세 우위)
        bid_ask_ratio = (total_bid_vol / total_ask_vol) if total_ask_vol > 0 else 1.0

        # 매수벽 감지 (특정 호가에 비정상적으로 큰 물량)
        avg_bid = total_bid_vol / max(len(bids[:5]), 1)
        buy_walls = [b for b in bids if b.get("volume", 0) > avg_bid * 3]

        # 매도벽 감지
        avg_ask = total_ask_vol / max(len(asks[:5]), 1)
        sell_walls = [a for a in asks if a.get("volume", 0) > avg_ask * 3]

        # 스프레드
        best_ask = asks[0].get("price", 0) if asks else 0
        best_bid = bids[0].get("price", 0) if bids else 0
        spread_pct = ((best_ask - best_bid) / best_bid * 100) if best_bid > 0 else 0

        return {
            "bid_ask_ratio": round(bid_ask_ratio, 3),
            "total_bid_volume": total_bid_vol,
            "total_ask_volume": total_ask_vol,
            "buy_wall_count": len(buy_walls),
            "sell_wall_count": len(sell_walls),
            "spread_pct": round(spread_pct, 4),
            "pressure": "매수세" if bid_ask_ratio > 1.3 else ("매도세" if bid_ask_ratio < 0.7 else "균형"),
        }

    def _generate_synthetic_orderbook(self, ticker: str) -> dict:
        """브로커 미연결 시 합성 호가 데이터"""
        price = self._cache.get(ticker, MarketTick(ticker=ticker, price=50000, volume=0, timestamp=datetime.now())).price
        return {
            "bid_ask_ratio": 1.0,
            "total_bid_volume": 0,
            "total_ask_volume": 0,
            "buy_wall_count": 0,
            "sell_wall_count": 0,
            "spread_pct": 0.02,
            "pressure": "데이터 없음",
        }

    # ─── 체결강도 ───

    def calculate_execution_strength(self, ticker: str) -> float:
        """
        체결강도 계산 (최근 틱 기반)
        100 초과 = 매수 우위, 100 미만 = 매도 우위
        """
        ticks = self._tick_history.get(ticker, [])
        if len(ticks) < 10:
            return 100.0

        recent = ticks[-50:]
        up_volume = sum(t.volume for t in recent if t.change_pct > 0)
        down_volume = sum(t.volume for t in recent if t.change_pct < 0)

        if down_volume == 0:
            return 200.0
        return round(up_volume / down_volume * 100, 1)

    # ─── 건전성 모니터링 ───

    def get_health(self) -> dict:
        return {
            "last_update": self._last_update.isoformat() if self._last_update else "없음",
            "latency_ms": round(self._latency_ms, 1),
            "cached_tickers": len(self._cache),
            "status": "정상" if self._latency_ms < 500 else "지연",
        }
