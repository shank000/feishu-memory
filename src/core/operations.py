"""操作引擎 - MEM0风格四操作: ADD/UPDATE/DELETE/NOOP"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.core.models import Episode, OpType


class OperationEngine:
    """执行 Episode 的四操作写入机制

    ADD:    全新事件，在现有记录中找不到相同主题
    UPDATE: 已有事件的状态/内容更新，旧版本加 superseded_by 字段
    DELETE: 明确被否决的旧决策，标记 valid_until + reason，不物理删除
    NOOP:   重复信息，已有更完整记录，跳过不写入
    """

    def __init__(self, episode_store=None):
        self.episode_store = episode_store

    def apply_operation(self, episode: Episode, existing_episodes: Optional[list[Episode]] = None) -> Optional[Episode]:
        """根据 Episode 的 operation 字段执行对应操作

        Args:
            episode: 待处理的 Episode (operation 字段已由 LLM 决定)
            existing_episodes: 现有 Episode 列表，用于 UPDATE/DELETE 时查找目标

        Returns:
            执行后的 Episode (NOOP 返回 None)
        """
        op = OpType(episode.operation)

        if op == OpType.ADD:
            return self._apply_add(episode)
        elif op == OpType.UPDATE:
            return self._apply_update(episode, existing_episodes or [])
        elif op == OpType.DELETE:
            return self._apply_delete(episode, existing_episodes or [])
        elif op == OpType.NOOP:
            return self._apply_noop(episode)

        return None

    def _apply_add(self, episode: Episode) -> Episode:
        """ADD: 创建新 Episode，valid_until=None 表示当前有效"""
        if not episode.valid_from:
            episode.valid_from = datetime.now().isoformat()
        if not episode.created_at:
            episode.created_at = datetime.now().isoformat()
        episode.valid_until = None  # 当前有效
        episode.supersedes = None
        return episode

    def _apply_update(self, episode: Episode, existing: list[Episode]) -> Episode:
        """UPDATE: 新 Episode 替代旧 Episode

        旧 Episode 设置 valid_until，新 Episode 设置 supersedes
        """
        now = datetime.now().isoformat()
        if not episode.valid_from:
            episode.valid_from = now
        if not episode.created_at:
            episode.created_at = now
        episode.valid_until = None  # 当前有效

        # 标记旧 Episode 为已过期
        if episode.supersedes:
            self._mark_superseded(episode.supersedes, existing, now)

        return episode

    def _apply_delete(self, episode: Episode, existing: list[Episode]) -> Optional[Episode]:
        """DELETE: 标记旧 Episode 为无效

        不物理删除，仅设置 valid_until
        返回 None 表示不创建新 Episode
        """
        now = datetime.now().isoformat()
        target_id = episode.supersedes
        if target_id:
            self._mark_superseded(target_id, existing, now)
        return None  # DELETE 不产生新 Episode

    def _apply_noop(self, episode: Episode) -> None:
        """NOOP: 重复信息，跳过不写入"""
        return None

    def _mark_superseded(self, target_id: str, existing: list[Episode], now_iso: str) -> None:
        """在存储中标记旧 Episode 为已过期"""
        if self.episode_store:
            # 通过 Store 更新
            self.episode_store.mark_superseded(target_id, now_iso)
        else:
            # 直接在列表中标记
            for ep in existing:
                if ep.ep_id == target_id and ep.valid_until is None:
                    ep.valid_until = now_iso
                    break


def decide_operation_with_conflict(
    new_title: str,
    new_tags: list[str],
    existing_episodes: list[Episode],
    similarity_threshold: float = 0.6,
) -> tuple[OpType, Optional[str]]:
    """基于标题相似性辅助判断操作类型 (非LLM的快速预判)

    Returns:
        (operation, supersedes_id)
    """
    new_title_lower = new_title.lower()

    for ep in existing_episodes:
        if not ep.is_active():
            continue
        ep_title_lower = ep.title.lower()

        # 简单的子串/相似度匹配
        if new_title_lower == ep_title_lower:
            return OpType.UPDATE, ep.ep_id

        # 计算简单词重叠率
        new_words = set(new_title_lower.split())
        ep_words = set(ep_title_lower.split())
        if new_words and ep_words:
            overlap = len(new_words & ep_words) / max(len(new_words | ep_words), 1)
            if overlap >= similarity_threshold:
                return OpType.UPDATE, ep.ep_id

    return OpType.ADD, None
