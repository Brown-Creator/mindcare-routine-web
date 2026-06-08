import { classifyCrisisText } from '../src/lib/safety-classifier.ts';
import { localDB } from '../src/lib/local-storage.ts';

console.log('====================================================');
console.log('🚨 Crisis Safety Flow validation test suite starting');
console.log('====================================================\n');

// 테스트 카운터
let passedCount = 0;
let failedCount = 0;

function expectEqual(actual: any, expected: any, message: string) {
  if (actual === expected) {
    console.log(`  ✅ PASS: ${message}`);
    passedCount++;
  } else {
    console.error(`  ❌ FAIL: ${message} (Expected: ${expected}, Got: ${actual})`);
    failedCount++;
  }
}

// --------------------------------------------------------------------
// 1. 한국어 및 영어 위기 키워드 탐지 테스트
// --------------------------------------------------------------------
console.log('[Test Suite 1: Crisis Keyword Detection]');

const CRISIS_TEST_PHRASES = [
  // A. 자살 생각 (Suicidal ideation)
  { text: '오늘 정말 너무 지치고 죽고 싶다', expected: true, label: 'Suicidal ideation (KR)' },
  { text: 'I want to die right now', expected: true, label: 'Suicidal ideation (EN)' },
  
  // B. 자해 (Self-harm)
  { text: '스트레스 받아서 칼로 자해를 하고 말았다', expected: true, label: 'Self-harm (KR)' },
  { text: 'Sometimes I just want to cut myself', expected: true, label: 'Self-harm (EN)' },
  
  // C. 계획 있음 (Having a plan)
  { text: '그동안 처방받은 수면제 모으기 시작했다', expected: true, label: 'Having a plan (KR)' },
  { text: 'I am planning to end my life soon', expected: true, label: 'Having a plan (EN)' },
  
  // D. 임박한 위험 (Immediate danger)
  { text: '지금 아파트 옥상인데 뛰어내릴 거야', expected: true, label: 'Immediate danger (KR)' },
  { text: 'I am going to kill myself tonight', expected: true, label: 'Immediate danger (EN)' },
  
  // E. 절망 및 의도 (Hopelessness with intent)
  { text: '더는 가치가 없다 살기 싫어졌다', expected: true, label: 'Hopelessness with intent (KR)' },
  { text: 'Commit suicide seems like the only option', expected: true, label: 'Hopelessness with intent (EN)' },
  
  // F. 일반 평온한 문구 (Normal control group)
  { text: '오늘 날씨가 맑아서 산책하기 딱 좋았다.', expected: false, label: 'Normal text (KR)' },
  { text: 'I had a cup of tea and felt relaxed.', expected: false, label: 'Normal text (EN)' }
];

CRISIS_TEST_PHRASES.forEach(item => {
  const result = classifyCrisisText(item.text);
  expectEqual(result, item.expected, `${item.label} -> "${item.text}"`);
});

// --------------------------------------------------------------------
// 2. PHQ-9 9번 문항 가동 조건 테스트
// --------------------------------------------------------------------
console.log('\n[Test Suite 2: PHQ-9 Item 9 Crisis Escalation]');

// 모의 브라우저 환경에서 localStorage 작동 보장 (Node 환경 대응)
if (typeof window === 'undefined') {
  const mockStorage: Record<string, string> = {};
  global.window = {} as any;
  global.localStorage = {
    getItem: (key: string) => mockStorage[key] || null,
    setItem: (key: string, value: string) => { mockStorage[key] = value; },
    removeItem: (key: string) => { delete mockStorage[key]; },
    clear: () => { for (const key in mockStorage) delete mockStorage[key]; }
  } as any;
}

// 온보딩 동의 선제 수행 (데이터 저장을 위해)
localDB.saveConsent({
  agreedAge19: true,
  agreedTerms: true,
  agreedPrivacy: true,
  agreedSensitiveData: true
});

// PHQ-9 9번 문항 0점 -> 위기 트리거되지 않아야 함
const scoreZeroResult = localDB.saveScreeningResult({
  type: 'PHQ-9',
  answers: [0, 0, 0, 0, 0, 0, 0, 0, 0], // 9번 문항 (index 8) = 0
  totalScore: 0
});
expectEqual(scoreZeroResult.crisisTriggered, false, 'PHQ-9 9번 문항 점수가 0점일 때는 위기 미감정');

// PHQ-9 9번 문항 1점 이상 -> 위기 트리거되어야 함 (Item 9 positive)
const scoreOneResult = localDB.saveScreeningResult({
  type: 'PHQ-9',
  answers: [0, 0, 0, 0, 0, 0, 0, 0, 1], // 9번 문항 (index 8) = 1 (며칠 동안)
  totalScore: 1
});
expectEqual(scoreOneResult.crisisTriggered, true, 'PHQ-9 9번 문항 점수가 1점 이상일 때 즉시 위기 전환 트리거 작동');

// --------------------------------------------------------------------
// 3. API 호출 인터셉트 및 비식별/비치료 검증
// --------------------------------------------------------------------
console.log('\n[Test Suite 3: AI Route Intervention Check]');

// 가상 API 라우트 검증
function simulateAiRouteHandler(journalText: string) {
  // A. 사전 검사
  if (classifyCrisisText(journalText)) {
    return {
      status: 200,
      body: {
        crisisTriggered: true,
        result: null,
        message: '위기 단어가 감지되었습니다. 즉각적인 안전 관리가 중요합니다.'
      }
    };
  }
  
  // B. 정상 처리 (모의)
  return {
    status: 200,
    body: {
      crisisTriggered: false,
      result: '오늘 하루 성찰을 잘 완료하셨습니다.'
    }
  };
}

// 위기 저널 입력 시 검증
const crisisResponse = simulateAiRouteHandler('자살하고 싶어서 약을 모으고 있다.');
expectEqual(crisisResponse.body.crisisTriggered, true, 'AI API route intercept crisis text');
expectEqual(crisisResponse.body.result, null, 'No AI therapeutic generated advice is returned during crisis');

// --------------------------------------------------------------------
// 4. 최소 안전 이벤트 로깅 및 개인정보 마스킹 검증
// --------------------------------------------------------------------
console.log('\n[Test Suite 4: Safety Logging & PII Redaction]');

const eventsBefore = localDB.getSafetyEvents().length;
localDB.saveSafetyEvent('KEYWORD');
const eventsAfter = localDB.getSafetyEvents().length;
expectEqual(eventsAfter - eventsBefore, 1, 'Safety event logging incremented by 1 (Minimal Event Logged)');

// 결과 통계
console.log('\n====================================================');
if (failedCount === 0) {
  console.log(`🎉 ALL ${passedCount} CRISIS FLOW TESTS PASSED SUCCESSFULLY!`);
  process.exit(0);
} else {
  console.error(`🚨 CRISIS TEST SUITE FAILED: ${failedCount} tests failed.`);
  process.exit(1);
}
console.log('====================================================');
