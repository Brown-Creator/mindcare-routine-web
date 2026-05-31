"""
LLM 기반 뉴스 & 공시 심층 분석 엔진
- OpenAI GPT / 로컬 Ollama 모델로 뉴스/공시 심층 분석
- 이벤트 분류: 어닝 서프라이즈, M&A, 규제, 지정학, 섹터이벤트
- 감성 점수 (-1.0 ~ +1.0) + 영향 강도 + 기간 추정
- 시장 영향 예측 (단기/중기)
"""
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """뉴스/공시 원문"""
    title: str
    content: str = ""
    source: str = ""
    published_at: str = ""
    ticker: str = ""
    url: str = ""


@dataclass
class LLMAnalysisResult:
    """LLM 분석 결과"""
    # 원문 정보
    title: str = ""
    ticker: str = ""
    # 감성
    sentiment_score: float = 0.0     # -1.0(강력매도) ~ +1.0(강력매수)
    sentiment_label: str = "중립"    # 매우긍정/긍정/중립/부정/매우부정
    confidence: float = 0.5          # 분석 신뢰도
    # 이벤트 분류
    event_type: str = "일반"         # 어닝/M&A/규제/지정학/공급망/경영진/제품/배당/법률
    event_impact_duration: str = "단기"  # 단기/중기/장기
    # 수치 영향 예측
    price_impact_pct: float = 0.0    # 예상 주가 영향 (%)
    impact_strength: str = "약"      # 강/중/약
    # 분석 요약
    summary: str = ""
    key_factors: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    # 메타
    analyzed_at: str = ""
    model_used: str = ""
    cached: bool = False


class LLMNewsAnalyzer:
    """
    LLM 기반 뉴스 심층 분석기
    - OpenAI GPT-4o-mini (속도/비용 균형)
    - 로컬 Ollama (Mistral/Llama) 폴백
    - 키워드 기반 규칙 (LLM 미사용 시 최종 폴백)
    """

    # 분석 프롬프트 템플릿
    ANALYSIS_PROMPT = """당신은 한국 주식 시장 전문 금융 분석가입니다.
다음 뉴스/공시를 분석하고 JSON 형식으로 정확히 응답하세요.

## 뉴스/공시 내용
제목: {title}
내용: {content}
관련 종목: {ticker}

## 요구 분석 항목
다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "sentiment_score": <-1.0~+1.0, +1이 가장 긍정>,
  "sentiment_label": <"매우긍정"/"긍정"/"중립"/"부정"/"매우부정">,
  "confidence": <0.0~1.0>,
  "event_type": <"어닝"/"M&A"/"규제"/"지정학"/"공급망"/"경영진교체"/"신제품"/"배당"/"법률소송"/"일반">,
  "event_impact_duration": <"단기(1-3일)"/"중기(1-4주)"/"장기(1개월+)">,
  "price_impact_pct": <예상 주가 등락률 숫자, 예: -2.5 또는 3.0>,
  "impact_strength": <"강"/"중"/"약">,
  "summary": <2-3문장 핵심 요약>,
  "key_factors": [<핵심 긍정 요인 리스트>],
  "risks": [<핵심 리스크 요인 리스트>]
}}"""

    def __init__(self, openai_api_key: str = "",
                 ollama_base_url: str = "http://localhost:11434",
                 cache_dir: str = "data/llm_cache"):
        self.openai_api_key = openai_api_key
        self.ollama_base_url = ollama_base_url
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, LLMAnalysisResult] = {}
        self._cache_ttl = timedelta(hours=24)
        self._cache_time: Dict[str, datetime] = {}
        self._total_analyzed = 0
        self._cost_usd = 0.0

    async def analyze(self, article: NewsArticle) -> LLMAnalysisResult:
        """뉴스 기사 심층 분석 (캐시 → OpenAI → Ollama → 규칙 폴백)"""
        cache_key = self._get_cache_key(article)

        # 캐시 확인
        cached = self._get_cached(cache_key)
        if cached:
            cached.cached = True
            return cached

        result = None

        # 1차: OpenAI GPT
        if self.openai_api_key:
            result = await self._analyze_with_openai(article)

        # 2차: 로컬 Ollama
        if not result and await self._is_ollama_available():
            result = await self._analyze_with_ollama(article)

        # 최종 폴백: 규칙 기반
        if not result:
            result = self._analyze_with_rules(article)

        result.analyzed_at = datetime.now().isoformat()
        self._set_cache(cache_key, result)
        self._total_analyzed += 1
        return result

    async def analyze_batch(self, articles: List[NewsArticle],
                             max_concurrent: int = 5) -> List[LLMAnalysisResult]:
        """배치 분석 (동시 처리)"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def limited_analyze(article):
            async with semaphore:
                return await self.analyze(article)

        tasks = [limited_analyze(a) for a in articles]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, LLMAnalysisResult)]

    def aggregate_sentiment(self, results: List[LLMAnalysisResult],
                             ticker: str) -> dict:
        """여러 뉴스 결과를 종합 센티먼트 점수로 집계"""
        if not results:
            return {"score": 0.0, "label": "중립", "article_count": 0}

        ticker_results = [r for r in results
                           if r.ticker == ticker or not r.ticker]
        if not ticker_results:
            ticker_results = results

        # 신뢰도 가중 평균
        total_weight = sum(r.confidence for r in ticker_results)
        if total_weight == 0:
            return {"score": 0.0, "label": "중립", "article_count": len(ticker_results)}

        weighted_score = sum(
            r.sentiment_score * r.confidence for r in ticker_results
        ) / total_weight

        # 영향 강도 분포
        strong_count = sum(1 for r in ticker_results if r.impact_strength == "강")
        positive_count = sum(1 for r in ticker_results if r.sentiment_score > 0.2)
        negative_count = sum(1 for r in ticker_results if r.sentiment_score < -0.2)

        # 이벤트 타입 집계
        event_types = [r.event_type for r in ticker_results]
        event_summary = list(set(event_types))

        # 고충격 이벤트 감지
        high_impact_events = [
            f"[{r.event_type}] {r.title[:30]}..." 
            for r in ticker_results
            if r.impact_strength == "강" and abs(r.sentiment_score) > 0.5
        ]

        # 레이블 결정
        if weighted_score > 0.4: label = "매우긍정"
        elif weighted_score > 0.15: label = "긍정"
        elif weighted_score < -0.4: label = "매우부정"
        elif weighted_score < -0.15: label = "부정"
        else: label = "중립"

        return {
            "score": round(weighted_score, 3),
            "label": label,
            "article_count": len(ticker_results),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "strong_impact_count": strong_count,
            "high_impact_events": high_impact_events,
            "event_types": event_summary,
            "positive_ratio": round(positive_count / len(ticker_results), 2),
            "negative_ratio": round(negative_count / len(ticker_results), 2),
        }

    # ─── LLM 백엔드 ───

    async def _analyze_with_openai(self, article: NewsArticle) -> Optional[LLMAnalysisResult]:
        """OpenAI GPT-4o-mini 분석"""
        try:
            import httpx
            prompt = self.ANALYSIS_PROMPT.format(
                title=article.title,
                content=article.content[:2000],  # 토큰 절약
                ticker=article.ticker or "알 수 없음",
            )

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 500,
                        "response_format": {"type": "json_object"},
                    }
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)

                    # 비용 추정 (GPT-4o-mini: ~$0.15/1M 입력 토큰)
                    tokens = data.get("usage", {}).get("total_tokens", 500)
                    self._cost_usd += tokens * 0.00000015

                    return self._parse_llm_response(parsed, article, "gpt-4o-mini")

        except Exception as e:
            logger.warning(f"OpenAI 분석 실패: {e}")
        return None

    async def _is_ollama_available(self) -> bool:
        """Ollama 서버 가용성 체크"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{self.ollama_base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def _analyze_with_ollama(self, article: NewsArticle) -> Optional[LLMAnalysisResult]:
        """로컬 Ollama 분석 (Mistral/Llama)"""
        try:
            import httpx
            prompt = self.ANALYSIS_PROMPT.format(
                title=article.title,
                content=article.content[:1500],
                ticker=article.ticker or "알 수 없음",
            )

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={
                        "model": "mistral",
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    parsed = json.loads(data.get("response", "{}"))
                    return self._parse_llm_response(parsed, article, "ollama-mistral")

        except Exception as e:
            logger.warning(f"Ollama 분석 실패: {e}")
        return None

    def _analyze_with_rules(self, article: NewsArticle) -> LLMAnalysisResult:
        """규칙 기반 폴백 분석 (LLM 없을 때)"""
        text = (article.title + " " + article.content).lower()

        # 강력 긍정 신호
        strong_positive = ["어닝 서프라이즈", "실적 급증", "흑자전환", "사상 최대",
                            "주요 계약 체결", "수주", "자사주 매입", "배당 증가",
                            "무상증자", "주가 급등", "목표주가 상향"]
        strong_negative = ["실적 하락", "적자전환", "어닝쇼크", "사망 사고", "소송",
                            "영업정지", "상장폐지", "주가 급락", "유상증자", "전환사채",
                            "대규모 손실", "구조조정", "CEO 해임"]

        positive_kw = ["성장", "증가", "수익", "흑자", "개선", "신규", "계약",
                        "투자", "확대", "상승", "호실적", "목표"]
        negative_kw = ["감소", "하락", "손실", "적자", "부진", "감원", "위기",
                        "부정", "악화", "리콜", "제재", "벌금", "경쟁 심화"]

        score = 0.0
        strong_pos = sum(1 for kw in strong_positive if kw in text)
        strong_neg = sum(1 for kw in strong_negative if kw in text)
        pos = sum(1 for kw in positive_kw if kw in text)
        neg = sum(1 for kw in negative_kw if kw in text)

        score += strong_pos * 0.3 - strong_neg * 0.4
        score += pos * 0.08 - neg * 0.1
        score = max(-1.0, min(1.0, score))

        if score > 0.4: label, strength = "긍정", "중"
        elif score > 0.1: label, strength = "긍정", "약"
        elif score < -0.4: label, strength = "부정", "중"
        elif score < -0.1: label, strength = "부정", "약"
        else: label, strength = "중립", "약"

        if strong_pos > 0 or strong_neg > 0:
            strength = "강"

        return LLMAnalysisResult(
            title=article.title,
            ticker=article.ticker,
            sentiment_score=round(score, 3),
            sentiment_label=label,
            confidence=0.4,
            event_type="일반",
            price_impact_pct=round(score * 3, 1),
            impact_strength=strength,
            summary=f"규칙 기반 분석: {label} ({score:+.2f})",
            key_factors=[kw for kw in positive_kw if kw in text][:3],
            risks=[kw for kw in negative_kw if kw in text][:3],
            model_used="rules",
        )

    def _parse_llm_response(self, data: dict, article: NewsArticle,
                             model: str) -> LLMAnalysisResult:
        """LLM JSON 응답 파싱"""
        try:
            return LLMAnalysisResult(
                title=article.title,
                ticker=article.ticker,
                sentiment_score=float(data.get("sentiment_score", 0)),
                sentiment_label=data.get("sentiment_label", "중립"),
                confidence=float(data.get("confidence", 0.5)),
                event_type=data.get("event_type", "일반"),
                event_impact_duration=data.get("event_impact_duration", "단기"),
                price_impact_pct=float(data.get("price_impact_pct", 0)),
                impact_strength=data.get("impact_strength", "약"),
                summary=data.get("summary", ""),
                key_factors=data.get("key_factors", []),
                risks=data.get("risks", []),
                model_used=model,
            )
        except Exception as e:
            logger.warning(f"LLM 응답 파싱 실패: {e}")
            return self._analyze_with_rules(article)

    # ─── 캐시 ───

    def _get_cache_key(self, article: NewsArticle) -> str:
        text = f"{article.ticker}:{article.title}"
        return hashlib.md5(text.encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[LLMAnalysisResult]:
        if key in self._cache:
            cache_time = self._cache_time.get(key)
            if cache_time and datetime.now() - cache_time < self._cache_ttl:
                return self._cache[key]
        return None

    def _set_cache(self, key: str, result: LLMAnalysisResult):
        self._cache[key] = result
        self._cache_time[key] = datetime.now()

    def get_stats(self) -> dict:
        return {
            "total_analyzed": self._total_analyzed,
            "cache_size": len(self._cache),
            "estimated_cost_usd": round(self._cost_usd, 4),
            "openai_enabled": bool(self.openai_api_key),
        }


# ─── 글로벌 인스턴스 ───

_llm_analyzer: Optional[LLMNewsAnalyzer] = None


def get_llm_analyzer(openai_api_key: str = "") -> LLMNewsAnalyzer:
    global _llm_analyzer
    if _llm_analyzer is None:
        _llm_analyzer = LLMNewsAnalyzer(openai_api_key=openai_api_key)
    return _llm_analyzer
