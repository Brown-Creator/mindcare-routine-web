"""
키움증권 REST API 브로커 어댑터

서버 주소:
  - 실전: https://api.kiwoom.com
  - 모의: https://mockapi.kiwoom.com

주요 API ID:
  - au10001: 접근 토큰 발급
  - ka10001: 주식 기본 정보 조회
  - ka10004: 주식 호가 조회
  - ka10005: 주식 일/주/월/시/분 조회
  - kt10000: 주식 매수 주문
  - kt10001: 주식 매도 주문
  - kt10002: 주식 정정 주문
  - kt10003: 주식 취소 주문
  - kt00004: 계좌 평가 현황 조회
  - kt00005: 체결 잔고 조회
"""
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from backend.brokers.base_broker import BaseBroker, BrokerMode


class KiwoomBroker(BaseBroker):
    """키움증권 REST API 브로커 어댑터"""

    BASE_URLS = {
        BrokerMode.LIVE: "https://api.kiwoom.com",
        BrokerMode.PAPER: "https://mockapi.kiwoom.com",
    }

    API_IDS = {
        "token": "au10001",
        "stock_info": "ka10001",
        "orderbook": "ka10004",
        "price_history": "ka10005",
        "buy_order": "kt10000",
        "sell_order": "kt10001",
        "modify_order": "kt10002",
        "cancel_order": "kt10003",
        "account_eval": "kt00004",
        "executions": "kt00005",
    }

    def __init__(self, mode: BrokerMode, app_key: str = "", app_secret: str = ""):
        super().__init__(mode)
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = self.BASE_URLS.get(mode, "")
        self.access_token = ""
        self.token_expires_at: Optional[datetime] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> bool:
        """OAuth2 토큰 발급"""
        if self.mode == BrokerMode.MOCK:
            self._connected = True
            return True

        if not self.app_key or not self.app_secret:
            raise ValueError("App Key와 App Secret이 설정되지 않았습니다.")

        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

        try:
            response = await self._client.post(
                "/oauth2/token",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.app_key,
                    "appsecret": self.app_secret,
                },
                headers={"Content-Type": "application/json;charset=UTF-8"},
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("access_token", "")
            expires_in = data.get("expires_in", 86400)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"키움 API 연결 실패: {str(e)}")

    async def disconnect(self) -> bool:
        if self._client:
            await self._client.aclose()
        self._connected = False
        self.access_token = ""
        return True

    async def is_connected(self) -> bool:
        if not self._connected:
            return False
        if self.token_expires_at and datetime.now() >= self.token_expires_at:
            return False
        return True

    def _get_headers(self, api_id: str, cont_yn: str = "N") -> dict:
        return {
            "Content-Type": "application/json;charset=UTF-8",
            "Authorization": f"Bearer {self.access_token}",
            "api-id": api_id,
            "cont-yn": cont_yn,
        }

    async def _request(self, method: str, path: str, api_id: str,
                       data: dict = None, params: dict = None) -> dict:
        """공통 API 요청 메서드"""
        if not await self.is_connected():
            await self.connect()

        headers = self._get_headers(api_id)
        
        if method == "GET":
            resp = await self._client.get(path, headers=headers, params=params)
        else:
            resp = await self._client.post(path, headers=headers, json=data)
        
        resp.raise_for_status()
        return resp.json()

    # ─── 시세 조회 ───

    async def get_stock_price(self, ticker: str) -> dict:
        if self.mode == BrokerMode.MOCK:
            return {}
        return await self._request(
            "POST", "/api/dostk/stock", self.API_IDS["stock_info"],
            data={"stk_cd": ticker}
        )

    async def get_stock_history(self, ticker: str, period: str = "D",
                                count: int = 120) -> List[dict]:
        if self.mode == BrokerMode.MOCK:
            return []
        period_map = {"D": "1", "W": "2", "M": "3"}
        return await self._request(
            "POST", "/api/dostk/chart", self.API_IDS["price_history"],
            data={
                "stk_cd": ticker,
                "base_dt": datetime.now().strftime("%Y%m%d"),
                "updn_tp": period_map.get(period, "1"),
                "cnt": str(count),
            }
        )

    async def get_orderbook(self, ticker: str) -> dict:
        if self.mode == BrokerMode.MOCK:
            return {}
        return await self._request(
            "POST", "/api/dostk/hoga", self.API_IDS["orderbook"],
            data={"stk_cd": ticker}
        )

    # ─── 주문 ───

    async def place_buy_order(self, ticker: str, price: float,
                              quantity: int, order_type: str = "limit") -> dict:
        if self.mode == BrokerMode.LIVE:
            self._ensure_not_live_without_confirmation()
        if self.mode == BrokerMode.MOCK:
            return {"status": "mock_submitted", "ticker": ticker, "price": price, "qty": quantity}

        ord_tp = "00" if order_type == "limit" else "03"
        return await self._request(
            "POST", "/api/dostk/order", self.API_IDS["buy_order"],
            data={
                "stk_cd": ticker,
                "ord_qty": str(quantity),
                "ord_prc": str(int(price)),
                "ord_tp": ord_tp,
            }
        )

    async def place_sell_order(self, ticker: str, price: float,
                               quantity: int, order_type: str = "limit") -> dict:
        if self.mode == BrokerMode.LIVE:
            self._ensure_not_live_without_confirmation()
        if self.mode == BrokerMode.MOCK:
            return {"status": "mock_submitted", "ticker": ticker, "price": price, "qty": quantity}

        ord_tp = "00" if order_type == "limit" else "03"
        return await self._request(
            "POST", "/api/dostk/order", self.API_IDS["sell_order"],
            data={
                "stk_cd": ticker,
                "ord_qty": str(quantity),
                "ord_prc": str(int(price)),
                "ord_tp": ord_tp,
            }
        )

    async def modify_order(self, order_id: str, price: float,
                           quantity: int) -> dict:
        if self.mode == BrokerMode.MOCK:
            return {"status": "mock_modified"}
        return await self._request(
            "POST", "/api/dostk/order", self.API_IDS["modify_order"],
            data={
                "orgn_ord_no": order_id,
                "ord_qty": str(quantity),
                "ord_prc": str(int(price)),
            }
        )

    async def cancel_order(self, order_id: str) -> dict:
        if self.mode == BrokerMode.MOCK:
            return {"status": "mock_cancelled"}
        return await self._request(
            "POST", "/api/dostk/order", self.API_IDS["cancel_order"],
            data={"orgn_ord_no": order_id}
        )

    # ─── 계좌 ───

    async def get_account_balance(self) -> dict:
        if self.mode == BrokerMode.MOCK:
            return {"total_value": 100000000, "cash": 95000000}
        return await self._request(
            "POST", "/api/dostk/acnt", self.API_IDS["account_eval"],
            data={}
        )

    async def get_positions(self) -> List[dict]:
        if self.mode == BrokerMode.MOCK:
            return []
        result = await self._request(
            "POST", "/api/dostk/acnt", self.API_IDS["account_eval"],
            data={}
        )
        return result.get("positions", [])

    async def get_order_history(self, date: Optional[str] = None) -> List[dict]:
        if self.mode == BrokerMode.MOCK:
            return []
        return await self._request(
            "POST", "/api/dostk/exec", self.API_IDS["executions"],
            data={"qry_dt": date or datetime.now().strftime("%Y%m%d")}
        )

    async def get_api_health(self) -> dict:
        if self.mode == BrokerMode.MOCK:
            return {"status": "정상", "mode": "mock", "latency_ms": 0}
        try:
            start = datetime.now()
            await self._client.get("/health")
            latency = (datetime.now() - start).total_seconds() * 1000
            return {"status": "정상", "mode": self.mode.value, "latency_ms": round(latency)}
        except Exception as e:
            return {"status": "오류", "error": str(e)}
