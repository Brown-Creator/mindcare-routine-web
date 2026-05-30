"""
팩터 가중치 주기적 재보정 잡.

`MultiFactorModel.DEFAULT_WEIGHTS` 는 정적이다. 시장 구조는 변하므로(어떤 팩터가
잘 듣는지도 시기마다 다르다) 실데이터로 주기적으로 IC를 재측정해 가중치를 갱신하는
것이 정석이다. 이 모듈은 그 재보정을 한 함수로 묶고 결과를 JSON 으로 영속화한다.

흐름: KRX 가격 페치 → 다기간 IC 백테스트 → ICIR 비례 가중치 → JSON 저장 →
이후 MultiFactorModel 이 부팅 시 이 파일을 로드해 보정된 가중치로 동작.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS_PATH = Path("data/factor_weights.json")


def persist_weights(weights: Dict[str, float], meta: dict = None,
                    path: Path = DEFAULT_WEIGHTS_PATH) -> None:
    """보정된 가중치 + 메타(IC 리포트, 시각 등)를 JSON 으로 저장."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"weights": weights, "meta": meta or {}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"팩터 가중치 저장: {path} {weights}")


def load_persisted_weights(path: Path = DEFAULT_WEIGHTS_PATH) -> Optional[Dict[str, float]]:
    """저장된 보정 가중치 로드(없으면 None)."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        w = payload.get("weights")
        return w if isinstance(w, dict) and w else None
    except Exception as e:
        logger.warning(f"팩터 가중치 로드 실패: {e}")
        return None


def recalibrate_factor_weights(
    loader, universe: List[dict], factor_model,
    start: str, end: str,
    rebalance_every: int = 20, lookback: int = 250, forward: int = 20,
    apply: bool = True, persist: bool = True,
    path: Path = DEFAULT_WEIGHTS_PATH,
    timestamp: str = "",
) -> dict:
    """
    팩터 가중치 재보정 1회 실행.

    loader  : KRXDataLoader (또는 fetch_ohlcv 를 갖는 호환 객체).
    universe: [{"ticker","name","sector","market_cap","fundamentals"?}, ...]
    apply   : True면 factor_model.weights 를 즉시 갱신.
    persist : True면 JSON 으로 저장(다음 부팅 시 로드).
    timestamp: 결과 메타에 기록할 시각(호출부에서 주입 — 결정론적 테스트 위해).

    반환: 백테스트 결과 + 적용 가중치.
    """
    from backend.data.factor_backtest import (
        fetch_price_history, run_factor_ic_backtest, calibrate_factor_model)

    price_history = fetch_price_history(loader, universe, start, end)
    meta = {u["ticker"]: {"name": u.get("name", ""), "sector": u.get("sector", ""),
                          "market_cap": u.get("market_cap", 0),
                          "fundamentals": u.get("fundamentals", {})}
            for u in universe}

    result = run_factor_ic_backtest(
        price_history, meta, factor_model,
        rebalance_every=rebalance_every, lookback=lookback, forward=forward)
    if "error" in result:
        return result

    weights = calibrate_factor_model(factor_model, result, apply=apply)
    if persist:
        persist_weights(weights, meta={
            "ic_report": result.get("ic_report"),
            "n_periods": result.get("n_periods"),
            "n_stocks": result.get("n_stocks"),
            "window": f"{start}~{end}",
            "calibrated_at": timestamp,
        }, path=path)

    return {"applied_weights": weights, "n_periods": result.get("n_periods"),
            "n_stocks": result.get("n_stocks"),
            "ic_report": result.get("ic_report")}
