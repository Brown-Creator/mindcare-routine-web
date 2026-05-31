"""
고급 백테스트 엔진
- Walk-Forward 최적화
- Monte Carlo 시뮬레이션
- 수수료/슬리피지 모델
- 표준 성과 지표 (Sharpe, Sortino, Calmar, MDD)
"""
import numpy as np
import pandas as pd
from typing import Dict, List
from dataclasses import dataclass, field
import logging

from backend.indicators import calculate_all_indicators
from backend.strategies import evaluate_all_strategies
from backend.quant import validation as qval
from backend.quant import metrics as qmet
from backend.quant.costs import CostModel

logger = logging.getLogger(__name__)

@dataclass
class BacktestConfig:
    initial_capital: float = 100_000_000
    commission_rate: float = 0.00015   # 매매 수수료 0.015%
    tax_rate: float = 0.0023           # 거래세 0.23% (매도시)
    slippage_pct: float = 0.05         # 슬리피지 0.05% (flat, 레거시)
    max_position_pct: float = 0.20     # 최대 종목당 20%
    entry_threshold: float = 60
    exit_profit_pct: float = 5.0
    hard_stop_pct: float = 7.0
    trailing_stop_pct: float = 3.0
    # ★ 백테스트 과적합 보정용: 전략 탐색 과정에서 시도한 구성(설정조합)의 수.
    #    Deflated Sharpe Ratio 계산에 사용 — 많이 시도했을수록 허들이 높아진다.
    n_trials: int = 1
    # ★ 제곱근 시장충격 모델 사용 여부. True면 flat slippage 대신
    #    (절반 스프레드 + η·σ·√(Q/ADV)) 를 체결가 슬리피지로 적용 → 용량/회전율
    #    효과를 현실적으로 반영(거래량 대비 큰 주문일수록 비싸진다).
    use_impact_model: bool = False
    cost_model: CostModel = None

class AdvancedBacktestEngine:
    """고급 백테스트 엔진"""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()

    def _slippage_frac(self, df: pd.DataFrame, i: int, qty: int, side: str) -> float:
        """
        체결가에 적용할 슬리피지 분율.
        - 기본(레거시): 고정 slippage_pct.
        - use_impact_model=True: 절반 스프레드 + 제곱근 시장충격
          (η·σ·√(Q/ADV)). 거래량(ADV)·변동성(σ)은 직전 20일에서 추정.
        """
        if not self.config.use_impact_model:
            return self.config.slippage_pct / 100.0
        cm = self.config.cost_model or CostModel()
        lo = max(0, i - 20)
        vol_window = df['volume'].iloc[lo:i]
        adv = float(vol_window.mean()) if len(vol_window) else 0.0
        ret = df['close'].iloc[lo:i + 1].pct_change().dropna()
        dvol = float(ret.std()) if len(ret) > 2 else 0.02
        half_spread = cm.half_spread_bps / 1e4
        impact = cm.market_impact_fraction(qty, adv, dvol)
        return half_spread + impact

    def run(self, df_history: pd.DataFrame, ticker: str) -> dict:
        """기본 백테스트 실행 (수수료/슬리피지 포함)"""
        if len(df_history) < 60:
            return {"error": "데이터 부족 (최소 60일)"}

        df = df_history.copy().sort_values('date').reset_index(drop=True)
        df = calculate_all_indicators(df)

        capital = self.config.initial_capital
        holdings = 0
        avg_price = 0
        peak_equity = capital
        trades = []
        equity_curve = []

        for i in range(60, len(df)):
            sub = df.iloc[:i + 1]
            row = df.iloc[i]
            price = row['close']
            date = row['date']

            ev = evaluate_all_strategies(sub)
            sb = ev['bottom_probability_score']
            st = ev['trend_score']
            sm = ev['momentum_score']

            # 매수 (수수료+슬리피지 반영)
            if holdings == 0 and sb > self.config.entry_threshold and st > 40:
                invest = capital * self.config.max_position_pct
                qty_est = int(invest / price) if price > 0 else 0
                exec_price = price * (1 + self._slippage_frac(df, i, qty_est, "buy"))
                commission = invest * self.config.commission_rate
                qty = int((invest - commission) / exec_price)
                if qty > 0:
                    cost = qty * exec_price + commission
                    capital -= cost
                    holdings = qty
                    avg_price = exec_price
                    trades.append({
                        "date": date, "type": "BUY", "price": round(exec_price),
                        "qty": qty, "commission": round(commission),
                        "reason": "신규진입"
                    })

            # 물타기
            elif holdings > 0 and price < avg_price * 0.95 and sb > 70:
                invest = capital * 0.3
                qty_est = int(invest / price) if price > 0 else 0
                exec_price = price * (1 + self._slippage_frac(df, i, qty_est, "buy"))
                commission = invest * self.config.commission_rate
                qty = int((invest - commission) / exec_price)
                if qty > 0:
                    cost = qty * exec_price + commission
                    capital -= cost
                    new_total = holdings + qty
                    avg_price = (holdings * avg_price + qty * exec_price) / new_total
                    holdings = new_total
                    trades.append({
                        "date": date, "type": "BUY", "price": round(exec_price),
                        "qty": qty, "commission": round(commission),
                        "reason": "물타기"
                    })

            # 매도
            elif holdings > 0:
                profit_pct = (price - avg_price) / avg_price * 100

                should_sell = False
                reason = ""

                # 트레일링 스탑
                equity = capital + holdings * price
                if equity > peak_equity:
                    peak_equity = equity
                trailing_dd = (equity - peak_equity) / peak_equity * 100
                if trailing_dd < -self.config.trailing_stop_pct and profit_pct > 0:
                    should_sell = True
                    reason = f"트레일링 스탑 ({trailing_dd:.1f}%)"

                # 익절
                if profit_pct >= self.config.exit_profit_pct and sm < 50:
                    should_sell = True
                    reason = f"익절 ({profit_pct:.1f}%)"

                # 손절
                if profit_pct <= -self.config.hard_stop_pct:
                    should_sell = True
                    reason = f"손절 ({profit_pct:.1f}%)"

                if should_sell:
                    exec_price = price * (1 - self._slippage_frac(df, i, holdings, "sell"))
                    proceeds = holdings * exec_price
                    commission = proceeds * self.config.commission_rate
                    tax = proceeds * self.config.tax_rate
                    capital += proceeds - commission - tax
                    trades.append({
                        "date": date, "type": "SELL", "price": round(exec_price),
                        "qty": holdings, "profit_pct": round(profit_pct, 2),
                        "commission": round(commission), "tax": round(tax),
                        "reason": reason
                    })
                    holdings = 0

            equity = capital + holdings * price
            equity_curve.append({"time": date, "value": round(equity)})

        if not equity_curve:
            return {"error": "시뮬레이션 실패"}

        return self._calculate_metrics(trades, equity_curve)

    def walk_forward(self, df: pd.DataFrame, ticker: str,
                     train_window: int = 200, test_window: int = 60,
                     n_folds: int = 5) -> dict:
        """Walk-Forward 검증"""
        if len(df) < train_window + test_window:
            return {"error": "데이터 부족"}

        results = []
        total_len = len(df)
        step = (total_len - train_window) // n_folds

        for fold in range(n_folds):
            start = fold * step
            train_end = start + train_window
            test_end = min(train_end + test_window, total_len)

            if test_end > total_len:
                break

            test_df = df.iloc[train_end:test_end].copy()
            if len(test_df) < 30:
                continue

            # 각 fold에서 백테스트
            fold_result = self.run(test_df, ticker)
            if "error" not in fold_result:
                fold_result["fold"] = fold + 1
                fold_result["period"] = f"{test_df.iloc[0]['date']} ~ {test_df.iloc[-1]['date']}"
                results.append(fold_result)

        if not results:
            return {"error": "Walk-Forward 실패"}

        # 종합 통계
        returns = [r["total_return_pct"] for r in results]
        sharpes = [r.get("sharpe_ratio", 0) for r in results]
        mdds = [r.get("mdd_pct", 0) for r in results]

        return {
            "n_folds": len(results),
            "avg_return": round(np.mean(returns), 2),
            "std_return": round(np.std(returns), 2),
            "avg_sharpe": round(np.mean(sharpes), 3),
            "avg_mdd": round(np.mean(mdds), 2),
            "worst_return": round(min(returns), 2),
            "best_return": round(max(returns), 2),
            "consistency": round(sum(1 for r in returns if r > 0) / len(returns), 2),
            "fold_details": results,
        }

    def monte_carlo(self, df: pd.DataFrame, ticker: str,
                    n_simulations: int = 1000) -> dict:
        """Monte Carlo 시뮬레이션"""
        base_result = self.run(df, ticker)
        if "error" in base_result:
            return base_result

        base_trades = base_result.get("trades", [])
        if not base_trades:
            return {"error": "거래 없음"}

        returns = [t.get("profit_pct", 0) for t in base_trades if t["type"] == "SELL"]
        if not returns:
            return {"error": "매도 거래 없음"}

        # ★ 정상(stationary) 블록 부트스트랩.
        #   iid 재추출(np.random.choice)은 거래 수익률의 '연속성(연승/연패 군집)'을
        #   파괴해 위험을 과소평가한다. 평균 블록길이 b 의 기하분포 블록을 이어붙여
        #   자기상관 구조를 보존한다(Politis-Romano).
        returns = np.array(returns, dtype=float)
        n = len(returns)
        avg_block = max(2, int(round(n ** (1 / 3))))   # 경험적 최적 블록길이 ~ n^(1/3)
        p_new = 1.0 / avg_block
        rng = np.random.default_rng(42)
        final_returns = []
        for _ in range(n_simulations):
            sampled = np.empty(n)
            idx = rng.integers(0, n)
            for i in range(n):
                if i == 0 or rng.random() < p_new:
                    idx = rng.integers(0, n)         # 새 블록 시작
                else:
                    idx = (idx + 1) % n              # 같은 블록 연장(순환)
                sampled[i] = returns[idx]
            cumulative = np.prod(1 + sampled / 100) - 1
            final_returns.append(cumulative * 100)

        final_returns = np.array(final_returns)
        return {
            "n_simulations": n_simulations,
            "bootstrap_method": "stationary_block",
            "avg_block_length": avg_block,
            "mean_return": round(np.mean(final_returns), 2),
            "median_return": round(np.median(final_returns), 2),
            "std_return": round(np.std(final_returns), 2),
            "percentile_5": round(np.percentile(final_returns, 5), 2),
            "percentile_25": round(np.percentile(final_returns, 25), 2),
            "percentile_75": round(np.percentile(final_returns, 75), 2),
            "percentile_95": round(np.percentile(final_returns, 95), 2),
            "prob_positive": round(np.mean(final_returns > 0) * 100, 1),
            "prob_10pct_gain": round(np.mean(final_returns > 10) * 100, 1),
            "prob_10pct_loss": round(np.mean(final_returns < -10) * 100, 1),
            "worst_case": round(np.min(final_returns), 2),
            "best_case": round(np.max(final_returns), 2),
        }

    def _calculate_metrics(self, trades: list, equity_curve: list) -> dict:
        """표준 성과 지표 계산"""
        eq = pd.DataFrame(equity_curve)
        initial = self.config.initial_capital
        final = eq['value'].iloc[-1]
        total_return = (final - initial) / initial * 100

        # 일별 수익률
        eq['return'] = eq['value'].pct_change()
        daily_ret = eq['return'].dropna()

        # MDD
        eq['peak'] = eq['value'].cummax()
        eq['dd'] = (eq['value'] - eq['peak']) / eq['peak']
        mdd = eq['dd'].min() * 100

        # Sharpe/Sortino/Calmar — 견고한 quant.metrics 사용.
        #   (거래가 없어 자본곡선이 평평하면 분산≈0 → 예전 코드는 부동소수점 미세값으로
        #    가드를 통과해 Sharpe가 ±1e16 로 폭주했다. qmet 은 std<eps 시 0을 반환.)
        ret_arr = daily_ret.to_numpy()
        if len(ret_arr) < 2 or float(np.nanstd(ret_arr)) < 1e-10:
            sharpe = sortino = calmar = 0.0
        else:
            sharpe = qmet.sharpe_ratio(ret_arr, rf=0.035, periods_per_year=252)
            sortino = qmet.sortino_ratio(ret_arr, rf=0.035, periods_per_year=252)
            calmar = qmet.calmar_ratio(ret_arr, periods_per_year=252)

        # 거래 통계
        sells = [t for t in trades if t['type'] == 'SELL']
        wins = [t for t in sells if t.get('profit_pct', 0) > 0]
        losses = [t for t in sells if t.get('profit_pct', 0) <= 0]

        avg_win = np.mean([t['profit_pct'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['profit_pct'] for t in losses]) if losses else 0
        win_rate = len(wins) / max(len(sells), 1) * 100

        # 총 수수료/세금
        total_comm = sum(t.get('commission', 0) for t in trades)
        total_tax = sum(t.get('tax', 0) for t in trades)

        # Profit Factor
        gross_profit = sum(t['profit_pct'] for t in wins) if wins else 0
        gross_loss = abs(sum(t['profit_pct'] for t in losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # ★ 통계적 유의성: 백테스트 샤프가 '운'이 아닌지 검증
        #   - PSR: 진짜 샤프 > 0 일 확률(표본길이·왜도·첨도 보정)
        #   - DSR: n_trials 회 시도했을 때 기대 최대 샤프를 허들로 한 보정 샤프
        #   거래가 거의 없으면(자본곡선 평평) 통계적 의미가 없으므로 None 처리.
        if len(sells) < 3 or len(ret_arr) < 5 or float(np.nanstd(ret_arr)) < 1e-10:
            psr = None
            dsr = {"deflated_sharpe": None, "passes": None,
                   "n_trials": max(self.config.n_trials, 1)}
        else:
            psr = round(float(qval.probabilistic_sharpe_ratio(ret_arr, benchmark_sr=0.0)), 4)
            dsr = qval.deflated_sharpe_ratio(ret_arr, n_trials=max(self.config.n_trials, 1))

        return {
            "initial_capital": initial,
            "final_capital": round(final),
            "total_return_pct": round(total_return, 2),
            "mdd_pct": round(mdd, 2),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "calmar_ratio": round(calmar, 3),
            "profit_factor": round(profit_factor, 2),
            "trade_count": len(sells),
            "win_rate_pct": round(win_rate, 1),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "total_commission": round(total_comm),
            "total_tax": round(total_tax),
            # ★ 과적합/유의성 진단
            "probabilistic_sharpe": psr,
            "deflated_sharpe": dsr.get("deflated_sharpe"),
            "dsr_passes": dsr.get("passes"),
            "n_trials": dsr.get("n_trials"),
            "trades": trades,
            "equity_curve": equity_curve,
        }
