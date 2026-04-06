import { getStateBadgeClass } from '../utils/formatters'

const LOGS = [
  { timestamp: '2025-04-05 09:30:00', ticker: '005490', name: '포스코홀딩스', action: '상태 변경', from_state: '관찰', to_state: '1차 물타기 후보', scores: { '바닥확률': 68, '추세': 45, '모멘텀': 55, '리스크': 35 }, details: 'RSI 과매도 진입 + 외국인 순매수 전환 확인 → 물타기 후보 전환' },
  { timestamp: '2025-04-05 09:15:22', ticker: '051910', name: 'LG화학', action: '매매 차단', from_state: '관찰', to_state: '매매금지', scores: { '바닥확률': 35, '추세': 22, '모멘텀': 28, '리스크': 72 }, details: '이벤트 리스크 75점 → 임계치(60점) 초과 → 리스크 엔진이 매매 차단' },
  { timestamp: '2025-04-05 09:05:00', ticker: '035420', name: 'NAVER', action: '상태 변경', from_state: '관찰', to_state: '신규진입 후보', scores: { '바닥확률': 61, '추세': 42, '모멘텀': 48, '리스크': 38 }, details: '52주 저점 근접 + 하락속도 둔화 → 신규진입 후보 전환' },
  { timestamp: '2025-04-04 14:50:00', ticker: '000660', name: 'SK하이닉스', action: '상태 유지', from_state: '보유', to_state: '보유', scores: { '바닥확률': 55, '추세': 62, '모멘텀': 68, '리스크': 28 }, details: '반등 모멘텀 유지 → 1차 매도가(195,000원) 도달 전까지 보유 유지' },
]

export default function StrategyLog() {
  const actionStyles = {
    '상태 변경': { bg: 'var(--accent-blue-dim)', color: 'var(--accent-blue)', cls: 'action-change' },
    '매매 차단': { bg: 'var(--color-sell-dim)', color: 'var(--color-sell)', cls: 'action-block' },
    '상태 유지': { bg: 'rgba(107,114,128,0.15)', color: '#9ca3af', cls: '' },
    '매수': { bg: 'var(--color-buy-dim)', color: 'var(--color-buy)', cls: 'action-buy' },
    '매도': { bg: 'var(--color-sell-dim)', color: 'var(--color-sell)', cls: 'action-sell' },
  }

  return (
    <div className="fade-in">
      <div className="section-header">
        <h2 className="section-title">📝 전략 로그</h2>
        <span className="section-subtitle">전략 엔진의 의사결정 기록</span>
      </div>

      <div style={{display:'flex',flexDirection:'column',gap:'8px'}}>
        {LOGS.map((log, i) => {
          const style = actionStyles[log.action] || actionStyles['상태 유지']
          return (
            <div key={i} className={`log-entry ${style.cls}`}>
              <div className="log-header">
                <span className="log-time">{log.timestamp}</span>
                <span className="log-stock">{log.name}</span>
                <span className="log-action" style={{background: style.bg, color: style.color}}>
                  {log.action}
                </span>
                {log.from_state !== log.to_state && (
                  <span style={{fontSize:'0.78rem',color:'var(--text-secondary)'}}>
                    <span className={`status-badge ${getStateBadgeClass(log.from_state)}`} style={{fontSize:'0.65rem',padding:'2px 6px'}}>
                      {log.from_state}
                    </span>
                    <span style={{margin:'0 6px'}}>→</span>
                    <span className={`status-badge ${getStateBadgeClass(log.to_state)}`} style={{fontSize:'0.65rem',padding:'2px 6px'}}>
                      {log.to_state}
                    </span>
                  </span>
                )}
              </div>
              <div className="log-detail">{log.details}</div>
              <div className="log-scores">
                {Object.entries(log.scores).map(([k, v]) => (
                  <span key={k} className="log-score">{k}: <strong>{v}</strong></span>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
