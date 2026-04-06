/**
 * 숫자/날짜 포맷 유틸리티
 */

/** 한국 원화 포맷 */
export function formatKRW(value, showSign = false) {
  if (value == null) return '-';
  const abs = Math.abs(value);
  let formatted;
  if (abs >= 1e12) formatted = (abs / 1e12).toFixed(1) + '조';
  else if (abs >= 1e8) formatted = (abs / 1e8).toFixed(1) + '억';
  else if (abs >= 1e4) formatted = Math.round(abs).toLocaleString('ko-KR');
  else formatted = abs.toLocaleString('ko-KR');
  
  const sign = value > 0 ? '+' : value < 0 ? '-' : '';
  if (showSign) return sign + formatted;
  return value < 0 ? '-' + formatted : formatted;
}

/** 전체 원화 포맷 (원 단위) */
export function formatFullKRW(value) {
  if (value == null) return '-';
  return Math.round(value).toLocaleString('ko-KR') + '원';
}

/** 가격 포맷 */
export function formatPrice(value) {
  if (value == null) return '-';
  return Math.round(value).toLocaleString('ko-KR');
}

/** 퍼센트 포맷 */
export function formatPercent(value, showSign = true) {
  if (value == null) return '-';
  const sign = showSign && value > 0 ? '+' : '';
  return sign + value.toFixed(2) + '%';
}

/** 거래량 포맷 */
export function formatVolume(value) {
  if (value == null) return '-';
  if (value >= 1e6) return (value / 1e6).toFixed(1) + 'M';
  if (value >= 1e3) return (value / 1e3).toFixed(0) + 'K';
  return value.toLocaleString('ko-KR');
}

/** 점수에 따른 색상 클래스 */
export function getScoreClass(score) {
  if (score >= 60) return 'high';
  if (score >= 40) return 'medium';
  return 'low';
}

/** 상태에 따른 뱃지 클래스 */
export function getStateBadgeClass(state) {
  const map = {
    '관찰': 'watch',
    '신규진입 후보': 'entry-candidate',
    '1차 물타기 후보': 'avg-down-1',
    '2차 물타기 후보': 'avg-down-2',
    '보유': 'holding',
    '1차 분할매도': 'exit-1',
    '2차 분할매도': 'exit-2',
    '전량매도': 'full-exit',
    '매매금지': 'blocked',
  };
  return map[state] || 'watch';
}

/** 알림 레벨 아이콘 */
export function getAlertIcon(level) {
  const icons = {
    '정보': 'ℹ️',
    '성공': '✅',
    '경고': '⚠️',
    '위험': '🚨',
    '오류': '❌',
  };
  return icons[level] || 'ℹ️';
}

/** 알림 타입 아이콘 */
export function getAlertTypeIcon(type) {
  const icons = {
    '전략': '📊',
    '리스크': '🛡️',
    '주문': '📋',
    '시장': '🌐',
    '시스템': '⚙️',
  };
  return icons[type] || '📌';
}
