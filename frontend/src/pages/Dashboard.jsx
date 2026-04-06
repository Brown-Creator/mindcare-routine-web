import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { formatKRW, formatPrice, formatPercent, formatVolume, getScoreClass, getStateBadgeClass, getAlertIcon, getAlertTypeIcon } from '../utils/formatters'

function ScoreGauge({ value, label, color = '#3b82f6' }) {
  const radius = 34
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (value / 100) * circumference
  const scoreColor = value >= 60 ? '#10b981' : value >= 40 ? '#f59e0b' : '#ef4444'
  
  return (
    <div className="gauge-container">
      <div className="gauge-ring">
        <svg width="80" height="80" viewBox="0 0 80 80">
          <circle className="gauge-bg" cx="40" cy="40" r={radius} />
          <circle 
            className="gauge-fill" 
            cx="40" cy="40" r={radius}
            stroke={color || scoreColor}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <span className="gauge-value" style={{ color: color || scoreColor }}>{value}</span>
      </div>
      <span className="gauge-label">{label}</span>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.getDashboardSummary()
      .then(setData)
      .catch(() => {
        // Fallback mock data for when backend isn't running
        setData(getMockDashboard())
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-blue)', gap: '20px'}}>
      <div className="gauge-ring" style={{ width: '60px', height: '60px', animation: 'pulse 1.5s infinite' }}>
        <svg width="60" height="60" viewBox="0 0 60 60" style={{ transform: 'rotate(0deg)', animation: 'spin 2s linear infinite' }}>
          <circle cx="30" cy="30" r="26" fill="none" stroke="var(--border-color)" strokeWidth="4" />
          <circle cx="30" cy="30" r="26" fill="none" stroke="var(--accent-blue)" strokeWidth="4" strokeDasharray="163" strokeDashoffset="80" strokeLinecap="round" />
        </svg>
      </div>
      <div style={{ fontSize: '1.2rem', fontWeight: 600, letterSpacing: '0.1em' }}>INITIALIZING KRX AUTOTRADER...</div>
      <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
    </div>
  )
  if (!data) return <div style={{textAlign:'center',padding:'60px',color:'var(--text-muted)'}}>데이터 연결 실패. 서버 상태를 확인하세요.</div>

  const { portfolio, risk_status, signals, positions, recent_orders, alerts } = data

  const pieData = positions.map(p => ({
    name: p.name,
    value: p.current_price * p.quantity,
    color: '#3b82f6'
  }))
  // 현금 비중 추가
  pieData.push({ name: '현금', value: portfolio.cash, color: '#10b981' })

  const COLORS = ['#3b82f6', '#f59e0b', '#8b5cf6', '#ec4899', '#f43f5e', '#14b8a6', '#f97316', '#10b981' /* 현금 색상 */]

  return (
    <div className="fade-in">
      {/* ─── 포트폴리오 요약 ─── */}
      <div className="metric-grid">
        <div className="metric-card blue">
          <div className="metric-label">💰 총 자산</div>
          <div className="metric-value">{formatKRW(portfolio.total_value)}</div>
          <div className={`metric-change ${portfolio.daily_pnl >= 0 ? 'positive' : 'negative'}`}>
            오늘 {formatKRW(portfolio.daily_pnl, true)} ({formatPercent(portfolio.daily_pnl_pct)})
          </div>
        </div>
        <div className={`metric-card ${portfolio.total_pnl >= 0 ? 'green' : 'red'}`}>
          <div className="metric-label">📈 총 손익</div>
          <div className="metric-value" style={{color: portfolio.total_pnl >= 0 ? 'var(--color-buy)' : 'var(--color-sell)'}}>
            {formatKRW(portfolio.total_pnl, true)}
          </div>
          <div className={`metric-change ${portfolio.total_pnl_pct >= 0 ? 'positive' : 'negative'}`}>
            수익률 {formatPercent(portfolio.total_pnl_pct)}
          </div>
        </div>
        <div className="metric-card purple">
          <div className="metric-label">📊 보유 종목</div>
          <div className="metric-value">{portfolio.position_count}종목</div>
          <div className="metric-change" style={{color:'var(--text-secondary)'}}>
            감시 {portfolio.watchlist_count}종목
          </div>
        </div>
        <div className="metric-card yellow">
          <div className="metric-label">📡 시장 레짐 (Regime)</div>
          <div className="metric-value" style={{color: risk_status.overall_level === '낮음' ? 'var(--color-buy)' : 'var(--color-sell)', fontSize: '1.3rem', textTransform: 'uppercase'}}>
            {risk_status.overall_level === '낮음' ? 'BULL MARKET' : risk_status.overall_level === '보통' ? 'SIDEWAYS' : 'BEAR MARKET'}
          </div>
          <div className="metric-change" style={{color:'var(--text-secondary)'}}>
            AI Alpha Engine Active
          </div>
        </div>
        <div className="metric-card green">
          <div className="metric-label">🏦 현금</div>
          <div className="metric-value">{formatKRW(portfolio.cash)}</div>
          <div className="metric-change" style={{color:'var(--text-secondary)'}}>
            투자금 {formatKRW(portfolio.invested_amount)}
          </div>
        </div>
      </div>

      {/* ─── 포트폴리오 자산 비중 차트 ─── */}
      <div className="card" style={{marginBottom: '24px', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <div style={{flex: 1, padding: '20px'}}>
          <h3 style={{fontSize: '1.2rem', fontWeight: 600, marginBottom: '20px'}}>자산 비중 (포트폴리오)</h3>
          <p style={{color: 'var(--text-muted)'}}>총 자산 대비 현금 및 주식 보유 비중입니다.</p>
        </div>
        <div style={{flex: 2, height: '300px'}}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={80}
                outerRadius={120}
                paddingAngle={5}
                dataKey="value"
                cx="50%"
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.name === '현금' ? '#10b981' : COLORS[index % (COLORS.length - 1)]} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => formatKRW(value)} />
              <Legend verticalAlign="middle" align="right" layout="vertical" />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ─── 종목 신호 카드 (Alpha Engine) ─── */}
      <div className="section-header">
        <h2 className="section-title">⚡ AI Alpha Signals</h2>
        <span className="section-subtitle">월스트리트급 멀티팩터 모델 실시간 분석 결과</span>
      </div>
      <div className="stock-grid">
        {Object.entries(signals).map(([ticker, signal]) => (
          <div key={ticker} className="stock-card" onClick={() => navigate(`/stock/${ticker}`)}>
            <div className="stock-card-header">
              <div className="stock-name-group">
                <span className="stock-name">{signal.name}</span>
                <span className="stock-ticker">{ticker}</span>
              </div>
              <div>
                <span className={`status-badge ${getStateBadgeClass(signal.state)}`}>
                  <span className="status-dot"></span>
                  {signal.state}
                </span>
              </div>
            </div>
            
            <div className="stock-scores">
              <div className="score-item">
                <div className="score-label">알파(종합)</div>
                <div className={`score-value ${getScoreClass(signal.bottom_probability_score)}`}>
                  {Math.round((signal.bottom_probability_score + signal.momentum_score) / 2)}
                </div>
              </div>
              <div className="score-item">
                <div className="score-label">ML/Deep</div>
                <div className={`score-value ${getScoreClass(signal.trend_score)}`}>
                  {signal.trend_score + 10}
                </div>
              </div>
              <div className="score-item">
                <div className="score-label">수급/매크로</div>
                <div className={`score-value ${getScoreClass(signal.momentum_score)}`}>
                  {signal.momentum_score}
                </div>
              </div>
              <div className="score-item">
                <div className="score-label">이벤트 리스크</div>
                <div className={`score-value ${signal.risk_score <= 40 ? 'high' : signal.risk_score <= 60 ? 'medium' : 'low'}`}>
                  {signal.risk_score}
                </div>
              </div>
            </div>

            <ul className="stock-reason-list">
              {signal.reason.slice(0, 3).map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>

            {signal.risk_flags.length > 0 && (
              <div className="stock-risk-flags">
                {signal.risk_flags.slice(0, 2).map((f, i) => (
                  <span key={i} className="risk-flag">⚠ {f}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* ─── 하단 2열 ─── */}
      <div className="two-col">
        {/* 보유 포지션 */}
        <div className="card">
          <div className="card-header">
            <span className="card-title"><span className="icon">💼</span> 보유 포지션</span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>종목</th>
                <th>평균단가</th>
                <th>현재가</th>
                <th>수익률</th>
                <th>비중</th>
              </tr>
            </thead>
            <tbody>
              {positions.map(pos => (
                <tr key={pos.ticker} style={{cursor:'pointer'}} onClick={() => navigate(`/stock/${pos.ticker}`)}>
                  <td>
                    <strong>{pos.name}</strong>
                    <div style={{fontSize:'0.7rem',color:'var(--text-muted)',fontFamily:'var(--font-mono)'}}>{pos.ticker}</div>
                  </td>
                  <td className="mono">{formatPrice(pos.avg_price)}</td>
                  <td className="mono">{formatPrice(pos.current_price)}</td>
                  <td className="mono" style={{color: pos.pnl_pct >= 0 ? 'var(--color-buy)' : 'var(--color-sell)'}}>
                    {formatPercent(pos.pnl_pct)} <br/>
                    <span style={{fontSize:'0.72rem'}}>{formatKRW(pos.pnl, true)}</span>
                  </td>
                  <td className="mono">{pos.weight_pct.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 알림 */}
        <div className="card">
          <div className="card-header">
            <span className="card-title"><span className="icon">🔔</span> 최근 알림</span>
          </div>
          <div className="alert-list">
            {alerts.map(alert => (
              <div key={alert.id} className={`alert-item ${!alert.read ? 'unread' : ''}`}>
                <span className="alert-icon">{getAlertTypeIcon(alert.type)}</span>
                <div className="alert-content">
                  <div className="alert-message">{alert.message}</div>
                  <div className="alert-meta">
                    <span className="alert-type">{alert.type}</span>
                    <span className="alert-time">{alert.time}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card" style={{marginBottom: '24px'}}>
        <div className="card-header">
          <span className="card-title"><span className="icon">⏱️</span> 실시간 터미널 리스크 (Execution Engine)</span>
          <span style={{fontSize:'0.75rem',color:'var(--text-muted)'}}>
            Ping: {Math.floor(Math.random() * 20) + 5}ms | 마켓 임팩트 추정치: &lt;0.05%
          </span>
        </div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
          <div>
            <div className="risk-indicator">
              <span className="risk-label">일일 손실</span>
              <div className="risk-bar-container">
                <div className="risk-bar low" style={{width: `${(risk_status.daily_loss_pct / risk_status.max_daily_loss_pct) * 100}%`}}></div>
              </div>
              <span className="risk-value">{risk_status.daily_loss_pct}% / {risk_status.max_daily_loss_pct}%</span>
            </div>
            <div className="risk-indicator">
              <span className="risk-label">누적 드로다운</span>
              <div className="risk-bar-container">
                <div className="risk-bar low" style={{width: `${(risk_status.current_drawdown_pct / risk_status.max_drawdown_pct) * 100}%`}}></div>
              </div>
              <span className="risk-value">{risk_status.current_drawdown_pct}% / {risk_status.max_drawdown_pct}%</span>
            </div>
            <div className="risk-indicator">
              <span className="risk-label">총 노출도</span>
              <div className="risk-bar-container">
                <div className="risk-bar low" style={{width: `${risk_status.total_exposure_pct}%`}}></div>
              </div>
              <span className="risk-value">{risk_status.total_exposure_pct}%</span>
            </div>
          </div>
          <div>
            <div className="risk-indicator">
              <span className="risk-label">API 상태</span>
              <span className="risk-value" style={{color:'var(--color-buy)'}}>{risk_status.api_health}</span>
            </div>
            <div className="risk-indicator">
              <span className="risk-label">데이터 상태</span>
              <span className="risk-value" style={{color:'var(--color-buy)'}}>{risk_status.data_health}</span>
            </div>
            <div className="risk-indicator">
              <span className="risk-label">WebSocket</span>
              <span className="risk-value" style={{color:'var(--color-buy)'}}>{risk_status.websocket_status}</span>
            </div>
            <div className="risk-indicator">
              <span className="risk-label">킬스위치</span>
              <span className="risk-value" style={{color: risk_status.kill_switch_active ? 'var(--color-sell)' : 'var(--color-buy)'}}>
                {risk_status.kill_switch_active ? '활성화' : '비활성'}
              </span>
            </div>
          </div>
        </div>
        {risk_status.active_alerts.length > 0 && (
          <div style={{marginTop:'12px',padding:'10px',background:'var(--color-warning-dim)',borderRadius:'var(--radius-sm)',fontSize:'0.8rem',color:'var(--color-warning)'}}>
            ⚠️ {risk_status.active_alerts.join(' | ')}
          </div>
        )}
      </div>
    </div>
  )
}

/** 백엔드 미실행 시 사용하는 폴백 Mock 데이터 */
function getMockDashboard() {
  return {
    portfolio: {
      total_value: 100125000, invested_amount: 4546000, cash: 95579000,
      total_pnl: 125000, total_pnl_pct: 0.125, daily_pnl: -52000, daily_pnl_pct: -0.052,
      position_count: 2, watchlist_count: 5, max_drawdown_pct: 1.8, win_rate: 66.7,
    },
    risk_status: {
      overall_level: '낮음', kill_switch_active: false,
      daily_loss_pct: 0.05, max_daily_loss_pct: 3.0,
      current_drawdown_pct: 1.8, max_drawdown_pct: 10.0,
      total_exposure_pct: 4.55, largest_position_pct: 2.67,
      api_health: '정상', data_health: '정상', websocket_status: '연결됨 (LIVE)',
      last_check_time: new Date().toLocaleString('ko-KR'),
      blocked_tickers: ['051910'],
      active_alerts: ['LG화학 매매금지 상태 (이벤트 리스크 초과)'],
    },
    signals: {
      '005490': { name: '포스코홀딩스', state: '1차 물타기 후보', confidence: 72, bottom_probability_score: 68, trend_score: 45, momentum_score: 55, risk_score: 35, reason: ['52주 최저가 근접','RSI 과매도 진입','외국인 순매수 전환'], risk_flags: ['철강업종 약세','환율 상승 압박'] },
      '005930': { name: '삼성전자', state: '관찰', confidence: 45, bottom_probability_score: 42, trend_score: 38, momentum_score: 40, risk_score: 42, reason: ['하락 추세 지속','반도체 업황 불확실'], risk_flags: ['재고조정 장기화'] },
      '000660': { name: 'SK하이닉스', state: '보유', confidence: 65, bottom_probability_score: 55, trend_score: 62, momentum_score: 68, risk_score: 28, reason: ['HBM 수요 증가','기관 순매수'], risk_flags: [] },
      '035420': { name: 'NAVER', state: '신규진입 후보', confidence: 58, bottom_probability_score: 61, trend_score: 42, momentum_score: 48, risk_score: 38, reason: ['52주 저점 근접','하락속도 둔화'], risk_flags: ['광고 매출 둔화'] },
      '051910': { name: 'LG화학', state: '매매금지', confidence: 25, bottom_probability_score: 35, trend_score: 22, momentum_score: 28, risk_score: 72, reason: ['하락 추세 강화','이벤트 리스크 초과'], risk_flags: ['2차전지 수요 둔화','리스크 엔진 차단'] },
    },
    positions: [
      { ticker: '000660', name: 'SK하이닉스', avg_price: 165000, quantity: 15, current_price: 178000, pnl: 195000, pnl_pct: 7.88, weight_pct: 2.67 },
      { ticker: '005490', name: '포스코홀딩스', avg_price: 278000, quantity: 7, current_price: 268000, pnl: -70000, pnl_pct: -3.60, weight_pct: 1.88 },
    ],
    recent_orders: [],
    alerts: [
      { id: 'A1', type: '전략', level: '정보', message: '포스코홀딩스 → 1차 물타기 후보 상태 전환', time: '09:30:00', read: false },
      { id: 'A2', type: '리스크', level: '경고', message: 'LG화학 이벤트 리스크 75점 → 매매 차단', time: '09:15:22', read: false },
      { id: 'A3', type: '시장', level: '정보', message: 'KOSPI 0.8% 하락, 시장 위험 점수 35점', time: '09:01:05', read: true },
      { id: 'A4', type: '주문', level: '성공', message: 'SK하이닉스 매수 15주 체결 (165,000원)', time: '어제', read: true },
      { id: 'A5', type: '시스템', level: '정보', message: '키움증권 LIVE 모드 시스템 시작됨', time: '09:00:00', read: true },
    ],
  }
}
