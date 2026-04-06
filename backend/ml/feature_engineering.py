"""
피처 엔지니어링 - 모든 ML 모델의 공통 입력 생성
- 기술적 지표 파생 피처 120+개
- 매크로 팩터 피처
- 수급/센티먼트 피처
- 시계열 피처 (lag, rolling, expanding)
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """종합 피처 엔지니어링"""

    @staticmethod
    def build_features(df: pd.DataFrame, macro: dict = None,
                       sentiment: dict = None, flow: dict = None) -> pd.DataFrame:
        """모든 피처를 한번에 생성"""
        feat = df.copy()
        feat = FeatureEngineer._price_features(feat)
        feat = FeatureEngineer._volume_features(feat)
        feat = FeatureEngineer._momentum_features(feat)
        feat = FeatureEngineer._volatility_features(feat)
        feat = FeatureEngineer._pattern_features(feat)
        feat = FeatureEngineer._lag_features(feat)

        if macro:
            feat = FeatureEngineer._macro_features(feat, macro)
        if sentiment:
            feat = FeatureEngineer._sentiment_features(feat, sentiment)
        if flow:
            feat = FeatureEngineer._flow_features(feat, flow)

        return feat

    @staticmethod
    def _price_features(df: pd.DataFrame) -> pd.DataFrame:
        """가격 기반 피처"""
        c = df['close']
        h = df['high']
        l = df['low']
        o = df['open']

        # 수익률 시리즈
        for period in [1, 2, 3, 5, 10, 20, 60]:
            df[f'return_{period}d'] = c.pct_change(period)

        # 로그 수익률
        df['log_return_1d'] = np.log(c / c.shift(1))
        df['log_return_5d'] = np.log(c / c.shift(5))

        # 이동평균 괴리율 (정규화)
        for ma in [5, 20, 60, 120]:
            ma_col = c.rolling(ma).mean()
            df[f'dist_ma{ma}'] = (c - ma_col) / ma_col

        # 이동평균 크로스
        df['ma5_20_cross'] = (c.rolling(5).mean() - c.rolling(20).mean()) / c
        df['ma20_60_cross'] = (c.rolling(20).mean() - c.rolling(60).mean()) / c

        # 이동평균 정배열 정도 (0~1)
        ma5 = c.rolling(5).mean()
        ma20 = c.rolling(20).mean()
        ma60 = c.rolling(60).mean()
        ma120 = c.rolling(120).mean()
        df['ma_alignment'] = (
            (ma5 > ma20).astype(float) + (ma20 > ma60).astype(float) +
            (ma60 > ma120).astype(float)
        ) / 3

        # 고가/저가 대비 위치
        df['high_low_range'] = (h - l) / l
        df['close_in_range'] = (c - l) / (h - l).replace(0, np.nan)

        # N일 최고가/최저가 대비
        for period in [20, 60, 120]:
            df[f'from_high_{period}d'] = c / h.rolling(period).max() - 1
            df[f'from_low_{period}d'] = c / l.rolling(period).min() - 1

        # 캔들 패턴
        body = abs(c - o)
        upper_shadow = h - pd.concat([c, o], axis=1).max(axis=1)
        lower_shadow = pd.concat([c, o], axis=1).min(axis=1) - l
        df['candle_body_ratio'] = body / (h - l).replace(0, np.nan)
        df['upper_shadow_ratio'] = upper_shadow / (h - l).replace(0, np.nan)
        df['lower_shadow_ratio'] = lower_shadow / (h - l).replace(0, np.nan)
        df['is_bullish'] = (c > o).astype(int)

        return df

    @staticmethod
    def _volume_features(df: pd.DataFrame) -> pd.DataFrame:
        """거래량 기반 피처"""
        v = df['volume'].astype(float)
        c = df['close']

        # 거래량 이동평균 비율
        for period in [5, 10, 20]:
            df[f'vol_ratio_{period}d'] = v / v.rolling(period).mean()

        # 거래대금
        df['turnover'] = v * c
        df['turnover_ratio_20d'] = df['turnover'] / df['turnover'].rolling(20).mean()

        # OBV (On-Balance Volume)
        direction = np.sign(c.diff())
        df['obv'] = (direction * v).cumsum()
        df['obv_ma20'] = df['obv'].rolling(20).mean()
        df['obv_trend'] = (df['obv'] - df['obv_ma20']) / df['obv_ma20'].replace(0, np.nan)

        # 거래량 가중 가격 (VWAP 근사)
        df['vwap_20d'] = (c * v).rolling(20).sum() / v.rolling(20).sum()
        df['price_vs_vwap'] = (c - df['vwap_20d']) / df['vwap_20d']

        # 거래량 클라이맥스 (폭락/폭등 감지)
        df['vol_zscore'] = (v - v.rolling(60).mean()) / v.rolling(60).std()

        # 축적/분산 (A/D Line)
        mfm = ((c - df['low']) - (df['high'] - c)) / (df['high'] - df['low']).replace(0, np.nan)
        df['ad_line'] = (mfm.fillna(0) * v).cumsum()

        return df

    @staticmethod
    def _momentum_features(df: pd.DataFrame) -> pd.DataFrame:
        """모멘텀 피처"""
        c = df['close']

        # RSI
        delta = c.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        for period in [7, 14, 21]:
            ag = gain.ewm(alpha=1/period, min_periods=period).mean()
            al = loss.ewm(alpha=1/period, min_periods=period).mean()
            df[f'rsi_{period}'] = 100 - 100 / (1 + ag / al.replace(0, np.nan))

        # Stochastic RSI
        rsi14 = df.get('rsi_14', pd.Series(dtype=float))
        if not rsi14.empty:
            rsi_min = rsi14.rolling(14).min()
            rsi_max = rsi14.rolling(14).max()
            df['stoch_rsi'] = (rsi14 - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan)

        # MACD 히스토그램 기울기
        ema12 = c.ewm(span=12).mean()
        ema26 = c.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        hist = macd - signal
        df['macd_hist'] = hist
        df['macd_hist_slope'] = hist.diff()
        df['macd_hist_accel'] = hist.diff().diff()

        # Rate of Change
        for p in [5, 10, 20]:
            df[f'roc_{p}d'] = c.pct_change(p) * 100

        # Williams %R
        for p in [14, 28]:
            hh = df['high'].rolling(p).max()
            ll = df['low'].rolling(p).min()
            df[f'williams_r_{p}'] = (hh - c) / (hh - ll).replace(0, np.nan) * -100

        # CCI (Commodity Channel Index)
        tp = (df['high'] + df['low'] + c) / 3
        tp_sma = tp.rolling(20).mean()
        tp_mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean())
        df['cci_20'] = (tp - tp_sma) / (0.015 * tp_mad)

        return df

    @staticmethod
    def _volatility_features(df: pd.DataFrame) -> pd.DataFrame:
        """변동성 피처"""
        c = df['close']
        ret = c.pct_change()

        # 실현 변동성
        for period in [5, 10, 20, 60]:
            df[f'realized_vol_{period}d'] = ret.rolling(period).std() * np.sqrt(252)

        # Parkinson 변동성 (고가/저가 기반, 더 정확)
        hl_ratio = np.log(df['high'] / df['low'])
        for period in [10, 20]:
            df[f'parkinson_vol_{period}d'] = np.sqrt(
                (hl_ratio ** 2).rolling(period).mean() / (4 * np.log(2))
            ) * np.sqrt(252)

        # 변동성 레짐 (현재 vs 장기)
        short_vol = ret.rolling(10).std()
        long_vol = ret.rolling(60).std()
        df['vol_regime'] = short_vol / long_vol.replace(0, np.nan)

        # ATR 기반 정규화 변동성
        tr = pd.concat([
            df['high'] - df['low'],
            abs(df['high'] - c.shift()),
            abs(df['low'] - c.shift())
        ], axis=1).max(axis=1)
        df['atr_14_pct'] = tr.rolling(14).mean() / c * 100

        # Bollinger Band Width
        bb_mid = c.rolling(20).mean()
        bb_std = c.rolling(20).std()
        df['bb_width'] = (4 * bb_std) / bb_mid
        df['bb_pctb'] = (c - (bb_mid - 2*bb_std)) / (4*bb_std).replace(0, np.nan)

        return df

    @staticmethod
    def _pattern_features(df: pd.DataFrame) -> pd.DataFrame:
        """패턴 인식 피처"""
        c = df['close']

        # 연속 상승/하락 일수
        up = (c.diff() > 0).astype(int)
        down = (c.diff() < 0).astype(int)
        df['consecutive_up'] = up.groupby((up != up.shift()).cumsum()).cumsum()
        df['consecutive_down'] = down.groupby((down != down.shift()).cumsum()).cumsum()

        # 지지/저항선 접근도
        for period in [20, 60]:
            df[f'support_{period}d'] = df['low'].rolling(period).min()
            df[f'resistance_{period}d'] = df['high'].rolling(period).max()
            support = df[f'support_{period}d']
            resistance = df[f'resistance_{period}d']
            df[f'dist_support_{period}d'] = (c - support) / support
            df[f'dist_resist_{period}d'] = (resistance - c) / c

        # 갭
        df['gap_pct'] = (df['open'] - c.shift()) / c.shift() * 100

        return df

    @staticmethod
    def _lag_features(df: pd.DataFrame, max_lag: int = 5) -> pd.DataFrame:
        """시차(lag) 피처 - 시계열 모델용"""
        for col in ['return_1d', 'vol_ratio_5d', 'rsi_14']:
            if col in df.columns:
                for lag in range(1, max_lag + 1):
                    df[f'{col}_lag{lag}'] = df[col].shift(lag)
        return df

    @staticmethod
    def _macro_features(df: pd.DataFrame, macro: dict) -> pd.DataFrame:
        """매크로 피처 주입"""
        df['vix'] = macro.get('vix', 20)
        df['usd_krw'] = macro.get('usd_krw', 1350)
        df['kospi_chg'] = macro.get('kospi_change_pct', 0)
        df['yield_spread'] = macro.get('yield_spread', 0)
        df['fear_greed'] = macro.get('fear_greed_index', 50)
        return df

    @staticmethod
    def _sentiment_features(df: pd.DataFrame, sent: dict) -> pd.DataFrame:
        """센티먼트 피처 주입"""
        df['news_sentiment'] = sent.get('score', 0)
        df['news_impact'] = sent.get('positive_ratio', 0) - sent.get('negative_ratio', 0)
        return df

    @staticmethod
    def _flow_features(df: pd.DataFrame, flow: dict) -> pd.DataFrame:
        """수급 피처 주입"""
        df['flow_score'] = flow.get('score', 50) / 100
        df['smart_money'] = 1 if flow.get('smart_money_signal') == '쌍끌이 매수' else (
            -1 if flow.get('smart_money_signal') == '쌍끌이 매도' else 0)
        return df

    @staticmethod
    def get_feature_names() -> list:
        """ML 모델에 사용할 핵심 피처 이름 목록"""
        return [
            'return_1d', 'return_5d', 'return_10d', 'return_20d',
            'dist_ma5', 'dist_ma20', 'dist_ma60', 'ma_alignment',
            'ma5_20_cross', 'ma20_60_cross',
            'close_in_range', 'from_high_60d', 'from_low_60d',
            'vol_ratio_5d', 'vol_ratio_20d', 'vol_zscore', 'obv_trend',
            'price_vs_vwap', 'turnover_ratio_20d',
            'rsi_7', 'rsi_14', 'rsi_21', 'stoch_rsi',
            'macd_hist', 'macd_hist_slope', 'macd_hist_accel',
            'roc_5d', 'roc_10d', 'roc_20d',
            'williams_r_14', 'cci_20',
            'realized_vol_10d', 'realized_vol_20d', 'vol_regime',
            'atr_14_pct', 'bb_width', 'bb_pctb',
            'consecutive_up', 'consecutive_down',
            'dist_support_20d', 'dist_resist_20d', 'gap_pct',
            'candle_body_ratio', 'is_bullish',
        ]
