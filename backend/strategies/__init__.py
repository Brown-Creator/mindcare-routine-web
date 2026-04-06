from .bottom_detector import analyze_bottom
from .trend_analyzer import analyze_trend
from .momentum_scorer import analyze_momentum
from .supply_demand import analyze_supply_demand

def evaluate_all_strategies(df, extra_data=None):
    """
    모든 전략을 평가해 최종 점수와 종합 의견을 도출
    """
    extra = extra_data or {}
    
    bottom = analyze_bottom(df)
    trend = analyze_trend(df)
    momentum = analyze_momentum(df)
    supply = analyze_supply_demand(extra)
    
    return {
        'bottom_probability_score': bottom['score'],
        'trend_score': trend['score'],
        'momentum_score': momentum['score'],
        'supply_demand_score': supply['score'],
        'reasons': list(set(bottom['factors'] + trend['factors'] + momentum['factors'] + supply['factors']))
    }
