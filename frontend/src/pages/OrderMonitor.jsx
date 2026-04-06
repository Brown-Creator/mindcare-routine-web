import { formatPrice, getStateBadgeClass } from '../utils/formatters'

const ORDERS = [
  { order_id: 'ORD-20250405-003', ticker: '005490', name: '포스코홀딩스', side: '매수', order_type: '지정가', price: 265000, quantity: 7, filled_quantity: 0, status: '대기', reason: '1차 물타기', risk_approved: true, created_at: '2025-04-05 09:30:00' },
  { order_id: 'ORD-20250405-001', ticker: '005490', name: '포스코홀딩스', side: '매수', order_type: '지정가', price: 278000, quantity: 7, filled_quantity: 7, status: '체결', reason: '신규진입', risk_approved: true, created_at: '2025-03-20 09:15:30', filled_at: '2025-03-20 09:15:42' },
  { order_id: 'ORD-20250405-002', ticker: '000660', name: 'SK하이닉스', side: '매수', order_type: '지정가', price: 165000, quantity: 15, filled_quantity: 15, status: '체결', reason: '신규진입', risk_approved: true, created_at: '2025-03-15 10:02:15', filled_at: '2025-03-15 10:02:28' },
]

export default function OrderMonitor() {
  const statusColors = {
    '대기': 'var(--color-hold)',
    '접수': 'var(--accent-blue)',
    '체결': 'var(--color-buy)',
    '취소': 'var(--text-muted)',
    '거부': 'var(--color-sell)',
  }

  return (
    <div className="fade-in">
      <div className="section-header">
        <h2 className="section-title">📋 주문/체결 모니터</h2>
        <span className="section-subtitle">자동매매 주문 내역 및 체결 상태</span>
      </div>

      <div className="metric-grid" style={{marginBottom:'24px'}}>
        <div className="metric-card blue">
          <div className="metric-label">총 주문</div>
          <div className="metric-value">{ORDERS.length}건</div>
        </div>
        <div className="metric-card yellow">
          <div className="metric-label">미체결</div>
          <div className="metric-value">{ORDERS.filter(o => o.status === '대기').length}건</div>
        </div>
        <div className="metric-card green">
          <div className="metric-label">체결 완료</div>
          <div className="metric-value">{ORDERS.filter(o => o.status === '체결').length}건</div>
        </div>
        <div className="metric-card purple">
          <div className="metric-label">리스크 승인률</div>
          <div className="metric-value">100%</div>
        </div>
      </div>

      <div className="card" style={{overflowX:'auto'}}>
        <table className="data-table">
          <thead>
            <tr>
              <th>주문번호</th>
              <th>종목</th>
              <th>구분</th>
              <th>유형</th>
              <th>가격</th>
              <th>수량</th>
              <th>체결</th>
              <th>상태</th>
              <th>사유</th>
              <th>리스크</th>
              <th>주문시간</th>
            </tr>
          </thead>
          <tbody>
            {ORDERS.map(order => (
              <tr key={order.order_id}>
                <td className="mono" style={{fontSize:'0.75rem'}}>{order.order_id}</td>
                <td>
                  <strong>{order.name}</strong>
                  <div style={{fontSize:'0.7rem',color:'var(--text-muted)',fontFamily:'var(--font-mono)'}}>{order.ticker}</div>
                </td>
                <td>
                  <span style={{color: order.side === '매수' ? 'var(--color-buy)' : 'var(--color-sell)', fontWeight: 700}}>
                    {order.side}
                  </span>
                </td>
                <td>{order.order_type}</td>
                <td className="mono">{formatPrice(order.price)}</td>
                <td className="mono">{order.quantity}</td>
                <td className="mono">{order.filled_quantity}/{order.quantity}</td>
                <td>
                  <span style={{
                    padding:'3px 8px',borderRadius:'4px',fontSize:'0.75rem',fontWeight:600,
                    background: order.status === '체결' ? 'var(--color-buy-dim)' : order.status === '대기' ? 'var(--color-hold-dim)' : 'var(--color-sell-dim)',
                    color: statusColors[order.status] || 'var(--text-primary)'
                  }}>
                    {order.status}
                  </span>
                </td>
                <td style={{fontSize:'0.78rem'}}>{order.reason}</td>
                <td>
                  <span style={{color: order.risk_approved ? 'var(--color-buy)' : 'var(--color-sell)', fontSize:'0.8rem'}}>
                    {order.risk_approved ? '✅ 승인' : '❌ 거부'}
                  </span>
                </td>
                <td style={{fontSize:'0.75rem',color:'var(--text-muted)',fontFamily:'var(--font-mono)'}}>{order.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
