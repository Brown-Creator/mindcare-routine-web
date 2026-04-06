"""주문 API 라우터"""
from fastapi import APIRouter
from backend.mock_data import MOCK_ORDERS

router = APIRouter(prefix="/api/orders", tags=["주문"])


@router.get("/")
async def get_orders():
    """주문 목록"""
    return MOCK_ORDERS


@router.get("/pending")
async def get_pending_orders():
    """미체결 주문"""
    return [o for o in MOCK_ORDERS if o["status"] in ("대기", "접수")]


@router.get("/history")
async def get_order_history():
    """체결 내역"""
    return [o for o in MOCK_ORDERS if o["status"] == "체결"]
