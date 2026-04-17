"""Episode 提取器 - 两阶段 LLM 处理流水线

阶段1: 从 Raw 消息中提取候选事件
阶段2: 为每个候选分配标签并决定 ADD/UPDATE/DELETE/NOOP
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from src.core.models import Episode, Message, OpType
from src.llm.provider import LLMProvider, MockLLMProvider
from src.llm.prompts import EXTRACT_EPISODES_PROMPT, EXTRACT_EPISODES_SYSTEM


class EpisodeExtractor:
    """两阶段 Episode 提取器"""

    def __init__(self, llm: LLMProvider, confidence_threshold: float = 0.5):
        self.llm = llm
        self.confidence_threshold = confidence_threshold

    async def extract(
        self,
        messages: list[Message],
        existing_episodes: Optional[list[Episode]] = None,
        date_str: Optional[str] = None,
    ) -> list[Episode]:
        """从消息中提取 Episodes

        Args:
            messages: 新增的原始消息
            existing_episodes: 现有 Episode 列表 (用于判断操作类型)
            date_str: 日期字符串

        Returns:
            提取出的 Episode 列表
        """
        if not messages:
            return []

        # 格式化消息文本
        messages_text = self._format_messages(messages)
        episodes_text = self._format_existing_episodes(existing_episodes or [])

        # 调用 LLM 提取
        prompt = EXTRACT_EPISODES_PROMPT.format(
            messages=messages_text,
            existing_episodes=episodes_text,
        )

        result = await self.llm.generate_json(prompt, EXTRACT_EPISODES_SYSTEM)

        # 解析 LLM 输出
        episodes = self._parse_llm_output(result, date_str)

        # 过滤低置信度结果
        episodes = [ep for ep in episodes if ep.confidence >= self.confidence_threshold]

        return episodes

    def _format_messages(self, messages: list[Message]) -> str:
        """格式化消息为可读文本"""
        lines = []
        for msg in messages:
            time_str = msg.timestamp[11:16] if msg.timestamp and len(msg.timestamp) > 16 else ""
            marker = " [会议结束]" if msg.is_meeting_end else ""
            lines.append(f"[{time_str}] {msg.sender_name}: {msg.msg_id} | {msg.content}{marker}")
        return "\n".join(lines)

    def _format_existing_episodes(self, episodes: list[Episode]) -> str:
        """格式化现有 Episodes"""
        if not episodes:
            return "(暂无现有 Episode)"
        lines = []
        for ep in episodes:
            status = "有效" if ep.is_active() else f"已于 {ep.valid_until} 失效"
            lines.append(
                f"- [{ep.ep_id}] {ep.title} | 标签: {ep.tags} | 状态: {status} | 摘要: {ep.summary[:80]}"
            )
        return "\n".join(lines)

    def _parse_llm_output(self, result: dict | list, date_str: Optional[str]) -> list[Episode]:
        """解析 LLM JSON 输出为 Episode 对象"""
        episodes = []

        # 处理不同的输出格式
        if isinstance(result, dict):
            # 可能包含在某个 key 下
            items = result.get("episodes", result.get("results", [result]))
        elif isinstance(result, list):
            items = result
        else:
            return episodes

        if not isinstance(items, list):
            items = [items]

        now = datetime.now()
        date_val = date_str or now.strftime("%Y-%m-%d")

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue

            try:
                tags = item.get("tags", [])
                if isinstance(tags, str):
                    tags = [tags]

                episode = Episode(
                    ep_id="",  # 将由 EpisodeStore 生成
                    date=date_val,
                    title=item.get("title", f"未命名事件-{i+1}"),
                    summary=item.get("summary", ""),
                    tags=tags,
                    source_msg_ids=item.get("source_msg_ids", []),
                    participants=item.get("participants", []),
                    operation=item.get("operation", OpType.ADD.value),
                    supersedes=item.get("supersedes"),
                    valid_from=now.isoformat(),
                    valid_until=None,
                    confidence=float(item.get("confidence", 0.8)),
                    created_at=now.isoformat(),
                )
                episodes.append(episode)
            except (TypeError, ValueError) as e:
                print(f"Warning: Failed to parse episode item: {e}")
                continue

        return episodes
