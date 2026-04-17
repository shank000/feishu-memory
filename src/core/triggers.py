"""触发器 - 评估是否应触发 Episode 提取或 Knowledge 合并"""

from __future__ import annotations

from src.core.config import Settings
from src.core.models import TriggerState


class TriggerEngine:
    """触发条件评估引擎

    Episode 提取触发条件:
    1. Raw 层新增 > threshold 条消息
    2. 检测到会议结束标记

    Knowledge 合并触发条件:
    1. Episode 层新增 > threshold 条
    2. 定时触发 (每天凌晨)
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.state = TriggerState()

    def load_state(self, state: TriggerState) -> None:
        self.state = state

    # ── Episode 触发 ──────────────────────────────────────

    def should_trigger_episode(self, new_messages_count: int, has_meeting_end: bool) -> tuple[bool, str]:
        """评估是否应触发 Episode 提取

        Returns:
            (should_trigger, reason)
        """
        threshold = self.settings.episode_message_threshold
        meeting_marker = self.settings.episode_meeting_end_marker

        # 条件1: 消息数量超过阈值
        if new_messages_count >= threshold:
            return True, f"新增消息 {new_messages_count} 条，超过阈值 {threshold}"

        # 条件2: 会议结束标记
        if meeting_marker and has_meeting_end:
            return True, "检测到会议结束标记"

        return False, ""

    def check_message_trigger(self, raw_store=None) -> tuple[bool, str]:
        """检查 Raw Store 的新增消息数量"""
        if raw_store:
            new_count = raw_store.count_new_since(self.state.last_episode_process_time)
            meeting_end = raw_store.has_meeting_end_since(self.state.last_episode_process_time)
            return self.should_trigger_episode(new_count, meeting_end)
        return False, ""

    # ── Knowledge 触发 ────────────────────────────────────

    def should_trigger_knowledge(self, new_episodes_count: int) -> tuple[bool, str]:
        """评估是否应触发 Knowledge 合并

        Returns:
            (should_trigger, reason)
        """
        threshold = self.settings.knowledge_episode_threshold

        if new_episodes_count >= threshold:
            return True, f"新增 Episode {new_episodes_count} 条，超过阈值 {threshold}"

        return False, ""

    def check_episode_trigger(self, episode_store=None) -> tuple[bool, str]:
        """检查 Episode Store 的新增数量"""
        if episode_store:
            new_count = episode_store.count_new_since(self.state.last_knowledge_merge_time)
            return self.should_trigger_knowledge(new_count)
        return False, ""

    # ── 状态更新 ──────────────────────────────────────────

    def mark_episode_processed(self, timestamp: str) -> None:
        """标记 Episode 提取已完成"""
        self.state.last_episode_process_time = timestamp
        self.state.new_message_count_since_process = 0
        self.state.meeting_end_detected = False

    def mark_knowledge_merged(self, timestamp: str) -> None:
        """标记 Knowledge 合并已完成"""
        self.state.last_knowledge_merge_time = timestamp
        self.state.new_episode_count_since_merge = 0

    def mark_collected(self, timestamp: str, new_count: int, meeting_end: bool) -> None:
        """标记数据采集已完成"""
        self.state.last_collect_time = timestamp
        self.state.new_message_count_since_process += new_count
        if meeting_end:
            self.state.meeting_end_detected = True