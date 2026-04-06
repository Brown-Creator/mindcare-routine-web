import pandas as pd
import numpy as np

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, multiplier: float = 2.0) -> pd.DataFrame:
    """
    볼린저 밴드 계산
    """
    result = df.copy()
    
    result['BB_Middle'] = result['close'].rolling(window=period).mean()
    std_dev = result['close'].rolling(window=period).std()
    
    result['BB_Upper'] = result['BB_Middle'] + (std_dev * multiplier)
    result['BB_Lower'] = result['BB_Middle'] - (std_dev * multiplier)
    
    # 밴드 폭 (Bandwidth) - 변동성 지표로 활용
    result['BB_Width'] = (result['BB_Upper'] - result['BB_Lower']) / result['BB_Middle']
    
    # %B 지표 - 밴드 내 현재 가격의 상대적 위치 (0 이하 = 하단 이탈, 1 이상 = 상단 돌파)
    result['BB_PB'] = (result['close'] - result['BB_Lower']) / (result['BB_Upper'] - result['BB_Lower'])
    
    return result
