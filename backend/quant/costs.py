"""
Transaction-cost & market-impact model.

A backtest that only subtracts a flat slippage_pct systematically overstates
capacity and Sharpe: real costs grow with how much of the day's volume you
demand. This module implements the components a real execution desk models:

    total one-way cost  =  commission  +  half-spread  +  market impact  (+ tax on sells)

Market impact uses the empirically robust **square-root law** (Almgren et al.,
Grinold-Kahn): the price you move scales with daily volatility times the square
root of your participation rate Q/ADV. This is what makes large positions in
thin KRX names genuinely expensive — and what a flat slippage misses entirely.

All rates are configurable; KRX defaults are provided. Unit-tested in
``backend/tests/test_costs.py``.
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass

_EPS = 1e-12


@dataclass
class CostModel:
    """
    Parameters
    ----------
    commission_bps : 편도 위탁수수료 (bps). KRX 온라인 ~1.5bp.
    sell_tax_bps   : 매도분 거래세 (bps). 매수에는 부과 안 됨.
    half_spread_bps: 절반 호가스프레드 (bps). 스프레드를 가로지르는 평균 비용.
    impact_coef    : 시장충격 계수 η (무차원). 제곱근법칙의 스케일(보통 0.1~1.0).
    impact_exponent: 참여율 지수 ψ. 0.5 = 제곱근법칙(표준).
    min_commission : 최소 수수료 (원).
    """
    commission_bps: float = 1.5
    sell_tax_bps: float = 18.0        # 2025 KRX 거래세 ~0.18% (매도시)
    half_spread_bps: float = 5.0
    impact_coef: float = 0.5
    impact_exponent: float = 0.5
    min_commission: float = 0.0

    # ── 시장충격 (가격 변동 분율) ──
    def market_impact_fraction(self, quantity: float, adv_shares: float,
                               daily_vol: float) -> float:
        """
        제곱근 시장충격 모델:

            impact = η · σ_daily · (Q / ADV)^ψ

        quantity   : 체결 주식 수 Q
        adv_shares : 평균 일거래량(주식 수) ADV
        daily_vol  : 일간 수익률 변동성 σ (예: 0.02 = 2%)
        반환: 가격 대비 충격 분율(0.001 = 10bp).
        """
        if adv_shares <= _EPS or quantity <= 0:
            return 0.0
        participation = quantity / adv_shares
        return float(self.impact_coef * max(daily_vol, 0.0)
                     * participation ** self.impact_exponent)

    def market_impact_bps(self, quantity: float, adv_shares: float,
                          daily_vol: float) -> float:
        return self.market_impact_fraction(quantity, adv_shares, daily_vol) * 1e4

    # ── 1회 체결 총비용 ──
    def trade_cost(self, price: float, quantity: float, side: str,
                   adv_shares: float = 0.0, daily_vol: float = 0.0) -> dict:
        """
        한 번의 체결에 대한 총비용(원)과 분해.

        side : "buy" / "sell"  (sell 에만 거래세 부과)
        adv_shares, daily_vol 제공 시 제곱근 시장충격을 더한다(미제공 시 충격=0).
        """
        notional = price * quantity
        if notional <= 0:
            return {"total": 0.0, "commission": 0.0, "tax": 0.0,
                    "spread": 0.0, "impact": 0.0, "cost_bps": 0.0}

        commission = max(notional * self.commission_bps / 1e4, self.min_commission)
        tax = notional * self.sell_tax_bps / 1e4 if side == "sell" else 0.0
        spread = notional * self.half_spread_bps / 1e4
        impact = notional * self.market_impact_fraction(quantity, adv_shares, daily_vol)

        total = commission + tax + spread + impact
        return {
            "total": round(total, 2),
            "commission": round(commission, 2),
            "tax": round(tax, 2),
            "spread": round(spread, 2),
            "impact": round(impact, 2),
            "cost_bps": round(total / notional * 1e4, 3),
        }

    def round_trip_bps(self, participation: float = 0.0, daily_vol: float = 0.0) -> float:
        """
        왕복(매수+매도) 비용을 bps로 추정(용량/회전율 분석용).
        participation = Q/ADV (편도 기준), 양방향 동일 가정.
        """
        impact = self.impact_coef * daily_vol * participation ** self.impact_exponent * 1e4
        buy = self.commission_bps + self.half_spread_bps + impact
        sell = self.commission_bps + self.sell_tax_bps + self.half_spread_bps + impact
        return float(buy + sell)


def apply_cost_to_return(gross_return: float, turnover: float,
                         cost_bps_one_way: float) -> float:
    """
    회전율 기반 순수익 = 총수익 − 회전율 × 편도비용.

    turnover: 해당 기간 단방향 회전율(0.5 = 자본의 50% 교체).
    포트폴리오 백테스트에서 비용을 수익에 반영하는 표준 방식.
    """
    return float(gross_return - turnover * cost_bps_one_way / 1e4)


def break_even_holding_days(expected_edge_bps: float, cost_model: CostModel,
                            participation: float = 0.0, daily_vol: float = 0.0,
                            daily_alpha_decay_bps: float = 0.0) -> float:
    """
    한 매매의 기대 엣지가 왕복 비용을 넘기 위한 최소 보유일수(근사).
    엣지가 비용보다 작으면 inf 반환(거래 자체가 손해).
    """
    rt = cost_model.round_trip_bps(participation, daily_vol)
    if expected_edge_bps <= rt:
        return float("inf")
    if daily_alpha_decay_bps <= 0:
        return 0.0
    return float((expected_edge_bps - rt) / daily_alpha_decay_bps)
