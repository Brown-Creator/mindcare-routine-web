def analyze_supply_demand(mock_data: dict) -> dict:
    """
    수급 분석 (0-100점)
    키움 API에서 실시간 기관/외인 수급은 TR을 따로 호출하거나, 
    일별/시간별 누적 추이를 봐야 함.
    이 파일은 엔진 인터페이스에 맞춰 향후 수급 분석을 위한 뼈대를 제공.
    """
    
    # 1단계에서는 우선 mock_data를 기반으로 상태를 파악함
    # 실전에서는 투자자별 매매동향(OPT10059 등)을 활용
    
    score = 50
    factors = []
    
    if "외국인" in str(mock_data.get('reason', '')):
        score += 20
        factors.append("외국인 순매수 지속 추정")
    
    if "기관" in str(mock_data.get('reason', '')):
        score += 20
        factors.append("기관 쌍끌이 매수 추정")

    return {'score': min(score, 100), 'factors': factors}
