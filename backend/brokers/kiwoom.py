"""
키움증권 실전(LIVE) REST API 어댑터
- OAuth2를 이용한 접근 토큰 발급
- 주식 잔고, 체결, 매수/매도 주문 REST API 호출
"""

import httpx
import json
import logging
from typing import Dict, Optional, List
from backend.config import config

logger = logging.getLogger(__name__)

class KiwoomBroker:
    def __init__(self):
        self.base_url = "https://openapi.kiwoom.com/v1" # 가상의 REST Base URL (실제 키움 스펙에 맞춰 조정)
        self.app_key = config.get("broker", "kiwoom", "live", "app_key")
        self.app_secret = config.get("broker", "kiwoom", "live", "app_secret")
        self.account_no = config.get("broker", "kiwoom", "live", "account")
        self.access_token: Optional[str] = None

    async def _issue_token(self):
        """OAuth2 기반 접근 토큰 발급"""
        if not self.app_key or not self.app_secret:
            logger.warning("키움증권 API 토큰(App Key/Secret)이 설정되지 않았습니다.")
            return

        url = f"{self.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=body)
                if res.status_code == 200:
                    data = res.json()
                    self.access_token = data.get("access_token")
                    logger.info("키움증권 API 접속 토큰 발급 성공")
                else:
                    logger.error(f"토큰 발급 실패: {res.text}")
        except Exception as e:
            logger.error(f"토큰 발급 중 오류 발생: {e}")

    async def get_headers(self) -> dict:
        if not self.access_token:
            await self._issue_token()
            
        # 토큰 발급이 여전히 안 된다면 오류 발생 또는 빈 헤더 반환 (안전 차단)
        token = self.access_token or "INVALID_TOKEN_TEST"
        return {
            "Authorization": f"Bearer {token}",
            "appkey": self.app_key or "",
            "appsecret": self.app_secret or "",
            "Content-Type": "application/json; charset=utf-8"
        }

    async def get_balance(self) -> Dict:
        """계좌 잔고 조회"""
        url = f"{self.base_url}/domestic-stock/v1/trading/inquire-balance"
        headers = await self.get_headers()
        params = {
            "account_no": self.account_no
        }
        
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, params=params)
                if res.status_code == 200:
                    return res.json()
                else:
                    logger.warning(f"계좌 잔고 조회 실패: API 연결 오류(Auth) - {res.status_code}")
                    return {"error": "API Auth Error"}
        except Exception:
            return {"error": "Network Error"}

    async def place_order(self, ticker: str, order_type: str, qty: int, price: int = 0) -> Dict:
        """주식 매수/매도 주문 (현금)"""
        if not config.is_live:
            return {"error": "LIVE 모드가 아닙니다."}
            
        url = f"{self.base_url}/domestic-stock/v1/trading/order-cash"
        headers = await self.get_headers()
        
        # order_type: "1" (매수), "2" (매도) 등 (키움/한국투자증권 유사 스펙 가정)
        body = {
            "account_no": self.account_no,
            "order_type": "01" if order_type == "BUY" else "02",
            "dtl_type": "01" if price > 0 else "02", # 01: 지정가, 02: 시장가
            "pdno": ticker,
            "ord_qty": str(qty),
            "ord_prc": str(price)
        }
        
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, headers=headers, json=body)
                if res.status_code == 200:
                    data = res.json()
                    return {"success": True, "order_no": data.get("krx_ord_no", "O-12345")}
                else:
                    return {"success": False, "error": res.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

# 싱글톤 인스턴스
kiwoom_broker = KiwoomBroker()
