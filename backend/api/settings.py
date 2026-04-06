"""설정 API 라우터"""
from fastapi import APIRouter
from backend.config import config

router = APIRouter(prefix="/api/settings", tags=["설정"])


@router.get("/")
async def get_settings():
    """현재 설정 (민감정보 마스킹)"""
    return config.to_safe_dict()

from pydantic import BaseModel
import os

class ApiKeys(BaseModel):
    kiwoom_app_key: str = ""
    kiwoom_app_secret: str = ""

@router.post("/keys")
async def update_api_keys(keys: ApiKeys):
    """.env 파일에 API 키 저장 및 업데이트"""
    env_file = ".env"
    
    # Read existing
    lines = []
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    # Update dict
    env_vars = {}
    for line in lines:
        if "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()
            
    if keys.kiwoom_app_key:
        env_vars["KIWOOM_LIVE_APP_KEY"] = keys.kiwoom_app_key
    if keys.kiwoom_app_secret:
        env_vars["KIWOOM_LIVE_APP_SECRET"] = keys.kiwoom_app_secret
        
    # Write back
    with open(env_file, "w", encoding="utf-8") as f:
        for k, v in env_vars.items():
            f.write(f'{k}="{v}"\n')
            
    return {"status": "success", "message": "API keys updated successfully"}

@router.get("/mode")
async def get_current_mode():
    """현재 운영 모드"""
    return {
        "mode": config.mode.value,
        "mode_label": {
            "mock": "Mock (개발/테스트)",
            "paper": "모의투자",
            "live": "실전투자",
        }.get(config.mode.value, config.mode.value),
        "is_live": config.is_live,
    }


@router.get("/risk")
async def get_risk_settings():
    """리스크 설정"""
    return config.risk_config


@router.get("/strategy")
async def get_strategy_settings():
    """전략 설정"""
    return config.strategy_config


@router.get("/deployment-checklist")
async def get_deployment_checklist():
    """배포 체크리스트 (키움 허용 IP 등)"""
    return {
        "items": [
            {
                "id": "account",
                "category": "계좌",
                "label": "키움증권 계좌 개설",
                "description": "키움증권 주식 계좌가 있어야 API를 사용할 수 있습니다.",
                "required": True,
                "checked": False,
            },
            {
                "id": "api_registration",
                "category": "API",
                "label": "REST API 사용 신청",
                "description": "openapi.kiwoom.com에서 API 사용 신청 및 App Key/Secret 발급",
                "required": True,
                "checked": False,
            },
            {
                "id": "allowed_ip",
                "category": "네트워크",
                "label": "허용 IP 등록",
                "description": "키움 REST API는 등록된 IP에서만 접근 가능합니다. 고정 IP가 필요합니다.",
                "required": True,
                "checked": False,
            },
            {
                "id": "fixed_ip",
                "category": "네트워크",
                "label": "고정 IP / VPS 환경 확보",
                "description": "자동매매 시스템은 고정 IP가 있는 VPS(클라우드 서버)에서 운영해야 합니다.",
                "required": True,
                "checked": False,
            },
            {
                "id": "paper_test",
                "category": "테스트",
                "label": "모의투자 테스트 완료",
                "description": "실전 전환 전에 반드시 모의투자(mockapi.kiwoom.com)로 충분히 테스트하세요.",
                "required": True,
                "checked": False,
            },
            {
                "id": "backtest",
                "category": "검증",
                "label": "백테스트 검증 완료",
                "description": "최소 1년 이상의 히스토리 데이터로 백테스트를 실행하고 성과를 검증하세요.",
                "required": True,
                "checked": False,
            },
            {
                "id": "risk_params",
                "category": "리스크",
                "label": "리스크 파라미터 설정",
                "description": "일일 최대 손실, 종목별 비중, MDD 제한 등을 본인에게 맞게 조정하세요.",
                "required": True,
                "checked": False,
            },
            {
                "id": "kill_switch",
                "category": "안전",
                "label": "킬스위치 테스트",
                "description": "킬스위치가 정상 작동하는지 모의투자에서 테스트하세요.",
                "required": True,
                "checked": False,
            },
            {
                "id": "notification",
                "category": "알림",
                "label": "알림 설정 (텔레그램 등)",
                "description": "주요 이벤트 알림을 받을 수 있도록 텔레그램 봇을 설정하세요.",
                "required": False,
                "checked": False,
            },
            {
                "id": "env_vars",
                "category": "보안",
                "label": "환경변수로 키 관리",
                "description": "App Key/Secret은 코드에 직접 넣지 말고 환경변수로 관리하세요.",
                "required": True,
                "checked": False,
            },
        ]
    }
