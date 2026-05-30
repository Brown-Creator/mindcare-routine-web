"""
End-to-end check of the upgraded ML ensemble (purged walk-forward CV + Platt
calibration + skill-weighted blending).

Requires xgboost / lightgbm / scikit-learn. If none are importable the test is
skipped (the production system degrades gracefully in that case too).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.ml.ml_ensemble import MLEnsemble, _platt_fit, _platt_apply

RNG = np.random.default_rng(7)


def _has_any_model() -> bool:
    for mod in ("xgboost", "lightgbm", "sklearn.ensemble"):
        try:
            __import__(mod)
            return True
        except ImportError:
            continue
    return False


def _learnable_dataset(n=900, p=8):
    """Features with a genuine (noisy) linear signal driving a binary label."""
    X = RNG.normal(0, 1, (n, p))
    beta = np.array([1.5, -1.0, 0.8, 0.0, 0.0, 0.5, -0.5, 0.0])
    logit = X @ beta + RNG.normal(0, 1.0, n)
    y = (logit > 0).astype(int)
    cols = [f"f{i}" for i in range(p)]
    return pd.DataFrame(X, columns=cols), pd.Series(y)


def test_platt_calibration_is_monotone_and_bounded():
    # Platt scaling must stay in (0,1) and preserve ordering.
    scores = np.clip(RNG.random(500), 1e-3, 1 - 1e-3)
    labels = (scores + RNG.normal(0, 0.1, 500) > 0.5).astype(int)
    ab = _platt_fit(scores, labels)
    p_lo, p_hi = _platt_apply(0.2, ab), _platt_apply(0.8, ab)
    assert 0.0 < p_lo < 1.0 and 0.0 < p_hi < 1.0
    assert p_hi > p_lo                                   # monotone in the score


def test_ml_ensemble_purged_cv_runs_and_learns():
    if not _has_any_model():
        print("  SKIP  no ML backend installed")
        return
    X, y = _learnable_dataset()
    ens = MLEnsemble(model_dir="data/models_test")
    results = ens.train(X, y, label_horizon=5, cv_splits=4)

    assert results and "error" not in results
    # Every fitted model reports an honest OOS accuracy from purged WF-CV...
    for name, r in results.items():
        assert "oos_accuracy" in r and "oos_auc" in r
        assert 0.0 <= r["oos_accuracy"] <= 1.0
    # ...and on a learnable signal the best model should beat a coin flip.
    assert max(r["oos_accuracy"] for r in results.values()) > 0.55
    # Skill weights normalized.
    assert abs(sum(ens._model_weights.values()) - 1.0) < 1e-6

    pred = ens.predict(X.tail(1), ticker="TEST")
    assert 0.0 <= pred.probability <= 1.0
    assert pred.direction in ("상승", "하락", "중립")


def test_auc_helper_matches_definition():
    # AUC of a perfect ranker is 1.0, of a reversed ranker 0.0.
    y = np.array([0, 0, 1, 1])
    assert abs(MLEnsemble._auc(y, np.array([0.1, 0.2, 0.8, 0.9])) - 1.0) < 1e-9
    assert abs(MLEnsemble._auc(y, np.array([0.9, 0.8, 0.2, 0.1])) - 0.0) < 1e-9


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}"); passed += 1
        except Exception:
            print(f"  FAIL  {fn.__name__}"); traceback.print_exc(); failed += 1
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
