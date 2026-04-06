/**
 * API 서비스
 */
const API_BASE = '/api';

async function fetchJSON(url) {
  const res = await fetch(API_BASE + url);
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

async function postJSON(url, body) {
  const res = await fetch(API_BASE + url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export const api = {
  // 대시보드
  getDashboardSummary: () => fetchJSON('/dashboard/summary'),
  getPortfolio: () => fetchJSON('/dashboard/portfolio'),
  getPositions: () => fetchJSON('/dashboard/positions'),
  getAlerts: () => fetchJSON('/dashboard/alerts'),
  getStrategyLogs: () => fetchJSON('/dashboard/strategy-logs'),

  // 종목
  getStocks: () => fetchJSON('/stocks/'),
  getStockDetail: (ticker) => fetchJSON(`/stocks/${ticker}`),
  getStockSignal: (ticker) => fetchJSON(`/stocks/${ticker}/signal`),
  getStockIndicators: (ticker) => fetchJSON(`/stocks/${ticker}/indicators`),
  getPriceHistory: (ticker, days = 60) => fetchJSON(`/stocks/${ticker}/history?days=${days}`),

  // 주문
  getOrders: () => fetchJSON('/orders/'),
  getPendingOrders: () => fetchJSON('/orders/pending'),
  getOrderHistory: () => fetchJSON('/orders/history'),

  // 전략
  getSignals: () => fetchJSON('/strategy/signals'),
  getStrategyLogs2: () => fetchJSON('/strategy/logs'),

  // 설정
  getSettings: () => fetchJSON('/settings/'),
  getCurrentMode: () => fetchJSON('/settings/mode'),
  getRiskSettings: () => fetchJSON('/settings/risk'),
  getDeploymentChecklist: () => fetchJSON('/settings/deployment-checklist'),
  updateApiKeys: (keys) => postJSON('/settings/keys', keys),

  // 백테스트
  runBacktest: (params) => postJSON('/backtest/run', params),
};
