"""
뉴스/공시 NLP 센티먼트 분석 엔진
- DART 공시 실시간 수집
- 뉴스 크롤링 + 한국어 NLP 센티먼트 스코어링
- 종목별 이벤트 리스크 판단
- 호재/악재 자동 분류
"""
import asyncio
import httpx
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    title: str
    source: str
    url: str = ""
    published_at: str = ""
    ticker: str = ""
    sentiment_score: float = 0      # -1 (극도 부정) ~ +1 (극도 긍정)
    sentiment_label: str = "중립"    # 호재/악재/중립
    impact_score: float = 0          # 영향도 0~1
    keywords: List[str] = field(default_factory=list)
    category: str = ""               # 실적, 수급, 정책, 기술, 경영 등


@dataclass
class DisclosureItem:
    """DART 공시 데이터"""
    title: str
    corp_name: str
    ticker: str = ""
    rcept_no: str = ""
    report_type: str = ""
    filed_at: str = ""
    impact: str = "중립"              # 호재/악재/중립
    impact_score: float = 0


class NewsSentimentEngine:
    """뉴스/공시 NLP 센티먼트 분석"""

    # 한국 주식시장 핵심 키워드 사전 (금융 도메인 특화)
    POSITIVE_KEYWORDS = {
        # 실적 관련
        "어닝 서프라이즈": 0.9, "실적 호전": 0.8, "매출 증가": 0.7,
        "영업이익 증가": 0.8, "흑자 전환": 0.9, "순이익 최대": 0.85,
        "목표가 상향": 0.7, "투자의견 상향": 0.75, "시장 기대치 상회": 0.8,
        # 수급
        "외국인 순매수": 0.6, "기관 순매수": 0.6, "대량 매수": 0.65,
        "자사주 매입": 0.7, "배당 확대": 0.65,
        # 산업/정책
        "신규 수주": 0.7, "대규모 계약": 0.8, "정부 지원": 0.6,
        "규제 완화": 0.6, "수출 증가": 0.65, "시장 확대": 0.6,
        # 기술
        "신기술 개발": 0.7, "특허 취득": 0.6, "AI 도입": 0.5,
        "반등": 0.5, "상승": 0.4, "급등": 0.6, "돌파": 0.5,
        "호재": 0.7, "호실적": 0.8,
    }

    NEGATIVE_KEYWORDS = {
        # 실적
        "어닝 쇼크": -0.9, "실적 악화": -0.8, "매출 감소": -0.7,
        "영업이익 감소": -0.8, "적자 전환": -0.9, "적자 확대": -0.85,
        "목표가 하향": -0.7, "투자의견 하향": -0.75, "시장 기대치 하회": -0.8,
        # 수급
        "외국인 순매도": -0.6, "기관 순매도": -0.6, "대량 매도": -0.65,
        "공매도 증가": -0.7, "신용잔고 급증": -0.5,
        # 리스크
        "횡령": -0.95, "분식회계": -0.95, "상장폐지": -1.0,
        "감사의견 거절": -0.95, "관리종목": -0.9, "불성실공시": -0.7,
        "소송": -0.6, "벌금": -0.5, "과징금": -0.6,
        # 시장
        "급락": -0.7, "폭락": -0.9, "하락": -0.4, "하한가": -0.9,
        "악재": -0.7, "부진": -0.6, "위기": -0.6, "부도": -0.95,
        "리콜": -0.7, "결함": -0.6,
    }

    # 고영향 이벤트 패턴
    HIGH_IMPACT_PATTERNS = [
        r"상장폐지|관리종목|감사의견",        # 극고위험
        r"유상증자|무상감자|CB발행",           # 고위험 (희석)
        r"합병|인수|지분.*매각",               # 고영향 (변수)
        r"실적.*발표|잠정.*실적",               # 고영향 (실적)
        r"배당|자사주",                         # 중영향 (주주환원)
    ]

    def __init__(self, dart_api_key: str = ""):
        self.dart_api_key = dart_api_key
        self._news_cache: Dict[str, List[NewsItem]] = defaultdict(list)
        self._disclosure_cache: Dict[str, List[DisclosureItem]] = defaultdict(list)
        self._sentiment_cache: Dict[str, float] = {}
        self._cache_ttl = timedelta(minutes=10)
        self._last_fetch: Optional[datetime] = None

    # ─── 공시 수집 (DART) ───

    async def fetch_disclosures(self, ticker: str = "", days: int = 7) -> List[DisclosureItem]:
        """DART 공시 수집"""
        try:
            if not self.dart_api_key:
                logger.debug("DART API 키 미설정, 공시 수집 생략")
                return []

            end_date = datetime.now()
            begin_date = end_date - timedelta(days=days)

            async with httpx.AsyncClient(timeout=15) as client:
                params = {
                    "crtfc_key": self.dart_api_key,
                    "bgn_de": begin_date.strftime("%Y%m%d"),
                    "end_de": end_date.strftime("%Y%m%d"),
                    "page_count": 50,
                }
                if ticker:
                    params["stock_code"] = ticker

                resp = await client.get(
                    "https://opendart.fss.or.kr/api/list.json",
                    params=params
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = []
                    for item in data.get("list", []):
                        disclosure = DisclosureItem(
                            title=item.get("report_nm", ""),
                            corp_name=item.get("corp_name", ""),
                            ticker=item.get("stock_code", ""),
                            rcept_no=item.get("rcept_no", ""),
                            report_type=item.get("report_nm", ""),
                            filed_at=item.get("rcept_dt", ""),
                        )
                        disclosure.impact, disclosure.impact_score = self._classify_disclosure(
                            disclosure.title
                        )
                        items.append(disclosure)

                        # 캐시 저장
                        if disclosure.ticker:
                            self._disclosure_cache[disclosure.ticker].append(disclosure)

                    return items
        except Exception as e:
            logger.error(f"DART 공시 수집 실패: {e}")
        return []

    # ─── 뉴스 수집 ───

    async def fetch_news(self, ticker: str, company_name: str = "",
                         limit: int = 20) -> List[NewsItem]:
        """뉴스 수집 + NLP 센티먼트 분석"""
        try:
            query = company_name or ticker
            async with httpx.AsyncClient(timeout=15) as client:
                # 네이버 뉴스 검색 API (또는 대안)
                resp = await client.get(
                    "https://openapi.naver.com/v1/search/news.json",
                    headers={
                        "X-Naver-Client-Id": "YOUR_CLIENT_ID",
                        "X-Naver-Client-Secret": "YOUR_CLIENT_SECRET",
                    },
                    params={"query": query, "display": limit, "sort": "date"}
                )

                items = []
                if resp.status_code == 200:
                    data = resp.json()
                    for article in data.get("items", []):
                        title = self._clean_html(article.get("title", ""))
                        news = NewsItem(
                            title=title,
                            source=article.get("originallink", ""),
                            url=article.get("link", ""),
                            published_at=article.get("pubDate", ""),
                            ticker=ticker,
                        )
                        # 센티먼트 분석
                        score, label = self._analyze_sentiment(title)
                        news.sentiment_score = score
                        news.sentiment_label = label
                        news.impact_score = self._calculate_impact(title)
                        news.keywords = self._extract_keywords(title)
                        news.category = self._categorize(title)
                        items.append(news)

                # 캐시 업데이트
                self._news_cache[ticker] = items
                self._last_fetch = datetime.now()
                return items
        except Exception as e:
            logger.error(f"뉴스 수집 실패 [{ticker}]: {e}")
        return self._news_cache.get(ticker, [])

    # ─── 센티먼트 분석 ───

    def _analyze_sentiment(self, text: str) -> Tuple[float, str]:
        """
        한국어 금융 텍스트 센티먼트 분석
        키워드 사전 + 가중치 기반 (딥러닝 모델 연동 가능)
        """
        text_lower = text.lower()
        pos_score = 0
        neg_score = 0
        pos_count = 0
        neg_count = 0

        for keyword, weight in self.POSITIVE_KEYWORDS.items():
            if keyword in text:
                pos_score += weight
                pos_count += 1

        for keyword, weight in self.NEGATIVE_KEYWORDS.items():
            if keyword in text:
                neg_score += abs(weight)
                neg_count += 1

        # 부정어 반전 처리
        negation_patterns = ["아니", "못", "않", "없"]
        has_negation = any(neg in text for neg in negation_patterns)

        if has_negation:
            pos_score, neg_score = neg_score * 0.7, pos_score * 0.7

        # 최종 스코어 (-1 ~ +1)
        total = pos_score + neg_score
        if total == 0:
            return 0, "중립"

        final_score = (pos_score - neg_score) / max(total, 1)
        final_score = max(-1.0, min(1.0, final_score))

        if final_score > 0.2:
            label = "호재"
        elif final_score < -0.2:
            label = "악재"
        else:
            label = "중립"

        return round(final_score, 3), label

    def _calculate_impact(self, text: str) -> float:
        """영향도 계산 (0~1)"""
        impact = 0.3  # 기본 영향도

        for i, pattern in enumerate(self.HIGH_IMPACT_PATTERNS):
            if re.search(pattern, text):
                impact = max(impact, 1.0 - i * 0.15)

        # 숫자 포함 시 영향도 증가 (구체적 정보)
        if re.search(r'\d+[%조억만]', text):
            impact = min(impact + 0.1, 1.0)

        return round(impact, 2)

    def _categorize(self, text: str) -> str:
        """뉴스 카테고리 분류"""
        categories = {
            "실적": ["실적", "매출", "영업이익", "순이익", "어닝", "분기"],
            "수급": ["외국인", "기관", "순매수", "순매도", "공매도", "수급"],
            "정책": ["정부", "규제", "정책", "금리", "통화", "관세"],
            "기술": ["신기술", "특허", "AI", "반도체", "배터리", "개발"],
            "경영": ["인수", "합병", "대표", "경영", "지배구조", "사외"],
            "시장": ["시장", "지수", "거래소", "코스피", "코스닥"],
        }
        for cat, keywords in categories.items():
            if any(k in text for k in keywords):
                return cat
        return "기타"

    def _extract_keywords(self, text: str) -> List[str]:
        """핵심 키워드 추출"""
        all_keywords = list(self.POSITIVE_KEYWORDS.keys()) + list(self.NEGATIVE_KEYWORDS.keys())
        return [k for k in all_keywords if k in text]

    def _classify_disclosure(self, title: str) -> Tuple[str, float]:
        """공시 호재/악재 분류"""
        positive = [
            "자기주식취득", "배당", "무상증자", "주식병합", 
            "투자판단관련주요경영사항(호재)",
        ]
        negative = [
            "유상증자", "전환사채", "감사보고서미제출", "관리종목",
            "상장폐지", "불성실공시", "감사의견거절", "횡령",
        ]
        for kw in negative:
            if kw in title.replace(" ", ""):
                return "악재", -0.8
        for kw in positive:
            if kw in title.replace(" ", ""):
                return "호재", 0.7
        return "중립", 0

    @staticmethod
    def _clean_html(text: str) -> str:
        """HTML 태그 제거"""
        return re.sub(r'<[^>]+>', '', text).strip()

    # ─── 종합 센티먼트 스코어 ───

    def get_aggregate_sentiment(self, ticker: str) -> dict:
        """종목의 종합 센티먼트 스코어"""
        news_list = self._news_cache.get(ticker, [])
        disclosures = self._disclosure_cache.get(ticker, [])

        if not news_list and not disclosures:
            return {
                "score": 0,
                "label": "데이터 없음",
                "news_count": 0,
                "disclosure_count": 0,
                "positive_ratio": 0,
                "negative_ratio": 0,
                "high_impact_events": [],
            }

        # 뉴스 센티먼트 (시간 가중)
        weighted_scores = []
        for news in news_list:
            # 최근 뉴스에 더 높은 가중치
            recency_weight = 1.0  # 기본
            weighted_scores.append(news.sentiment_score * news.impact_score * recency_weight)

        avg_news_sentiment = sum(weighted_scores) / max(len(weighted_scores), 1)

        # 공시 영향
        disclosure_impact = sum(d.impact_score for d in disclosures) / max(len(disclosures), 1)

        # 종합 (뉴스 60% + 공시 40%)
        combined = avg_news_sentiment * 0.6 + disclosure_impact * 0.4

        positive_count = sum(1 for n in news_list if n.sentiment_label == "호재")
        negative_count = sum(1 for n in news_list if n.sentiment_label == "악재")
        total = max(len(news_list), 1)

        high_impact = [n.title for n in news_list if n.impact_score > 0.7]

        return {
            "score": round(combined, 3),
            "label": "호재" if combined > 0.15 else ("악재" if combined < -0.15 else "중립"),
            "news_count": len(news_list),
            "disclosure_count": len(disclosures),
            "positive_ratio": round(positive_count / total, 2),
            "negative_ratio": round(negative_count / total, 2),
            "high_impact_events": high_impact[:5],
        }
