"""
ML 앙상블 수익률 예측 엔진
- XGBoost/LightGBM 기반 수익률 방향 예측
- 앙상블 투표 (다수결 + 신뢰도 가중)
- Walk-forward 자동 재학습
- 피처 중요도 분석
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class MLPrediction:
    ticker: str
    direction: str = "중립"      # 상승/하락/중립
    probability: float = 0.5     # 상승 확률 (0~1)
    confidence: float = 0        # 예측 신뢰도 (0~1)
    expected_return: float = 0   # 예상 수익률 (%)
    model_agreement: float = 0   # 모델 간 합의도 (0~1)
    feature_importance: Dict = None

class MLEnsemble:
    """
    XGBoost + LightGBM + RandomForest 앙상블
    3개 모델의 예측을 합산하여 최종 결정
    """

    def __init__(self, model_dir: str = "data/models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.models = {}
        self._is_trained = False
        self._feature_names = []
        self._train_history = []

    def train(self, X: pd.DataFrame, y: pd.Series,
              feature_names: List[str] = None) -> dict:
        """
        모델 학습 (Walk-Forward 방식)
        y: 향후 N일 수익률 방향 (1=상승, 0=하락)
        """
        self._feature_names = feature_names or list(X.columns)

        # NaN 처리
        X = X.fillna(0)
        valid_mask = ~(X.isna().any(axis=1) | y.isna())
        X = X[valid_mask]
        y = y[valid_mask]

        if len(X) < 100:
            logger.warning(f"학습 데이터 부족 ({len(X)}건). 최소 100건 필요.")
            return {"error": "insufficient_data"}

        # Train/Val Split (시계열이므로 시간 기준)
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

        results = {}

        # 1. XGBoost
        try:
            import xgboost as xgb
            xgb_model = xgb.XGBClassifier(
                n_estimators=300, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8,
                reg_alpha=0.1, reg_lambda=1.0,
                eval_metric='logloss', use_label_encoder=False,
                random_state=42
            )
            xgb_model.fit(X_train, y_train,
                         eval_set=[(X_val, y_val)], verbose=False)
            self.models['xgboost'] = xgb_model
            val_acc = (xgb_model.predict(X_val) == y_val).mean()
            results['xgboost'] = {'accuracy': round(val_acc, 4)}
            logger.info(f"XGBoost 학습 완료 - 검증 정확도: {val_acc:.2%}")
        except ImportError:
            logger.warning("xgboost 미설치, 건너뜀")

        # 2. LightGBM
        try:
            import lightgbm as lgb
            lgb_model = lgb.LGBMClassifier(
                n_estimators=300, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8,
                reg_alpha=0.1, reg_lambda=1.0,
                verbose=-1, random_state=42
            )
            lgb_model.fit(X_train, y_train,
                         eval_set=[(X_val, y_val)])
            self.models['lightgbm'] = lgb_model
            val_acc = (lgb_model.predict(X_val) == y_val).mean()
            results['lightgbm'] = {'accuracy': round(val_acc, 4)}
            logger.info(f"LightGBM 학습 완료 - 검증 정확도: {val_acc:.2%}")
        except ImportError:
            logger.warning("lightgbm 미설치, 건너뜀")

        # 3. RandomForest (sklearn 기본 제공)
        try:
            from sklearn.ensemble import RandomForestClassifier
            rf_model = RandomForestClassifier(
                n_estimators=200, max_depth=8,
                min_samples_leaf=10, random_state=42, n_jobs=-1
            )
            rf_model.fit(X_train, y_train)
            self.models['random_forest'] = rf_model
            val_acc = (rf_model.predict(X_val) == y_val).mean()
            results['random_forest'] = {'accuracy': round(val_acc, 4)}
            logger.info(f"RandomForest 학습 완료 - 검증 정확도: {val_acc:.2%}")
        except Exception as e:
            logger.warning(f"RandomForest 학습 실패: {e}")

        self._is_trained = len(self.models) > 0
        if self._is_trained:
            self._save_models()
            self._train_history.append({
                "timestamp": pd.Timestamp.now().isoformat(),
                "samples": len(X),
                "results": results,
            })

        return results

    def predict(self, X: pd.DataFrame, ticker: str = "") -> MLPrediction:
        """앙상블 예측"""
        if not self._is_trained:
            self._load_models()
        if not self.models:
            return MLPrediction(ticker=ticker, direction="중립", confidence=0)

        X = X.fillna(0)
        predictions = {}
        probabilities = {}

        for name, model in self.models.items():
            try:
                pred = model.predict(X)[-1]
                prob = model.predict_proba(X)[-1]
                predictions[name] = int(pred)
                probabilities[name] = float(prob[1]) if len(prob) > 1 else 0.5
            except Exception as e:
                logger.warning(f"{name} 예측 실패: {e}")

        if not predictions:
            return MLPrediction(ticker=ticker, direction="중립", confidence=0)

        # 앙상블 투표
        avg_prob = np.mean(list(probabilities.values()))
        agreement = 1 - np.std(list(probabilities.values())) * 2  # 합의도

        if avg_prob > 0.6:
            direction = "상승"
        elif avg_prob < 0.4:
            direction = "하락"
        else:
            direction = "중립"

        confidence = abs(avg_prob - 0.5) * 2 * max(agreement, 0)

        # 피처 중요도 (XGBoost 우선)
        importance = self._get_feature_importance()

        return MLPrediction(
            ticker=ticker,
            direction=direction,
            probability=round(avg_prob, 3),
            confidence=round(confidence, 3),
            expected_return=round((avg_prob - 0.5) * 10, 2),
            model_agreement=round(max(agreement, 0), 3),
            feature_importance=importance,
        )

    def _get_feature_importance(self) -> Dict:
        """피처 중요도 상위 10개"""
        for name in ['xgboost', 'lightgbm', 'random_forest']:
            model = self.models.get(name)
            if model and hasattr(model, 'feature_importances_'):
                imp = model.feature_importances_
                if len(self._feature_names) == len(imp):
                    top_idx = np.argsort(imp)[-10:][::-1]
                    return {
                        self._feature_names[i]: round(float(imp[i]), 4)
                        for i in top_idx
                    }
        return {}

    def _save_models(self):
        """모델 저장"""
        for name, model in self.models.items():
            path = self.model_dir / f"{name}.pkl"
            try:
                with open(path, 'wb') as f:
                    pickle.dump(model, f)
            except Exception as e:
                logger.error(f"모델 저장 실패 [{name}]: {e}")

    def _load_models(self):
        """모델 로드"""
        for name in ['xgboost', 'lightgbm', 'random_forest']:
            path = self.model_dir / f"{name}.pkl"
            if path.exists():
                try:
                    with open(path, 'rb') as f:
                        self.models[name] = pickle.load(f)
                    self._is_trained = True
                except Exception as e:
                    logger.warning(f"모델 로드 실패 [{name}]: {e}")
