# 🚀 KRX AutoTrader v2.1 — Quant-Grade

한국(KRX) 주식 자동매매 시스템. v2.1에서 핵심 의사결정 로직을 **실제 검증 가능한
계량(퀀트) 방법론**으로 재구축했다 — "그럴듯해 보이는" 휴리스틱을 걷어내고,
기관 수준의 표준 기법으로 교체했다.

## 🧮 Quant Core (`backend/quant/`)

numpy/pandas/scipy만으로 구현된, **단위 테스트로 정확성이 증명된** 계량 라이브러리.
(전부 `backend/tests/test_quant.py` 에서 수학적 성질로 검증 — 26개 테스트.)

| 모듈 | 핵심 기능 | 왜 중요한가 |
|------|-----------|-------------|
| `cross_section` | MAD 윈저화 · 순위→정규(Blom) · 회귀 중립화 · IC/ICIR | 팩터는 **절대 임계값이 아니라 동종 유니버스 내 상대 순위**로 표준화해야 한다 |
| `covariance` | Ledoit-Wolf 수축 · EWMA · nearest-PSD | 표본 공분산을 그대로 최적화에 넣으면 추정오차가 해를 지배("error maximization") |
| `optimization` | 볼록 max-Sharpe / min-var / mean-var · **진짜 ERC 리스크패리티** · 최대분산화 | 난수 탐색이 아닌 SLSQP 기반 실제 최적화 + 회전율/박스 제약 |
| `metrics` | Cornish-Fisher VaR/CVaR · MDD(지속기간) · Sortino/Calmar/Omega | 팻테일(왜도·첨도)을 반영한 꼬리위험 |
| `validation` | **Purged/Embargoed CV** · **Deflated & Probabilistic Sharpe** | 라벨 누수 차단 + 다중검정 보정으로 과적합 백테스트 폭로 |
| `sizing` | 이산/연속/다자산 Kelly · 변동성 타겟팅 · 드로다운 스로틀 | 엣지를 파산 없이 베팅 크기로 환산 |
| `factor_research` | 롤링 IC · **ICIR 가중치 추정** · 팩터 감쇠 · **분위 스프레드 백테스트** | 직관이 아닌 데이터로 팩터 가중치를 정한다 |
| `costs` | 수수료+거래세+스프레드+**제곱근 시장충격**(η·σ·√(Q/ADV)) | flat slippage가 놓치는 용량·회전율 비용을 반영 |

### v2.0 → v2.1 에서 실제로 고친 것

- **팩터 모델**: `if PER<8 → +25점` 식 절대 점수 → **횡단면 표준화(winsorize→rank-z→섹터·사이즈 중립화→IC 가중 결합)**. `MultiFactorModel.score_universe()` 가 정석 경로. IC 추적기 포함.
- **포트폴리오 최적화**: 디리클레 난수 1만 개 brute-force → **scipy 볼록 최적화 + Ledoit-Wolf 수축 공분산**. "리스크패리티"도 단순 역변동성 → **진짜 등위험기여(ERC)**.
- **ML 앙상블**: 단일 80/20 분할(룩어헤드 누수) → **purged walk-forward CV** + **Platt 확률 보정** + **OOS 스킬 가중 앙상블**.
- **백테스트**: **Deflated/Probabilistic Sharpe Ratio**(다중검정·표본길이·왜도 보정) + **정상 블록 부트스트랩**(자기상관 보존).
- **리스크 엔진**: 정의만 되고 미사용이던 **섹터별 스트레스 충격을 실제 적용**(+종목 베타), **Cornish-Fisher VaR** 추가, `StockState` 임포트 누락 버그 수정.
- **레짐 감지**: 미사용이던 `TRANSITION_MATRIX` 를 실제 사용 → **HMM forward filter**(예측-갱신 베이지안)로 레짐을 시간적으로 평활화.
- **알파 엔진**: 인스턴스 가중치 변형으로 인한 **async 동시성 버그 수정**(지역 가중치화), 신뢰도를 **방향 일치도 × 확신도**의 기하평균으로 재정의(전부 중립일 때 신뢰도=1이던 결함 제거).

## 🏗️ Architecture

- **Backend**: Python (FastAPI), AsyncIO, NumPy/Pandas/SciPy. ML(scikit-learn/XGBoost/LightGBM)은 **선택적** — 미설치 시 자동 우회하며 시스템은 정상 가동.
- **Frontend**: React, Vite, Recharts, Lightweight-Charts.
- **Broker**: Kiwoom OpenAPI (REST).

```
backend/
  quant/        # ★ 검증된 계량 코어 (cross_section/covariance/optimization/metrics/
                #    validation/sizing/factor_research/costs)
  data/         # krx_loader — pykrx 실데이터 → records[] + 팩터 리서치 러너
  api/          # quant.py — 퀀트 진단지표 API (/api/quant/*)
  engines/      # alpha / portfolio / risk / regime / backtest / execution (퀀트 코어에 위임)
  ml/           # factor_model(횡단면) / ml_ensemble(누수제거) / feature_engineering
  strategies/   # bottom / trend / momentum / supply_demand / deep_recovery
  tests/        # 46개 정확성 테스트 (quant/factor_research/ml_pipeline/costs/krx_loader)
frontend/src/pages/QuantAnalytics.jsx   # 퀀트 진단지표 시각화 (/quant)
```

## 🚀 Getting Started

### Backend
1. `python -m venv .venv && .venv\Scripts\activate`
2. `pip install -r backend/requirements.txt`  (최소 numpy/pandas/scipy/fastapi면 가동)
3. `.env` 또는 대시보드 Settings 에서 API 키 설정
4. `python -m backend.main`

### Frontend
1. `cd frontend && npm install`
2. `npm run dev`

### 리서치 워크플로 (재현 가능한 단일 명령)
```bash
python -m backend.research                 # 합성 유니버스 (네트워크 불필요)
python -m backend.research --live --n 10   # 실 KRX 데이터 (pykrx)
python -m backend.research --apply         # 보정 가중치 영속화 → 다음 부팅 반영
```
유니버스 → 다기간 팩터 IC 백테스트 → ICIR 가중치 보정 → 공분산 수축 + 볼록 최적화 → 리포트.

### 테스트 (정확성 검증, 총 58개 / 8개 스위트)
```bash
python -m backend.tests.test_quant            # 26 — 코어 수학적 성질
python -m backend.tests.test_factor_research  #  5 — IC/분위 스프레드
python -m backend.tests.test_ml_pipeline      #  3 — purged WF-CV (ML 라이브러리 필요)
python -m backend.tests.test_costs            #  7 — 거래비용·시장충격
python -m backend.tests.test_krx_loader       #  8 — 데이터 어댑터 + DART(오프라인)
python -m backend.tests.test_factor_backtest  #  4 — 다기간 IC 백테스트
python -m backend.tests.test_recalibration    #  3 — 가중치 재보정/영속화
python -m backend.tests.test_integration      #  2 — 전체 파이프라인 합성
# pytest 로도 실행 가능: pytest backend/tests -q
```

## 🛡️ Risk Management
- 일일 손실 한도 / MDD 실드 / 스마트 킬스위치(이벤트 기반)
- Historical + **Cornish-Fisher** CVaR(99%), 상관 집중도(HHI), **섹터·베타 반영 스트레스 테스트**, 유동성 청산일수
- 포지션 사이징: **Fractional Kelly + 변동성 타겟팅 + 드로다운 스로틀**

---
*Disclaimer: 주식 투자는 상당한 위험을 수반합니다. 본 시스템은 교육 및 전문 트레이딩 목적입니다. 과거 성과가 미래 수익을 보장하지 않습니다.*
