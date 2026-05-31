"""
유니버스 스크리닝 엔진
- 전체 KRX 종목 자동 스캔
- 멀티팩터 랭킹
- 섹터 로테이션
- 유동성/시가총액 필터
"""
import logging
from typing import Dict, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class ScreeningResult:
    ticker: str
    name: str
    sector: str = ""
    market: str = "KOSPI"
    market_cap: float = 0
    score: float = 0
    rank: int = 0
    passed_filters: List[str] = field(default_factory=list)
    signals: Dict = field(default_factory=dict)

@dataclass
class ScreeningFilter:
    min_market_cap: float = 3000e8     # 최소 시가총액 3000억
    min_avg_volume: int = 100000       # 최소 일평균 거래량 10만주
    max_per: float = 50                # 최대 PER
    min_roe: float = 0                 # 최소 ROE
    exclude_sectors: List[str] = field(default_factory=list)
    include_markets: List[str] = field(default_factory=lambda: ["KOSPI", "KOSDAQ"])

class UniverseScreener:
    """KRX 전체 유니버스 스크리닝"""

    def __init__(self, broker=None):
        self.broker = broker
        self._universe: List[dict] = []
        self._screened: List[ScreeningResult] = []

    async def load_universe(self) -> List[dict]:
        """KRX 전체 종목 로드"""
        try:
            import pandas as pd
            # KRX 상장종목 목록 (krx 모듈 또는 공개 API)
            try:
                import pykrx
                from pykrx import stock
                tickers = stock.get_market_ticker_list()
                universe = []
                for t in tickers[:500]:  # 성능을 위해 제한
                    name = stock.get_market_ticker_name(t)
                    universe.append({"ticker": t, "name": name})
                self._universe = universe
                return universe
            except ImportError:
                pass

            # 대안: 하드코딩된 주요 종목
            self._universe = self._get_default_universe()
            return self._universe
        except Exception as e:
            logger.error(f"유니버스 로드 실패: {e}")
            self._universe = self._get_default_universe()
            return self._universe

    def screen(self, universe: List[dict] = None,
               filters: ScreeningFilter = None) -> List[ScreeningResult]:
        """필터 기반 스크리닝"""
        filters = filters or ScreeningFilter()
        stocks = universe or self._universe

        results = []
        for stock in stocks:
            passed = []

            # 시가총액
            cap = stock.get("market_cap", 0)
            if cap > 0 and cap < filters.min_market_cap:
                continue
            if cap >= filters.min_market_cap:
                passed.append(f"시총 {cap/1e8:.0f}억")

            # 거래량
            vol = stock.get("avg_volume", 0)
            if vol > 0 and vol < filters.min_avg_volume:
                continue
            if vol >= filters.min_avg_volume:
                passed.append(f"거래량 {vol:,}")

            # PER
            per = stock.get("per", 0)
            if 0 < per > filters.max_per:
                continue

            # 시장
            market = stock.get("market", "KOSPI")
            if market not in filters.include_markets:
                continue

            # 섹터 제외
            sector = stock.get("sector", "")
            if sector in filters.exclude_sectors:
                continue

            results.append(ScreeningResult(
                ticker=stock.get("ticker", ""),
                name=stock.get("name", ""),
                sector=sector, market=market,
                market_cap=cap,
                passed_filters=passed,
            ))

        self._screened = results
        return results

    def rank_by_factors(self, records: List[dict], factor_model,
                        top_n: int = None) -> List[ScreeningResult]:
        """
        ★ 진짜 멀티팩터 랭킹 (이전 screen()은 필터링만 하고 랭킹은 미구현이었음).

        factor_model.score_universe() 로 유니버스를 횡단면 표준화 채점한 뒤
        composite_z(유니버스 상대 점수) 내림차순으로 랭킹한다.

        records: [{"ticker","name","sector","market_cap","fundamentals","price_data"}, ...]
        반환: composite_score/percentile/세부 팩터점수가 채워진 ScreeningResult 리스트.
        """
        if not records or factor_model is None:
            return []
        scores = factor_model.score_universe(records)
        meta = {r["ticker"]: r for r in records}
        results = []
        for s in scores:
            r = meta.get(s.ticker, {})
            results.append(ScreeningResult(
                ticker=s.ticker, name=s.name or r.get("name", ""),
                sector=r.get("sector", ""), market=r.get("market", "KOSPI"),
                market_cap=r.get("market_cap", 0),
                score=s.composite_score, rank=s.rank,
                signals={
                    "composite_z": s.composite_z, "percentile": s.percentile,
                    **s.factors_detail,
                },
            ))
        self._screened = results
        return results[:top_n] if top_n else results

    def get_sector_rotation(self, sector_scores: Dict[str, float]) -> List[str]:
        """섹터 로테이션 기반 추천 섹터"""
        sorted_sectors = sorted(sector_scores.items(), key=lambda x: x[1], reverse=True)
        # 상위 30% 섹터
        n = max(1, len(sorted_sectors) // 3)
        return [s[0] for s in sorted_sectors[:n]]

    def _get_default_universe(self) -> List[dict]:
        """기본 KRX 주요 종목"""
        return [
            {"ticker": "005930", "name": "삼성전자", "sector": "반도체", "market": "KOSPI", "market_cap": 400e12},
            {"ticker": "000660", "name": "SK하이닉스", "sector": "반도체", "market": "KOSPI", "market_cap": 120e12},
            {"ticker": "005490", "name": "포스코홀딩스", "sector": "철강", "market": "KOSPI", "market_cap": 25e12},
            {"ticker": "035420", "name": "NAVER", "sector": "인터넷", "market": "KOSPI", "market_cap": 35e12},
            {"ticker": "051910", "name": "LG화학", "sector": "화학", "market": "KOSPI", "market_cap": 30e12},
            {"ticker": "006400", "name": "삼성SDI", "sector": "배터리", "market": "KOSPI", "market_cap": 35e12},
            {"ticker": "035720", "name": "카카오", "sector": "인터넷", "market": "KOSPI", "market_cap": 18e12},
            {"ticker": "005380", "name": "현대차", "sector": "자동차", "market": "KOSPI", "market_cap": 45e12},
            {"ticker": "000270", "name": "기아", "sector": "자동차", "market": "KOSPI", "market_cap": 35e12},
            {"ticker": "068270", "name": "셀트리온", "sector": "바이오", "market": "KOSPI", "market_cap": 25e12},
            {"ticker": "105560", "name": "KB금융", "sector": "금융", "market": "KOSPI", "market_cap": 25e12},
            {"ticker": "055550", "name": "신한지주", "sector": "금융", "market": "KOSPI", "market_cap": 20e12},
            {"ticker": "028260", "name": "삼성물산", "sector": "건설", "market": "KOSPI", "market_cap": 20e12},
            {"ticker": "066570", "name": "LG전자", "sector": "가전", "market": "KOSPI", "market_cap": 15e12},
            {"ticker": "003550", "name": "LG", "sector": "지주", "market": "KOSPI", "market_cap": 12e12},
            {"ticker": "034730", "name": "SK", "sector": "지주", "market": "KOSPI", "market_cap": 15e12},
            {"ticker": "096770", "name": "SK이노베이션", "sector": "에너지", "market": "KOSPI", "market_cap": 12e12},
            {"ticker": "012330", "name": "현대모비스", "sector": "자동차부품", "market": "KOSPI", "market_cap": 20e12},
            {"ticker": "003670", "name": "포스코퓨처엠", "sector": "소재", "market": "KOSPI", "market_cap": 10e12},
            {"ticker": "247540", "name": "에코프로비엠", "sector": "배터리소재", "market": "KOSDAQ", "market_cap": 15e12},
            {"ticker": "086790", "name": "하나금융지주", "sector": "금융", "market": "KOSPI", "market_cap": 18e12},
            {"ticker": "032830", "name": "삼성생명", "sector": "보험", "market": "KOSPI", "market_cap": 14e12},
            {"ticker": "015760", "name": "한국전력", "sector": "유틸리티", "market": "KOSPI", "market_cap": 16e12},
            {"ticker": "034020", "name": "두산에너빌리티", "sector": "원전", "market": "KOSPI", "market_cap": 12e12},
            {"ticker": "009150", "name": "삼성전기", "sector": "전자부품", "market": "KOSPI", "market_cap": 10e12},
            {"ticker": "010130", "name": "고려아연", "sector": "비철금속", "market": "KOSPI", "market_cap": 10e12},
            {"ticker": "373220", "name": "LG에너지솔루션", "sector": "배터리", "market": "KOSPI", "market_cap": 85e12},
            {"ticker": "207940", "name": "삼성바이오로직스", "sector": "바이오", "market": "KOSPI", "market_cap": 45e12},
            {"ticker": "018260", "name": "삼성에스디에스", "sector": "IT서비스", "market": "KOSPI", "market_cap": 10e12},
            {"ticker": "011200", "name": "HMM", "sector": "해운", "market": "KOSPI", "market_cap": 8e12},
        ]
