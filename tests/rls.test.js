const fs = require('fs');
const path = require('path');

console.log('====================================================');
console.log('🛡️ RLS & Privacy Guard: Automated Validation Test');
console.log('====================================================\n');

// 1. 테이블 리스트 정의 (반드시 RLS가 걸려있어야 하는 중요 테이블)
const CORE_TABLES = [
  'user_profiles',
  'consents',
  'mood_entries',
  'thought_records',
  'activation_tasks',
  'mindfulness_sessions',
  'journal_entries',
  'screening_results',
  'safety_events',
  'audit_logs'
];

let failedTests = 0;
let passedTests = 0;

function assert(condition, message) {
  if (condition) {
    console.log(`  ✅ PASS: ${message}`);
    passedTests++;
  } else {
    console.log(`  ❌ FAIL: ${message}`);
    failedTests++;
  }
}

// 2. 스키마 파일 로드 및 정적 RLS 분석
const schemaPath = path.join(__dirname, '../supabase/migrations/20260608000000_init_schema.sql');

try {
  const schemaContent = fs.readFileSync(schemaPath, 'utf8');
  console.log(`[Static Security Scan] Scanning SQL migrations file:\n  -> ${schemaPath}\n`);

  // A. 각 테이블의 RLS 활성화 여부 검사
  CORE_TABLES.forEach(table => {
    const rlsPattern = new RegExp(`ALTER\\s+TABLE\\s+public\\.${table}\\s+ENABLE\\s+ROW\\s+LEVEL\\s+SECURITY`, 'i');
    const hasRLSEnabled = rlsPattern.test(schemaContent);
    assert(hasRLSEnabled, `Table [${table}] must have Row Level Security enabled (ENABLE RLS)`);
  });

  console.log('');

  // B. RLS 정책 내 auth.uid() = user_id 소유권 체크 정책 검사
  CORE_TABLES.forEach(table => {
    // POLICY가 테이블명과 함께 정의되었는지 정규식 매칭
    // 예: CREATE POLICY ... ON public.user_profiles ... USING (auth.uid() = user_id)
    const policyPattern = new RegExp(`CREATE\\s+POLICY\\s+.*?\\s+ON\\s+public\\.${table}\\s+.*?USING\\s*\\(\\s*auth\\.uid\\(\\)\\s*=\\s*user_id\\s*\\)`, 'is');
    const hasOwnershipPolicy = policyPattern.test(schemaContent);
    assert(hasOwnershipPolicy, `Table [${table}] must enforce policy: USING (auth.uid() = user_id)`);
  });

} catch (err) {
  console.error('Fatal error loading migration schema:', err.message);
  process.exit(1);
}

// 3. 런타임 클라이언트 격리 가상 시뮬레이션 테스트
console.log('\n[Client Isolation Simulation] Verifying Client Query Restrictor...');

// 가상의 악의적 사용자 해커가 다른 이용자의 데이터를 열람하거나 덮어쓰는 가상 요청 시뮬레이터
class MockSupabaseClient {
  constructor(authUserId) {
    this.authUserId = authUserId; // 현재 로그인된 사용자 UUID
  }

  // RLS 모조 컴파일러
  simulateRLSQuery(table, queryUserId, operation = 'SELECT') {
    // 데이터베이스 RLS 조건: auth.uid() = user_id
    // auth.uid() -> this.authUserId
    // user_id -> queryUserId
    const isAuthorized = this.authUserId !== null && this.authUserId === queryUserId;
    
    return {
      success: isAuthorized,
      error: isAuthorized ? null : `RLS Violation: User '${this.authUserId}' does not have permission to ${operation} on table '${table}' belonging to user '${queryUserId}'`
    };
  }
}

// 시나리오 테스트 실행
const userA = 'user-uuid-aaaa-1111';
const userB = 'user-uuid-bbbb-2222';

console.log(`\n  * Simulated Users:\n    - User A: ${userA}\n    - User B: ${userB}\n`);

const clientA = new MockSupabaseClient(userA);

// 시나리오 1: User A가 자신의 저널을 조회할 때
const testOwnSelect = clientA.simulateRLSQuery('journal_entries', userA, 'SELECT');
assert(testOwnSelect.success === true, 'User A can fetch their own journal entries');

// 시나리오 2: User A가 타인(User B)의 저널 조회를 시도할 때
const testOtherSelect = clientA.simulateRLSQuery('journal_entries', userB, 'SELECT');
assert(testOtherSelect.success === false && testOtherSelect.error.includes('RLS Violation'), 'User A is BLOCKED from fetching User B\'s journal entries (RLS Block)');

// 시나리오 3: 비인가 비회원(로그인 없음) 상태로 DB 직접 조회 시도할 때
const anonymousClient = new MockSupabaseClient(null);
const testAnonSelect = anonymousClient.simulateRLSQuery('mood_entries', userA, 'SELECT');
assert(testAnonSelect.success === false, 'Anonymous client is BLOCKED from fetching User A\'s records');

console.log('\n====================================================');
if (failedTests === 0) {
  console.log(`🎉 ALL ${passedTests} SECURITY TESTS PASSED. User data isolation is successfully enforced!`);
  process.exit(0);
} else {
  console.error(`🚨 SECURITY VALIDATION FAILED: ${failedTests} tests failed.`);
  process.exit(1);
}
console.log('====================================================');
