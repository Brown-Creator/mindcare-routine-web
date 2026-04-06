import pandas as pd
import numpy as np

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    ATR (Average True Range) 계산 - 변동성 측정
    """
    result = df.copy()
    
    high_low = result['high'] - result['low']
    high_close = np.abs(result['high'] - result['close'].shift())
    low_close = np.abs(result['low'] - result['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    
    result['TR'] = true_range
    result['ATR'] = true_range.rolling(window=period).mean()
    
    # 변동성 비율: 가격대비 ATR (퍼센트)
    result['Volatility_Pct'] = (result['ATR'] / result['close']) * 100
    
    return result
