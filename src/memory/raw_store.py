"""Raw Store - Layer 1 原文存档

核心原则: 原文永久保留，绝不修改，只追加写入
按日期分目录，每天一个 JSONL 文件
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.models import Message


class RawStore:
    """Layer 1: Raw 原文存档 - 仅追加"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _day_file(self, day: str) -> Path:
        """获取某天的 JSONL 文件路径

        Args:
            day: YYYY-MM-DD 格式日期
        """
        day_dir = self.base_dir / day.replace("-", "/")
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir / f"{day}.jsonl"

    def append(self, messages: list[Message]) -> int:
        """追加写入消息到对应日期的 JSONL 文件

        Returns:
            写入的消息数量
        """
        count = 0
        for msg in messages:
            day = msg.timestamp[:10] if msg.timestamp else datetime.now().strftime("%Y-%m-%d")
            filepath = self._day_file(day)
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(msg.to_json() + "\n")
            count += 1
        return count

    def append_single(self, msg: Message) -> None:
        """追加单条消息"""
        self.append([msg])

    def read_day(self, day: str) -> list[Message]:
        """读取某天的所有消息"""
        filepath = self._day_file(day)
        if not filepath.exists():
            return []
        messages = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(Message.from_json(line))
                    except json.JSONDecodeError:
                        continue
        return messages

    def read_range(self, start_day: str, end_day: str) -> list[Message]:
        """读取日期范围内的所有消息"""
        from datetime import timedelta
        start = datetime.strptime(start_day, "%Y-%m-%d")
        end = datetime.strptime(end_day, "%Y-%m-%d")
        messages = []
        current = start
        while current <= end:
            day_str = current.strftime("%Y-%m-%d")
            messages.extend(self.read_day(day_str))
            current += timedelta(days=1)
        return messages

    def read_new_since(self, since_timestamp: str) -> list[Message]:
        """读取指定时间戳之后的所有新消息"""
        if not since_timestamp:
            return self.read_all()
        messages = []
        for day_file in sorted(self.base_dir.rglob("*.jsonl")):
            with open(day_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            msg = Message.from_json(line)
                            if msg.timestamp > since_timestamp:
                                messages.append(msg)
                        except json.JSONDecodeError:
                            continue
        return messages

    def count_new_since(self, since_timestamp: str) -> int:
        """计算指定时间戳之后的新消息数量"""
        return len(self.read_new_since(since_timestamp))

    def has_meeting_end_since(self, since_timestamp: str) -> bool:
        """检查是否有会议结束标记"""
        new_msgs = self.read_new_since(since_timestamp)
        return any(msg.is_meeting_end for msg in new_msgs)

    def read_all(self) -> list[Message]:
        """读取所有消息 (慎用)"""
        messages = []
        for day_file in sorted(self.base_dir.rglob("*.jsonl")):
            with open(day_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            messages.append(Message.from_json(line))
                        except json.JSONDecodeError:
                            continue
        return messages

    def search(self, query: str, top_k: int = 10) -> list[Message]:
        """关键词搜索 - 支持中英混合多词匹配"""
        from src.core.utils import extract_search_keywords
        keywords = extract_search_keywords(query)

        if not keywords:
            return []

        scored = []
        for msg in self.read_all():
            content_lower = msg.content.lower()
            score = sum(1 for kw in keywords if kw in content_lower)
            if score > 0:
                scored.append((score, msg))

        scored.sort(key=lambda x: -x[0])
        return [msg for _, msg in scored[:top_k]]

    def get_available_days(self) -> list[str]:
        """获取有数据的所有日期"""
        days = []
        for day_file in sorted(self.base_dir.rglob("*.jsonl")):
            # 文件名格式: YYYY-MM-DD.jsonl
            day_str = day_file.stem
            if day_str.count("-") == 2:
                days.append(day_str)
        return days

    def stats(self) -> dict:
        """统计信息"""
        days = self.get_available_days()
        total = 0
        for day in days:
            total += len(self.read_day(day))
        return {
            "total_days": len(days),
            "total_messages": total,
            "days": days,
        }