import { useState, useEffect } from 'react'
import { api } from '../services/api'

/**
 * 퀀트 분석 패널 — 새 계량 코어(backend.quant)의 실제 산출물 시각화.
 * 차트 라이브러리 의존 없이 인라인 스타일로 렌더(확실한 표시 보장).
 */

const C = {
  bg: '#0b0f17', card: 'rgba(255,255,255,0.04)', border: 'rgba(255,255,255,0.08)',
  text: '#e6edf3', sub: '#8b97a7', accent: '#4f9cff', up: '#22c55e', down: '#ef4444',
  warn: '#f59e0b', purple: '#a855f7',
}

function Card({ title, hint, children, span = 1 }) {
  return (
    <div style={{
      gridColumn: `span ${span}`, background: C.card, border: `1px solid ${C.border}`,
      borderRadius: 14, padding: 18, backdropFilter: 'blur(8px)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
        <h3 style={{ margin: 0, fontSize: 14, color: C.text, letterSpacing: 0.3 }}>{title}</h3>
        {hint && <span style={{ fontSize: 11, color: C.sub }}>{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function Metric({ label, value, unit = '', color = C.text, big = false }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <span style={{ fontSize: 11, color: C.sub }}>{label}</span>
      <span style={{ fontSize: big ? 26 : 18, fontWeight: 700, color }}>
        {value}<span style={{ fontSize: 12, color: C.sub, marginLeft: 2 }}>{unit}</span>
      </span>
    </div>
  )
}

function WeightBar({ name, ticker, weight, max }) {
  const pct = (weight / max) * 100
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 7 }}>
      <div style={{ width: 96, fontSize: 12, color: C.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {name || ticker}
      </div>
      <div style={{ flex: 1, height: 16, background: 'rgba(255,255,255,0.05)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: `linear-gradient(90deg,${C.accent},${C.purple})`, borderRadius: 4 }} />
      </div>
      <div style={{ width: 52, textAlign: 'right', fontSize: 12, color: C.text, fontVariantNumeric: 'tabular-nums' }}>
        {(weight * 100).toFixed(1)}%
      </div>
    </div>
  )
}

export default function QuantAnalytics() {
  const [data, setData] = useState(null)
  const [method, setMethod] = useState('max_sharpe')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [live, setLive] = useState(null)
  const [liveLoading, setLiveLoading] = useState(false)

  const loadLive = async () => {
    setLiveLoading(true)
    try { setLive(await api.getQuantLiveResearch(8, 300)) }
    catch (e) { setLive({ error: String(e) }) }
    finally { setLiveLoading(false) }
  }

  const load = async (m = method) => {
    setLoading(true); setError(null)
    try {
      const [summary, portfolio] = await Promise.all([
        api.getQuantSummary(),
        api.getQuantPortfolio(m, 0.30),
      ])
      setData({ ...summary, portfolio })
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])  // eslint-disable-line

  const onMethod = (m) => { setMethod(m); load(m) }

  if (loading && !data) return <div style={{ color: C.sub, padding: 40 }}>퀀트 엔진 계산 중…</div>
  if (error) return <div style={{ color: C.down, padding: 40 }}>오류: {error}</div>
  if (!data) return null

  const p = data.portfolio, r = data.risk, costs = data.costs, sig = data.significance
  const maxW = Math.max(...p.allocations.map(a => a.weight), 0.01)
  const maxCost = Math.max(...costs.curve.map(c => c.total_cost_bps), 1)
  const dsrPass = sig.passes_at_95pct

  return (
    <div style={{ color: C.text }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20 }}>🧮 퀀트 분석 <span style={{ fontSize: 12, color: C.sub }}>Quant Core</span></h2>
          <span style={{ fontSize: 12, color: C.sub }}>
            볼록 최적화 · Ledoit-Wolf 수축 · Cornish-Fisher VaR · Deflated Sharpe · 제곱근 시장충격
          </span>
        </div>
        <button onClick={() => load()} style={{
          background: C.accent, color: '#fff', border: 'none', borderRadius: 8,
          padding: '8px 16px', cursor: 'pointer', fontSize: 13,
        }}>↻ 새로고침</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>

        {/* 포트폴리오 최적화 */}
        <Card title="포트폴리오 최적화" hint={p.data_source} span={2}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
            {[['max_sharpe', '최대샤프'], ['risk_parity', '리스크패리티'], ['min_variance', '최소분산'], ['max_diversification', '최대분산화']].map(([m, label]) => (
              <button key={m} onClick={() => onMethod(m)} style={{
                flex: 1, fontSize: 11, padding: '6px 4px', cursor: 'pointer',
                borderRadius: 6, border: `1px solid ${method === m ? C.accent : C.border}`,
                background: method === m ? 'rgba(79,156,255,0.15)' : 'transparent',
                color: method === m ? C.accent : C.sub,
              }}>{label}</button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 18, marginBottom: 16, flexWrap: 'wrap' }}>
            <Metric label="기대 샤프(연율)" value={p.diagnostics.sharpe} color={C.up} big />
            <Metric label="기대수익" value={p.diagnostics.expected_return_pct} unit="%" />
            <Metric label="기대변동성" value={p.diagnostics.expected_vol_pct} unit="%" />
            <Metric label="유효종목수" value={p.diagnostics.effective_n} />
            <Metric label="분산화비율" value={p.diagnostics.diversification_ratio} />
            <Metric label="LW 수축강도" value={p.diagnostics.ledoit_wolf_shrinkage} color={C.purple} />
          </div>
          <div style={{ fontSize: 11, color: C.sub, marginBottom: 8 }}>목표 비중 (상한 30%)</div>
          {p.allocations.map(a => (
            <WeightBar key={a.ticker} name={a.name} ticker={a.ticker} weight={a.weight} max={maxW} />
          ))}
          <div style={{ marginTop: 12, padding: 10, background: 'rgba(34,197,94,0.08)', borderRadius: 8, fontSize: 12 }}>
            최적화 샤프 <b style={{ color: C.up }}>{p.vs_equal_weight.optimized_sharpe}</b>
            {' '}vs 동일가중 <b style={{ color: C.sub }}>{p.vs_equal_weight.equal_weight_sharpe}</b>
          </div>
        </Card>

        {/* 위험 분석 */}
        <Card title="위험 분석" hint="Historical + Cornish-Fisher" span={2}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div style={{ padding: 12, background: 'rgba(239,68,68,0.06)', borderRadius: 8 }}>
              <div style={{ fontSize: 11, color: C.sub, marginBottom: 8 }}>VaR / CVaR</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <Metric label="VaR 95% (Historical)" value={r.var_cvar.var_95_historical_pct} unit="%" color={C.down} />
                <Metric label="CVaR 95% (Historical)" value={r.var_cvar.cvar_95_historical_pct} unit="%" color={C.down} />
                <Metric label="VaR 99% (Cornish-Fisher)" value={r.var_cvar.var_99_cornish_fisher_pct} unit="%" color={C.warn} />
                <Metric label="CVaR 99% (Cornish-Fisher)" value={r.var_cvar.cvar_99_cornish_fisher_pct} unit="%" color={C.warn} />
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <Metric label="최대낙폭 (MDD)" value={r.drawdown.max_drawdown_pct} unit="%" color={C.down} />
              <div style={{ display: 'flex', gap: 16 }}>
                <Metric label="Sortino" value={r.ratios.sortino} />
                <Metric label="Calmar" value={r.ratios.calmar} />
              </div>
              <div style={{ display: 'flex', gap: 16 }}>
                <Metric label="왜도" value={r.distribution.skew} />
                <Metric label="초과첨도" value={r.distribution.excess_kurtosis} />
              </div>
              <div style={{ display: 'flex', gap: 16 }}>
                <Metric label="꼬리비율" value={r.distribution.tail_ratio ?? '-'} />
                <Metric label="적중률" value={(r.distribution.hit_rate * 100).toFixed(0)} unit="%" />
              </div>
            </div>
          </div>
        </Card>

        {/* 시장충격 비용 곡선 */}
        <Card title="거래비용·시장충격" hint={costs.model} span={2}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {costs.curve.map(c => (
              <div key={c.participation_pct} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ width: 70, fontSize: 12, color: C.sub }}>참여율 {c.participation_pct}%</span>
                <div style={{ flex: 1, height: 14, background: 'rgba(255,255,255,0.05)', borderRadius: 4 }}>
                  <div style={{ width: `${(c.total_cost_bps / maxCost) * 100}%`, height: '100%', background: `linear-gradient(90deg,${C.warn},${C.down})`, borderRadius: 4 }} />
                </div>
                <span style={{ width: 60, textAlign: 'right', fontSize: 12 }}>{c.total_cost_bps}bp</span>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 10, fontSize: 11, color: C.sub }}>
            거래량 대비 큰 주문일수록 비용이 √(Q/ADV)로 증가 — flat slippage가 놓치는 용량 효과
          </div>
        </Card>

        {/* 백테스트 유의성 */}
        <Card title="백테스트 유의성" hint={`다중검정 ${sig.n_trials}회 보정`} span={2}>
          <div style={{ display: 'flex', gap: 18, alignItems: 'center', marginBottom: 14 }}>
            <Metric label="관측 샤프(연율)" value={sig.observed_annual_sharpe} big />
            <div style={{
              padding: '6px 14px', borderRadius: 20, fontSize: 13, fontWeight: 700,
              background: dsrPass ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
              color: dsrPass ? C.up : C.down,
            }}>
              {dsrPass ? '✓ 유의 (95%)' : '✗ 미유의 (운일 수 있음)'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 24 }}>
            <Metric label="Probabilistic Sharpe" value={(sig.probabilistic_sharpe * 100).toFixed(1)} unit="%" color={C.accent} />
            <Metric label="Deflated Sharpe" value={(sig.deflated_sharpe * 100).toFixed(1)} unit="%" color={dsrPass ? C.up : C.down} />
            <Metric label="기대 최대샤프(귀무)" value={sig.expected_max_sharpe_under_null} />
          </div>
          <div style={{ marginTop: 12, fontSize: 11, color: C.sub, lineHeight: 1.5 }}>
            {sig.note}
          </div>
        </Card>

        {/* 실데이터 팩터 리서치 (pykrx 라이브, 온디맨드) */}
        <Card title="실데이터 횡단면 팩터 리서치" hint="pykrx 라이브 · KRX" span={4}>
          {!live && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <button onClick={loadLive} disabled={liveLoading} style={{
                background: C.purple, color: '#fff', border: 'none', borderRadius: 8,
                padding: '8px 16px', cursor: liveLoading ? 'wait' : 'pointer', fontSize: 13,
              }}>{liveLoading ? '실데이터 수집 중…(수초)' : '▶ 실데이터로 팩터 채점 실행'}</button>
              <span style={{ fontSize: 12, color: C.sub }}>
                실제 KRX 일봉으로 유니버스를 횡단면 표준화 채점하고 IC/분위 스프레드를 계산합니다.
              </span>
            </div>
          )}
          {live && live.error && <div style={{ color: C.down, fontSize: 12 }}>오류: {live.error}</div>}
          {live && !live.error && (
            <div>
              <div style={{ display: 'flex', gap: 24, marginBottom: 14, flexWrap: 'wrap' }}>
                <Metric label="데이터" value={live.data_source} />
                <Metric label="유니버스" value={live.universe_size} unit="종목" />
                <Metric label="횡단면 IC" value={live.cross_sectional_ic ?? '-'} color={C.accent} />
                <Metric label="기간" value={live.window} />
                <button onClick={loadLive} disabled={liveLoading} style={{
                  marginLeft: 'auto', background: 'transparent', color: C.sub,
                  border: `1px solid ${C.border}`, borderRadius: 6, padding: '4px 10px',
                  cursor: 'pointer', fontSize: 11, height: 28, alignSelf: 'center',
                }}>↻ 갱신</button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: 8 }}>
                {(live.scores || []).sort((a, b) => b.composite_z - a.composite_z).map(s => (
                  <div key={s.ticker} style={{
                    padding: 10, background: 'rgba(255,255,255,0.03)', borderRadius: 8,
                    border: `1px solid ${C.border}`,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 13, fontWeight: 600 }}>{s.name}</span>
                      <span style={{ fontSize: 12, color: s.composite_z >= 0 ? C.up : C.down }}>z {s.composite_z}</span>
                    </div>
                    <div style={{ fontSize: 11, color: C.sub }}>
                      백분위 {s.percentile} · 모멘텀 {s.momentum} · 저변동 {s.low_vol}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
