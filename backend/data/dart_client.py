"""
DART OpenAPI 실시간 재무 데이터 클라이언트
- 분기별 재무제표 자동 파싱 (손익계산서, 재무상태표, 현금흐름표)
- 임원/대주주 변동 공시 추적 (내부자 거래 시그널)
- 중요 공시 실시간 알림 (유상증자, 합병, 자기주식 등)
- factor_model 입력을 위한 fundamentals dict 자동 생성
"""
import asyncio
import httpx
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Fundamentals:
    """종목 재무 기본 데이터"""
    ticker: str
    name: str = ""
    # 밸류에이션
    per: float = 0.0       # 주가수익비율
    pbr: float = 0.0       # 주가순자산비율
    psr: float = 0.0       # 주가매출비율
    ev_ebitda: float = 0.0 # EV/EBITDA
    dividend_yield: float = 0.0  # 배당수익률 (%)
    # 수익성
    roe: float = 0.0        # 자기자본이익률
    roa: float = 0.0        # 총자산이익률
    operating_margin: float = 0.0  # 영업이익률 (%)
    net_margin: float = 0.0        # 순이익률 (%)
    ebitda_margin: float = 0.0     # EBITDA 마진
    # 안정성
    debt_ratio: float = 0.0        # 부채비율 (%)
    current_ratio: float = 0.0     # 유동비율
    interest_coverage: float = 0.0 # 이자보상배율
    # 성장성
    revenue_growth: float = 0.0    # 매출 성장률 YoY (%)
    eps_growth: float = 0.0        # EPS 성장률 YoY (%)
    operating_profit_growth: float = 0.0  # 영업이익 성장률
    # 현금흐름
    free_cash_flow: float = 0.0    # FCF (억원)
    operating_cash_flow: float = 0.0
    capex: float = 0.0
    # 기타
    market_cap: float = 0.0        # 시가총액 (억원)
    shares_outstanding: int = 0    # 발행주식수
    guidance: str = ""             # 실적 가이던스
    # 내부자
    insider_buy_signal: bool = False
    insider_sell_signal: bool = False
    insider_detail: str = ""
    # 메타
    updated_at: str = ""
    source: str = "DART"


@dataclass
class DisclosureAlert:
    """중요 공시 알림"""
    ticker: str
    corp_name: str
    disclosure_type: str    # 유상증자/자기주식/합병/분할 등
    title: str
    impact: str             # positive/negative/neutral
    impact_score: float     # -100 ~ +100
    filed_at: str
    url: str = ""


class DARTClient:
    """
    금융감독원 DART (전자공시시스템) API 클라이언트
    API 키 발급: https://opendart.fss.or.kr/
    """

    BASE_URL = "https://opendart.fss.or.kr/api"

    # 중요 공시 타입 분류
    DISCLOSURE_IMPACT = {
        # 긍정적 공시
        "자기주식취득결정": ("positive", 60),
        "자기주식취득완료": ("positive", 40),
        "무상증자결정": ("positive", 70),
        "주식배당결정": ("positive", 50),
        "현금배당결정": ("positive", 30),
        "대규모내부거래이사회결의": ("positive", 20),
        # 부정적 공시
        "유상증자결정": ("negative", -50),
        "전환사채권발행결정": ("negative", -40),
        "신주인수권부사채권발행결정": ("negative", -40),
        "소송등제기": ("negative", -30),
        "대표이사변경": ("negative", -20),
        # 중립
        "합병결정": ("neutral", 0),
        "주요사항보고서": ("neutral", 0),
    }

    def __init__(self, api_key: str = "", cache_dir: str = "data/dart_cache"):
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._corp_code_map: Dict[str, str] = {}  # ticker -> corp_code
        self._fundamentals_cache: Dict[str, Fundamentals] = {}
        self._cache_ttl = timedelta(hours=6)  # 6시간 캐시
        self._cache_time: Dict[str, datetime] = {}

    # ─── 기업코드 조회 ───

    async def get_corp_code(self, ticker: str) -> Optional[str]:
        """종목코드 → DART 법인코드 변환"""
        if ticker in self._corp_code_map:
            return self._corp_code_map[ticker]

        # 캐시 파일 확인
        cache_file = self.cache_dir / "corp_codes.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    codes = json.load(f)
                    if ticker in codes:
                        self._corp_code_map[ticker] = codes[ticker]
                        return codes[ticker]
            except Exception:
                pass

        # DART API 호출 (법인코드 검색)
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/company.json",
                    params={"crtfc_key": self.api_key, "stock_code": ticker}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "000":
                        corp_code = data.get("corp_code", "")
                        if corp_code:
                            self._corp_code_map[ticker] = corp_code
                            return corp_code
        except Exception as e:
            logger.warning(f"DART 법인코드 조회 실패 [{ticker}]: {e}")
        return None

    # ─── 재무 데이터 조회 ───

    async def get_fundamentals(self, ticker: str,
                                force_refresh: bool = False) -> Fundamentals:
        """종목 재무 기본 데이터 조회 (캐시 적용)"""
        now = datetime.now()
        cached = self._fundamentals_cache.get(ticker)
        cache_time = self._cache_time.get(ticker)

        if (not force_refresh and cached and cache_time and
                now - cache_time < self._cache_ttl):
            return cached

        fund = Fundamentals(ticker=ticker, updated_at=now.isoformat())

        if not self.api_key:
            # API 키 없으면 기본값 반환 (실전 환경에서는 API 키 필요)
            logger.debug(f"DART API 키 미설정 [{ticker}] - 기본 재무 데이터 사용")
            return self._get_default_fundamentals(ticker)

        corp_code = await self.get_corp_code(ticker)
        if not corp_code:
            return fund

        # 재무제표 조회 (XBRL 기반)
        try:
            financials = await self._fetch_financial_statements(corp_code)
            ratios = await self._fetch_financial_ratios(corp_code)

            # 통합
            self._parse_financials(fund, financials, ratios)

        except Exception as e:
            logger.error(f"재무 데이터 조회 실패 [{ticker}]: {e}")

        fund.updated_at = now.isoformat()
        self._fundamentals_cache[ticker] = fund
        self._cache_time[ticker] = now
        return fund

    async def _fetch_financial_statements(self, corp_code: str) -> dict:
        """재무제표 조회 (단일회사 전체 재무제표)"""
        year = datetime.now().year - 1  # 전년도 연간
        quarter = self._get_latest_quarter()

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/fnlttSinglAcntAll.json",
                    params={
                        "crtfc_key": self.api_key,
                        "corp_code": corp_code,
                        "bsns_year": str(year),
                        "reprt_code": quarter,  # 1Q=11013, 반기=11012, 3Q=11014, 연간=11011
                        "fs_div": "OFS",  # 개별재무제표
                    }
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.warning(f"재무제표 조회 실패: {e}")
        return {}

    async def _fetch_financial_ratios(self, corp_code: str) -> dict:
        """재무비율 조회"""
        year = datetime.now().year - 1
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/fnlttFinaRatio.json",
                    params={
                        "crtfc_key": self.api_key,
                        "corp_code": corp_code,
                        "bsns_year": str(year),
                        "reprt_code": "11011",  # 연간
                    }
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.warning(f"재무비율 조회 실패: {e}")
        return {}

    def _parse_financials(self, fund: Fundamentals, statements: dict, ratios: dict):
        """DART 응답 파싱 → Fundamentals 채우기"""
        items = statements.get("list", [])
        ratio_items = ratios.get("list", [])

        # 항목명 → 값 맵핑
        stmt_map = {}
        for item in items:
            name = item.get("account_nm", "")
            value = item.get("thstrm_amount", "0")
            try:
                stmt_map[name] = float(str(value).replace(",", ""))
            except Exception:
                pass

        ratio_map = {}
        for item in ratio_items:
            name = item.get("account_nm", "")
            value = item.get("thstrm_amount", "0")
            try:
                ratio_map[name] = float(str(value).replace(",", ""))
            except Exception:
                pass

        # 재무비율 파싱
        fund.roe = ratio_map.get("ROE(지배주주)", ratio_map.get("자기자본이익률", 0))
        fund.roa = ratio_map.get("ROA", ratio_map.get("총자산이익률", 0))
        fund.debt_ratio = ratio_map.get("부채비율", 0)
        fund.current_ratio = ratio_map.get("유동비율", 0)
        fund.operating_margin = ratio_map.get("영업이익률", 0)
        fund.net_margin = ratio_map.get("순이익률", 0)

        # 성장률 (전년 대비)
        revenue_curr = stmt_map.get("매출액", stmt_map.get("수익(매출액)", 0))
        revenue_prev = stmt_map.get("매출액(전기)", 0)
        if revenue_prev and revenue_prev != 0:
            fund.revenue_growth = round((revenue_curr - revenue_prev) / abs(revenue_prev) * 100, 2)

        # FCF
        op_cf = stmt_map.get("영업활동현금흐름", 0)
        capex = abs(stmt_map.get("유형자산취득", 0))
        fund.operating_cash_flow = op_cf / 1e8  # 원 → 억원
        fund.capex = capex / 1e8
        fund.free_cash_flow = (op_cf - capex) / 1e8

        fund.source = "DART"

    # ─── 공시 알림 ───

    async def get_recent_disclosures(self, ticker: str,
                                      days: int = 7) -> List[DisclosureAlert]:
        """최근 N일 주요 공시 조회"""
        if not self.api_key:
            return []

        corp_code = await self.get_corp_code(ticker)
        if not corp_code:
            return []

        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        alerts = []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/list.json",
                    params={
                        "crtfc_key": self.api_key,
                        "corp_code": corp_code,
                        "bgn_de": start_date,
                        "end_de": end_date,
                        "pblntf_ty": "A",  # 정기공시
                        "page_count": 20,
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("list", []):
                        report_nm = item.get("report_nm", "")
                        impact_info = self._classify_disclosure(report_nm)
                        if impact_info:
                            alert = DisclosureAlert(
                                ticker=ticker,
                                corp_name=item.get("corp_name", ""),
                                disclosure_type=impact_info[0],
                                title=report_nm,
                                impact=impact_info[1],
                                impact_score=impact_info[2],
                                filed_at=item.get("rcept_dt", ""),
                                url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('rcept_no', '')}",
                            )
                            alerts.append(alert)
        except Exception as e:
            logger.warning(f"공시 조회 실패 [{ticker}]: {e}")

        return alerts

    async def get_insider_transactions(self, ticker: str, days: int = 30) -> List[dict]:
        """임원/대주주 주식 거래 내역 (내부자 거래 추적)"""
        if not self.api_key:
            return []

        corp_code = await self.get_corp_code(ticker)
        if not corp_code:
            return []

        transactions = []
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/elestock.json",
                    params={
                        "crtfc_key": self.api_key,
                        "corp_code": corp_code,
                        "bgn_de": start_date,
                        "end_de": end_date,
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("list", []):
                        transactions.append({
                            "name": item.get("repror_nm", ""),
                            "position": item.get("rltvps_shrholdr_nm", ""),
                            "shares": int(item.get("change_qy", 0) or 0),
                            "direction": "매수" if int(item.get("change_qy", 0) or 0) > 0 else "매도",
                            "date": item.get("rcept_dt", ""),
                        })
        except Exception as e:
            logger.warning(f"내부자 거래 조회 실패 [{ticker}]: {e}")

        return transactions

    def _classify_disclosure(self, report_name: str):
        """공시 제목 → 영향 분류"""
        for keyword, (impact_type, impact_magnitude) in self.DISCLOSURE_IMPACT.items():
            if keyword in report_name:
                return (keyword, impact_type, impact_magnitude)
        return None

    def _get_latest_quarter(self) -> str:
        """현재 기준 최근 분기 코드"""
        month = datetime.now().month
        if month <= 3: return "11013"   # 1분기
        elif month <= 6: return "11012" # 반기
        elif month <= 9: return "11014" # 3분기
        else: return "11011"            # 연간

    def _get_default_fundamentals(self, ticker: str) -> Fundamentals:
        """API 키 없을 때 업종 평균 기본값 반환"""
        defaults = {
            # 삼성전자
            "005930": Fundamentals(ticker=ticker, name="삼성전자",
                                    per=12.0, pbr=1.2, roe=8.5, roa=4.2,
                                    debt_ratio=45.0, operating_margin=8.5,
                                    revenue_growth=5.0, eps_growth=10.0,
                                    free_cash_flow=15000.0, dividend_yield=2.5),
            # SK하이닉스
            "000660": Fundamentals(ticker=ticker, name="SK하이닉스",
                                    per=15.0, pbr=1.8, roe=12.0, roa=5.5,
                                    debt_ratio=55.0, operating_margin=20.0,
                                    revenue_growth=30.0, eps_growth=50.0,
                                    free_cash_flow=8000.0, dividend_yield=0.5),
            # 포스코홀딩스
            "005490": Fundamentals(ticker=ticker, name="포스코홀딩스",
                                    per=8.0, pbr=0.5, roe=6.0, roa=3.0,
                                    debt_ratio=70.0, operating_margin=5.0,
                                    revenue_growth=-5.0, eps_growth=-10.0,
                                    free_cash_flow=2000.0, dividend_yield=4.5),
            # LG화학
            "051910": Fundamentals(ticker=ticker, name="LG화학",
                                    per=18.0, pbr=1.0, roe=5.0, roa=2.5,
                                    debt_ratio=80.0, operating_margin=3.5,
                                    revenue_growth=-3.0, eps_growth=-20.0,
                                    free_cash_flow=500.0, dividend_yield=1.5),
        }
        default = defaults.get(ticker, Fundamentals(
            ticker=ticker,
            per=12.0, pbr=1.0, roe=10.0, roa=4.0,
            debt_ratio=60.0, operating_margin=8.0,
            revenue_growth=5.0, eps_growth=8.0,
            free_cash_flow=500.0, dividend_yield=2.0,
        ))
        default.updated_at = datetime.now().isoformat()
        default.source = "DEFAULT"
        return default

    async def enrich_fundamentals_with_insider(self, ticker: str, fund: Fundamentals) -> Fundamentals:
        """내부자 거래 정보 반영"""
        transactions = await self.get_insider_transactions(ticker, days=30)
        if not transactions:
            return fund

        buy_count = sum(1 for t in transactions if t["direction"] == "매수")
        sell_count = sum(1 for t in transactions if t["direction"] == "매도")

        if buy_count >= 2 and buy_count > sell_count:
            fund.insider_buy_signal = True
            fund.insider_detail = f"최근 30일 임원 매수 {buy_count}건"
        elif sell_count >= 3 and sell_count > buy_count * 2:
            fund.insider_sell_signal = True
            fund.insider_detail = f"최근 30일 임원 매도 {sell_count}건"

        return fund


# ─── 글로벌 인스턴스 ───

_dart_client: Optional[DARTClient] = None


def get_dart_client(api_key: str = "") -> DARTClient:
    global _dart_client
    if _dart_client is None:
        _dart_client = DARTClient(api_key=api_key)
    return _dart_client
