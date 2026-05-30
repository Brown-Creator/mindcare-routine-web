"""
ML 앙상블 수익률 예측 엔진 (★ 누수 제거 + 확률 보정 + 스킬 가중 ★)

이전 구현의 치명적 문제:
  - docstring은 "Walk-forward"라 했지만 실제로는 단일 80/20 분할 1회 → 라벨(전방
    수익률)이 겹치는 구간에서 룩어헤드 누수 발생. 보고된 검증 정확도가 부풀려진다.
  - 3개 모델을 단순 평균(동일 가중) → 약한 모델이 강한 모델을 희석.
  - 확률 보정(calibration) 부재 → predict_proba 값을 그대로 신뢰.

개선:
  - backend.quant.validation.PurgedWalkForward 로 purge+embargo가 적용된 워크포워드
    교차검증을 수행해 '정직한' OOS 성능을 측정한다.
  - 모델별 OOS 스킬(정확도−0.5, 음수는 0)로 앙상블 가중치를 부여한다.
  - Platt scaling(로지스틱 재보정)으로 확률을 보정한다.
  - xgboost/lightgbm/sklearn 미설치 환경에서도 import/predict가 깨지지 않도록 방어.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import logging
import pickle
from pathlib import Path

from backend.quant.validation import PurgedWalkForward

logger = logging.getLogger(__name__)


@dataclass
class MLPrediction:
    ticker: str
    direction: str = "중립"      # 상승/하락/중립
    probability: float = 0.5     # 상승 확률 (0~1, 보정 후)
    confidence: float = 0        # 예측 신뢰도 (0~1)
    expected_return: float = 0   # 예상 수익률 (%)
    model_agreement: float = 0   # 모델 간 합의도 (0~1)
    feature_importance: Dict = None


def _platt_fit(scores: np.ndarray, labels: np.ndarray) -> Tuple[float, float]:
    """
    Platt scaling: P(y=1) = σ(a·s + b) 의 (a, b)를 로그손실 최소화로 적합.
    scores 는 모델의 원확률(또는 로짓). scipy 만으로 구현(=sklearn 불필요).
    """
    from scipy.optimize import minimize
    s = np.clip(scores, 1e-6, 1 - 1e-6)
    logit = np.log(s / (1 - s))                    # 확률 → 로짓
    y = labels.astype(float)

    def nll(params):
        a, b = params
        z = a * logit + b
        p = 1.0 / (1.0 + np.exp(-z))
        p = np.clip(p, 1e-9, 1 - 1e-9)
        return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

    res = minimize(nll, x0=np.array([1.0, 0.0]), method="Nelder-Mead",
                   options={"maxiter": 500, "xatol": 1e-6, "fatol": 1e-8})
    a, b = res.x
    return float(a), float(b)


def _platt_apply(prob: float, ab: Tuple[float, float]) -> float:
    a, b = ab
    p = float(np.clip(prob, 1e-6, 1 - 1e-6))
    logit = np.log(p / (1 - p))
    return float(1.0 / (1.0 + np.exp(-(a * logit + b))))


class MLEnsemble:
    """XGBoost + LightGBM + RandomForest 앙상블 (누수 제거·확률 보정·스킬 가중)."""

    def __init__(self, model_dir: str = "data/models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.models = {}
        self._is_trained = False
        self._feature_names = []
        self._train_history = []
        self._model_weights: Dict[str, float] = {}     # OOS 스킬 기반 앙상블 가중
        self._calibration: Dict[str, Tuple[float, float]] = {}  # 모델별 Platt (a,b)

    # ── 모델 팩토리 (지연 임포트로 미설치 환경 방어) ──
    @staticmethod
    def _build_models() -> Dict[str, object]:
        models = {}
        try:
            import xgboost as xgb
            models["xgboost"] = xgb.XGBClassifier(
                n_estimators=300, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=1.0,
                eval_metric="logloss", random_state=42)
        except ImportError:
            logger.warning("xgboost 미설치, 건너뜀")
        try:
            import lightgbm as lgb
            models["lightgbm"] = lgb.LGBMClassifier(
                n_estimators=300, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=1.0,
                verbose=-1, random_state=42)
        except ImportError:
            logger.warning("lightgbm 미설치, 건너뜀")
        try:
            from sklearn.ensemble import RandomForestClassifier
            models["random_forest"] = RandomForestClassifier(
                n_estimators=200, max_depth=8, min_samples_leaf=10,
                random_state=42, n_jobs=-1)
        except ImportError:
            logger.warning("sklearn 미설치, RandomForest 건너뜀")
        return models

    def train(self, X: pd.DataFrame, y: pd.Series,
              feature_names: List[str] = None,
              label_horizon: int = 5, cv_splits: int = 5) -> dict:
        """
        모델 학습 + purged walk-forward 교차검증.

        label_horizon: 라벨(전방수익률)의 기간 h — CV에서 purge 폭으로 사용해 누수 차단.
        cv_splits: 워크포워드 폴드 수.
        """
        self._feature_names = feature_names or list(X.columns)

        X = X.fillna(0)
        valid_mask = ~(X.isna().any(axis=1) | y.isna())
        X, y = X[valid_mask].reset_index(drop=True), y[valid_mask].reset_index(drop=True)

        if len(X) < 120:
            logger.warning(f"학습 데이터 부족 ({len(X)}건). 최소 120건 필요.")
            return {"error": "insufficient_data"}

        results: Dict[str, dict] = {}

        # ── 1) Purged Walk-Forward CV로 정직한 OOS 성능 측정 ──
        splitter = PurgedWalkForward(n_splits=cv_splits, label_horizon=label_horizon,
                                     embargo_pct=0.01, expanding=True)
        oos_pred: Dict[str, List[np.ndarray]] = {}
        oos_true: List[np.ndarray] = []
        for tr_idx, te_idx in splitter.split(len(X)):
            X_tr, y_tr = X.iloc[tr_idx], y.iloc[tr_idx]
            X_te, y_te = X.iloc[te_idx], y.iloc[te_idx]
            if y_tr.nunique() < 2:
                continue
            fold_models = self._build_models()
            for name, model in fold_models.items():
                try:
                    model.fit(X_tr, y_tr)
                    p = model.predict_proba(X_te)[:, 1]
                    oos_pred.setdefault(name, []).append(p)
                except Exception as e:
                    logger.warning(f"[CV] {name} 실패: {e}")
            if fold_models:
                oos_true.append(y_te.to_numpy())

        # OOS 정확도/AUC → 스킬 가중치 + Platt 보정 적합
        if oos_true:
            y_oos = np.concatenate(oos_true)
            for name, parts in oos_pred.items():
                p_oos = np.concatenate(parts)
                m = min(len(p_oos), len(y_oos))
                p_oos, y_seg = p_oos[:m], y_oos[:m]
                acc = float(((p_oos > 0.5).astype(int) == y_seg).mean())
                auc = self._auc(y_seg, p_oos)
                skill = max(0.0, acc - 0.5)
                self._model_weights[name] = skill
                try:
                    self._calibration[name] = _platt_fit(p_oos, y_seg)
                except Exception:
                    self._calibration[name] = (1.0, 0.0)
                results[name] = {"oos_accuracy": round(acc, 4), "oos_auc": round(auc, 4),
                                 "skill": round(skill, 4)}
                logger.info(f"{name} OOS 정확도 {acc:.2%} / AUC {auc:.3f} (purged WF-CV)")

        # 스킬 합이 0이면 동일 가중
        if sum(self._model_weights.values()) <= 1e-9:
            n = max(len(oos_pred), 1)
            self._model_weights = {k: 1.0 / n for k in oos_pred}
        else:
            tot = sum(self._model_weights.values())
            self._model_weights = {k: v / tot for k, v in self._model_weights.items()}

        # ── 2) 전체 데이터로 최종 모델 적합(배포용) ──
        self.models = self._build_models()
        for name, model in list(self.models.items()):
            try:
                model.fit(X, y)
            except Exception as e:
                logger.warning(f"{name} 최종 학습 실패: {e}")
                self.models.pop(name, None)

        self._is_trained = len(self.models) > 0
        if self._is_trained:
            self._save_models()
            self._train_history.append({
                "timestamp": pd.Timestamp.now().isoformat(),
                "samples": len(X), "results": results,
                "model_weights": dict(self._model_weights),
            })
        return results

    @staticmethod
    def _auc(y_true: np.ndarray, scores: np.ndarray) -> float:
        """ROC-AUC (Mann-Whitney U 통계) — sklearn 불필요."""
        y_true = np.asarray(y_true)
        pos = scores[y_true == 1]
        neg = scores[y_true == 0]
        if len(pos) == 0 or len(neg) == 0:
            return 0.5
        ranks = pd.Series(scores).rank().to_numpy()
        rank_pos = ranks[y_true == 1].sum()
        auc = (rank_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))
        return float(auc)

    def predict(self, X: pd.DataFrame, ticker: str = "") -> MLPrediction:
        """스킬 가중 + 확률 보정을 적용한 앙상블 예측."""
        if not self._is_trained:
            self._load_models()
        if not self.models:
            return MLPrediction(ticker=ticker, direction="중립", confidence=0)

        X = X.fillna(0)
        cal_probs: Dict[str, float] = {}
        for name, model in self.models.items():
            try:
                prob = float(model.predict_proba(X)[-1][1])
                ab = self._calibration.get(name)
                cal_probs[name] = _platt_apply(prob, ab) if ab else prob
            except Exception as e:
                logger.warning(f"{name} 예측 실패: {e}")

        if not cal_probs:
            return MLPrediction(ticker=ticker, direction="중립", confidence=0)

        # 스킬 가중 평균
        names = list(cal_probs.keys())
        w = np.array([self._model_weights.get(n, 1.0 / len(names)) for n in names])
        w = w / w.sum() if w.sum() > 0 else np.ones(len(names)) / len(names)
        probs = np.array([cal_probs[n] for n in names])
        avg_prob = float(np.dot(w, probs))

        # 합의도: 가중 표준편차 역수 기반
        spread = float(np.sqrt(np.dot(w, (probs - avg_prob) ** 2)))
        agreement = max(0.0, 1 - spread * 2)

        if avg_prob > 0.6:
            direction = "상승"
        elif avg_prob < 0.4:
            direction = "하락"
        else:
            direction = "중립"

        confidence = abs(avg_prob - 0.5) * 2 * agreement

        return MLPrediction(
            ticker=ticker,
            direction=direction,
            probability=round(avg_prob, 3),
            confidence=round(confidence, 3),
            expected_return=round((avg_prob - 0.5) * 10, 2),
            model_agreement=round(agreement, 3),
            feature_importance=self._get_feature_importance(),
        )

    def _get_feature_importance(self) -> Dict:
        for name in ["xgboost", "lightgbm", "random_forest"]:
            model = self.models.get(name)
            if model is not None and hasattr(model, "feature_importances_"):
                imp = model.feature_importances_
                if len(self._feature_names) == len(imp):
                    top_idx = np.argsort(imp)[-10:][::-1]
                    return {self._feature_names[i]: round(float(imp[i]), 4) for i in top_idx}
        return {}

    def _save_models(self):
        for name, model in self.models.items():
            try:
                with open(self.model_dir / f"{name}.pkl", "wb") as f:
                    pickle.dump(model, f)
            except Exception as e:
                logger.error(f"모델 저장 실패 [{name}]: {e}")
        # 메타(가중치/보정) 저장
        try:
            with open(self.model_dir / "ensemble_meta.pkl", "wb") as f:
                pickle.dump({"weights": self._model_weights,
                             "calibration": self._calibration,
                             "features": self._feature_names}, f)
        except Exception as e:
            logger.error(f"메타 저장 실패: {e}")

    def _load_models(self):
        for name in ["xgboost", "lightgbm", "random_forest"]:
            path = self.model_dir / f"{name}.pkl"
            if path.exists():
                try:
                    with open(path, "rb") as f:
                        self.models[name] = pickle.load(f)
                    self._is_trained = True
                except Exception as e:
                    logger.warning(f"모델 로드 실패 [{name}]: {e}")
        meta = self.model_dir / "ensemble_meta.pkl"
        if meta.exists():
            try:
                with open(meta, "rb") as f:
                    d = pickle.load(f)
                self._model_weights = d.get("weights", {})
                self._calibration = d.get("calibration", {})
                self._feature_names = d.get("features", self._feature_names)
            except Exception as e:
                logger.warning(f"메타 로드 실패: {e}")
