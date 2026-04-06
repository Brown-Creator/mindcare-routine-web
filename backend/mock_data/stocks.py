"""
Mock 종목 데이터 - 포스코홀딩스 포함 5개 종목
실시간 가격, 기술적 지표, 전략 신호를 모두 포함
"""
import random
import math
from datetime import datetime, timedelta
from typing import Dict, List
from backend.models.stock import (
    StockInfo, StockSignal, StockState, OHLCV,
    PortfolioSummary, Position
)
from backend.models.order import Order, OrderSide, OrderType, OrderStatus, OrderReason
from backend.models.risk import RiskStatus, RiskLevel


def _generate_ohlcv(base_price: float, days: int = 120, volatility: float = 0.02) -> List[dict]:
    """가격 히스토리 생성"""
    data = []
    price = base_price * 1.15
    for i in range(days, 0, -1):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        change = random.gauss(0, volatility)
        # Simulate downtrend then stabilization
        if i > 60:
            change -= 0.003
        elif i > 30:
            change -= 0.001
        else:
            change += 0.0005
        
        price = price * (1 + change)
        o = price * (1 + random.gauss(0, 0.005))
        h = max(o, price) * (1 + abs(random.gauss(0, 0.008)))
        l = min(o, price) * (1 - abs(random.gauss(0, 0.008)))
        c = price
        v = int(random.gauss(500000, 150000))
        
        data.append({
            "date": date,
            "open": round(o, 0),
            "high": round(h, 0),
            "low": round(l, 0),
            "close": round(c, 0),
            "volume": max(v, 50000)
        })
    return data


MOCK_STOCKS: Dict[str, StockInfo] = {
    "005490": StockInfo(
        ticker="005490",
        name="포스코홀딩스",
        market="KOSPI",
        sector="철강",
        current_price=268000,
        prev_close=271000,
        change_pct=-1.11,
        volume=892340,
        market_cap=20700000000000,
        high_52w=398000,
        low_52w=254000,
    ),
    "005930": StockInfo(
        ticker="005930",
        name="삼성전자",
        market="KOSPI",
        sector="반도체",
        current_price=71200,
        prev_close=71800,
        change_pct=-0.84,
        volume=12450000,
        market_cap=425000000000000,
        high_52w=88800,
        low_52w=53000,
    ),
    "000660": StockInfo(
        ticker="000660",
        name="SK하이닉스",
        market="KOSPI",
        sector="반도체",
        current_price=178000,
        prev_close=175500,
        change_pct=1.42,
        volume=3210000,
        market_cap=130000000000000,
        high_52w=248000,
        low_52w=132000,
    ),
    "035420": StockInfo(
        ticker="035420",
        name="NAVER",
        market="KOSPI",
        sector="인터넷",
        current_price=195000,
        prev_close=197000,
        change_pct=-1.02,
        volume=1580000,
        market_cap=32000000000000,
        high_52w=245000,
        low_52w=175000,
    ),
    "051910": StockInfo(
        ticker="051910",
        name="LG화학",
        market="KOSPI",
        sector="화학",
        current_price=285000,
        prev_close=288000,
        change_pct=-1.04,
        volume=420000,
        market_cap=20100000000000,
        high_52w=415000,
        low_52w=262000,
    ),
}


MOCK_SIGNALS: Dict[str, StockSignal] = {
    "005490": StockSignal(
        ticker="005490",
        name="포스코홀딩스",
        state=StockState.AVG_DOWN_1_CANDIDATE,
        confidence=72,
        bottom_probability_score=68,
        trend_score=45,
        momentum_score=55,
        mean_reversion_score=71,
        supply_demand_score=62,
        event_risk_score=40,
        market_risk_score=35,
        risk_score=35,
        buy_price_1=265000,
        buy_amount_1=2000000,
        buy_price_2=250000,
        buy_amount_2=3000000,
        exit_price_1=285000,
        exit_price_2=305000,
        exit_trailing_stop=258000,
        hard_stop=240000,
        reason=[
            "52주 최저가 근접 (254,000원 대비 5.5% 위)",
            "RSI(14) 28.5 → 과매도 구간 진입",
            "외국인 3일 연속 순매수 전환",
            "거래량 20일 평균 대비 바닥 형성",
            "60일 이동평균 괴리율 -12.3%",
            "볼린저밴드 하단 근접",
        ],
        risk_flags=[
            "철강업종 전반적 약세 지속",
            "환율(원/달러) 상승 압박",
            "중국 철강 수출 증가로 업황 부담",
        ],
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ),
    "005930": StockSignal(
        ticker="005930",
        name="삼성전자",
        state=StockState.WATCH,
        confidence=45,
        bottom_probability_score=42,
        trend_score=38,
        momentum_score=40,
        mean_reversion_score=55,
        supply_demand_score=48,
        event_risk_score=30,
        market_risk_score=35,
        risk_score=42,
        buy_price_1=68000,
        buy_amount_1=3000000,
        exit_price_1=78000,
        exit_price_2=85000,
        exit_trailing_stop=66000,
        hard_stop=62000,
        reason=[
            "하락 추세 지속 중",
            "반도체 업황 개선 신호 미약",
            "거래량 감소세 → 바닥 형성 단계 관찰 필요",
        ],
        risk_flags=[
            "반도체 재고조정 장기화 우려",
            "미중 무역갈등 재부각",
        ],
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ),
    "000660": StockSignal(
        ticker="000660",
        name="SK하이닉스",
        state=StockState.HOLDING,
        confidence=65,
        bottom_probability_score=55,
        trend_score=62,
        momentum_score=68,
        mean_reversion_score=45,
        supply_demand_score=72,
        event_risk_score=25,
        market_risk_score=30,
        risk_score=28,
        buy_price_1=165000,
        buy_amount_1=2500000,
        exit_price_1=195000,
        exit_price_2=220000,
        exit_trailing_stop=170000,
        hard_stop=155000,
        reason=[
            "HBM 수요 증가 수혜 기대",
            "기관 순매수 전환 확인",
            "반등 모멘텀 점수 개선 중",
        ],
        risk_flags=[
            "단기 과열 구간 진입 가능성",
        ],
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ),
    "035420": StockSignal(
        ticker="035420",
        name="NAVER",
        state=StockState.NEW_ENTRY_CANDIDATE,
        confidence=58,
        bottom_probability_score=61,
        trend_score=42,
        momentum_score=48,
        mean_reversion_score=65,
        supply_demand_score=55,
        event_risk_score=35,
        market_risk_score=38,
        risk_score=38,
        buy_price_1=190000,
        buy_amount_1=2000000,
        exit_price_1=215000,
        exit_price_2=235000,
        exit_trailing_stop=183000,
        hard_stop=172000,
        reason=[
            "52주 최저가 대비 바닥권 접근",
            "AI/검색 신사업 성장 기대",
            "하락 속도 둔화 → 바닥 형성 징후",
        ],
        risk_flags=[
            "광고 매출 둔화",
            "글로벌 빅테크 경쟁 심화",
        ],
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ),
    "051910": StockSignal(
        ticker="051910",
        name="LG화학",
        state=StockState.TRADE_BLOCKED,
        confidence=25,
        bottom_probability_score=35,
        trend_score=22,
        momentum_score=28,
        mean_reversion_score=40,
        supply_demand_score=30,
        event_risk_score=75,
        market_risk_score=60,
        risk_score=72,
        buy_price_1=None,
        buy_amount_1=None,
        exit_price_1=320000,
        exit_price_2=350000,
        exit_trailing_stop=275000,
        hard_stop=255000,
        reason=[
            "하락 추세 강화 중",
            "배터리 업황 불확실성 확대",
            "이벤트 리스크 점수 임계치 초과 → 매매 금지",
        ],
        risk_flags=[
            "2차전지 수요 둔화",
            "전기차 보조금 축소 우려",
            "원재료 가격 변동성 급등",
            "리스크 엔진이 매매를 차단함",
        ],
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ),
}


MOCK_POSITIONS: List[Position] = [
    Position(
        ticker="000660",
        name="SK하이닉스",
        avg_price=165000,
        quantity=15,
        current_price=178000,
        market_value=2670000,
        pnl=195000,
        pnl_pct=7.88,
        weight_pct=2.67,
        avg_down_count=0,
        entry_date="2025-03-15",
        holding_days=21,
    ),
    Position(
        ticker="005490",
        name="포스코홀딩스",
        avg_price=278000,
        quantity=7,
        current_price=268000,
        market_value=1876000,
        pnl=-70000,
        pnl_pct=-3.60,
        weight_pct=1.88,
        avg_down_count=0,
        entry_date="2025-03-20",
        holding_days=16,
    ),
]


MOCK_ORDERS: List[dict] = [
    {
        "order_id": "ORD-20250405-001",
        "ticker": "005490",
        "name": "포스코홀딩스",
        "side": "매수",
        "order_type": "지정가",
        "price": 278000,
        "quantity": 7,
        "filled_quantity": 7,
        "avg_filled_price": 278000,
        "status": "체결",
        "reason": "신규진입",
        "risk_approved": True,
        "created_at": "2025-03-20 09:15:30",
        "filled_at": "2025-03-20 09:15:42",
    },
    {
        "order_id": "ORD-20250405-002",
        "ticker": "000660",
        "name": "SK하이닉스",
        "side": "매수",
        "order_type": "지정가",
        "price": 165000,
        "quantity": 15,
        "filled_quantity": 15,
        "avg_filled_price": 165000,
        "status": "체결",
        "reason": "신규진입",
        "risk_approved": True,
        "created_at": "2025-03-15 10:02:15",
        "filled_at": "2025-03-15 10:02:28",
    },
    {
        "order_id": "ORD-20250405-003",
        "ticker": "005490",
        "name": "포스코홀딩스",
        "side": "매수",
        "order_type": "지정가",
        "price": 265000,
        "quantity": 7,
        "filled_quantity": 0,
        "avg_filled_price": 0,
        "status": "대기",
        "reason": "1차 물타기",
        "risk_approved": True,
        "created_at": "2025-04-05 09:30:00",
        "filled_at": None,
    },
]


MOCK_PORTFOLIO = PortfolioSummary(
    total_value=100125000,
    invested_amount=4546000,
    cash=95579000,
    total_pnl=125000,
    total_pnl_pct=0.125,
    daily_pnl=-52000,
    daily_pnl_pct=-0.052,
    position_count=2,
    watchlist_count=5,
    max_drawdown_pct=1.8,
    win_rate=66.7,
)


MOCK_RISK_STATUS = RiskStatus(
    overall_level=RiskLevel.LOW,
    kill_switch_active=False,
    daily_loss_pct=0.05,
    max_daily_loss_pct=3.0,
    current_drawdown_pct=1.8,
    max_drawdown_pct=10.0,
    total_exposure_pct=4.55,
    largest_position_pct=2.67,
    api_health="정상",
    data_health="정상",
    websocket_status="연결됨 (Mock)",
    last_check_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    blocked_tickers=["051910"],
    active_alerts=["LG화학 매매금지 상태 (이벤트 리스크 초과)"],
)


MOCK_ALERTS: List[dict] = [
    {
        "id": "ALT-001",
        "type": "전략",
        "level": "정보",
        "message": "포스코홀딩스 → 1차 물타기 후보 상태 전환",
        "time": "09:30:00",
        "read": False,
    },
    {
        "id": "ALT-002",
        "type": "리스크",
        "level": "경고",
        "message": "LG화학 이벤트 리스크 점수 75점 → 매매 차단",
        "time": "09:15:22",
        "read": False,
    },
    {
        "id": "ALT-003",
        "type": "시장",
        "level": "정보",
        "message": "KOSPI 0.8% 하락 출발, 시장 위험 점수 35점",
        "time": "09:01:05",
        "read": True,
    },
    {
        "id": "ALT-004",
        "type": "주문",
        "level": "성공",
        "message": "SK하이닉스 매수 15주 체결 완료 (165,000원)",
        "time": "어제 10:02",
        "read": True,
    },
    {
        "id": "ALT-005",
        "type": "시스템",
        "level": "정보",
        "message": "Mock 모드 자동매매 시스템 시작됨",
        "time": "09:00:00",
        "read": True,
    },
]


MOCK_STRATEGY_LOGS: List[dict] = [
    {
        "timestamp": "2025-04-05 09:30:00",
        "ticker": "005490",
        "name": "포스코홀딩스",
        "action": "상태 변경",
        "from_state": "관찰",
        "to_state": "1차 물타기 후보",
        "scores": {"바닥확률": 68, "추세": 45, "모멘텀": 55, "리스크": 35},
        "details": "RSI 과매도 진입 + 외국인 순매수 전환 확인 → 물타기 후보 전환",
    },
    {
        "timestamp": "2025-04-05 09:15:22",
        "ticker": "051910",
        "name": "LG화학",
        "action": "매매 차단",
        "from_state": "관찰",
        "to_state": "매매금지",
        "scores": {"바닥확률": 35, "추세": 22, "모멘텀": 28, "리스크": 72},
        "details": "이벤트 리스크 75점 → 임계치(60점) 초과 → 리스크 엔진이 매매 차단",
    },
    {
        "timestamp": "2025-04-05 09:05:00",
        "ticker": "035420",
        "name": "NAVER",
        "action": "상태 변경",
        "from_state": "관찰",
        "to_state": "신규진입 후보",
        "scores": {"바닥확률": 61, "추세": 42, "모멘텀": 48, "리스크": 38},
        "details": "52주 저점 근접 + 하락속도 둔화 → 신규진입 후보 전환",
    },
    {
        "timestamp": "2025-04-04 14:50:00",
        "ticker": "000660",
        "name": "SK하이닉스",
        "action": "상태 유지",
        "from_state": "보유",
        "to_state": "보유",
        "scores": {"바닥확률": 55, "추세": 62, "모멘텀": 68, "리스크": 28},
        "details": "반등 모멘텀 유지 → 1차 매도가(195,000원) 도달 전까지 보유 유지",
    },
]


def generate_price_history(ticker: str) -> List[dict]:
    """종목별 120일 가격 히스토리 생성"""
    base_prices = {
        "005490": 268000,
        "005930": 71200,
        "000660": 178000,
        "035420": 195000,
        "051910": 285000,
    }
    base = base_prices.get(ticker, 100000)
    return _generate_ohlcv(base, days=120, volatility=0.018)


def get_indicators(ticker: str) -> dict:
    """종목별 기술적 지표 Mock 데이터"""
    indicators_data = {
        "005490": {
            "ma5": 270200, "ma20": 275800, "ma60": 295000, "ma120": 320000,
            "rsi14": 28.5,
            "macd": -3200, "macd_signal": -2800, "macd_histogram": -400,
            "bb_upper": 290000, "bb_middle": 275000, "bb_lower": 260000,
            "atr14": 8500,
            "volume_ratio": 0.85,
            "gap_pct": -1.11,
            "volatility_surge": False,
        },
        "005930": {
            "ma5": 71800, "ma20": 73500, "ma60": 76000, "ma120": 78500,
            "rsi14": 35.2,
            "macd": -850, "macd_signal": -720, "macd_histogram": -130,
            "bb_upper": 76000, "bb_middle": 73000, "bb_lower": 70000,
            "atr14": 1800,
            "volume_ratio": 0.72,
            "gap_pct": -0.84,
            "volatility_surge": False,
        },
        "000660": {
            "ma5": 176000, "ma20": 172000, "ma60": 180000, "ma120": 195000,
            "rsi14": 58.3,
            "macd": 2100, "macd_signal": 1500, "macd_histogram": 600,
            "bb_upper": 192000, "bb_middle": 178000, "bb_lower": 164000,
            "atr14": 5200,
            "volume_ratio": 1.15,
            "gap_pct": 1.42,
            "volatility_surge": False,
        },
        "035420": {
            "ma5": 196000, "ma20": 200000, "ma60": 210000, "ma120": 218000,
            "rsi14": 32.8,
            "macd": -2500, "macd_signal": -2100, "macd_histogram": -400,
            "bb_upper": 215000, "bb_middle": 200000, "bb_lower": 185000,
            "atr14": 6000,
            "volume_ratio": 0.90,
            "gap_pct": -1.02,
            "volatility_surge": False,
        },
        "051910": {
            "ma5": 288000, "ma20": 298000, "ma60": 325000, "ma120": 355000,
            "rsi14": 24.1,
            "macd": -8500, "macd_signal": -7200, "macd_histogram": -1300,
            "bb_upper": 315000, "bb_middle": 298000, "bb_lower": 272000,
            "atr14": 11000,
            "volume_ratio": 0.65,
            "gap_pct": -1.04,
            "volatility_surge": True,
        },
    }
    return indicators_data.get(ticker, {})
