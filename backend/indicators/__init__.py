from .moving_averages import calculate_ma
from .rsi import calculate_rsi
from .macd import calculate_macd
from .bollinger import calculate_bollinger_bands
from .atr import calculate_atr
from .volume import calculate_volume_indicators
import pandas as pd

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """모든 기술적 지표를 한 번에 계산"""
    df = df.copy()
    
    if len(df) < 14:  # 최소 필요 데이터 길이 방어코드
        return df
        
    df = calculate_ma(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger_bands(df)
    df = calculate_atr(df)
    df = calculate_volume_indicators(df)
    
    return df
