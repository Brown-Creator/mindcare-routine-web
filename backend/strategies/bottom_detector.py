import pandas as pd

def analyze_bottom(df: pd.DataFrame) -> dict:
    """
    바닥 확률 점수 계산 (0-100점)
    목표: 하락이 진정되고 바닥을 다지는 구간을 점수화
    """
    if len(df) < 60:
        return {'score': 0, 'factors': []}
        
    latest = df.iloc[-1]
    
    score = 0
    factors = []
    
    # 1. RSI 기반 (과매도 구간)
    if 'RSI' in df.columns:
        if latest['RSI'] < 30:
            score += 30
            factors.append("RSI 30 이하 심해 과매도")
        elif latest['RSI'] < 40:
            score += 20
            factors.append("RSI 40 이하 진과매도 터치")
        
        # 다이버전스 (주가는 하락하는데 RSI는 상승하는지) - 대략적 체크
        if len(df) >= 20:
            recent_low = df['close'].iloc[-10:].min()
            past_low = df['close'].iloc[-20:-10].min()
            recent_rsi = df['RSI'].iloc[-10:].min()
            past_rsi = df['RSI'].iloc[-20:-10].min()
            
            if recent_low < past_low and recent_rsi > past_rsi:
                score += 20
                factors.append("RSI 상승 다이버전스 발생")
                
    # 2. 거래량 바닥 (투매가 끝나고 거래가 마르는 현상)
    if 'Volume_Drying_Up' in df.columns and latest['Volume_Drying_Up']:
        score += 15
        factors.append("단기 거래량 바닥 (매도세 진정)")
        
    # 3. 볼린저 밴드 하단 근접 (주가가 볼린저 하단 근처 혹은 이탈)
    if 'BB_PB' in df.columns:
        if latest['BB_PB'] < 0.1:  # 거의 하단
            score += 15
            factors.append("볼린저밴드 하단 터치")
            
    # 4. 20일 이동평균선 이격도 대폭 하회
    if 'MA20_disparity' in df.columns:
        if latest['MA20_disparity'] < -10:  # 20일선 보다 10% 이상 하락 (급락)
            score += 20
            factors.append("20일선 대비 깊은 마이너스 괴리율")
            
    score = min(score, 100)
    return {'score': score, 'factors': factors}
