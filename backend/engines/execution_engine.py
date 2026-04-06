"""
스마트 주문 실행 엔진
- TWAP (Time-Weighted Average Price)
- VWAP (Volume-Weighted Average Price)
- 슬리피지 모델링
- 마켓 임팩트 최소화
- 주문 분할 + 타이밍 최적화
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class ExecutionAlgo(str, Enum):
    MARKET = "시장가"
    LIMIT = "지정가"
    TWAP = "TWAP"
    VWAP = "VWAP"
    ICEBERG = "아이스버그"

@dataclass
class ExecutionPlan:
    ticker: str
    total_quantity: int
    algo: ExecutionAlgo
    child_orders: List[dict] = field(default_factory=list)
    estimated_slippage_pct: float = 0
    estimated_impact_pct: float = 0
    urgency: str = "보통"         # 긴급/보통/여유
    time_horizon_minutes: int = 30

@dataclass
class SlippageModel:
    """슬리피지 및 마켓 임팩트 모델"""
    base_spread_pct: float = 0.03      # 기본 스프레드 (%)
    impact_coefficient: float = 0.1     # 마켓 임팩트 계수
    volatility_multiplier: float = 1.0

class SmartExecutionEngine:
    """스마트 주문 실행"""

    def __init__(self, broker=None):
        self.broker = broker
        self._slippage = SlippageModel()
        self._execution_log: List[dict] = []

    def create_execution_plan(self, ticker: str, side: str, quantity: int,
                               price: float, avg_daily_volume: int,
                               volatility_pct: float = 2.0,
                               urgency: str = "보통") -> ExecutionPlan:
        """최적 실행 계획 생성"""

        participation_rate = quantity / max(avg_daily_volume, 1)

        # 알고리즘 자동 선택
        if urgency == "긴급" or participation_rate < 0.01:
            algo = ExecutionAlgo.MARKET
        elif participation_rate > 0.05:
            algo = ExecutionAlgo.ICEBERG
        elif participation_rate > 0.02:
            algo = ExecutionAlgo.TWAP
        else:
            algo = ExecutionAlgo.VWAP

        # 슬리피지 추정
        slippage = self._estimate_slippage(quantity, avg_daily_volume, volatility_pct)
        impact = self._estimate_market_impact(quantity, avg_daily_volume, price)

        # 자식 주문 분할
        if algo == ExecutionAlgo.TWAP:
            children = self._create_twap_orders(ticker, side, quantity, price)
        elif algo == ExecutionAlgo.VWAP:
            children = self._create_vwap_orders(ticker, side, quantity, price)
        elif algo == ExecutionAlgo.ICEBERG:
            children = self._create_iceberg_orders(ticker, side, quantity, price, avg_daily_volume)
        else:
            children = [{"ticker": ticker, "side": side, "quantity": quantity,
                        "price": price, "type": "시장가", "delay_sec": 0}]

        time_horizon = {
            "긴급": 5, "보통": 30, "여유": 60
        }.get(urgency, 30)

        return ExecutionPlan(
            ticker=ticker, total_quantity=quantity, algo=algo,
            child_orders=children,
            estimated_slippage_pct=round(slippage, 4),
            estimated_impact_pct=round(impact, 4),
            urgency=urgency, time_horizon_minutes=time_horizon,
        )

    def _create_twap_orders(self, ticker: str, side: str,
                             quantity: int, price: float,
                             n_slices: int = 5) -> List[dict]:
        """TWAP: 시간 균등 분할"""
        slice_qty = quantity // n_slices
        remainder = quantity % n_slices
        orders = []

        interval = 360  # 6분 간격 (30분 / 5)
        for i in range(n_slices):
            qty = slice_qty + (1 if i < remainder else 0)
            if qty <= 0:
                continue
            orders.append({
                "ticker": ticker, "side": side, "quantity": qty,
                "price": price, "type": "지정가",
                "delay_sec": i * interval,
                "slice": f"{i+1}/{n_slices}",
            })
        return orders

    def _create_vwap_orders(self, ticker: str, side: str,
                             quantity: int, price: float) -> List[dict]:
        """VWAP: 거래량 비중 기반 분할 (한국 시장 U자형 패턴)"""
        # 한국 시장 시간대별 거래량 비중 (U자형)
        volume_profile = {
            "09:00-09:30": 0.15,   # 개장 초반 높은 거래
            "09:30-10:00": 0.12,
            "10:00-11:00": 0.13,
            "11:00-12:00": 0.08,   # 점심 전 감소
            "12:00-13:00": 0.07,   # 점심시간 최저
            "13:00-14:00": 0.10,
            "14:00-14:30": 0.12,
            "14:30-15:00": 0.13,   # 장 마감 전 증가
            "15:00-15:30": 0.10,   # 동시호가
        }

        orders = []
        delay = 0
        for time_slot, weight in volume_profile.items():
            qty = max(1, int(quantity * weight))
            orders.append({
                "ticker": ticker, "side": side, "quantity": qty,
                "price": price, "type": "지정가",
                "time_slot": time_slot, "delay_sec": delay,
                "weight": weight,
            })
            delay += 1800  # 30분 간격

        # 잔량 조정
        total = sum(o["quantity"] for o in orders)
        if total < quantity and orders:
            orders[-1]["quantity"] += (quantity - total)

        return orders

    def _create_iceberg_orders(self, ticker: str, side: str,
                                quantity: int, price: float,
                                avg_volume: int) -> List[dict]:
        """아이스버그: 소량 반복 주문 (대량 주문 은닉)"""
        # 평균 거래량의 1% 이하로 분할
        show_qty = max(1, int(avg_volume * 0.01))
        n_orders = max(1, quantity // show_qty)

        orders = []
        remaining = quantity
        for i in range(n_orders):
            qty = min(show_qty, remaining)
            if qty <= 0:
                break
            orders.append({
                "ticker": ticker, "side": side, "quantity": qty,
                "price": price, "type": "지정가",
                "delay_sec": i * 120,  # 2분 간격
                "visible_qty": qty, "hidden_total": quantity,
            })
            remaining -= qty

        if remaining > 0 and orders:
            orders[-1]["quantity"] += remaining

        return orders

    def _estimate_slippage(self, quantity: int, avg_volume: int,
                           volatility_pct: float) -> float:
        """슬리피지 추정 (%)"""
        participation = quantity / max(avg_volume, 1)
        return self._slippage.base_spread_pct + \
               participation * volatility_pct * self._slippage.volatility_multiplier

    def _estimate_market_impact(self, quantity: int, avg_volume: int,
                                 price: float) -> float:
        """마켓 임팩트 추정 (%) - Square Root 모델"""
        participation = quantity / max(avg_volume, 1)
        # Almgren-Chriss 근사
        return self._slippage.impact_coefficient * (participation ** 0.5) * 100

    async def execute_plan(self, plan: ExecutionPlan) -> dict:
        """실행 계획 비동기 실행"""
        results = []
        for order in plan.child_orders:
            delay = order.get("delay_sec", 0)
            if delay > 0:
                await asyncio.sleep(min(delay, 5))  # 테스트 시 축소

            if self.broker:
                try:
                    if order["side"] == "매수":
                        result = await self.broker.place_buy_order(
                            order["ticker"], order["price"], order["quantity"]
                        )
                    else:
                        result = await self.broker.place_sell_order(
                            order["ticker"], order["price"], order["quantity"]
                        )
                    results.append({"status": "성공", "order": order, "result": result})
                except Exception as e:
                    results.append({"status": "실패", "order": order, "error": str(e)})
            else:
                results.append({"status": "시뮬레이션", "order": order})

        self._execution_log.append({
            "plan": plan, "results": results, "timestamp": datetime.now().isoformat()
        })

        return {
            "algo": plan.algo.value,
            "total_orders": len(plan.child_orders),
            "completed": len([r for r in results if r["status"] != "실패"]),
            "estimated_slippage": plan.estimated_slippage_pct,
            "estimated_impact": plan.estimated_impact_pct,
        }
