"""
모델 드리프트 감지 + 자동 재학습 트리거
- PSI (Population Stability Index) 기반 입력 피처 드리프트
- KS 검정 (Kolmogorov-Smirnov) 기반 예측 분포 드리프트
- CUSUM (Cumulative Sum Control Chart) 기반 정확도 드리프트
- 드리프트 감지 시 자동 재학습 트리거
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
import json
from pathlib import Path
from scipy import stats

logger = logging.getLogger(__name__)


class DriftSeverity(str, Enum):
    NONE = "정상"
    MINOR = "경미"
    MODERATE = "중간"
    SEVERE = "심각"
    CRITICAL = "위험"


@dataclass
class DriftReport:
    timestamp: str = ""
    psi_score: float = 0.0           # Population Stability Index
    ks_statistic: float = 0.0        # KS 검정 통계량
    ks_pvalue: float = 1.0           # KS p-value
    cusum_signal: bool = False        # CUSUM 경보
    accuracy_recent: float = 0.0     # 최근 예측 정확도
    accuracy_baseline: float = 0.0   # 기준선 정확도
    accuracy_drop: float = 0.0       # 정확도 하락
    severity: DriftSeverity = DriftSeverity.NONE
    features_drifted: List[str] = field(default_factory=list)
    recommendation: str = "모니터링 계속"
    retrain_required: bool = False


@dataclass
class ModelSnapshot:
    """학습 시점 기준 분포 스냅샷"""
    feature_stats: Dict[str, dict] = field(default_factory=dict)  # mean, std, percentiles
    prediction_distribution: List[float] = field(default_factory=list)
    accuracy_history: List[float] = field(default_factory=list)
    created_at: str = ""
    sample_count: int = 0


class ModelDriftMonitor:
    """
    모델 드리프트 감지 및 자동 재학습 관리자
    Two Sigma, Citadel 수준의 MLOps 모니터링
    """

    PSI_THRESHOLDS = {
        "none": 0.1,
        "minor": 0.2,
        "moderate": 0.25,
        "severe": 0.3,
    }

    CUSUM_H = 5.0     # CUSUM 경보 임계값
    CUSUM_K = 0.5     # CUSUM 허용 편차

    def __init__(self, model_name: str, monitor_dir: str = "data/monitors"):
        self.model_name = model_name
        self.monitor_dir = Path(monitor_dir)
        self.monitor_dir.mkdir(parents=True, exist_ok=True)

        self._baseline_snapshot: Optional[ModelSnapshot] = None
        self._prediction_log: List[dict] = []   # {pred, actual, proba, timestamp}
        self._cusum_pos: float = 0.0
        self._cusum_neg: float = 0.0
        self._drift_history: List[DriftReport] = []
        self._retrain_cooldown: Optional[datetime] = None
        self._retrain_cooldown_hours = 24  # 재학습 후 24시간 쿨다운

        self._load_snapshot()

    # ─── 기준선 설정 ───

    def set_baseline(self, X_train: pd.DataFrame, predictions: List[float],
                     actuals: List[float] = None):
        """학습 데이터로 기준선 스냅샷 설정"""
        snapshot = ModelSnapshot(created_at=datetime.now().isoformat(),
                                  sample_count=len(X_train))

        # 피처 통계 계산
        for col in X_train.columns:
            col_data = X_train[col].dropna()
            if len(col_data) > 0:
                snapshot.feature_stats[col] = {
                    "mean": float(col_data.mean()),
                    "std": float(col_data.std()),
                    "p10": float(col_data.quantile(0.10)),
                    "p25": float(col_data.quantile(0.25)),
                    "p50": float(col_data.quantile(0.50)),
                    "p75": float(col_data.quantile(0.75)),
                    "p90": float(col_data.quantile(0.90)),
                    "min": float(col_data.min()),
                    "max": float(col_data.max()),
                }

        snapshot.prediction_distribution = list(predictions)

        # 초기 정확도
        if actuals and predictions:
            acc = np.mean([1 if (p > 0.5) == (a > 0.5) else 0
                           for p, a in zip(predictions, actuals)])
            snapshot.accuracy_history = [acc]

        self._baseline_snapshot = snapshot
        self._save_snapshot()
        logger.info(f"[{self.model_name}] 기준선 스냅샷 저장 완료 ({len(X_train)}건)")

    # ─── 실시간 모니터링 ───

    def log_prediction(self, prediction_proba: float, actual: Optional[float] = None):
        """예측 결과 로깅"""
        self._prediction_log.append({
            "proba": prediction_proba,
            "actual": actual,
            "correct": (1 if (prediction_proba > 0.5) == (actual > 0.5) else 0) if actual is not None else None,
            "timestamp": datetime.now().isoformat(),
        })

        # 로그 최대 10,000건 유지
        if len(self._prediction_log) > 10000:
            self._prediction_log = self._prediction_log[-5000:]

        # CUSUM 업데이트 (정확도 드리프트)
        if actual is not None:
            correct = 1 if (prediction_proba > 0.5) == (actual > 0.5) else 0
            self._update_cusum(correct)

    def _update_cusum(self, observation: float):
        """CUSUM 통계 업데이트 (정확도 기반)"""
        baseline_acc = (np.mean(self._baseline_snapshot.accuracy_history)
                        if self._baseline_snapshot and self._baseline_snapshot.accuracy_history
                        else 0.55)

        # 허용 범위 이상의 변화 누적
        self._cusum_pos = max(0, self._cusum_pos + observation - baseline_acc + self.CUSUM_K)
        self._cusum_neg = max(0, self._cusum_neg - observation + baseline_acc + self.CUSUM_K)

    def check_drift(self, X_current: pd.DataFrame) -> DriftReport:
        """현재 입력 데이터의 드리프트 종합 분석"""
        report = DriftReport(timestamp=datetime.now().isoformat())

        if self._baseline_snapshot is None:
            report.recommendation = "기준선 미설정 - 학습 후 set_baseline() 호출 필요"
            return report

        # 1. PSI 계산 (피처 드리프트)
        psi_scores = {}
        for col in X_current.columns:
            if col in self._baseline_snapshot.feature_stats:
                try:
                    psi = self._calculate_psi(
                        X_current[col].dropna(),
                        self._baseline_snapshot.feature_stats[col]
                    )
                    psi_scores[col] = psi
                except Exception:
                    pass

        report.psi_score = float(np.mean(list(psi_scores.values()))) if psi_scores else 0.0
        report.features_drifted = [col for col, psi in psi_scores.items()
                                    if psi > self.PSI_THRESHOLDS["minor"]]

        # 2. KS 검정 (예측 분포 드리프트)
        recent_probas = [p["proba"] for p in self._prediction_log[-200:]]
        if recent_probas and self._baseline_snapshot.prediction_distribution:
            ks_stat, ks_p = stats.ks_2samp(
                self._baseline_snapshot.prediction_distribution,
                recent_probas
            )
            report.ks_statistic = round(float(ks_stat), 4)
            report.ks_pvalue = round(float(ks_p), 4)

        # 3. CUSUM 경보
        report.cusum_signal = (self._cusum_pos > self.CUSUM_H or
                                self._cusum_neg > self.CUSUM_H)

        # 4. 정확도 비교
        recent_correct = [p["correct"] for p in self._prediction_log[-100:]
                          if p["correct"] is not None]
        if recent_correct:
            report.accuracy_recent = round(float(np.mean(recent_correct)), 4)
        baseline_accuracies = self._baseline_snapshot.accuracy_history
        if baseline_accuracies:
            report.accuracy_baseline = round(float(np.mean(baseline_accuracies)), 4)
        report.accuracy_drop = round(report.accuracy_baseline - report.accuracy_recent, 4)

        # 5. 심각도 판단
        report.severity = self._assess_severity(report)
        report.retrain_required = report.severity in [DriftSeverity.SEVERE, DriftSeverity.CRITICAL]
        report.recommendation = self._generate_recommendation(report)

        self._drift_history.append(report)
        if report.retrain_required:
            self._log_retrain_trigger(report)

        return report

    def _calculate_psi(self, current_data: pd.Series, baseline_stats: dict) -> float:
        """PSI 계산 (10 분위 버킷 기반)"""
        percentiles = [baseline_stats.get(f"p{p}", 0)
                       for p in [10, 25, 50, 75, 90]]
        # 버킷 분류
        buckets = [-np.inf] + percentiles + [np.inf]

        baseline_arr = np.array([baseline_stats["p10"], baseline_stats["p25"],
                                  baseline_stats["p50"], baseline_stats["p75"],
                                  baseline_stats["p90"]])

        current_counts = np.histogram(current_data, bins=buckets)[0]
        # baseline 기준 분포 (균등 가정)
        baseline_counts = np.ones(len(current_counts)) * len(current_data) / len(current_counts)

        # PSI = Σ (current% - baseline%) * ln(current% / baseline%)
        current_pct = current_counts / max(current_counts.sum(), 1) + 1e-7
        baseline_pct = baseline_counts / max(baseline_counts.sum(), 1) + 1e-7

        psi = float(np.sum((current_pct - baseline_pct) * np.log(current_pct / baseline_pct)))
        return abs(psi)

    def _assess_severity(self, report: DriftReport) -> DriftSeverity:
        """드리프트 심각도 종합 평가"""
        score = 0

        # PSI 기반 점수
        if report.psi_score > self.PSI_THRESHOLDS["severe"]: score += 3
        elif report.psi_score > self.PSI_THRESHOLDS["moderate"]: score += 2
        elif report.psi_score > self.PSI_THRESHOLDS["minor"]: score += 1

        # KS 기반 점수
        if report.ks_pvalue < 0.01: score += 3
        elif report.ks_pvalue < 0.05: score += 2
        elif report.ks_pvalue < 0.1: score += 1

        # CUSUM
        if report.cusum_signal: score += 2

        # 정확도 하락
        if report.accuracy_drop > 0.10: score += 3
        elif report.accuracy_drop > 0.05: score += 2
        elif report.accuracy_drop > 0.02: score += 1

        if score >= 7: return DriftSeverity.CRITICAL
        elif score >= 5: return DriftSeverity.SEVERE
        elif score >= 3: return DriftSeverity.MODERATE
        elif score >= 1: return DriftSeverity.MINOR
        return DriftSeverity.NONE

    def _generate_recommendation(self, report: DriftReport) -> str:
        if report.severity == DriftSeverity.CRITICAL:
            return "🚨 즉시 재학습 필요 - 모델 신뢰도 위험 수준"
        elif report.severity == DriftSeverity.SEVERE:
            return f"⚠️ 재학습 권장 - 피처 드리프트({len(report.features_drifted)}개), 정확도 하락 {report.accuracy_drop*100:.1f}%"
        elif report.severity == DriftSeverity.MODERATE:
            return f"📊 모니터링 강화 필요 - PSI={report.psi_score:.3f}"
        elif report.severity == DriftSeverity.MINOR:
            return "✅ 경미한 드리프트 감지 - 정상 모니터링 유지"
        return "✅ 정상 - 드리프트 없음"

    def _log_retrain_trigger(self, report: DriftReport):
        """재학습 트리거 이벤트 로깅"""
        now = datetime.now()
        if (self._retrain_cooldown and
                now - self._retrain_cooldown < timedelta(hours=self._retrain_cooldown_hours)):
            logger.info(f"[{self.model_name}] 재학습 쿨다운 중 ({self._retrain_cooldown_hours}시간)")
            return
        self._retrain_cooldown = now
        logger.warning(f"[{self.model_name}] 🔄 재학습 트리거! 심각도={report.severity.value}, "
                        f"PSI={report.psi_score:.3f}, 정확도하락={report.accuracy_drop*100:.1f}%")

    def should_retrain(self) -> Tuple[bool, str]:
        """재학습 필요 여부 반환"""
        if not self._drift_history:
            return False, "드리프트 이력 없음"
        latest = self._drift_history[-1]
        if latest.retrain_required:
            return True, latest.recommendation
        return False, latest.recommendation

    def get_dashboard_data(self) -> dict:
        """대시보드용 드리프트 요약"""
        if not self._drift_history:
            return {"status": "데이터 없음", "model": self.model_name}
        latest = self._drift_history[-1]
        return {
            "model": self.model_name,
            "severity": latest.severity.value,
            "psi_score": latest.psi_score,
            "ks_pvalue": latest.ks_pvalue,
            "accuracy_recent": latest.accuracy_recent,
            "accuracy_baseline": latest.accuracy_baseline,
            "accuracy_drop_pct": round(latest.accuracy_drop * 100, 2),
            "features_drifted": latest.features_drifted,
            "retrain_required": latest.retrain_required,
            "recommendation": latest.recommendation,
            "cusum_alarm": latest.cusum_signal,
            "prediction_count": len(self._prediction_log),
            "last_check": latest.timestamp,
        }

    # ─── 영속성 ───

    def _save_snapshot(self):
        path = self.monitor_dir / f"{self.model_name}_snapshot.json"
        try:
            data = {
                "feature_stats": self._baseline_snapshot.feature_stats,
                "prediction_distribution": self._baseline_snapshot.prediction_distribution[:500],
                "accuracy_history": self._baseline_snapshot.accuracy_history,
                "created_at": self._baseline_snapshot.created_at,
                "sample_count": self._baseline_snapshot.sample_count,
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"스냅샷 저장 실패: {e}")

    def _load_snapshot(self):
        path = self.monitor_dir / f"{self.model_name}_snapshot.json"
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._baseline_snapshot = ModelSnapshot(**data)
                logger.info(f"[{self.model_name}] 기준선 스냅샷 로드 완료")
            except Exception as e:
                logger.warning(f"스냅샷 로드 실패: {e}")


# ─── 전역 모니터 레지스트리 ───

_monitors: Dict[str, ModelDriftMonitor] = {}


def get_monitor(model_name: str) -> ModelDriftMonitor:
    """모델별 드리프트 모니터 반환 (싱글톤)"""
    if model_name not in _monitors:
        _monitors[model_name] = ModelDriftMonitor(model_name)
    return _monitors[model_name]


def get_all_monitors_status() -> dict:
    """모든 모니터 상태 요약"""
    return {name: mon.get_dashboard_data() for name, mon in _monitors.items()}
