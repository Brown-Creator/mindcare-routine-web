import pandas as pd

def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    MACD (Moving Average Convergence Divergence) 계산
    """
    result = df.copy()
    
    ema_fast = result['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = result['close'].ewm(span=slow, adjust=False).mean()
    
    result['MACD'] = ema_fast - ema_slow
    result['MACD_Signal'] = result['MACD'].ewm(span=signal, adjust=False).mean()
    result['MACD_Hist'] = result['MACD'] - result['MACD_Signal']
    
    return result
