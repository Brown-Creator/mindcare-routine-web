import pandas as pd
import numpy as np

def calculate_volume_indicators(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    거래량 지표 및 가격/거래량 변동성 측정
    """
    result = df.copy()
    
    # 평균 거래량
    result['Volume_MA'] = result['volume'].rolling(window=period).mean()
    
    # 거래량 비율 (현재 거래량 / 평균 거래량) - 1 이상이면 거래량 증가
    result['Volume_Ratio'] = result['volume'] / result['Volume_MA']
    
    # OBV (On-Balance Volume)
    daily_return = result['close'].diff()
    direction = np.where(daily_return > 0, 1, np.where(daily_return < 0, -1, 0))
    result['OBV'] = (direction * result['volume']).cumsum()
    
    # 거래량 급감 여부 (추세의 바닥을 확인할 때 유용)
    result['Volume_Drying_Up'] = (result['Volume_Ratio'] < 0.5) & (result['Volume_Ratio'].rolling(window=3).mean() < 0.7)
    
    # 갭 발생 여부
    result['Gap_Pct'] = (result['open'] - result['close'].shift()) / result['close'].shift() * 100
    
    return result
