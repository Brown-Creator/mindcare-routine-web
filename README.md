# MindCare Routine (마음케어 루틴) MVP

한국 성인(만 19세 이상)을 위한 근거 기반 마음건강 자가관리(Self-Help) 웹 애플리케이션입니다. 인지행동치료(CBT) 사고 기록, 마음챙김 명상, 행동활성화(Behavioral Activation) 및 정신역동적 대인관계 패턴 성찰 일지를 제공하여 바쁜 성인들이 일상의 마음 건강을 스스로 지킬 수 있도록 조력합니다.

* **실제 배포 데모 (Vercel Live URL):** [https://mindcare-routine-web.vercel.app](https://mindcare-routine-web.vercel.app)

---

## 🚀 기술 스택 (Tech Stack)

* **프레임워크:** Next.js 16 (React 19, TypeScript, App Router)
* **스타일링:** Tailwind CSS 4
* **데이터베이스 및 보안:** Supabase (PostgreSQL), Row Level Security (RLS) 및 로컬 퍼스트(IndexedDB/LocalStorage) 작동 폴백
* **아이콘:** Lucide React

---

## 🛠️ 설치 및 설정 방법 (Setup & Run)

### 1. 패키지 설치
프로젝트 루트 디렉토리에서 아래 명령어를 실행하여 필요한 모든 종속 패키지를 설치합니다:
```bash
npm install
```

### 2. 데이터베이스 설정 (Supabase 마이그레이션)
본 프로젝트는 Supabase PostgreSQL 데이터베이스 및 Row Level Security를 준수합니다.
1. [Supabase](https://supabase.com)에 프로젝트를 생성합니다.
2. `supabase/migrations/20260608000000_init_schema.sql` 파일 내의 SQL 스크립트를 복사하여 Supabase **SQL Editor**에 실행하거나, Supabase CLI를 통해 마이그레이션을 적용합니다:
   ```bash
   supabase db push
   ```

### 3. 환경 변수 설정
루트 디렉토리에 `.env.local` 파일을 생성하고 다음 환경 변수를 추가합니다.
*(만약 값이 비어있다면, 애플리케이션은 브라우저 스토리지 전용 **로컬 퍼스트(Local-First) 익명 모드**로 자동 안전 가동됩니다.)*
```env
NEXT_PUBLIC_SUPABASE_URL="https://your-project.supabase.co"
NEXT_PUBLIC_SUPABASE_ANON_KEY="your-anon-public-key"
OPENAI_API_KEY="your-openai-api-key"
```

### 4. 로컬 서버 실행
```bash
npm run dev
```
브라우저에서 [http://localhost:3000](http://localhost:3000)으로 접속합니다.

---

## 🔒 프라이버시 및 위기 관리 (Privacy & Safety)

* **로컬 퍼스트 모드:** 로그인 없이 익명으로 작성된 모든 글과 마음 상태는 브라우저 외부로 송출되지 않고 로컬 스토리지에 격리되어 가장 안전합니다.
* **실시간 위기 필터:** 체크인 메모나 저널 본문에 자해/자살 극단 선택 키워드가 입력되거나 PHQ-9 우울 선별검사에서 자조 성향(9번 문항)이 탐지되면, 정상 화면을 강제 잠금하고 **위기 지원 화면 (Crisis Support)**으로 즉각 에스컬레이션됩니다.
* **데이터 내보내기/삭제:** 설정 및 개인정보 페이지를 통해 즉각적으로 모든 데이터를 파일(JSON/CSV)로 내보내거나, 복구 불가능하게 영구 소멸(Right to be Forgotten) 시킬 수 있습니다.

---

## 📚 주요 설계 및 검증 문서 일람 (Documentation)

애플리케이션의 구현을 뒷받침하는 핵심 콘텐츠 맵, 프라이버시 정책, 보안 규격 및 자가 테스트 보고서 목록입니다.

* **[CONTENT_MAP.md](CONTENT_MAP.md):** 근거 기반 마음건강 한국어 자가관리 가이드 및 세부 데이터 사양서
* **[PRIVACY_IMPLEMENTATION.md](PRIVACY_IMPLEMENTATION.md):** 민감정보 동의 격리, Row-level Security(RLS) 및 개인정보 삭제/내보내기 설계 명세서
* **[SECURITY.md](SECURITY.md):** 시스템 보안 아키텍처 및 로그 비식별화(Masking) 가이드라인
* **[SAFETY_TEST_REPORT.md](SAFETY_TEST_REPORT.md):** 한국어/영어 극단 선택 문장 및 PHQ-9 9번 트리거를 검증한 위기 차단(Crisis Safety) 테스트 보고서
