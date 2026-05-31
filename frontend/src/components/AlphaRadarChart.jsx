/**
 * AlphaRadarChart - 7개 알파 팩터 레이더 차트 시각화
 * Recharts RadarChart 사용, Glassmorphism 스타일
 */
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, ResponsiveContainer, Tooltip, Legend
} from 'recharts'

const FACTOR_LABELS = {
  technical: '기술적',
  factor: '팩터',
  ml: 'ML예측',
  deep: '딥러닝',
  sentiment: '센티먼트',
  flow: '수급',
  macro: '매크로',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]
  return (
    <div style={{
      background: 'rgba(10,15,30,0.95)',
      border: '1px solid rgba(0,212,255,0.3)',
      borderRadius: 8,
      padding: '8px 12px',
      fontSize: 12,
    }}>
      <div style={{ color: '#00d4ff', fontWeight: 700 }}>{d.name}</div>
      <div style={{ color: '#a0aec0' }}>점수: <span style={{ color: '#fff', fontWeight: 600 }}>{d.value}</span></div>
    </div>
  )
}

const CustomPolarAngleAxis = ({ cx, cy, x, y, payload }) => {
  const label = FACTOR_LABELS[payload.value] || payload.value
  const isRight = x > cx
  const isBottom = y > cy
  return (
    <text
      x={x}
      y={y}
      textAnchor={isRight ? 'start' : x < cx ? 'end' : 'middle'}
      dominantBaseline={isBottom ? 'hanging' : 'auto'}
      style={{ fontSize: 11, fill: '#7dd3fc', fontWeight: 600, fontFamily: 'Inter, sans-serif' }}
    >
      {label}
    </text>
  )
}

export default function AlphaRadarChart({ signalDetails, ticker, name, alphaScore, confidence }) {
  // signal_details: { technical: 65, factor: 72, ml: 58, deep: 60, sentiment: 45, flow: 70, macro: 50 }
  const data = Object.entries(FACTOR_LABELS).map(([key, label]) => ({
    factor: key,
    label,
    score: Math.round(signalDetails?.[key] ?? 50),
    fullMark: 100,
  }))

  // 알파 점수에 따른 색상
  const getAlphaColor = (score) => {
    if (score >= 70) return '#10b981'
    if (score >= 55) return '#3b82f6'
    if (score >= 45) return '#f59e0b'
    return '#ef4444'
  }

  const alphaColor = getAlphaColor(alphaScore)
  const direction = alphaScore >= 70 ? '강력 매수'
    : alphaScore >= 60 ? '매수'
    : alphaScore <= 30 ? '매도'
    : '중립'

  const directionColor = direction.includes('매수') ? '#10b981'
    : direction.includes('매도') ? '#ef4444'
    : '#f59e0b'

  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 16,
      padding: '20px',
      backdropFilter: 'blur(10px)',
    }}>
      {/* 헤더 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 13, color: '#64748b', fontWeight: 500 }}>{ticker}</div>
          <div style={{ fontSize: 16, color: '#e2e8f0', fontWeight: 700 }}>{name || ticker}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{
            fontSize: 28, fontWeight: 800, color: alphaColor,
            fontFamily: 'JetBrains Mono, monospace',
            textShadow: `0 0 20px ${alphaColor}60`,
          }}>
            {alphaScore}
          </div>
          <div style={{ fontSize: 10, color: '#64748b' }}>ALPHA SCORE</div>
        </div>
      </div>

      {/* 방향 뱃지 */}
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 12px',
        borderRadius: 20,
        background: `${directionColor}18`,
        border: `1px solid ${directionColor}40`,
        marginBottom: 16,
      }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: directionColor,
          boxShadow: `0 0 8px ${directionColor}`,
          animation: 'pulse 2s infinite',
        }} />
        <span style={{ fontSize: 12, color: directionColor, fontWeight: 700 }}>{direction}</span>
        <span style={{ fontSize: 11, color: '#64748b' }}>신뢰도 {Math.round(confidence * 100)}%</span>
      </div>

      {/* 레이더 차트 */}
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart cx="50%" cy="50%" outerRadius={80} data={data}>
          <PolarGrid
            stroke="rgba(255,255,255,0.06)"
            gridType="polygon"
          />
          <PolarAngleAxis
            dataKey="factor"
            tick={<CustomPolarAngleAxis />}
          />
          <PolarRadiusAxis
            angle={30}
            domain={[0, 100]}
            tick={false}
            axisLine={false}
          />
          <Radar
            name="알파 점수"
            dataKey="score"
            stroke={alphaColor}
            fill={alphaColor}
            fillOpacity={0.15}
            strokeWidth={2}
            dot={{ fill: alphaColor, strokeWidth: 0, r: 3 }}
          />
          {/* 기준선 (50점) */}
          <Radar
            name="기준선"
            dataKey={() => 50}
            stroke="rgba(255,255,255,0.1)"
            fill="transparent"
            strokeWidth={1}
            strokeDasharray="4 4"
          />
          <Tooltip content={<CustomTooltip />} />
        </RadarChart>
      </ResponsiveContainer>

      {/* 팩터 점수 바 */}
      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {data.map(({ factor, label, score }) => {
          const barColor = score >= 65 ? '#10b981' : score >= 50 ? '#3b82f6' : '#ef4444'
          return (
            <div key={factor} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ fontSize: 10, color: '#64748b', width: 54, flexShrink: 0 }}>{label}</div>
              <div style={{
                flex: 1, height: 4, borderRadius: 2,
                background: 'rgba(255,255,255,0.06)', overflow: 'hidden',
              }}>
                <div style={{
                  height: '100%', width: `${score}%`,
                  background: `linear-gradient(90deg, ${barColor}80, ${barColor})`,
                  borderRadius: 2,
                  transition: 'width 0.5s ease',
                }} />
              </div>
              <div style={{
                fontSize: 10, color: barColor, fontWeight: 700,
                width: 24, textAlign: 'right', fontFamily: 'monospace',
              }}>
                {score}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
