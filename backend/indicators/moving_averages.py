import pandas as pd
import numpy as np

def calculate_ma(df: pd.DataFrame, periods: list = [5, 20, 60, 120]) -> pd.DataFrame:
    """
    이동평균선 및 괴리율 계산
    """
    result = df.copy()
    for period in periods:
        # 단기 이동평균은 지수이동평균(EMA), 장기는 단순이동평균(SMA) 사용 가능하지만
        # 한국 주식 시장의 일반적 기준에 맞춰 모두 SMA로 통일
        result[f'MA{period}'] = result['close'].rolling(window=period).mean()
        # 괴리율 (현재 가격이 이동평균선과 얼마나 떨어져 있는지)
        result[f'MA{period}_disparity'] = (result['close'] - result[f'MA{period}']) / result[f'MA{period}'] * 100
        
    return result
