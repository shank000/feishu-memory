"""配置加载 - 支持YAML配置 + 环境变量覆盖"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml


class Settings:
    """全局配置单例"""

    _instance: Optional["Settings"] = None

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent.parent.parent / "config"
        self._settings = self._load_yaml(self.config_dir / "settings.yaml")
        self._agents = self._load_yaml(self.config_dir / "agents.yaml")
        self._feishu = self._load_yaml(self.config_dir / "feishu.yaml")
        self._resolve_env_vars(self._settings)

    @classmethod
    def get(cls, config_dir: Optional[str] = None) -> Settings:
        if cls._instance is None:
            cls._instance = cls(config_dir)
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    # ── 核心属性 ──────────────────────────────────────────

    @property
    def mode(self) -> str:
        return self._settings.get("mode", "demo")

    @property
    def is_demo(self) -> bool:
        return self.mode == "demo"

    @property
    def is_real(self) -> bool:
        return self.mode == "real"

    # ── LLM ───────────────────────────────────────────────

    @property
    def llm_provider(self) -> str:
        return self._settings.get("llm", {}).get("provider", "openai")

    @property
    def llm_model(self) -> str:
        return self._settings.get("llm", {}).get("model", "gpt-4o")

    @property
    def llm_api_key(self) -> str:
        return self._settings.get("llm", {}).get("api_key", "")

    @property
    def llm_base_url(self) -> str:
        return self._settings.get("llm", {}).get("base_url", "https://api.openai.com/v1")

    @property
    def llm_temperature(self) -> float:
        return self._settings.get("llm", {}).get("temperature", 0.3)

    @property
    def llm_max_tokens(self) -> int:
        return self._settings.get("llm", {}).get("max_tokens", 4096)

    # ── 触发阈值 ──────────────────────────────────────────

    @property
    def episode_message_threshold(self) -> int:
        return self._settings.get("triggers", {}).get("episode", {}).get("message_threshold", 20)

    @property
    def episode_meeting_end_marker(self) -> bool:
        return self._settings.get("triggers", {}).get("episode", {}).get("meeting_end_marker", True)

    @property
    def knowledge_episode_threshold(self) -> int:
        return self._settings.get("triggers", {}).get("knowledge", {}).get("episode_threshold", 10)

    @property
    def knowledge_daily_schedule(self) -> str:
        return self._settings.get("triggers", {}).get("knowledge", {}).get("daily_schedule", "02:00")

    @property
    def digest_daily_schedule(self) -> str:
        return self._settings.get("triggers", {}).get("digest", {}).get("daily_schedule", "18:00")

    @property
    def push_schedule(self) -> str:
        return self._settings.get("triggers", {}).get("push", {}).get("schedule", "10:00")

    @property
    def push_cooldown_hours(self) -> int:
        return self._settings.get("triggers", {}).get("push", {}).get("cooldown_hours", 24)

    # ── 采集器 ─────────────────────────────────────────────

    @property
    def collector_heartbeat_minutes(self) -> int:
        return self._settings.get("collector", {}).get("heartbeat_minutes", 30)

    @property
    def collector_batch_size(self) -> int:
        return self._settings.get("collector", {}).get("batch_size", 100)

    # ── 检索 ──────────────────────────────────────────────

    @property
    def retrieval_top_k(self) -> int:
        return self._settings.get("retrieval", {}).get("top_k", 5)

    @property
    def layer_weight_knowledge(self) -> float:
        return self._settings.get("retrieval", {}).get("layer_weights", {}).get("knowledge", 1.0)

    @property
    def layer_weight_episode(self) -> float:
        return self._settings.get("retrieval", {}).get("layer_weights", {}).get("episode", 0.7)

    @property
    def layer_weight_raw(self) -> float:
        return self._settings.get("retrieval", {}).get("layer_weights", {}).get("raw", 0.4)

    # ── 存储 ──────────────────────────────────────────────

    @property
    def storage_base(self) -> Path:
        return Path(__file__).parent.parent.parent

    @property
    def raw_dir(self) -> Path:
        d = self._settings.get("storage", {}).get("raw_dir", "memory_store/raw")
        return self.storage_base / d

    @property
    def episodes_dir(self) -> Path:
        d = self._settings.get("storage", {}).get("episodes_dir", "memory_store/episodes")
        return self.storage_base / d

    @property
    def knowledge_dir(self) -> Path:
        d = self._settings.get("storage", {}).get("knowledge_dir", "memory_store/knowledge")
        return self.storage_base / d

    # ── 飞书 ──────────────────────────────────────────────

    @property
    def feishu_config(self) -> dict:
        return self._feishu

    @property
    def agents_config(self) -> dict:
        return self._agents

    # ── 内部方法 ──────────────────────────────────────────

    @staticmethod
    def _load_yaml(path: Path) -> dict:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    @staticmethod
    def _resolve_env_vars(d: dict) -> None:
        """递归解析 ${ENV_VAR} 格式的环境变量引用"""
        for key, value in d.items():
            if isinstance(value, dict):
                Settings._resolve_env_vars(value)
            elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_name = value[2:-1]
                d[key] = os.environ.get(env_name, "")
