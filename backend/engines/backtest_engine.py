"""
과거 OHLCV 데이터를 루프하며 매매 전략의 성과를 분석하는 백테스팅 엔진
"""
import pandas as pd
from backend.indicators import calculate_all_indicators
from backend.strategies import evaluate_all_strategies

class BacktestEngine:
    def __init__(self, initial_capital=100000000):
        self.initial_capital = initial_capital

    def run(self, df_history: pd.DataFrame, ticker: str):
        if len(df_history) < 60:
            return {"error": "데이터가 부족합니다 (최소 60일 필요)"}
            
        # 미래 참조 방지: 전체 지표는 shift 기반이나 rolling 기반이므로 미리 계산해도 안전합니다.
        # 단, 실제 환경에서는 철저를 위해 for문 안에서 계산하나, 성능(Mock)을 위해 밖에 둡니다.
        df = df_history.copy()
        df = df.sort_values('date').reset_index(drop=True)
        df_ind = calculate_all_indicators(df)
        
        capital = self.initial_capital
        holdings = 0
        avg_price = 0
        
        equity_curve = []
        trades = []
        
        for i in range(60, len(df_ind)):
            sub_df = df_ind.iloc[:i+1] # 현재 시점(i)까지의 데이터
            current_row = df_ind.iloc[i]
            
            date = current_row['date']
            current_price = current_row['close']
            
            # 전략 엔진 통해 점수 평가
            eval_res = evaluate_all_strategies(sub_df)
            
            score_bottom = eval_res['bottom_probability_score']
            score_trend = eval_res['trend_score']
            score_momentum = eval_res['momentum_score']
            
            # 1. 매수 로직 (신규진입 조건)
            if holdings == 0 and score_bottom > 60 and score_trend > 40:
                # 자금의 20%만 매수 투입 (분할매수)
                invest_amount = capital * 0.2
                quantity = int(invest_amount / current_price)
                if quantity > 0:
                    capital -= (quantity * current_price)
                    holdings += quantity
                    avg_price = current_price
                    trades.append({
                        "date": date, "type": "BUY", "price": current_price, 
                        "qty": quantity, "reason": "신규 진입 (바닥확률+추세강도 조건충족)"
                    })
                    
            # 2. 물타기 로직 (1차 매수 후 -5% 초과 하락 시)
            elif holdings > 0 and current_price < avg_price * 0.95 and score_bottom > 70:
                invest_amount = capital * 0.3 # 30% 물타기
                quantity = int(invest_amount / current_price)
                if quantity > 0:
                    capital -= (quantity * current_price)
                    new_total_qty = holdings + quantity
                    avg_price = ((holdings * avg_price) + (quantity * current_price)) / new_total_qty
                    holdings = new_total_qty
                    trades.append({
                        "date": date, "type": "BUY", "price": current_price, 
                        "qty": quantity, "reason": "1차 물타기 (강한 바닥재확인)"
                    })

            # 3. 매도 로직 (하드스탑 -7% 또는 익절 +5%)
            elif holdings > 0:
                profit_pct = (current_price - avg_price) / avg_price * 100
                
                if profit_pct >= 5.0 and score_momentum < 50:
                    # 익절 
                    capital += (holdings * current_price)
                    trades.append({
                        "date": date, "type": "SELL", "price": current_price, 
                        "qty": holdings, "reason": "익절 (+5% 도달 및 모멘텀 둔화)", "profit": profit_pct
                    })
                    holdings = 0
                    
                elif profit_pct <= -7.0:
                    # 하드스탑 손절
                    capital += (holdings * current_price)
                    trades.append({
                        "date": date, "type": "SELL", "price": current_price, 
                        "qty": holdings, "reason": "하드스탑 손절 (-7% 초과)", "profit": profit_pct
                    })
                    holdings = 0
            
            # 자산 밸류 트래킹
            equity = capital + (holdings * current_price)
            equity_curve.append({
                "time": date,
                "value": equity
            })

        if not equity_curve:
            return {"error": "시뮬레이션 데이터 생성 실패"}

        eq_df = pd.DataFrame(equity_curve)
        eq_df['drawdown'] = (eq_df['value'] / eq_df['value'].cummax()) - 1
        mdd = eq_df['drawdown'].min() * 100
        
        final_value = equity_curve[-1]['value']
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100
        
        sell_trades = [t for t in trades if t['type'] == 'SELL']
        win_trades = [t for t in sell_trades if t.get('profit', 0) > 0]
        win_rate = (len(win_trades) / len(sell_trades) * 100) if sell_trades else 0
        
        return {
            "initial_capital": self.initial_capital,
            "final_capital": final_value,
            "total_return_pct": round(total_return, 2),
            "mdd_pct": round(mdd, 2),
            "trade_count": len(sell_trades),
            "win_rate_pct": round(win_rate, 2),
            "trades": trades,
            "equity_curve": equity_curve
        }
