import { create } from 'zustand';

const useStore = create((set, get) => ({
  livePrices: {}, // { "005490": { price: 268000, change_pct: -1.1, volume: 890000 } }
  liveSignals: {}, 
  wsConnected: false,
  ws: null,

  connectWebSocket: () => {
    if (get().ws) return;
    
    // 접속 URL을 동적으로 감지 (개발환경 프록시 사용 대응)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      set({ wsConnected: true });
      console.log('🚀 WebSocket 연결 완료! (실시간 시세 수신 시작)');
      // 대시보드 상태이므로 전체 종목 구독
      ws.send(JSON.stringify({ action: 'subscribe', ticker: 'ALL' }));
    };
    
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'market_tick') {
          const { ticker, price, change_pct, volume } = payload.data;
          set((state) => ({
            livePrices: {
              ...state.livePrices,
              [ticker]: { price, change_pct, volume }
            }
          }));
        } else if (payload.type === 'signal_update') {
          const { ticker, signal } = payload.data;
          set((state) => ({
            liveSignals: {
              ...state.liveSignals,
              [ticker]: signal
            }
          }));
        }
      } catch (e) {
        console.error('WebSocket 파싱 오류:', e);
      }
    };
    
    ws.onclose = () => {
      console.log('⚠️ WebSocket 연결 끊김. 3초 후 재연결 시도...');
      set({ wsConnected: false, ws: null });
      setTimeout(() => {
        get().connectWebSocket();
      }, 3000);
    };
    
    set({ ws });
  },
  
  disconnectWebSocket: () => {
    const { ws } = get();
    if (ws) {
      ws.close();
    }
  }
}));

export default useStore;
