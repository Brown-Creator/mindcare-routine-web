import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Dashboard from './pages/Dashboard'
import StockDetail from './pages/StockDetail'
import AutoTradePanel from './pages/AutoTradePanel'
import OrderMonitor from './pages/OrderMonitor'
import StrategyLog from './pages/StrategyLog'
import Settings from './pages/Settings'
import KillSwitchPanel from './pages/KillSwitchPanel'
import Backtester from './pages/Backtester'
import QuantAnalytics from './pages/QuantAnalytics'
import useStore from './store/useStore'

function Sidebar({ killSwitchActive, onToggleKillSwitch }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h1>📈 KRX AutoTrader</h1>
        <span className="mode-badge live-mode" style={{background:'var(--color-sell)', color:'white'}}>🔥 LIVE 실전</span>
      </div>
      <nav className="sidebar-nav">
        <div className="nav-section">
          <div className="nav-section-title">메인</div>
          <NavLink to="/" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`} end>
            <span className="nav-icon">📊</span> 대시보드
          </NavLink>
          <NavLink to="/auto-trade" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">🤖</span> 자동매매 상태판
          </NavLink>
        </div>
        <div className="nav-section">
          <div className="nav-section-title">모니터링</div>
          <NavLink to="/orders" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">📋</span> 주문/체결
            <span className="nav-badge">1</span>
          </NavLink>
          <NavLink to="/strategy-log" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">📝</span> 전략 로그
          </NavLink>
          <NavLink to="/backtest" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">🔄</span> 백테스트
          </NavLink>
          <NavLink to="/quant" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">🧮</span> 퀀트 분석
          </NavLink>
        </div>
        <div className="nav-section">
          <div className="nav-section-title">종목</div>
          <NavLink to="/stock/005490" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">🏭</span> 포스코홀딩스
          </NavLink>
          <NavLink to="/stock/005930" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">📱</span> 삼성전자
          </NavLink>
          <NavLink to="/stock/000660" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">💾</span> SK하이닉스
          </NavLink>
          <NavLink to="/stock/035420" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">🌐</span> NAVER
          </NavLink>
          <NavLink to="/stock/051910" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">🔋</span> LG화학
          </NavLink>
        </div>
        <div className="nav-section">
          <div className="nav-section-title">시스템</div>
          <NavLink to="/settings" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">⚙️</span> 설정
          </NavLink>
          <NavLink to="/kill-switch" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
            <span className="nav-icon">🛑</span> 킬스위치
          </NavLink>
        </div>
      </nav>
      <div className="kill-switch-container">
        <button 
          className={`kill-switch-btn ${killSwitchActive ? 'active' : ''}`}
          onClick={onToggleKillSwitch}
        >
          {killSwitchActive ? '🔴 킬스위치 활성화됨' : '⏹️ 긴급 정지'}
        </button>
      </div>
    </aside>
  )
}

function Header() {
  const location = useLocation()
  const pageNames = {
    '/': '대시보드',
    '/auto-trade': '자동매매 상태판',
    '/orders': '주문/체결 모니터',
    '/strategy-log': '전략 로그',
    '/backtest': '백테스터',
    '/quant': '퀀트 분석',
    '/settings': '설정',
    '/kill-switch': '킬스위치 패널',
  }
  const title = location.pathname.startsWith('/stock/') 
    ? '종목 상세' 
    : pageNames[location.pathname] || '대시보드'

  return (
    <header className="header">
      <div className="header-left">
        <h2 className="header-title">{title}</h2>
      </div>
      <div className="header-right">
        <div className="market-ticker">
          <div className="ticker-item">
            <span className="ticker-label">KOSPI</span>
            <span className="ticker-value down">2,580.5 (-0.8%)</span>
          </div>
          <div className="ticker-item">
            <span className="ticker-label">KOSDAQ</span>
            <span className="ticker-value down">725.3 (-1.2%)</span>
          </div>
          <div className="ticker-item">
            <span className="ticker-label">USD/KRW</span>
            <span className="ticker-value up">1,385.5</span>
          </div>
        </div>
      </div>
    </header>
  )
}

export default function App() {
  const [killSwitchActive, setKillSwitchActive] = useState(false)
  const connectWebSocket = useStore(state => state.connectWebSocket)
  const disconnectWebSocket = useStore(state => state.disconnectWebSocket)

  useEffect(() => {
    connectWebSocket()
    return () => {
      disconnectWebSocket()
    }
  }, [connectWebSocket, disconnectWebSocket])

  const handleToggleKillSwitch = () => {
    if (!killSwitchActive) {
      if (window.confirm('⚠️ 킬스위치를 활성화하면 모든 자동주문이 즉시 중단됩니다.\n\n정말 활성화하시겠습니까?')) {
        setKillSwitchActive(true)
      }
    } else {
      setKillSwitchActive(false)
    }
  }

  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar killSwitchActive={killSwitchActive} onToggleKillSwitch={handleToggleKillSwitch} />
        <Header />
        <main className="main-content">
          <div className="page-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/stock/:ticker" element={<StockDetail />} />
              <Route path="/auto-trade" element={<AutoTradePanel />} />
              <Route path="/orders" element={<OrderMonitor />} />
              <Route path="/strategy-log" element={<StrategyLog />} />
              <Route path="/backtest" element={<Backtester />} />
              <Route path="/quant" element={<QuantAnalytics />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/kill-switch" element={<KillSwitchPanel />} />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  )
}
