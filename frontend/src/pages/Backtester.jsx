import { useState } from 'react'
import { api } from '../services/api'
import { formatKRW, formatPercent } from '../utils/formatters'
import EquityChart from '../components/EquityChart'

export default function Backtester() {
  const [params, setParams] = useState({
    ticker: '005490',
    initial_capital: 100000000,
    days: 250
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    
    try {
      const res = await api.runBacktest({
          ticker: params.ticker,
          initial_capital: Number(params.initial_capital),
          days: Number(params.days)
      })
      if (res.error) {
        setError(res.error)
      } else {
        setResult(res)
      }
    } catch (err) {
      setError('서버 응답 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fade-in">
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-end',marginBottom:'24px'}}>
        <div>
          <h1 style={{fontSize:'1.8rem',fontWeight:800,marginBottom:'8px'}}>🔄 전략 백테스터</h1>
          <p style={{color:'var(--text-muted)'}}>과거 데이터를 기반으로 현재의 알고리즘 수익성을 검증합니다.</p>
        </div>
      </div>

      <div className="card" style={{marginBottom:'24px'}}>
        <form onSubmit={handleSubmit} style={{display:'flex',gap:'16px',alignItems:'flex-end',flexWrap:'wrap'}}>
          <div className="form-group" style={{flex: 1, minWidth:'200px'}}>
            <label className="form-label">테스트 대상 종목</label>
            <select 
              className="select-input" 
              value={params.ticker} 
              onChange={e => setParams({...params, ticker: e.target.value})}
              style={{width:'100%',padding:'10px',background:'var(--bg-secondary)',border:'none',borderRadius:'4px',color:'var(--text-primary)'}}
            >
              <option value="005490">포스코홀딩스 (005490)</option>
              <option value="005930">삼성전자 (005930)</option>
              <option value="000660">SK하이닉스 (000660)</option>
              <option value="035420">NAVER (035420)</option>
              <option value="051910">LG화학 (051910)</option>
            </select>
          </div>
          <div className="form-group" style={{flex: 1, minWidth:'150px'}}>
            <label className="form-label">초기 투자금(원)</label>
            <input 
              type="number" 
              className="input-field" 
              value={params.initial_capital} 
              onChange={e => setParams({...params, initial_capital: e.target.value})}
              style={{width:'100%',padding:'10px',background:'var(--bg-secondary)',border:'none',borderRadius:'4px',color:'var(--text-primary)'}}
            />
          </div>
          <div className="form-group" style={{flex: 1, minWidth:'150px'}}>
            <label className="form-label">테스트 기간(영업일)</label>
            <input 
              type="number" 
              className="input-field" 
              value={params.days} 
              onChange={e => setParams({...params, days: e.target.value})}
              style={{width:'100%',padding:'10px',background:'var(--bg-secondary)',border:'none',borderRadius:'4px',color:'var(--text-primary)'}}
            />
          </div>
          <button type="submit" className="action-btn" disabled={loading} style={{padding:'10px 24px'}}>
            {loading ? '시뮬레이션 중...' : '▶ 백테스트 실행'}
          </button>
        </form>
      </div>

      {error && (
        <div className="card" style={{color:'var(--color-sell)', border:'1px solid var(--color-sell)'}}>
          ❌ {error}
        </div>
      )}

      {result && (
        <>
          <div className="three-col" style={{marginBottom:'24px'}}>
            <div className="card" style={{textAlign:'center'}}>
              <div style={{color:'var(--text-muted)',fontSize:'0.85rem',marginBottom:'8px'}}>누적 수익률</div>
              <div style={{fontSize:'1.8rem',fontWeight:'bold',color: result.total_return_pct >= 0 ? 'var(--color-buy)' : 'var(--color-sell)'}}>
                {formatPercent(result.total_return_pct)}
              </div>
            </div>
            <div className="card" style={{textAlign:'center'}}>
              <div style={{color:'var(--text-muted)',fontSize:'0.85rem',marginBottom:'8px'}}>최종 자산</div>
              <div style={{fontSize:'1.8rem',fontWeight:'bold'}}>{formatKRW(result.final_capital)}</div>
            </div>
            <div className="card" style={{textAlign:'center'}}>
              <div style={{color:'var(--text-muted)',fontSize:'0.85rem',marginBottom:'8px'}}>최대 낙폭 (MDD)</div>
              <div style={{fontSize:'1.8rem',fontWeight:'bold',color:'var(--color-sell)'}}>{formatPercent(result.mdd_pct)}</div>
            </div>
          </div>

          <div className="two-col" style={{marginBottom:'24px'}}>
            <div className="card" style={{textAlign:'center'}}>
              <div style={{color:'var(--text-muted)',fontSize:'0.85rem',marginBottom:'8px'}}>총 매매(완료) 횟수</div>
              <div style={{fontSize:'1.5rem',fontWeight:'bold'}}>{result.trade_count} 회</div>
            </div>
            <div className="card" style={{textAlign:'center'}}>
              <div style={{color:'var(--text-muted)',fontSize:'0.85rem',marginBottom:'8px'}}>승률</div>
              <div style={{fontSize:'1.5rem',fontWeight:'bold',color: result.win_rate_pct >= 50 ? 'var(--color-buy)' : 'var(--color-sell)'}}>
                {result.win_rate_pct}%
              </div>
            </div>
          </div>

          <div className="card" style={{marginBottom:'24px', padding:0, overflow:'hidden'}}>
            <div className="card-header" style={{padding:'16px'}}>
              <span className="card-title">📈 자산 추이 곡선 (Equity Curve)</span>
            </div>
            <EquityChart data={result.equity_curve} />
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title">📋 주요 체결 내역</span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>일자</th>
                  <th>구분</th>
                  <th>사유</th>
                  <th>평가금액</th>
                  <th>손익</th>
                </tr>
              </thead>
              <tbody>
                {result.trades.map((t, idx) => (
                  <tr key={idx}>
                    <td>{t.date}</td>
                    <td style={{color: t.type === 'BUY' ? 'var(--color-buy)' : 'var(--color-sell)'}}>{t.type === 'BUY' ? '매수' : '매도'}</td>
                    <td>{t.reason}</td>
                    <td className="mono">{formatKRW(t.price * t.qty)}</td>
                    <td className="mono" style={{color: t.profit > 0 ? 'var(--color-buy)' : t.profit < 0 ? 'var(--color-sell)' : ''}}>
                      {t.profit !== undefined ? formatPercent(t.profit) : '-'}
                    </td>
                  </tr>
                ))}
                {result.trades.length === 0 && (
                  <tr>
                    <td colSpan="5" style={{textAlign:'center',padding:'20px',color:'var(--text-muted)'}}>체결 내역이 없습니다. (조건 미달)</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
