import { useState } from 'react'

export default function KillSwitchPanel() {
  const [active, setActive] = useState(false)
  const [logs, setLogs] = useState([
    { time: '09:00:00', action: '시스템 시작', detail: '킬스위치 비활성 상태로 자동매매 시스템 시작됨' },
  ])

  const handleActivate = () => {
    if (window.confirm('⚠️ 킬스위치를 활성화하면:\n\n• 모든 자동 주문이 즉시 중단됩니다\n• 미체결 주문은 전량 취소됩니다\n• 수동으로 해제할 때까지 자동매매가 비활성화됩니다\n\n정말 활성화하시겠습니까?')) {
      setActive(true)
      setLogs(prev => [{ time: new Date().toLocaleTimeString('ko-KR'), action: '킬스위치 활성화', detail: '수동으로 킬스위치 활성화 → 모든 자동주문 중단' }, ...prev])
    }
  }

  const handleDeactivate = () => {
    if (window.confirm('킬스위치를 해제하면 자동매매가 다시 시작됩니다.\n\n해제하시겠습니까?')) {
      setActive(false)
      setLogs(prev => [{ time: new Date().toLocaleTimeString('ko-KR'), action: '킬스위치 해제', detail: '수동으로 킬스위치 해제 → 자동매매 재개' }, ...prev])
    }
  }

  return (
    <div className="fade-in">
      <div className="section-header">
        <h2 className="section-title">🛑 킬스위치 패널</h2>
        <span className="section-subtitle">긴급 상황 시 모든 자동매매를 즉시 중단합니다</span>
      </div>

      {/* 킬스위치 메인 */}
      <div className="card" style={{
        marginBottom: '24px',
        textAlign: 'center',
        padding: '40px',
        border: active ? '2px solid var(--color-sell)' : '1px solid var(--border-color)',
        background: active ? 'rgba(239,68,68,0.05)' : 'var(--bg-card)',
      }}>
        <div style={{fontSize:'4rem',marginBottom:'12px'}}>
          {active ? '🔴' : '⏹️'}
        </div>
        <h2 style={{
          fontSize: '1.5rem',
          fontWeight: 800,
          marginBottom: '8px',
          color: active ? 'var(--color-sell)' : 'var(--text-primary)',
        }}>
          {active ? '킬스위치 활성화됨' : '킬스위치 비활성'}
        </h2>
        <p style={{color:'var(--text-secondary)',marginBottom:'24px',fontSize:'0.9rem'}}>
          {active
            ? '모든 자동주문이 중단되었습니다. 수동으로 해제하세요.'
            : '자동매매 시스템이 정상 운영 중입니다.'}
        </p>

        {active ? (
          <button
            onClick={handleDeactivate}
            style={{
              padding: '14px 40px',
              borderRadius: 'var(--radius-md)',
              border: '2px solid var(--color-buy)',
              background: 'transparent',
              color: 'var(--color-buy)',
              fontSize: '1rem',
              fontWeight: 700,
              fontFamily: 'var(--font-sans)',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onMouseOver={e => { e.target.style.background = 'var(--color-buy)'; e.target.style.color = 'white' }}
            onMouseOut={e => { e.target.style.background = 'transparent'; e.target.style.color = 'var(--color-buy)' }}
          >
            🔓 킬스위치 해제
          </button>
        ) : (
          <button
            onClick={handleActivate}
            style={{
              padding: '14px 40px',
              borderRadius: 'var(--radius-md)',
              border: '2px solid var(--color-sell)',
              background: 'var(--color-sell)',
              color: 'white',
              fontSize: '1rem',
              fontWeight: 700,
              fontFamily: 'var(--font-sans)',
              cursor: 'pointer',
              transition: 'all 0.2s',
              boxShadow: '0 0 20px rgba(239,68,68,0.3)',
            }}
            onMouseOver={e => { e.target.style.boxShadow = '0 0 40px rgba(239,68,68,0.5)' }}
            onMouseOut={e => { e.target.style.boxShadow = '0 0 20px rgba(239,68,68,0.3)' }}
          >
            🛑 긴급 정지
          </button>
        )}
      </div>

      {/* 킬스위치 정보 */}
      <div className="two-col">
        <div className="card">
          <div className="card-header"><span className="card-title">ℹ️ 킬스위치 동작</span></div>
          <div style={{fontSize:'0.85rem',lineHeight:1.8,color:'var(--text-secondary)'}}>
            <p>킬스위치가 활성화되면:</p>
            <p>1. <strong style={{color:'var(--text-primary)'}}>모든 자동 주문이 즉시 중단</strong>됩니다</p>
            <p>2. <strong style={{color:'var(--text-primary)'}}>미체결 주문이 전량 취소</strong>됩니다</p>
            <p>3. <strong style={{color:'var(--text-primary)'}}>전략 엔진의 주문 요청이 차단</strong>됩니다</p>
            <p>4. 기존 보유 포지션은 <strong style={{color:'var(--color-hold)'}}>유지</strong>됩니다</p>
            <p>5. 수동 해제 전까지 자동매매가 <strong style={{color:'var(--color-sell)'}}>비활성화</strong>됩니다</p>
          </div>
        </div>
        <div className="card">
          <div className="card-header"><span className="card-title">📜 킬스위치 로그</span></div>
          <div style={{display:'flex',flexDirection:'column',gap:'8px'}}>
            {logs.map((log, i) => (
              <div key={i} className={`log-entry ${log.action.includes('활성화') ? 'action-block' : log.action.includes('해제') ? 'action-buy' : ''}`}>
                <div className="log-header">
                  <span className="log-time">{log.time}</span>
                  <span className="log-stock">{log.action}</span>
                </div>
                <div className="log-detail">{log.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
