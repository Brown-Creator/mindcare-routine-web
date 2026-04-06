import { useState, useEffect } from 'react'
import { api } from '../services/api'

const CHECKLIST = [
  { id: 'account', category: '계좌', label: '키움증권 계좌 개설', description: '키움증권 주식 계좌가 있어야 API를 사용할 수 있습니다.', required: true },
  { id: 'api_registration', category: 'API', label: 'REST API 사용 신청', description: 'openapi.kiwoom.com에서 API 사용 신청 및 App Key/Secret 발급', required: true },
  { id: 'allowed_ip', category: '네트워크', label: '허용 IP 등록', description: '키움 REST API는 등록된 IP에서만 접근 가능합니다. 고정 IP가 필요합니다.', required: true },
  { id: 'fixed_ip', category: '네트워크', label: '고정 IP / VPS 환경 확보', description: '자동매매 시스템은 고정 IP가 있는 VPS(클라우드 서버)에서 운영해야 합니다.', required: true },
  { id: 'paper_test', category: '테스트', label: '모의투자 테스트 완료', description: '실전 전환 전에 반드시 모의투자(mockapi.kiwoom.com)로 충분히 테스트하세요.', required: true },
  { id: 'backtest', category: '검증', label: '백테스트 검증 완료', description: '최소 1년 이상의 히스토리 데이터로 백테스트를 실행하고 성과를 검증하세요.', required: true },
  { id: 'risk_params', category: '리스크', label: '리스크 파라미터 설정', description: '일일 최대 손실, 종목별 비중, MDD 제한 등을 본인에게 맞게 조정하세요.', required: true },
  { id: 'kill_switch', category: '안전', label: '킬스위치 테스트', description: '킬스위치가 정상 작동하는지 모의투자에서 테스트하세요.', required: true },
  { id: 'notification', category: '알림', label: '알림 설정 (텔레그램 등)', description: '주요 이벤트 알림을 받을 수 있도록 텔레그램 봇을 설정하세요.', required: false },
  { id: 'env_vars', category: '보안', label: '환경변수로 키 관리', description: 'App Key/Secret은 코드에 직접 넣지 말고 환경변수로 관리하세요.', required: true },
]

export default function Settings() {
  const [checked, setChecked] = useState({})
  const [tab, setTab] = useState('general')
  const [apiKeys, setApiKeys] = useState({kiwoom_app_key: '', kiwoom_app_secret: ''})
  const [saveStatus, setSaveStatus] = useState('')

  const handleApiKeyChange = (e) => {
    setApiKeys({...apiKeys, [e.target.name]: e.target.value})
  }

  const handleSaveApiKeys = async (e) => {
    e.preventDefault()
    setSaveStatus('saving')
    try {
      await api.updateApiKeys(apiKeys)
      setSaveStatus('success')
      setTimeout(() => setSaveStatus(''), 3000)
    } catch (err) {
      console.error(err)
      setSaveStatus('error')
      setTimeout(() => setSaveStatus(''), 3000)
    }
  }

  const toggleCheck = (id) => {
    setChecked(prev => ({...prev, [id]: !prev[id]}))
  }

  const completedRequired = CHECKLIST.filter(i => i.required && checked[i.id]).length
  const totalRequired = CHECKLIST.filter(i => i.required).length

  return (
    <div className="fade-in">
      <div className="section-header">
        <h2 className="section-title">⚙️ 설정</h2>
      </div>

      <div className="page-tabs">
        <button className={`page-tab ${tab === 'general' ? 'active' : ''}`} onClick={() => setTab('general')}>일반</button>
        <button className={`page-tab ${tab === 'risk' ? 'active' : ''}`} onClick={() => setTab('risk')}>리스크</button>
        <button className={`page-tab ${tab === 'broker' ? 'active' : ''}`} onClick={() => setTab('broker')}>브로커</button>
        <button className={`page-tab ${tab === 'deploy' ? 'active' : ''}`} onClick={() => setTab('deploy')}>배포 체크리스트</button>
      </div>

      {tab === 'general' && (
        <div className="two-col">
          <div className="card">
            <div className="card-header"><span className="card-title">🖥️ 시스템 정보</span></div>
            <table className="data-table">
              <tbody>
                <tr><td>운영 모드</td><td><span className="status-badge entry-candidate" style={{padding:'4px 12px'}}>Mock (개발/테스트)</span></td></tr>
                <tr><td>버전</td><td className="mono">0.1.0</td></tr>
                <tr><td>전략 엔진</td><td style={{color:'var(--color-buy)'}}>활성</td></tr>
                <tr><td>리스크 엔진</td><td style={{color:'var(--color-buy)'}}>활성</td></tr>
                <tr><td>주문 엔진</td><td style={{color:'var(--color-hold)'}}>대기 (Mock)</td></tr>
                <tr><td>데이터 소스</td><td>Mock 데이터</td></tr>
              </tbody>
            </table>
          </div>
          <div className="card">
            <div className="card-header"><span className="card-title">⏰ 거래 시간</span></div>
            <table className="data-table">
              <tbody>
                <tr><td>프리마켓</td><td className="mono">08:30</td></tr>
                <tr><td>장 시작</td><td className="mono">09:00</td></tr>
                <tr><td>장 마감</td><td className="mono">15:30</td></tr>
                <tr><td>포스트마켓</td><td className="mono">16:00</td></tr>
                <tr><td>과열 구간 필터</td><td className="mono">장 시작 후 15분</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'risk' && (
        <div className="two-col">
          <div className="card">
            <div className="card-header"><span className="card-title">🛡️ 리스크 제한</span></div>
            <table className="data-table">
              <tbody>
                <tr><td>일일 최대 손실</td><td className="mono">3.0%</td></tr>
                <tr><td>종목별 최대 비중</td><td className="mono">20.0%</td></tr>
                <tr><td>최대 드로다운</td><td className="mono">10.0%</td></tr>
                <tr><td>주문당 최대 손실</td><td className="mono">2.0%</td></tr>
                <tr><td>슬리피지 한도</td><td className="mono">0.5%</td></tr>
                <tr><td>물타기 최대 횟수</td><td className="mono">2회</td></tr>
              </tbody>
            </table>
          </div>
          <div className="card">
            <div className="card-header"><span className="card-title">📊 전략 기준</span></div>
            <table className="data-table">
              <tbody>
                <tr><td>최소 바닥확률 점수</td><td className="mono">60점</td></tr>
                <tr><td>최소 신뢰도</td><td className="mono">50%</td></tr>
                <tr><td>신규 진입 비율</td><td className="mono">5.0%</td></tr>
                <tr><td>1차 물타기 비율</td><td className="mono">3.0%</td></tr>
                <tr><td>2차 물타기 비율</td><td className="mono">5.0%</td></tr>
                <tr><td>1차 매도 목표</td><td className="mono">+5.0%</td></tr>
                <tr><td>트레일링 스탑</td><td className="mono">-3.0%</td></tr>
                <tr><td>하드 스탑</td><td className="mono">-8.0%</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'broker' && (
        <div className="two-col">
          <div className="card">
            <div className="card-header"><span className="card-title">🔑 API 키 관리</span></div>
            <form onSubmit={handleSaveApiKeys} style={{padding: '10px 0'}}>
              <div className="form-group">
                <label className="form-label">키움증권 App Key (실전/모의 공통)</label>
                <input 
                  type="password" 
                  name="kiwoom_app_key"
                  className="form-input" 
                  placeholder="발급받은 App Key 입력"
                  value={apiKeys.kiwoom_app_key}
                  onChange={handleApiKeyChange}
                />
              </div>
              <div className="form-group">
                <label className="form-label">키움증권 App Secret</label>
                <input 
                  type="password" 
                  name="kiwoom_app_secret"
                  className="form-input" 
                  placeholder="발급받은 App Secret 입력" 
                  value={apiKeys.kiwoom_app_secret}
                  onChange={handleApiKeyChange}
                />
              </div>
              <div style={{display:'flex', alignItems:'center', gap:'12px', marginTop:'24px'}}>
                <button type="submit" className="btn-primary">키 저장 및 .env 업데이트</button>
                {saveStatus === 'saving' && <span style={{color:'var(--accent-blue)'}}>저장 중...</span>}
                {saveStatus === 'success' && <span style={{color:'var(--color-buy)'}}>✅ 성공적으로 저장되었습니다.</span>}
                {saveStatus === 'error' && <span style={{color:'var(--color-sell)'}}>❌ 저장 실패</span>}
              </div>
              <div style={{marginTop:'16px', fontSize:'0.75rem', color:'var(--text-muted)'}}>
                * 서버의 .env 파일에 안전하게 기록됩니다. 보안을 위해 입력한 키는 다시 표시되지 않습니다.
              </div>
            </form>
          </div>
          <div className="card">
            <div className="card-header"><span className="card-title">📡 API 엔드포인트</span></div>
            <table className="data-table">
              <thead><tr><th>기능</th><th>API ID</th></tr></thead>
              <tbody>
                <tr><td>토큰 발급</td><td className="mono">au10001</td></tr>
                <tr><td>주식 기본정보</td><td className="mono">ka10001</td></tr>
                <tr><td>호가 조회</td><td className="mono">ka10004</td></tr>
                <tr><td>차트 조회</td><td className="mono">ka10005</td></tr>
                <tr><td>매수 주문</td><td className="mono">kt10000</td></tr>
                <tr><td>매도 주문</td><td className="mono">kt10001</td></tr>
                <tr><td>정정 주문</td><td className="mono">kt10002</td></tr>
                <tr><td>취소 주문</td><td className="mono">kt10003</td></tr>
                <tr><td>계좌 조회</td><td className="mono">kt00004</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'deploy' && (
        <div>
          <div className="card" style={{marginBottom:'16px',padding:'14px 20px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
              <span style={{fontSize:'0.9rem',fontWeight:600}}>📋 실전 배포 준비 상태</span>
              <span className="mono" style={{
                color: completedRequired === totalRequired ? 'var(--color-buy)' : 'var(--color-hold)',
                fontWeight: 700
              }}>
                {completedRequired}/{totalRequired} 필수 항목 완료
              </span>
            </div>
            <div className="risk-bar-container" style={{marginTop:'10px'}}>
              <div className="risk-bar" style={{
                width: `${(completedRequired/totalRequired)*100}%`,
                background: completedRequired === totalRequired 
                  ? 'linear-gradient(90deg, var(--color-buy), #059669)' 
                  : 'linear-gradient(90deg, var(--color-hold), #d97706)'
              }}></div>
            </div>
          </div>

          {CHECKLIST.map(item => (
            <div key={item.id} className="checklist-item" onClick={() => toggleCheck(item.id)}>
              <div className={`checklist-check ${checked[item.id] ? 'checked' : ''}`}>
                {checked[item.id] && <span style={{color:'white',fontSize:'0.75rem'}}>✓</span>}
              </div>
              <div style={{flex:1}}>
                <div className="checklist-label">{item.label} {item.required && <span style={{color:'var(--color-sell)',fontSize:'0.7rem'}}>필수</span>}</div>
                <div className="checklist-desc">{item.description}</div>
              </div>
              <span className="checklist-category">{item.category}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
