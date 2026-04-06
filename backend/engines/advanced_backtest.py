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

logger = logging.getLogger(__name__)

@dataclass
class BacktestConfig:
    initial_capital: float = 100_000_000
    commission_rate: float = 0.00015   # 매매 수수료 0.015%
    tax_rate: float = 0.0023           # 거래세 0.23% (매도시)
    slippage_pct: float = 0.05         # 슬리피지 0.05%
    max_position_pct: float = 0.20     # 최대 종목당 20%
    entry_threshold: float = 60
    exit_profit_pct: float = 5.0
    hard_stop_pct: float = 7.0
    trailing_stop_pct: float = 3.0

class AdvancedBacktestEngine:
    """고급 백테스트 엔진"""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()

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
                exec_price = price * (1 + self.config.slippage_pct / 100)
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
                exec_price = price * (1 + self.config.slippage_pct / 100)
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
                    exec_price = price * (1 - self.config.slippage_pct / 100)
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

        # 부트스트랩 시뮬레이션
        final_returns = []
        for _ in range(n_simulations):
            sampled = np.random.choice(returns, size=len(returns), replace=True)
            cumulative = np.prod(1 + np.array(sampled) / 100) - 1
            final_returns.append(cumulative * 100)

        final_returns = np.array(final_returns)
        return {
            "n_simulations": n_simulations,
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

        # Sharpe (연율화, rf=3.5%)
        excess = daily_ret - 0.035 / 252
        sharpe = (excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0

        # Sortino
        downside = daily_ret[daily_ret < 0].std()
        sortino = ((daily_ret.mean() - 0.035/252) / downside * np.sqrt(252)) if downside > 0 else 0

        # Calmar
        ann_ret = daily_ret.mean() * 252
        calmar = (ann_ret / abs(mdd/100)) if mdd != 0 else 0

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
            "trades": trades,
            "equity_curve": equity_curve,
        }
