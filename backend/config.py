"""
KRX AutoTrader 설정 관리
Mock / 모의투자(Paper) / 실전(Live) 모드 분리
"""
import os
import yaml
from enum import Enum
from pathlib import Path
from typing import Optional


class TradingMode(str, Enum):
    LIVE = "live"


class Config:
    _instance: Optional['Config'] = None
    _config: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._config:
            self.load()

    def load(self):
        config_dir = Path(__file__).parent.parent / "config"
        
        # Load default config
        default_path = config_dir / "default.yaml"
        if default_path.exists():
            with open(default_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}

        # Determine mode
        mode = os.environ.get("TRADING_MODE", self._config.get("app", {}).get("mode", "live"))
        
        # Load mode-specific override
        mode_path = config_dir / f"{mode}.yaml"
        if mode_path.exists():
            with open(mode_path, "r", encoding="utf-8") as f:
                override = yaml.safe_load(f) or {}
                self._deep_merge(self._config, override)

        # Override with environment variables
        self._apply_env_overrides()

    def _deep_merge(self, base: dict, override: dict):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _apply_env_overrides(self):
        """환경변수로 민감한 설정 오버라이드"""
        env_mappings = {
            "KIWOOM_LIVE_APP_KEY": ("broker", "kiwoom", "live", "app_key"),
            "KIWOOM_LIVE_APP_SECRET": ("broker", "kiwoom", "live", "app_secret"),
            "TELEGRAM_BOT_TOKEN": ("notifications", "telegram", "bot_token"),
            "TELEGRAM_CHAT_ID": ("notifications", "telegram", "chat_id"),
        }
        for env_key, config_path in env_mappings.items():
            value = os.environ.get(env_key)
            if value:
                self._set_nested(self._config, config_path, value)

    def _set_nested(self, d: dict, keys: tuple, value):
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

    @property
    def mode(self) -> TradingMode:
        return TradingMode(self._config.get("app", {}).get("mode", "live"))

    @property
    def is_live(self) -> bool:
        return True

    @property
    def is_paper(self) -> bool:
        return False

    @property
    def is_mock(self) -> bool:
        return False

    def get(self, *keys, default=None):
        """Nested key access: config.get('broker', 'kiwoom', 'live', 'app_key')"""
        d = self._config
        for key in keys:
            if isinstance(d, dict):
                d = d.get(key)
            else:
                return default
            if d is None:
                return default
        return d

    @property
    def broker_config(self) -> dict:
        broker_type = self.get("broker", "type", default="kiwoom")
        if broker_type == "kiwoom":
            return self.get("broker", "kiwoom", "live", default={})
        return {}

    @property
    def risk_config(self) -> dict:
        return self.get("risk", default={})

    @property
    def strategy_config(self) -> dict:
        return self.get("strategy", default={})

    @property
    def watchlist(self) -> list:
        return self.get("trading", "watchlist", default=[])

    def to_safe_dict(self) -> dict:
        """민감 정보 마스킹된 설정 반환 (UI 표시용)"""
        import copy
        safe = copy.deepcopy(self._config)
        # Mask secrets
        sensitive_keys = ["app_key", "app_secret", "bot_token"]
        self._mask_recursive(safe, sensitive_keys)
        return safe

    def _mask_recursive(self, d: dict, keys: list):
        for k, v in d.items():
            if isinstance(v, dict):
                self._mask_recursive(v, keys)
            elif k in keys and isinstance(v, str) and v:
                d[k] = v[:4] + "****" if len(v) > 4 else "****"


config = Config()
