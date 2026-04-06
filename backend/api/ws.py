"""WebSocket 라우터 및 실시간 푸시 관리자"""
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

router = APIRouter(tags=["웹소켓"])

class ConnectionManager:
    def __init__(self):
        # 활성화된 WebSocket 연결 스토어
        self.active_connections: List[WebSocket] = []
        # 클라이언트별 구독 목록 (ws -> set of tickers)
        self.subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = set()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]

    def subscribe(self, websocket: WebSocket, ticker: str):
        if websocket in self.subscriptions:
            self.subscriptions[websocket].add(ticker)

    def unsubscribe(self, websocket: WebSocket, ticker: str):
        if websocket in self.subscriptions and ticker in self.subscriptions[websocket]:
            self.subscriptions[websocket].remove(ticker)

    async def broadcast_market_data(self, data: dict):
        """특정 종목을 구독한 클라이언트나, 대시보드(전체시세) 구독 클라이언트에게 전송"""
        message = json.dumps({"type": "market_tick", "data": data})
        
        for connection in self.active_connections:
            # 상태가 연결되어 있을 때만 전송
            if connection.client_state == WebSocketState.CONNECTED:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    self.disconnect(connection)

    async def broadcast_signal_update(self, signal: dict):
        """전략 엔진 신호 변경 푸시"""
        message = json.dumps({"type": "signal_update", "data": signal})
        for connection in self.active_connections:
            if connection.client_state == WebSocketState.CONNECTED:
                try:
                    await connection.send_text(message)
                except Exception:
                    self.disconnect(connection)

manager = ConnectionManager()

@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    프론트엔드와 연결되는 웹소켓 메인 엔드포인트
    구독 관리(subscribe/unsubscribe) 메시지를 처리합니다.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                action = message.get("action")
                ticker = message.get("ticker", "ALL")
                
                if action == "subscribe":
                    manager.subscribe(websocket, ticker)
                elif action == "unsubscribe":
                    manager.unsubscribe(websocket, ticker)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
