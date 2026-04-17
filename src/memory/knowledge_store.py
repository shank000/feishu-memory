"""Knowledge Store - Layer 3 知识固化层

管理四个 Markdown 文件:
- 技术决策库.md
- 待跟进议题.md (含状态: 开放/已关闭)
- 项目规范.md
- 人员职责.md
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.models import KnowledgeCategory, KnowledgeItem


class KnowledgeStore:
    """Layer 3: Knowledge 知识固化层"""

    FILE_MAP = {
        KnowledgeCategory.TECH_DECISIONS: "技术决策库.md",
        KnowledgeCategory.FOLLOW_UP: "待跟进议题.md",
        KnowledgeCategory.PROJECT_NORMS: "项目规范.md",
        KnowledgeCategory.PERSONNEL: "人员职责.md",
    }

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = base_dir / "_meta.json"
        self._meta = self._load_meta()
        # 确保所有知识文件存在
        self._ensure_files()

    def _load_meta(self) -> dict:
        if self.meta_file.exists():
            with open(self.meta_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"last_merge_time": "", "item_count": {}}

    def _save_meta(self) -> None:
        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(self._meta, f, ensure_ascii=False, indent=2)

    def _ensure_files(self) -> None:
        """确保所有知识文件存在且有标准头"""
        for category, filename in self.FILE_MAP.items():
            filepath = self.base_dir / filename
            if not filepath.exists():
                header = self._file_header(category.value)
                filepath.write_text(header, encoding="utf-8")

    def _file_header(self, category_name: str) -> str:
        """标准 Markdown 文件头"""
        return f"""# {category_name}

> 由记忆中枢自动维护，最后更新: {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

"""

    def _filepath(self, category: KnowledgeCategory) -> Path:
        return self.base_dir / self.FILE_MAP[category]

    # ── 读取操作 ──────────────────────────────────────────

    def read_file(self, category: KnowledgeCategory) -> str:
        """读取整个知识文件内容"""
        filepath = self._filepath(category)
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return ""

    def get_all_items(self, category: KnowledgeCategory) -> list[KnowledgeItem]:
        """解析 Markdown 文件为 KnowledgeItem 列表"""
        content = self.read_file(category)
        items = []
        # 解析每个条目 (以 ### 开头)
        blocks = re.split(r"\n### ", content)
        for block in blocks[1:]:  # 跳过文件头
            lines = block.strip().split("\n")
            if not lines:
                continue
            title = lines[0].strip()
            metadata = {}
            content_lines = []
            meta_lines = []  # 保存元数据行的原文，用于搜索

            for line in lines[1:]:
                # 解析元数据行 - 支持 **key**: value 和 - key: value 两种格式
                meta_match = re.match(r"-\s*(.+?):\s*(.+)", line.strip())
                if not meta_match:
                    meta_match = re.match(r"\*\*(.+?)\*\*:\s*(.+)", line.strip())
                if meta_match:
                    key = meta_match.group(1).strip().rstrip(":")
                    value = meta_match.group(2).strip()
                    metadata[key] = value
                    meta_lines.append(value)  # 保存值用于搜索
                else:
                    content_lines.append(line)

            # 将元数据值也并入搜索文本
            full_content = "\n".join(content_lines + meta_lines).strip()

            item = KnowledgeItem(
                k_id=metadata.get("ID", ""),
                category=category.value,
                title=title,
                content=full_content,  # 包含元数据值，便于搜索
                status=metadata.get("状态", ""),
                valid_from=metadata.get("生效时间", metadata.get("时间", "")),
                valid_until=metadata.get("失效时间", None) or None,
                last_updated=metadata.get("更新时间", ""),
                assignee=metadata.get("负责人", None) or None,
                deadline=metadata.get("截止日期", None) or None,
                source_ep_ids=metadata.get("来源Episode", "").split(",") if metadata.get("来源Episode") else [],
            )
            items.append(item)
        return items

    def get_open_issues(self) -> list[KnowledgeItem]:
        """获取所有开放状态的待跟进议题"""
        items = self.get_all_items(KnowledgeCategory.FOLLOW_UP)
        return [item for item in items if item.status == "开放"]

    def get_closed_issues(self) -> list[KnowledgeItem]:
        """获取所有已关闭的待跟进议题"""
        items = self.get_all_items(KnowledgeCategory.FOLLOW_UP)
        return [item for item in items if item.status == "已关闭"]

    # ── 写入操作 ──────────────────────────────────────────

    def write_file(self, category: KnowledgeCategory, content: str) -> None:
        """覆写整个知识文件"""
        filepath = self._filepath(category)
        filepath.write_text(content, encoding="utf-8")
        self._meta["item_count"][category.value] = content.count("### ")
        self._meta["last_merge_time"] = datetime.now().isoformat()
        self._save_meta()

    def append_item(self, item: KnowledgeItem) -> None:
        """追加单个知识条目到对应文件"""
        category = KnowledgeCategory(item.category)
        content = self.read_file(category)
        entry = self._item_to_markdown(item)
        # 在末尾追加
        if not content.endswith("\n\n"):
            content += "\n\n"
        content += entry
        self.write_file(category, content)

    def update_item(self, k_id: str, item: KnowledgeItem) -> None:
        """更新已有知识条目"""
        category = KnowledgeCategory(item.category)
        content = self.read_file(category)
        # 找到并替换该条目
        pattern = rf"\n### .*\n(?:\*\*ID\*\*:\s*{re.escape(k_id)}.*?)(?=\n### |\Z)"
        replacement = self._item_to_markdown(item)
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        if new_content != content:
            self.write_file(category, new_content)

    def close_issue(self, k_id: str) -> None:
        """关闭待跟进议题"""
        items = self.get_all_items(KnowledgeCategory.FOLLOW_UP)
        for item in items:
            if item.k_id == k_id and item.status == "开放":
                item.status = "已关闭"
                item.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")
                self.update_item(k_id, item)
                return True
        return False

    # ── 搜索 ──────────────────────────────────────────────

    def search(self, query: str, top_k: int = 10) -> list[KnowledgeItem]:
        """跨所有知识文件搜索 - 支持中英混合多词匹配"""
        from src.core.utils import extract_search_keywords
        keywords = extract_search_keywords(query)

        if not keywords:
            return []

        scored = []
        for category in KnowledgeCategory:
            items = self.get_all_items(category)
            for item in items:
                text = (item.title + " " + item.content).lower()
                score = sum(1 for kw in keywords if kw in text)
                if score > 0:
                    scored.append((score, item))

        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored[:top_k]]

    # ── 内部方法 ──────────────────────────────────────────

    def _item_to_markdown(self, item: KnowledgeItem) -> str:
        """将 KnowledgeItem 转为 Markdown 格式"""
        lines = [f"\n### {item.title}\n"]
        lines.append(f"**ID**: {item.k_id}")

        # 根据类别添加不同元数据
        if item.category == KnowledgeCategory.FOLLOW_UP.value:
            if item.status:
                lines.append(f"**状态**: {item.status}")
            if item.assignee:
                lines.append(f"**负责人**: {item.assignee}")
            if item.deadline:
                lines.append(f"**截止日期**: {item.deadline}")

        if item.valid_from:
            lines.append(f"**生效时间**: {item.valid_from}")
        if item.valid_until:
            lines.append(f"**失效时间**: {item.valid_until}")
        lines.append(f"**更新时间**: {item.last_updated or datetime.now().strftime('%Y-%m-%d %H:%M')}")
        if item.source_ep_ids:
            lines.append(f"**来源Episode**: {','.join(item.source_ep_ids)}")

        lines.append(f"\n{item.content}\n")
        return "\n".join(lines)

    # ── 统计 ──────────────────────────────────────────────

    def stats(self) -> dict:
        stats = {}
        for category in KnowledgeCategory:
            items = self.get_all_items(category)
            stats[category.value] = {
                "total": len(items),
                "active": sum(1 for i in items if not i.valid_until),
            }
            if category == KnowledgeCategory.FOLLOW_UP:
                stats[category.value]["open"] = sum(1 for i in items if i.status == "开放")
                stats[category.value]["closed"] = sum(1 for i in items if i.status == "已关闭")
        return stats