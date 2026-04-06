"""
경제 캘린더 + 이벤트 리스크 엔진
"""
import logging
from datetime import datetime, timedelta, date
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class EventImpact(str, Enum):
    LOW = "낮음"
    MEDIUM = "보통"
    HIGH = "높음"
    CRITICAL = "매우높음"

class EventType(str, Enum):
    MONETARY_POLICY = "통화정책"
    EMPLOYMENT = "고용지표"
    INFLATION = "물가지표"
    GDP = "경제성장"
    TRADE = "무역지표"
    EARNINGS = "실적시즌"
    OPTIONS_EXPIRY = "옵션만기"
    POLITICAL = "정치이벤트"

@dataclass
class EconomicEvent:
    name: str
    event_type: EventType
    date: str
    time: str = ""
    country: str = "KR"
    impact: EventImpact = EventImpact.MEDIUM
    description: str = ""
    risk_adjustment: float = 0

class EconomicCalendar:
    EARNINGS_SEASONS = {
        1: {"start": "01-20", "end": "02-15", "label": "4Q 잠정실적"},
        4: {"start": "04-20", "end": "05-15", "label": "1Q 실적시즌"},
        7: {"start": "07-20", "end": "08-15", "label": "2Q 실적시즌"},
        10: {"start": "10-20", "end": "11-15", "label": "3Q 실적시즌"},
    }

    def __init__(self):
        self._events: List[EconomicEvent] = []
        self._init_events()

    def _init_events(self):
        year = datetime.now().year
        # 옵션만기 (매월 두번째 목요일)
        for month in range(1, 13):
            first = date(year, month, 1)
            days = (3 - first.weekday()) % 7
            second_thu = first + timedelta(days=days + 7)
            is_quad = month in [3, 6, 9, 12]
            self._events.append(EconomicEvent(
                name=f"{'쿼드러플 위칭' if is_quad else '옵션만기'} ({month}월)",
                event_type=EventType.OPTIONS_EXPIRY, date=second_thu.strftime("%Y-%m-%d"),
                impact=EventImpact.HIGH if is_quad else EventImpact.MEDIUM,
                risk_adjustment=-0.2 if is_quad else -0.1,
            ))
        # FOMC
        for m in [1, 3, 5, 6, 7, 9, 11, 12]:
            self._events.append(EconomicEvent(
                name="FOMC 금리결정", event_type=EventType.MONETARY_POLICY,
                date=f"{year}-{m:02d}-15", country="US",
                impact=EventImpact.CRITICAL, risk_adjustment=-0.3,
            ))
        # 금통위
        for m in [1, 2, 4, 5, 7, 8, 10, 11]:
            self._events.append(EconomicEvent(
                name="한은 금통위", event_type=EventType.MONETARY_POLICY,
                date=f"{year}-{m:02d}-20", country="KR",
                impact=EventImpact.HIGH, risk_adjustment=-0.2,
            ))

    def get_upcoming_events(self, days_ahead: int = 7) -> List[EconomicEvent]:
        now = datetime.now()
        cutoff = now + timedelta(days=days_ahead)
        t, c = now.strftime("%Y-%m-%d"), cutoff.strftime("%Y-%m-%d")
        return sorted([e for e in self._events if t <= e.date <= c], key=lambda e: e.date)

    def is_earnings_season(self) -> Optional[str]:
        now = datetime.now()
        for m, info in self.EARNINGS_SEASONS.items():
            sm, sd = map(int, info["start"].split("-"))
            em, ed = map(int, info["end"].split("-"))
            if (now.month == sm and now.day >= sd) or (now.month == em and now.day <= ed):
                return info["label"]
        return None

    def is_high_risk_period(self) -> dict:
        upcoming = self.get_upcoming_events(2)
        high = [e for e in upcoming if e.impact in (EventImpact.HIGH, EventImpact.CRITICAL)]
        risk_score = sum(abs(e.risk_adjustment) for e in high)
        if self.is_earnings_season():
            risk_score += 0.1
        return {
            "is_high_risk": risk_score > 0.3,
            "risk_score": round(min(risk_score, 1.0), 2),
            "risk_factors": [e.name for e in high],
            "upcoming_events": [{"name": e.name, "date": e.date, "impact": e.impact.value} for e in upcoming[:5]],
        }

    def get_event_risk_adjustment(self) -> float:
        upcoming = self.get_upcoming_events(3)
        total = 0
        for ev in upcoming:
            days_until = max((datetime.strptime(ev.date, "%Y-%m-%d") - datetime.now()).days, 0)
            total += ev.risk_adjustment / (1 + days_until * 0.5)
        return round(max(total, -0.5), 3)

    def get_market_calendar_context(self) -> dict:
        risk = self.is_high_risk_period()
        return {
            "is_high_risk_period": risk["is_high_risk"],
            "event_risk_score": risk["risk_score"],
            "event_risk_adjustment": self.get_event_risk_adjustment(),
            "risk_factors": risk["risk_factors"],
            "earnings_season": self.is_earnings_season(),
            "upcoming_events": risk["upcoming_events"],
        }
