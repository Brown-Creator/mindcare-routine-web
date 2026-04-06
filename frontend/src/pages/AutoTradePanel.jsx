import { formatPrice, formatPercent, getScoreClass, getStateBadgeClass } from '../utils/formatters'

const SIGNALS = {
  '005490': { name: '포스코홀딩스', state: '1차 물타기 후보', confidence: 72, bottom_probability_score: 68, trend_score: 45, momentum_score: 55, risk_score: 35, buy_price_1: 265000, exit_price_1: 285000, hard_stop: 240000 },
  '005930': { name: '삼성전자', state: '관찰', confidence: 45, bottom_probability_score: 42, trend_score: 38, momentum_score: 40, risk_score: 42, buy_price_1: 68000, exit_price_1: 78000, hard_stop: 62000 },
  '000660': { name: 'SK하이닉스', state: '보유', confidence: 65, bottom_probability_score: 55, trend_score: 62, momentum_score: 68, risk_score: 28, buy_price_1: 165000, exit_price_1: 195000, hard_stop: 155000 },
  '035420': { name: 'NAVER', state: '신규진입 후보', confidence: 58, bottom_probability_score: 61, trend_score: 42, momentum_score: 48, risk_score: 38, buy_price_1: 190000, exit_price_1: 215000, hard_stop: 172000 },
  '051910': { name: 'LG화학', state: '매매금지', confidence: 25, bottom_probability_score: 35, trend_score: 22, momentum_score: 28, risk_score: 72, buy_price_1: null, exit_price_1: 320000, hard_stop: 255000 },
}

export default function AutoTradePanel() {
  return (
    <div className="fade-in">
      <div className="section-header">
        <div style={{display:'flex', alignItems: 'center', gap: '12px'}}>
          <h2 className="section-title">🤖 AI Strategy Matrix</h2>
          <span className="mode-badge" style={{background:'var(--accent-blue)', color:'white', padding: '4px 8px', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 800, letterSpacing: '0.05em'}}>ALPHA ENGINE V2.0</span>
        </div>
        <span className="section-subtitle">다차원 멀티팩터 기반 실시간 오더 플로우 분석 대시보드</span>
      </div>

      <div className="card" style={{marginBottom:'24px',padding:'14px 20px',background:'var(--accent-blue-dim)',border:'1px solid rgba(59,130,246,0.2)'}}>
        <div style={{display:'flex',alignItems:'center',gap:'8px',fontSize:'0.85rem',color:'var(--accent-blue-light)'}}>
          ℹ️ 현재 <strong>Mock 모드</strong>로 운영 중입니다. 실제 주문은 발생하지 않습니다.
        </div>
      </div>

      <div className="card" style={{marginBottom:'24px',overflowX:'auto'}}>
        <table className="data-table">
          <thead>
            <tr>
              <th rowSpan="2" style={{borderBottom: '1px solid var(--border-color)', verticalAlign: 'middle'}}>Asset</th>
              <th rowSpan="2" style={{borderBottom: '1px solid var(--border-color)', verticalAlign: 'middle'}}>Action Protocol</th>
              <th colSpan="5" style={{textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid var(--border-color)'}}>AI Core Analytics (0-100)</th>
              <th colSpan="3" style={{textAlign: 'center', background: 'var(--accent-purple-dim)', borderBottom: '1px solid var(--border-color)'}}>Execution Parameters</th>
            </tr>
            <tr>
              <th><span style={{fontSize: '0.7rem'}}>Alpha Conf.</span></th>
              <th><span style={{fontSize: '0.7rem'}}>Bottom Prob.</span></th>
              <th><span style={{fontSize: '0.7rem'}}>Deep Trend</span></th>
              <th><span style={{fontSize: '0.7rem'}}>Momentum</span></th>
              <th><span style={{fontSize: '0.7rem'}}>Event Risk</span></th>
              <th style={{color: 'var(--color-buy)'}}><span style={{fontSize: '0.7rem'}}>Target Entry</span></th>
              <th style={{color: 'var(--color-sell)'}}><span style={{fontSize: '0.7rem'}}>Target Exit</span></th>
              <th style={{color: 'var(--color-warning)'}}><span style={{fontSize: '0.7rem'}}>Hard Stop</span></th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(SIGNALS).map(([ticker, s]) => (
              <tr key={ticker} style={{transition: 'background 0.2s', '&:hover': {background: 'rgba(255,255,255,0.05)'}}}>
                <td>
                  <strong style={{fontSize: '1.05rem'}}>{s.name}</strong>
                  <div style={{fontSize:'0.7rem',color:'var(--accent-blue-light)',fontFamily:'var(--font-mono)'}}>{ticker}</div>
                </td>
                <td>
                  <span className={`status-badge ${getStateBadgeClass(s.state)}`} style={{padding: '6px 12px', fontSize: '0.75rem', border: s.state === '매매금지' ? '1px solid var(--color-sell)' : 'none'}}>
                    <span className="status-dot"></span>
                    {s.state}
                  </span>
                </td>
                <td>
                  <div style={{display:'flex', alignItems:'center', gap:'8px'}}>
                    <span className="mono" style={{fontWeight:800, color: s.confidence >= 60 ? 'var(--color-buy)' : s.confidence >= 40 ? 'var(--color-hold)' : 'var(--color-sell)'}}>{s.confidence}%</span>
                    <div style={{width:'40px', height:'4px', background:'var(--bg-input)', borderRadius:'2px', overflow:'hidden'}}>
                      <div style={{height:'100%', width:`${s.confidence}%`, background: s.confidence >= 60 ? 'var(--color-buy)' : s.confidence >= 40 ? 'var(--color-hold)' : 'var(--color-sell)'}}></div>
                    </div>
                  </div>
                </td>
                <td><span className={`mono ${getScoreClass(s.bottom_probability_score)}`} style={{fontWeight:700, fontSize:'0.9rem'}}>{s.bottom_probability_score}</span></td>
                <td><span className={`mono ${getScoreClass(s.trend_score)}`} style={{fontWeight:700, fontSize:'0.9rem'}}>{s.trend_score}</span></td>
                <td><span className={`mono ${getScoreClass(s.momentum_score)}`} style={{fontWeight:700, fontSize:'0.9rem'}}>{s.momentum_score}</span></td>
                <td>
                  <span className={`mono ${s.risk_score <= 40 ? 'high' : s.risk_score <= 60 ? 'medium' : 'low'}`} style={{fontWeight:800, padding:'2px 6px', borderRadius:'4px', background: s.risk_score > 60 ? 'var(--color-sell-dim)' : 'transparent'}}>{s.risk_score} <span style={{fontSize:'10px'}}>{s.risk_score > 60 ? '⚠️' : ''}</span></span>
                </td>
                <td className="mono" style={{color:'var(--color-buy)', fontWeight: 600, background: 'rgba(16, 185, 129, 0.05)'}}>{s.buy_price_1 ? formatPrice(s.buy_price_1) : '-'}</td>
                <td className="mono" style={{color:'var(--color-sell)', fontWeight: 600, background: 'rgba(239, 68, 68, 0.05)'}}>{s.exit_price_1 ? formatPrice(s.exit_price_1) : '-'}</td>
                <td className="mono" style={{color:'var(--color-warning)', fontWeight: 600, background: 'rgba(245, 158, 11, 0.05)'}}>{s.hard_stop ? formatPrice(s.hard_stop) : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="two-col">
        <div className="card">
          <div className="card-header"><span className="card-title"><span className="icon">📊</span> 알고리즘 액션 프로필</span></div>
          <div style={{display:'flex',flexDirection:'column',gap:'10px'}}>
            {['관찰','신규진입 후보','1차 물타기 후보','보유','매매금지'].map(state => {
              const count = Object.values(SIGNALS).filter(s => s.state === state).length
              return (
                <div key={state} style={{display:'flex',alignItems:'center',gap:'12px'}}>
                  <span className={`status-badge ${getStateBadgeClass(state)}`} style={{minWidth:'130px', justifyContent:'center'}}>
                    <span className="status-dot"></span>{state}
                  </span>
                  <div className="risk-bar-container" style={{flex:1, height: '8px'}}>
                    <div className="risk-bar" style={{
                      width:`${(count/5)*100}%`, 
                      background: state === '매매금지' ? 'var(--color-sell)' : state === '보유' ? 'var(--color-buy)' : 'var(--accent-blue)',
                      boxShadow: state === '매매금지' ? 'var(--shadow-glow-red)' : state === '보유' ? 'var(--shadow-glow-green)' : 'var(--shadow-glow-blue)'
                    }}></div>
                  </div>
                  <span className="mono" style={{minWidth:'30px',textAlign:'right', fontWeight:800, fontSize:'1.1rem'}}>{count}</span>
                </div>
              )
            })}
          </div>
        </div>
        <div className="card" style={{border: '1px solid var(--accent-purple-dim)', position: 'relative', overflow: 'hidden'}}>
          <div style={{position: 'absolute', top: 0, right: 0, width: '150px', height: '150px', background: 'radial-gradient(circle, var(--accent-purple-dim) 0%, transparent 70%)', transform: 'translate(50%, -50%)', opacity: 0.5}}></div>
          <div className="card-header"><span className="card-title"><span className="icon">⚛️</span> Advanced Execution Protocol</span></div>
          <div style={{fontSize:'0.82rem',lineHeight:1.8,color:'var(--text-secondary)'}}>
            <p>• <strong>Max Drawdown Shield:</strong> <strong style={{color:'var(--color-buy)'}}>ACTIVE</strong> (Hard cap at 10%)</p>
            <p>• <strong>Smart Routing:</strong> TWAP & VWAP Hybrid (Execution limit 3%)</p>
            <p>• <strong>Averaging Down Logic:</strong> <strong style={{color:'var(--text-primary)'}}>Strict Regime Filter</strong> (Max 2 tranches)</p>
            <p style={{marginLeft: '12px', fontSize: '0.75rem', color: 'var(--text-muted)'}}>- Level 1: Initial mean-reversion bounce (3% BP)</p>
            <p style={{marginLeft: '12px', fontSize: '0.75rem', color: 'var(--text-muted)'}}>- Level 2: Institutional flow confirmation only</p>
            <p>• <strong>Kill Switch Condition:</strong> Event risk &gt; 60 OR VIX surge &gt; 20%</p>
            <div style={{marginTop: '16px', padding: '10px', background: 'rgba(139, 92, 246, 0.1)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--accent-purple-dim)', display: 'flex', alignItems: 'center', gap: '8px'}}>
              <div className="status-dot" style={{color: 'var(--accent-purple)', animation: 'pulse 1.5s infinite'}}></div>
              <span style={{color: 'var(--accent-purple)', fontWeight: 600}}>퀀트 모델이 전체 유니버스를 지속 스크리닝 중입니다.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
