import pandas as pd

def analyze_momentum(df: pd.DataFrame) -> dict:
    """
    모멘텀 점수 계산 (0-100점)
    목표: 단기적인 반등 강도, 수급 유입 및 가격 가속도를 측정
    """
    if len(df) < 5:
        return {'score': 50, 'factors': []}
        
    latest = df.iloc[-1]
    
    score = 0
    factors = []
    
    # 1. 단기 수익률 (5일전 대비)
    return_5d = (latest['close'] - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100
    if return_5d > 5:
        score += 25
        factors.append("5일 단기 급등 (>5%)")
    elif return_5d > 2:
        score += 15
        factors.append("단기 반등세")
        
    # 2. 거래량 실린 양봉 여부
    if 'Volume_Ratio' in df.columns:
        is_yangbong = latest['close'] > latest['open']
        is_gap_up = latest['Gap_Pct'] > 0 if 'Gap_Pct' in df.columns else False
        
        if is_yangbong and latest['Volume_Ratio'] > 1.5:
            score += 30
            factors.append("거래량 급증을 동반한 장대양봉")
        elif is_yangbong and latest['Volume_Ratio'] > 1.0:
            score += 15
            factors.append("거래량이 실린 양봉")
            
        if is_gap_up and latest['Gap_Pct'] > 1.0:
            score += 10
            factors.append("1% 이상 갭상승 출발")
            
    # 3. MACD 히스토그램 확산
    if 'MACD_Hist' in df.columns and len(df) > 2:
        hist_latest = latest['MACD_Hist']
        hist_prev = df['MACD_Hist'].iloc[-2]
        
        if hist_latest > 0 and hist_latest > hist_prev:
            score += 20
            factors.append("MACD 양의 모멘텀 확대")
        elif hist_latest < 0 and hist_latest > hist_prev: # 음수지만 커지고 있음 (골든크로스 임박)
            score += 15
            factors.append("MACD 하락 모멘텀 축소 (반등 시도)")

    score = min(score, 100)
    return {'score': score, 'factors': factors}
