import pandas as pd

def analyze_trend(df: pd.DataFrame) -> dict:
    """
    추세 점수 계산 (0-100점)
    목표: 현재 주가의 추세(상승, 하락, 횡보) 강도를 점수화
    역배열 속 반등인지, 정배열 상승인지 구분
    """
    if len(df) < 120:
        return {'score': 50, 'factors': []}
        
    latest = df.iloc[-1]
    
    score = 0
    factors = []
    
    # 1. 정배열 / 역배열 (단기 ~ 장기)
    if all(k in df.columns for k in ['MA5', 'MA20', 'MA60', 'MA120']):
        if latest['MA5'] > latest['MA20'] > latest['MA60'] > latest['MA120']:
            score += 40
            factors.append("완벽한 정배열 상승 추세")
        elif latest['MA20'] > latest['MA60'] > latest['MA120']:
            score += 30
            factors.append("중장기 정배열")
        elif latest['MA5'] < latest['MA20'] < latest['MA60'] < latest['MA120']:
            score += 5
            factors.append("완벽한 역배열 하락 추세")
        else:
            score += 15  # 혼조 구간
            
        # 2. 이동평균선 방향 (기울기)
        if len(df) >= 3:
            ma20_slope = latest['MA20'] - df['MA20'].iloc[-3]
            ma60_slope = latest['MA60'] - df['MA60'].iloc[-3]
            
            if ma20_slope > 0:
                score += 15
                factors.append("20일선 우상향")
            if ma60_slope > 0:
                score += 20
                factors.append("60일선 우상향 (추세 안정)")

    # 3. MACD
    if 'MACD' in df.columns and 'MACD_Signal' in df.columns:
        if latest['MACD'] > latest['MACD_Signal']:
            score += 15
            factors.append("MACD 골든크로스 / 강세")
        if latest['MACD'] > 0:
            score += 10
            factors.append("MACD 0선 상회 (안정적 상승 영역)")
            
    score = min(max(score, 0), 100)
    return {'score': score, 'factors': factors}
