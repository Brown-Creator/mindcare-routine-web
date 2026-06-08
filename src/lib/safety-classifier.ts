// 위기 키워드 탐지 목록 (대소문자 무시 매칭 및 정규식)
const CRISIS_KEYWORDS = [
  "죽고 싶", "죽고싶", "자살", "자해", "살기 싫", "살기싫", "목숨을 끊", "극단적 선택", 
  "뛰어내", "수면제 모", "세상을 떠", "목매", "동반 자살",
  "suicide", "self-harm", "want to die", "end my life", "kill myself", "cut myself", "hang myself"
];

/**
 * 사용자 입력 텍스트에서 위기 키워드(자살/자해)를 실시간으로 탐지합니다.
 * @param text 사용자가 입력한 자유 서술형 텍스트
 * @returns 위기 상황 감지 여부 (true = 위험, false = 정상)
 */
export function classifyCrisisText(text: string): boolean {
  if (!text) return false;
  
  const normalizedText = text.toLowerCase().replace(/\s+/g, "");
  
  for (const keyword of CRISIS_KEYWORDS) {
    const normalizedKeyword = keyword.toLowerCase().replace(/\s+/g, "");
    if (normalizedText.includes(normalizedKeyword)) {
      return true;
    }
  }
  return false;
}

/**
 * 서버 로그나 콘솔에 출력되기 전 민감 정보 및 저널 기밀 데이터를 필터링(Redact)합니다.
 * 개인정보 보호 및 HIPAA/GDPR 보안 수칙에 따라, 사용자 입력 글이 로그에 쌓이는 것을 방지합니다.
 * @param content 원본 로그 메시지 또는 데이터
 * @returns 민감 단어와 본문이 마스킹 처리된 안전한 문자열
 */
export function redactSensitiveLogs(content: any): string {
  if (content === null || content === undefined) return "";
  
  let stringContent = typeof content === "string" ? content : JSON.stringify(content);
  
  // 저널 본문이나 내용으로 의심되는 키/값 탐지 패턴
  const journalContentPattern = /("journalContent"|"content"|"note"|"automaticThought"|"situation"|content|note):\s*"([^"]+)"/gi;
  
  // 감지된 값들을 마스킹 처리
  stringContent = stringContent.replace(journalContentPattern, (match, key, val) => {
    return `${key}: "[REDACTED_SENSITIVE_TEXT]"`;
  });

  // 이메일 주소 마스킹
  const emailPattern = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
  stringContent = stringContent.replace(emailPattern, (email) => {
    const [user, domain] = email.split("@");
    return `${user.substring(0, Math.min(3, user.length))}***@${domain}`;
  });

  return stringContent;
}
