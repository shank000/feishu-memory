"""Episode Store - Layer 2 结构化事件存储

每个 Episode 一个 JSON 文件 + 索引文件 _index.json
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.models import Episode, OpType


class EpisodeStore:
    """Layer 2: Episode 结构化事件存储"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = base_dir / "_index.json"
        self._index = self._load_index()

    # ── 索引管理 ──────────────────────────────────────────

    def _load_index(self) -> dict:
        """加载索引"""
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"episodes": {}, "next_id": 1}

    def _save_index(self) -> None:
        """保存索引"""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)

    def _generate_id(self, date_str: str) -> str:
        """生成 Episode ID: EP-YYYY-MMDD-NNN"""
        n = self._index.get("next_id", 1)
        self._index["next_id"] = n + 1
        return f"EP-{date_str}-{n:03d}"

    # ── 写入操作 ──────────────────────────────────────────

    def add(self, episode: Episode) -> Episode:
        """添加 Episode"""
        if not episode.ep_id:
            day = episode.date or datetime.now().strftime("%Y-%m-%d")
            episode.ep_id = self._generate_id(day.replace("-", ""))

        if not episode.created_at:
            episode.created_at = datetime.now().isoformat()

        # 写入 JSON 文件
        filepath = self.base_dir / f"{episode.ep_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(episode.to_dict(), f, ensure_ascii=False, indent=2)

        # 更新索引
        self._index["episodes"][episode.ep_id] = {
            "date": episode.date,
            "title": episode.title,
            "tags": episode.tags,
            "operation": episode.operation,
            "supersedes": episode.supersedes,
            "valid_from": episode.valid_from,
            "valid_until": episode.valid_until,
            "is_active": episode.is_active(),
        }
        self._save_index()
        return episode

    def add_batch(self, episodes: list[Episode]) -> list[Episode]:
        """批量添加 Episodes"""
        results = []
        for ep in episodes:
            results.append(self.add(ep))
        return results

    def mark_superseded(self, target_id: str, valid_until: str) -> None:
        """标记旧 Episode 为已过期"""
        # 更新 JSON 文件
        filepath = self.base_dir / f"{target_id}.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["valid_until"] = valid_until
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        # 更新索引
        if target_id in self._index["episodes"]:
            self._index["episodes"][target_id]["valid_until"] = valid_until
            self._index["episodes"][target_id]["is_active"] = False
            self._save_index()

    # ── 查询操作 ──────────────────────────────────────────

    def get(self, ep_id: str) -> Optional[Episode]:
        """获取单个 Episode"""
        filepath = self.base_dir / f"{ep_id}.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return Episode.from_dict(json.load(f))
        return None

    def get_all_active(self) -> list[Episode]:
        """获取所有当前有效的 Episodes"""
        episodes = []
        for ep_id, meta in self._index["episodes"].items():
            if meta.get("is_active", True):
                ep = self.get(ep_id)
                if ep:
                    episodes.append(ep)
        return episodes

    def get_all(self) -> list[Episode]:
        """获取所有 Episodes"""
        episodes = []
        for ep_id in self._index["episodes"]:
            ep = self.get(ep_id)
            if ep:
                episodes.append(ep)
        return episodes

    def get_by_date(self, date_str: str) -> list[Episode]:
        """获取某日期的 Episodes"""
        episodes = []
        for ep_id, meta in self._index["episodes"].items():
            if meta.get("date") == date_str:
                ep = self.get(ep_id)
                if ep:
                    episodes.append(ep)
        return episodes

    def get_by_tag(self, tag: str) -> list[Episode]:
        """获取某标签的 Episodes"""
        episodes = []
        for ep_id, meta in self._index["episodes"].items():
            if tag in meta.get("tags", []):
                ep = self.get(ep_id)
                if ep:
                    episodes.append(ep)
        return episodes

    def get_new_since(self, since_timestamp: str) -> list[Episode]:
        """获取指定时间戳之后的新 Episodes"""
        if not since_timestamp:
            return self.get_all_active()
        episodes = []
        for ep_id, meta in self._index["episodes"].items():
            if meta.get("valid_from", "") > since_timestamp:
                ep = self.get(ep_id)
                if ep:
                    episodes.append(ep)
        return episodes

    def count_new_since(self, since_timestamp: str) -> int:
        """计算新增数量"""
        return len(self.get_new_since(since_timestamp))

    def search(self, query: str, top_k: int = 10, only_active: bool = True) -> list[Episode]:
        """关键词搜索 - 支持中英混合多词匹配"""
        from src.core.utils import extract_search_keywords
        keywords = extract_search_keywords(query)

        if not keywords:
            return []

        pool = self.get_all_active() if only_active else self.get_all()
        scored = []
        for ep in pool:
            text = (ep.title + " " + ep.summary).lower()
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scored.append((score, ep))

        scored.sort(key=lambda x: -x[0])
        return [ep for _, ep in scored[:top_k]]

    # ── 统计 ──────────────────────────────────────────────

    def stats(self) -> dict:
        total = len(self._index["episodes"])
        active = sum(1 for m in self._index["episodes"].values() if m.get("is_active", True))
        by_tag = {}
        for meta in self._index["episodes"].values():
            for tag in meta.get("tags", []):
                by_tag[tag] = by_tag.get(tag, 0) + 1
        return {
            "total_episodes": total,
            "active_episodes": active,
            "by_tag": by_tag,
        }