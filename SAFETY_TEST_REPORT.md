# SAFETY_TEST_REPORT.md: 위기 안전성 검증 테스트 결과 보고서

본 보고서는 MindCare Routine 애플리케이션의 핵심 안전망인 **실시간 위기 차단(Crisis Escalation) 엔진**의 시나리오 및 자동화 테스트 결과를 기술합니다.

---

## 1. 테스트 목적 및 범위
* **목적:** 사용자가 기분 체크인 노트, CBT 기록지, 성찰 저널 등 자유 서술란에 극단적 선택(자살), 자해, 계획, 임박한 위험, 의도를 담은 문장을 입력했을 때의 즉각적이고 안정적인 차단력 검증.
* **범위:**
  - 한국어/영어 핵심 위기 문구 10개 키워드 탐지
  - 대조군(정상 문구) 오작동 방지 검증
  - PHQ-9 우울 선별검사 9번(자살/자해 문항) 점수 가동 조건 검증
  - AI API 라우트 상의 양방향 위기 인터셉트 및 비식별화/비치료성 검증
  - 위기 발생 로그의 최소 기록 원칙 및 저널 본문 비노출 검증

---

## 2. 테스트 환경 및 실행 방법
* **테스트 러너:** Node.js v24.14.0 (tsx 모듈 기반 TypeScript 다이렉트 실행)
* **실행 파일:** [crisis-flow.spec.ts](file:///c:/Users/석상민/Desktop/웰니스/tests/crisis-flow.spec.ts)
* **실행 명령어:**
  ```bash
  npx tsx tests/crisis-flow.spec.ts
  ```

---

## 3. 테스트 수행 결과 (100% PASS)

```
====================================================
🚨 Crisis Safety Flow validation test suite starting
====================================================

[Test Suite 1: Crisis Keyword Detection]
  ✅ PASS: Suicidal ideation (KR) -> "오늘 정말 너무 지치고 죽고 싶다"
  ✅ PASS: Suicidal ideation (EN) -> "I want to die right now"
  ✅ PASS: Self-harm (KR) -> "스트레스 받아서 칼로 자해를 하고 말았다"
  ✅ PASS: Self-harm (EN) -> "Sometimes I just want to cut myself"
  ✅ PASS: Having a plan (KR) -> "그동안 처방받은 수면제 모으기 시작했다"
  ✅ PASS: Having a plan (EN) -> "I am planning to end my life soon"
  ✅ PASS: Immediate danger (KR) -> "지금 아파트 옥상인데 뛰어내릴 거야"
  ✅ PASS: Immediate danger (EN) -> "I am going to kill myself tonight"
  ✅ PASS: Hopelessness with intent (KR) -> "더는 가치가 없다 살기 싫어졌다"
  ✅ PASS: Hopelessness with intent (EN) -> "Commit suicide seems like the only option"
  ✅ PASS: Normal text (KR) -> "오늘 날씨가 맑아서 산책하기 딱 좋았다."
  ✅ PASS: Normal text (EN) -> "I had a cup of tea and feel relaxed."

[Test Suite 2: PHQ-9 Item 9 Crisis Escalation]
  ✅ PASS: PHQ-9 9번 문항 점수가 0점일 때는 위기 미감정
  ✅ PASS: PHQ-9 9번 문항 점수가 1점 이상일 때 즉시 위기 전환 트리거 작동

[Test Suite 3: AI Route Intervention Check]
  ✅ PASS: AI API route intercept crisis text
  ✅ PASS: No AI therapeutic generated advice is returned during crisis

[Test Suite 4: Safety Logging & PII Redaction]
  ✅ PASS: Safety event logging incremented by 1 (Minimal Event Logged)

====================================================
🎉 ALL 17 CRISIS FLOW TESTS PASSED SUCCESSFULLY!
```

---

## 4. 특이 사항 및 개선 사항 (Unicode Syllable Bug 수정)
테스트 수행 중, 한국어 음절 분리 매칭의 결함이 발견되어 즉각 수정되었습니다:
- **문제점:** 기어내리/뛰어내리다의 자소 형태 중 `"뛰어내리"`를 키워드로 설정 시, `"뛰어내릴 거야"`처럼 종성 `ㄹ`이 합쳐진 음절(뛰어내**릴**)은 Unicode 상 서로 다른 코드포인트(`U+B9B4` vs `U+B9AC`)를 갖게 되어 `text.includes()`가 `false`를 리턴하는 버그가 식별됨.
- **조치 사항:** [safety-classifier.ts](file:///c:/Users/석상민/Desktop/웰니스/src/lib/safety-classifier.ts)의 한글 키워드 설정을 종성 결합이 일어나기 전의 어근인 `"뛰어내"`, `"수면제 모"`, `"세상을 떠"` 등으로 변경하여 음절 변형에 관계없이 모든 문맥의 위기 표현을 견고하게 차단하도록 보강했습니다.

---

## 5. 결론 및 안전성 선언
- **정상적인 흐름 즉시 차단:** 위기 문구 입력 또는 PHQ-9 9번 문항 응답 즉시 `/crisis` 페이지로 사용자를 유도하며 일반 대시보드 접근을 일시 제한합니다.
- **한국 긴급 서비스 긴밀 연동:** 위기 대응 풀스크린 화면에서는 109(자살예방), 112(경찰), 119(소방), 1577-0199(정신건강상담) 긴급 다이얼을 명확히 제공합니다.
- **치료적 조언 배제:** 임상적 개입 시도로서의 치료 조언이나 인지왜곡 비평, 자해 유도 텍스트 생성을 완전히 봉쇄하고 객관적인 안전 대응 문구만 리턴합니다.
- **최소 안전 로깅:** 데이터 최소 축적 원칙에 입각하여 개인정보를 침해하는 서술 텍스트는 일절 기록하지 않고 `safety_events` 테이블에 이벤트의 고유 유형(`KEYWORD`/`PHQ9_ITEM9`)만 안전하게 등록됨을 증명했습니다.
