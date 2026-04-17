"""数据采集器 - 抽象接口 + 模拟采集器 + Lark采集器"""

from __future__ import annotations

import json
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.core.models import Message, MessageSource


class BaseCollector(ABC):
    """采集器抽象接口"""

    @abstractmethod
    async def collect_messages(self, since: Optional[str] = None) -> list[Message]:
        """采集新消息"""
        ...

    @abstractmethod
    async def mark_collected(self, up_to: str) -> None:
        """记录采集进度"""
        ...


class SimCollector(BaseCollector):
    """模拟采集器 - 从预定义场景或随机生成数据

    用于 Demo 模式，无需真实飞书凭据
    """

    def __init__(self, scenarios_path: Optional[Path] = None):
        self.scenarios_path = scenarios_path
        self._scenarios: list[dict] = []
        self._cursor = 0
        self._last_collect_time = ""
        self._message_pool: list[Message] = []
        if scenarios_path and scenarios_path.exists():
            self._load_scenarios()

    def _load_scenarios(self) -> None:
        """加载预定义场景"""
        import yaml
        with open(self.scenarios_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._scenarios = data.get("scenarios", [])
        self._build_message_pool()

    def _build_message_pool(self) -> None:
        """将场景转换为消息池"""
        self._message_pool = []
        for scenario in self._scenarios:
            chat_id = scenario.get("chat_id", "oc_demo_001")
            for msg_data in scenario.get("messages", []):
                msg = Message(
                    msg_id=msg_data.get("msg_id", f"sim_{len(self._message_pool):06d}"),
                    chat_id=chat_id,
                    sender_id=msg_data.get("sender_id", ""),
                    sender_name=msg_data.get("sender_name", ""),
                    content=msg_data.get("content", ""),
                    msg_type=msg_data.get("msg_type", "text"),
                    timestamp=msg_data.get("timestamp", ""),
                    source=MessageSource.GROUP_CHAT,
                    is_meeting_end=msg_data.get("is_meeting_end", False),
                    collected_at=datetime.now().isoformat(),
                )
                self._message_pool.append(msg)

    async def collect_messages(self, since: Optional[str] = None) -> list[Message]:
        """返回未采集的消息"""
        if since:
            new_msgs = [m for m in self._message_pool if m.timestamp > since]
        else:
            new_msgs = self._message_pool[self._cursor:]

        self._cursor = len(self._message_pool)
        return new_msgs

    async def mark_collected(self, up_to: str) -> None:
        self._last_collect_time = up_to

    def load_from_jsonl(self, jsonl_path: Path) -> int:
        """从 JSONL 文件加载消息 (用于Demo回放)"""
        count = 0
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    msg = Message.from_json(line)
                    self._message_pool.append(msg)
                    count += 1
        return count


class LarkCollector(BaseCollector):
    """Lark CLI 采集器 - 真实模式

    通过 lark-cli 命令行工具拉取飞书数据
    """

    def __init__(self, feishu_config: dict):
        self.config = feishu_config
        self._last_collect_time = ""

    async def collect_messages(self, since: Optional[str] = None) -> list[Message]:
        """通过 Lark CLI 拉取新消息"""
        import asyncio

        messages = []
        for chat in self.config.get("monitored_chats", []):
            chat_id = chat["chat_id"]
            cmd = f"lark-cli im messages list --chat-id {chat_id}"
            if since:
                cmd += f" --start-time {since}"

            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0:
                    parsed = self._parse_lark_output(stdout.decode("utf-8"), chat_id)
                    messages.extend(parsed)
            except Exception as e:
                print(f"Lark CLI error for {chat_id}: {e}")

        return messages

    async def mark_collected(self, up_to: str) -> None:
        self._last_collect_time = up_to

    def _parse_lark_output(self, output: str, chat_id: str) -> list[Message]:
        """解析 Lark CLI 输出为 Message 对象"""
        messages = []
        try:
            data = json.loads(output)
            items = data if isinstance(data, list) else data.get("items", [])
            for item in items:
                msg = Message(
                    msg_id=item.get("message_id", ""),
                    chat_id=chat_id,
                    sender_id=item.get("sender", {}).get("id", ""),
                    sender_name=item.get("sender", {}).get("name", ""),
                    content=item.get("body", {}).get("content", ""),
                    msg_type=item.get("msg_type", "text"),
                    timestamp=item.get("create_time", ""),
                    source=MessageSource.GROUP_CHAT,
                    source_url=item.get("url"),
                    is_meeting_end=self._detect_meeting_end(item.get("body", {}).get("content", "")),
                    collected_at=datetime.now().isoformat(),
                )
                messages.append(msg)
        except json.JSONDecodeError:
            pass
        return messages

    @staticmethod
    def _detect_meeting_end(content: str) -> bool:
        """检测会议结束标记"""
        markers = ["会议结束", "meeting ended", "会议已结束", "散会", "会议纪要"]
        return any(m in content.lower() for m in [m.lower() for m in markers])
