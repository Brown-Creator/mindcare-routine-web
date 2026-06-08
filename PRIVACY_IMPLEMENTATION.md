# PRIVACY_IMPLEMENTATION.md: 개인정보 보호 및 프라이버시 설계 구현 보고서

본 보고서는 MindCare Routine 애플리케이션의 **프라이버시 중심 설계(Privacy-by-Design)** 구현 내역과 구체적 메커니즘을 명문화합니다.

---

## 1. 민감 정보 별도 동의 처리 (Separated Sensitive Data Consent)
- **구현 파일:** [onboarding/page.tsx](file:///c:/Users/석상민/Desktop/웰니스/src/app/onboarding/page.tsx)
- **메커니즘:** 
  연령 확인(만 19세 이상), 서비스 이용약관, 개인정보 수집 및 이용 방침 외에, **'정신건강 민감 정보 수집 및 이용 동의'**를 별도 체크박스로 노출하여 수집 전 이용자의 능동적인 선택(Separated Affirmative Consent)을 구합니다.
- **영향 범위:** 
  [local-storage.ts](file:///c:/Users/석상민/Desktop/웰니스/src/lib/local-storage.ts)의 `saveConsent`를 통해 동의 상태가 저장되며, `agreedSensitiveData`가 `false`일 경우 선별 도구(PHQ-9/GAD-7) 등의 민감한 분석 결과는 화면에만 출력될 뿐 브라우저 스토리지 및 데이터베이스에 절대 영구 저장되지 않습니다.

---

## 2. 행 레벨 보안 정책 및 격리 (Row-Level Security & Isolation)
- **구현 파일:** [20260608000000_init_schema.sql](file:///c:/Users/석상민/Desktop/웰니스/supabase/migrations/20260608000000_init_schema.sql)
- **메커니즘:**
  데이터베이스 단에서 다른 사용자의 정보 접근을 원천 차단하기 위해 PostgreSQL/Supabase의 **행 레벨 보안(RLS)**을 강제합니다.
  - 모든 테이블에 대해 `ALTER TABLE public.<table_name> ENABLE ROW LEVEL SECURITY;` 선언.
  - 모든 CRUD 명령(`SELECT`, `INSERT`, `UPDATE`, `DELETE`)에 대해 `auth.uid() = user_id` 조건의 검증 정책(Policy) 강제.
  - 이를 통해 토큰을 가진 사용자가 자기 ID에 매핑된 행만 생성하고 조회할 수 있습니다.

---

## 3. 사용자 데이터 주권 보장 (Data Portability: Export & Delete)
- **구현 파일:** [privacy/page.tsx](file:///c:/Users/석상민/Desktop/웰니스/src/app/privacy/page.tsx), [local-storage.ts](file:///c:/Users/석상민/Desktop/웰니스/src/lib/local-storage.ts)
- **메커니즘:**
  - **내보내기 (Export):** 사용자의 기분 기록, 성찰 저널, CBT 기록지 전체를 구조화된 **JSON** 파일로 다운로드받거나 기분 흐름을 범용 **CSV** 포맷으로 일괄 백업받을 수 있는 파일 생성 핸들러 내장.
  - **완전 파기 (Delete):** 탈퇴 시 Soft-delete(단순 플래그 변경)가 아닌 물리적 로우 삭제(`DELETE`) 및 `localStorage.clear()`를 동시 구동하여 디바이스와 서버 데이터베이스 저장소 모두에서 데이터 파편을 즉시 제거합니다.

---

## 4. 서버 로그 민감 정보 마스킹 (PII & Journal Text Redaction)
- **구현 파일:** [safety-classifier.ts](file:///c:/Users/석상민/Desktop/웰니스/src/lib/safety-classifier.ts)
- **메커니즘:**
  서버의 모니터링 로그(클라우드 왓치, Vercel 로그 등)에 사용자의 저널 원문 및 스크리닝 입력 텍스트가 노출되지 않도록 하는 마스킹 함수 `redactSensitiveLogs`를 탑재했습니다.
  - 정규식을 이용해 로그 문자열 속 `"journalContent"`, `"automaticThought"`, `"situation"`, `"note"` 필드를 탐지.
  - 탐지된 자유 서술식 민감 텍스트 본문을 `[REDACTED_SENSITIVE_TEXT]`로 영구 치환하여 출력.
  - 이메일 주소의 경우 도메인을 제외한 아이디 앞 3자리만 남기고 별표 마스킹(`***@domain.com`).

---

## 5. 제3자 트래커 및 외부 분석 배제 (Zero Analytics & Ads)
- **구현 방침:**
  - 본 웹 애플리케이션은 사용자 기분 및 일기 분석 용도로 Google Analytics, Facebook Pixel, Mixpanel, Hotjar 등의 타사 마케팅 추적기나 행동 분석 광고 스크립트를 **일절 로드하거나 설치하지 않습니다.**
  - 웹브라우저의 모든 네트워크 트래픽은 오직 자체 호스팅 API 라우트 및 지정된 Supabase 엔드포인트로만 안전하게 통신합니다.

---

## 6. RLS 방어망 검증 테스트 (RLS Verification Tests)
- **검증 파일:** `tests/rls.test.js`
- **검증 시나리오:**
  1. **정적 검증 (Static Check):** Supabase 스키마 SQL 파일을 스캔하여 모든 테이블의 RLS(Row Level Security) 강제 활성화 여부 확인.
  2. **동작 검증 (Behavioral Check):** 사용자의 데이터 소유 주권 격리가 온전히 보장되는지, 정책이 누락된 테이블이 없는지 구문 스캔을 통해 검증합니다.
