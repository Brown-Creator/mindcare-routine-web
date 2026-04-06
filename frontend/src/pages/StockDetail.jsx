import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../services/api'
import { formatPrice, formatPercent, formatKRW, formatVolume, getScoreClass, getStateBadgeClass } from '../utils/formatters'
import StockChart from '../components/StockChart'
import useStore from '../store/useStore'

function ScoreGauge({ value, label, size = 90 }) {
  const radius = (size - 12) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (value / 100) * circumference
  const color = value >= 60 ? '#10b981' : value >= 40 ? '#f59e0b' : '#ef4444'
  
  return (
    <div className="gauge-container">
      <div className="gauge-ring" style={{width: size, height: size}}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle className="gauge-bg" cx={size/2} cy={size/2} r={radius} />
          <circle className="gauge-fill" cx={size/2} cy={size/2} r={radius}
            stroke={color} strokeDasharray={circumference} strokeDashoffset={offset} />
        </svg>
        <span className="gauge-value" style={{ color }}>{value}</span>
      </div>
      <span className="gauge-label">{label}</span>
    </div>
  )
}

const MOCK_DETAILS = {
  '005490': {
    stock: { ticker: '005490', name: '포스코홀딩스', market: 'KOSPI', sector: '철강', current_price: 268000, prev_close: 271000, change_pct: -1.11, volume: 892340, market_cap: 20700000000000, high_52w: 398000, low_52w: 254000 },
    signal: { ticker: '005490', name: '포스코홀딩스', state: '1차 물타기 후보', confidence: 72, bottom_probability_score: 68, trend_score: 45, momentum_score: 55, mean_reversion_score: 71, supply_demand_score: 62, event_risk_score: 40, market_risk_score: 35, risk_score: 35,
      buy_price_1: 265000, buy_amount_1: 2000000, buy_price_2: 250000, buy_amount_2: 3000000,
      exit_price_1: 285000, exit_price_2: 305000, exit_trailing_stop: 258000, hard_stop: 240000,
      reason: ['52주 최저가 근접 (254,000원 대비 5.5% 위)','RSI(14) 28.5 → 과매도 구간 진입','외국인 3일 연속 순매수 전환','거래량 20일 평균 대비 바닥 형성','60일 이동평균 괴리율 -12.3%','볼린저밴드 하단 근접'],
      risk_flags: ['철강업종 전반적 약세 지속','환율(원/달러) 상승 압박','중국 철강 수출 증가로 업황 부담'] },
    indicators: { ma5: 270200, ma20: 275800, ma60: 295000, ma120: 320000, rsi14: 28.5, macd: -3200, macd_signal: -2800, macd_histogram: -400, bb_upper: 290000, bb_middle: 275000, bb_lower: 260000, atr14: 8500, volume_ratio: 0.85, volatility_surge: false },
  },
  '005930': {
    stock: { ticker: '005930', name: '삼성전자', market: 'KOSPI', sector: '반도체', current_price: 71200, prev_close: 71800, change_pct: -0.84, volume: 12450000, market_cap: 425000000000000, high_52w: 88800, low_52w: 53000 },
    signal: { ticker: '005930', name: '삼성전자', state: '관찰', confidence: 45, bottom_probability_score: 42, trend_score: 38, momentum_score: 40, mean_reversion_score: 55, supply_demand_score: 48, event_risk_score: 30, market_risk_score: 35, risk_score: 42,
      buy_price_1: 68000, buy_amount_1: 3000000, exit_price_1: 78000, exit_price_2: 85000, exit_trailing_stop: 66000, hard_stop: 62000,
      reason: ['하락 추세 지속 중','반도체 업황 개선 신호 미약','거래량 감소세 → 바닥 형성 단계 관찰 필요'],
      risk_flags: ['반도체 재고조정 장기화 우려','미중 무역갈등 재부각'] },
    indicators: { ma5: 71800, ma20: 73500, ma60: 76000, ma120: 78500, rsi14: 35.2, macd: -850, macd_signal: -720, macd_histogram: -130, bb_upper: 76000, bb_middle: 73000, bb_lower: 70000, atr14: 1800, volume_ratio: 0.72, volatility_surge: false },
  },
  '000660': {
    stock: { ticker: '000660', name: 'SK하이닉스', market: 'KOSPI', sector: '반도체', current_price: 178000, prev_close: 175500, change_pct: 1.42, volume: 3210000, market_cap: 130000000000000, high_52w: 248000, low_52w: 132000 },
    signal: { ticker: '000660', name: 'SK하이닉스', state: '보유', confidence: 65, bottom_probability_score: 55, trend_score: 62, momentum_score: 68, mean_reversion_score: 45, supply_demand_score: 72, event_risk_score: 25, market_risk_score: 30, risk_score: 28,
      buy_price_1: 165000, buy_amount_1: 2500000, exit_price_1: 195000, exit_price_2: 220000, exit_trailing_stop: 170000, hard_stop: 155000,
      reason: ['HBM 수요 증가 수혜 기대','기관 순매수 전환 확인','반등 모멘텀 점수 개선 중'],
      risk_flags: ['단기 과열 구간 진입 가능성'] },
    indicators: { ma5: 176000, ma20: 172000, ma60: 180000, ma120: 195000, rsi14: 58.3, macd: 2100, macd_signal: 1500, macd_histogram: 600, bb_upper: 192000, bb_middle: 178000, bb_lower: 164000, atr14: 5200, volume_ratio: 1.15, volatility_surge: false },
  },
  '035420': {
    stock: { ticker: '035420', name: 'NAVER', market: 'KOSPI', sector: '인터넷', current_price: 195000, prev_close: 197000, change_pct: -1.02, volume: 1580000, market_cap: 32000000000000, high_52w: 245000, low_52w: 175000 },
    signal: { ticker: '035420', name: 'NAVER', state: '신규진입 후보', confidence: 58, bottom_probability_score: 61, trend_score: 42, momentum_score: 48, mean_reversion_score: 65, supply_demand_score: 55, event_risk_score: 35, market_risk_score: 38, risk_score: 38,
      buy_price_1: 190000, buy_amount_1: 2000000, exit_price_1: 215000, exit_price_2: 235000, exit_trailing_stop: 183000, hard_stop: 172000,
      reason: ['52주 최저가 대비 바닥권 접근','AI/검색 신사업 성장 기대','하락 속도 둔화 → 바닥 형성 징후'],
      risk_flags: ['광고 매출 둔화','글로벌 빅테크 경쟁 심화'] },
    indicators: { ma5: 196000, ma20: 200000, ma60: 210000, ma120: 218000, rsi14: 32.8, macd: -2500, macd_signal: -2100, macd_histogram: -400, bb_upper: 215000, bb_middle: 200000, bb_lower: 185000, atr14: 6000, volume_ratio: 0.90, volatility_surge: false },
  },
  '051910': {
    stock: { ticker: '051910', name: 'LG화학', market: 'KOSPI', sector: '화학', current_price: 285000, prev_close: 288000, change_pct: -1.04, volume: 420000, market_cap: 20100000000000, high_52w: 415000, low_52w: 262000 },
    signal: { ticker: '051910', name: 'LG화학', state: '매매금지', confidence: 25, bottom_probability_score: 35, trend_score: 22, momentum_score: 28, mean_reversion_score: 40, supply_demand_score: 30, event_risk_score: 75, market_risk_score: 60, risk_score: 72,
      buy_price_1: null, buy_amount_1: null, exit_price_1: 320000, exit_price_2: 350000, exit_trailing_stop: 275000, hard_stop: 255000,
      reason: ['하락 추세 강화 중','배터리 업황 불확실성 확대','이벤트 리스크 점수 임계치 초과 → 매매 금지'],
      risk_flags: ['2차전지 수요 둔화','전기차 보조금 축소 우려','원재료 가격 변동성 급등','리스크 엔진이 매매를 차단함'] },
    indicators: { ma5: 288000, ma20: 298000, ma60: 325000, ma120: 355000, rsi14: 24.1, macd: -8500, macd_signal: -7200, macd_histogram: -1300, bb_upper: 315000, bb_middle: 298000, bb_lower: 272000, atr14: 11000, volume_ratio: 0.65, volatility_surge: true },
  },
}

export default function StockDetail() {
  const { ticker } = useParams()
  const [data, setData] = useState(null)
  const [tab, setTab] = useState('signal')

  useEffect(() => {
    api.getStockDetail(ticker)
      .then(setData)
      .catch(() => {
        setData(MOCK_DETAILS[ticker] || null)
      })
  }, [ticker])

  const livePrices = useStore(state => state.livePrices)
  const liveSignals = useStore(state => state.liveSignals)

  if (!data) return <div style={{textAlign:'center',padding:'60px',color:'var(--text-muted)'}}>로딩 중...</div>
  
  const { stock, indicators, price_history } = data
  
  // 실시간 라이브 데이터가 있으면 오버라이드
  const livePriceData = livePrices[stock.ticker]
  const currentPrice = livePriceData ? livePriceData.price : stock.current_price
  const changePct = livePriceData ? livePriceData.change_pct : stock.change_pct
  const changeAmt = currentPrice - stock.prev_close
  
  const currentSignal = liveSignals[stock.ticker] || data.signal

  return (
    <div className="fade-in">
      {/* ─── 종목 헤더 ─── */}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:'24px'}}>
        <div>
          <h1 style={{fontSize:'1.8rem',fontWeight:800,marginBottom:'4px'}}>{stock.name}</h1>
          <div style={{display:'flex',alignItems:'center',gap:'12px',color:'var(--text-muted)',fontSize:'0.85rem'}}>
            <span style={{fontFamily:'var(--font-mono)'}}>{stock.ticker}</span>
            <span>{stock.market}</span>
            <span>{stock.sector}</span>
          </div>
        </div>
        <div style={{textAlign:'right'}}>
          <div style={{fontSize:'2rem',fontWeight:800,fontFamily:'var(--font-mono)', transition: 'color 0.3s'}}>{formatPrice(currentPrice)}</div>
          <div style={{fontSize:'1rem',fontWeight:600,fontFamily:'var(--font-mono)',color: changePct >= 0 ? 'var(--color-buy)' : 'var(--color-sell)'}}>
            {formatPercent(changePct)} ({formatPrice(changeAmt)})
          </div>
        </div>
      </div>

      {/* ─── 상태 + 점수 요약 (ALPHA MULTI-FACTOR MODEL) ─── */}
      {currentSignal && (
        <div className="card" style={{marginBottom:'24px', border: '1px solid var(--accent-blue-dim)'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
            <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
              <h3 style={{margin:0, fontSize:'1.1rem', color:'var(--accent-blue-light)', display:'flex', alignItems:'center', gap:'8px'}}>
                <span className="icon">🧠</span> AI Alpha Factors
              </h3>
              <span className={`status-badge ${getStateBadgeClass(currentSignal.state)}`} style={{fontSize:'0.85rem',padding:'6px 14px', marginLeft:'12px'}}>
                <span className="status-dot"></span>
                Action Layer: {currentSignal.state}
              </span>
              <span style={{color:'var(--text-muted)',fontSize:'0.85rem'}}>Signal Confidence: {currentSignal.confidence}%</span>
            </div>
            <div style={{fontSize:'0.75rem', color:'var(--text-muted)'}}>Alpha Engine Build: 2.0.4</div>
          </div>

          <div style={{display:'flex',justifyContent:'space-around',flexWrap:'wrap',gap:'16px'}}>
            <ScoreGauge value={currentSignal.bottom_probability_score} label="Mean Reversion" size={100} />
            <ScoreGauge value={currentSignal.trend_score} label="Deep Trend" size={100} />
            <ScoreGauge value={currentSignal.momentum_score} label="Momentum" size={100}/>
            <ScoreGauge value={currentSignal.supply_demand_score || 0} label="Inst Demand" size={100} />
            <ScoreGauge value={100 - (currentSignal.event_risk_score || 0)} label="Event Safety" size={100} color={currentSignal.event_risk_score > 60 ? '#ef4444' : '#10b981'} />
            <ScoreGauge value={100 - (currentSignal.market_risk_score || 0)} label="Macro Safety" size={100} color={currentSignal.market_risk_score > 60 ? '#ef4444' : '#10b981'} />
          </div>
        </div>
      )}

      {/* ─── 캔들 차트 ─── */}
      {price_history && <StockChart data={price_history} signal={currentSignal} />}

      {/* ─── 탭 ─── */}
      <div className="page-tabs">
        <button className={`page-tab ${tab === 'signal' ? 'active' : ''}`} onClick={() => setTab('signal')}>📡 전략 신호</button>
        <button className={`page-tab ${tab === 'indicators' ? 'active' : ''}`} onClick={() => setTab('indicators')}>📐 기술적 지표</button>
        <button className={`page-tab ${tab === 'plan' ? 'active' : ''}`} onClick={() => setTab('plan')}>📋 매매 계획</button>
        <button className={`page-tab ${tab === 'info' ? 'active' : ''}`} onClick={() => setTab('info')}>ℹ️ 종목 정보</button>
      </div>

      {/* ─── 탭 컨텐츠 ─── */}
      {tab === 'signal' && currentSignal && (
        <div className="two-col">
          <div className="card">
            <div className="card-header">
              <span className="card-title">📊 분석 근거</span>
            </div>
            <ul className="stock-reason-list" style={{fontSize:'0.85rem'}}>
              {currentSignal.reason.map((r, i) => <li key={i} style={{padding:'6px 0',paddingLeft:'16px'}}>{r}</li>)}
            </ul>
          </div>
          <div className="card">
            <div className="card-header">
              <span className="card-title">⚠️ 리스크 요인</span>
            </div>
            {currentSignal.risk_flags && currentSignal.risk_flags.length > 0 ? (
              <div style={{display:'flex',flexDirection:'column',gap:'8px'}}>
                {currentSignal.risk_flags.map((f, i) => (
                  <div key={i} style={{padding:'10px 14px',background:'var(--color-warning-dim)',borderRadius:'var(--radius-sm)',fontSize:'0.82rem',color:'var(--color-warning)'}}>
                    ⚠️ {f}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{color:'var(--color-buy)',fontSize:'0.85rem'}}>✅ 특별한 리스크 요인 없음</div>
            )}
          </div>
        </div>
      )}

      {tab === 'indicators' && indicators && (
        <div className="three-col">
          <div className="card">
            <div className="card-header"><span className="card-title">📈 이동평균선</span></div>
            <table className="data-table">
              <tbody>
                <tr><td>MA(5)</td><td className="mono">{formatPrice(indicators.ma5)}</td><td className="mono" style={{color: currentPrice > indicators.ma5 ? 'var(--color-buy)' : 'var(--color-sell)'}}>{formatPercent((currentPrice - indicators.ma5) / indicators.ma5 * 100)}</td></tr>
                <tr><td>MA(20)</td><td className="mono">{formatPrice(indicators.ma20)}</td><td className="mono" style={{color: currentPrice > indicators.ma20 ? 'var(--color-buy)' : 'var(--color-sell)'}}>{formatPercent((currentPrice - indicators.ma20) / indicators.ma20 * 100)}</td></tr>
                <tr><td>MA(60)</td><td className="mono">{formatPrice(indicators.ma60)}</td><td className="mono" style={{color: currentPrice > indicators.ma60 ? 'var(--color-buy)' : 'var(--color-sell)'}}>{formatPercent((currentPrice - indicators.ma60) / indicators.ma60 * 100)}</td></tr>
                <tr><td>MA(120)</td><td className="mono">{formatPrice(indicators.ma120)}</td><td className="mono" style={{color: currentPrice > indicators.ma120 ? 'var(--color-buy)' : 'var(--color-sell)'}}>{formatPercent((currentPrice - indicators.ma120) / indicators.ma120 * 100)}</td></tr>
              </tbody>
            </table>
          </div>
          <div className="card">
            <div className="card-header"><span className="card-title">📊 오실레이터</span></div>
            <table className="data-table">
              <tbody>
                <tr><td>RSI(14)</td><td className="mono" style={{color: indicators.rsi14 < 30 ? 'var(--color-sell)' : indicators.rsi14 > 70 ? 'var(--color-buy)' : 'var(--text-primary)'}}>{indicators.rsi14}</td><td style={{fontSize:'0.75rem',color:'var(--text-muted)'}}>{indicators.rsi14 < 30 ? '과매도' : indicators.rsi14 > 70 ? '과매수' : '중립'}</td></tr>
                <tr><td>MACD</td><td className="mono">{formatPrice(indicators.macd)}</td><td></td></tr>
                <tr><td>Signal</td><td className="mono">{formatPrice(indicators.macd_signal)}</td><td></td></tr>
                <tr><td>Histogram</td><td className="mono" style={{color: indicators.macd_histogram >= 0 ? 'var(--color-buy)' : 'var(--color-sell)'}}>{formatPrice(indicators.macd_histogram)}</td><td></td></tr>
              </tbody>
            </table>
          </div>
          <div className="card">
            <div className="card-header"><span className="card-title">📏 볼린저/ATR</span></div>
            <table className="data-table">
              <tbody>
                <tr><td>상단</td><td className="mono">{formatPrice(indicators.bb_upper)}</td><td></td></tr>
                <tr><td>중간</td><td className="mono">{formatPrice(indicators.bb_middle)}</td><td></td></tr>
                <tr><td>하단</td><td className="mono">{formatPrice(indicators.bb_lower)}</td><td></td></tr>
                <tr><td>ATR(14)</td><td className="mono">{formatPrice(indicators.atr14)}</td><td></td></tr>
                <tr><td>거래량 비율</td><td className="mono">{indicators.volume_ratio?.toFixed(2)}x</td><td style={{fontSize:'0.75rem',color:'var(--text-muted)'}}>{indicators.volume_ratio > 1.5 ? '급증' : indicators.volume_ratio < 0.5 ? '극감소' : '보통'}</td></tr>
                <tr><td>변동성 급등</td><td className="mono" style={{color: indicators.volatility_surge ? 'var(--color-sell)' : 'var(--color-buy)'}}>{indicators.volatility_surge ? '감지됨 ⚠️' : '정상'}</td><td></td></tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'plan' && currentSignal && (
        <div className="card" style={{border: '1px solid var(--border-color-active)', background: 'linear-gradient(180deg, rgba(17,24,39,1) 0%, rgba(30,58,138,0.1) 100%)'}}>
          <div className="card-header"><span className="card-title"><span className="icon">🎯</span> Execution Matrix (Smart Routing)</span></div>
          <div className="trade-plan">
            <div className="plan-item" style={{background: 'rgba(16, 185, 129, 0.05)'}}>
              <div className="plan-label">L1 Entry (TWAP)</div>
              <div className="plan-value buy">{currentSignal.buy_price_1 ? formatPrice(currentSignal.buy_price_1) : '-'}</div>
            </div>
            <div className="plan-item" style={{background: 'rgba(16, 185, 129, 0.05)'}}>
              <div className="plan-label">L1 Sizing</div>
              <div className="plan-value buy">{currentSignal.buy_amount_1 ? formatKRW(currentSignal.buy_amount_1) : '-'}</div>
            </div>
            <div className="plan-item" style={{background: 'rgba(16, 185, 129, 0.02)'}}>
              <div className="plan-label">L2 Entry (VWAP)</div>
              <div className="plan-value buy">{currentSignal.buy_price_2 ? formatPrice(currentSignal.buy_price_2) : '-'}</div>
            </div>
            <div className="plan-item" style={{background: 'rgba(16, 185, 129, 0.02)'}}>
              <div className="plan-label">L2 Sizing</div>
              <div className="plan-value buy">{currentSignal.buy_amount_2 ? formatKRW(currentSignal.buy_amount_2) : '-'}</div>
            </div>
            <div className="plan-item" style={{background: 'rgba(245, 158, 11, 0.05)'}}>
              <div className="plan-label">Exit 1 (TP)</div>
              <div className="plan-value sell">{currentSignal.exit_price_1 ? formatPrice(currentSignal.exit_price_1) : '-'}</div>
            </div>
            <div className="plan-item" style={{background: 'rgba(245, 158, 11, 0.05)'}}>
              <div className="plan-label">Exit 2 (TP2)</div>
              <div className="plan-value sell">{currentSignal.exit_price_2 ? formatPrice(currentSignal.exit_price_2) : '-'}</div>
            </div>
            <div className="plan-item" style={{background: 'rgba(239, 68, 68, 0.05)'}}>
              <div className="plan-label">Trailing Stop</div>
              <div className="plan-value stop">{currentSignal.exit_trailing_stop ? formatPrice(currentSignal.exit_trailing_stop) : '-'}</div>
            </div>
            <div className="plan-item" style={{background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239,68,68,0.3)'}}>
              <div className="plan-label" style={{color: 'var(--color-sell)'}}>Hard Stop (SL)</div>
              <div className="plan-value stop">{currentSignal.hard_stop ? formatPrice(currentSignal.hard_stop) : '-'}</div>
            </div>
          </div>
        </div>
      )}

      {tab === 'info' && (
        <div className="two-col">
          <div className="card">
            <div className="card-header"><span className="card-title">ℹ️ 기본 정보</span></div>
            <table className="data-table">
              <tbody>
                <tr><td>시장</td><td>{stock.market}</td></tr>
                <tr><td>섹터</td><td>{stock.sector}</td></tr>
                <tr><td>시가총액</td><td className="mono">{formatKRW(stock.market_cap)}</td></tr>
                <tr><td>거래량</td><td className="mono">{formatVolume(stock.volume)}</td></tr>
              </tbody>
            </table>
          </div>
          <div className="card">
            <div className="card-header"><span className="card-title">📊 가격 범위</span></div>
            <table className="data-table">
              <tbody>
                <tr><td>현재가</td><td className="mono">{formatPrice(currentPrice)}</td></tr>
                <tr><td>전일종가</td><td className="mono">{formatPrice(stock.prev_close)}</td></tr>
                <tr><td>52주 최고</td><td className="mono" style={{color:'var(--color-buy)'}}>{formatPrice(stock.high_52w)}</td></tr>
                <tr><td>52주 최저</td><td className="mono" style={{color:'var(--color-sell)'}}>{formatPrice(stock.low_52w)}</td></tr>
                <tr><td>52주 최저 대비</td><td className="mono" style={{color:'var(--accent-blue)'}}>
                  {stock.low_52w ? formatPercent((currentPrice - stock.low_52w) / stock.low_52w * 100) : '-'}
                </td></tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
