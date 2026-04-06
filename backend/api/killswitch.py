"""킬스위치 API 라우터"""
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api/killswitch", tags=["킬스위치"])

# 인메모리 킬스위치 상태
_kill_switch_state = {
    "active": False,
    "activated_at": None,
    "logs": [
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": "시스템 시작",
            "detail": "킬스위치 비활성 상태로 자동매매 시스템 시작됨",
        }
    ],
}


class KillSwitchAction(BaseModel):
    action: str  # "activate" or "deactivate"


@router.get("/status")
async def get_kill_switch_status():
    """킬스위치 상태 조회"""
    return {
        "active": _kill_switch_state["active"],
        "activated_at": _kill_switch_state["activated_at"],
        "logs": _kill_switch_state["logs"][-20:],
    }


@router.post("/toggle")
async def toggle_kill_switch(action: KillSwitchAction):
    """킬스위치 활성화/비활성화"""
    now = datetime.now().strftime("%H:%M:%S")

    if action.action == "activate":
        _kill_switch_state["active"] = True
        _kill_switch_state["activated_at"] = now
        _kill_switch_state["logs"].insert(0, {
            "time": now,
            "action": "킬스위치 활성화",
            "detail": "수동으로 킬스위치 활성화 → 모든 자동주문 중단",
        })
        return {"status": "activated", "message": "킬스위치가 활성화되었습니다."}

    elif action.action == "deactivate":
        _kill_switch_state["active"] = False
        _kill_switch_state["activated_at"] = None
        _kill_switch_state["logs"].insert(0, {
            "time": now,
            "action": "킬스위치 해제",
            "detail": "수동으로 킬스위치 해제 → 자동매매 재개",
        })
        return {"status": "deactivated", "message": "킬스위치가 해제되었습니다."}

    return {"status": "error", "message": "잘못된 action입니다. 'activate' 또는 'deactivate'를 사용하세요."}
