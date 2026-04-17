"""Knowledge 合并器 - LLM 驱动的 Episode → Knowledge 合并"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.core.models import Episode, KnowledgeCategory
from src.llm.provider import LLMProvider
from src.llm.prompts import CONSOLIDATE_KNOWLEDGE_PROMPT, CONSOLIDATE_KNOWLEDGE_SYSTEM
from src.memory.knowledge_store import KnowledgeStore


class KnowledgeConsolidator:
    """将 Episodes 合并到 Knowledge 层"""

    def __init__(self, llm: LLMProvider, knowledge_store: KnowledgeStore):
        self.llm = llm
        self.store = knowledge_store

    async def consolidate(self, new_episodes: list[Episode]) -> dict:
        """将新的 Episodes 合并到知识文件

        Returns:
            合并结果统计 {"updated_files": [...], "items_added": N}
        """
        if not new_episodes:
            return {"updated_files": [], "items_added": 0}

        # 读取当前所有知识文件
        current_knowledge = {}
        for category in KnowledgeCategory:
            current_knowledge[category.value] = self.store.read_file(category)

        # 格式化新 Episodes
        episodes_text = self._format_episodes(new_episodes)
        knowledge_text = self._format_all_knowledge(current_knowledge)

        # 调用 LLM 合并
        prompt = CONSOLIDATE_KNOWLEDGE_PROMPT.format(
            new_episodes=episodes_text,
            current_knowledge=knowledge_text,
        )

        result = await self.llm.generate(prompt, CONSOLIDATE_KNOWLEDGE_SYSTEM)

        # 解析并写入知识文件
        return self._apply_merge_result(result, current_knowledge)

    def _format_episodes(self, episodes: list[Episode]) -> str:
        """格式化 Episodes"""
        lines = []
        for ep in episodes:
            lines.append(
                f"[{ep.ep_id}] {ep.date} | 标签: {ep.tags} | 参与人: {ep.participants}\n"
                f"标题: {ep.title}\n"
                f"摘要: {ep.summary}\n"
            )
        return "\n".join(lines)

    def _format_all_knowledge(self, knowledge: dict) -> str:
        """格式化所有知识文件"""
        parts = []
        for name, content in knowledge.items():
            parts.append(f"### {name}\n{content}\n")
        return "\n".join(parts)

    def _apply_merge_result(self, llm_output: str, original: dict) -> dict:
        """解析 LLM 输出并写入知识文件"""
        import re

        updated_files = []
        items_added = 0

        # 尝试解析 LLM 输出中的四个知识文件
        file_patterns = {
            KnowledgeCategory.TECH_DECISIONS: r"1\.\s*技术决策库.*?```markdown\n(.*?)```",
            KnowledgeCategory.FOLLOW_UP: r"2\.\s*待跟进议题.*?```markdown\n(.*?)```",
            KnowledgeCategory.PROJECT_NORMS: r"3\.\s*项目规范.*?```markdown\n(.*?)```",
            KnowledgeCategory.PERSONNEL: r"4\.\s*人员职责.*?```markdown\n(.*?)```",
        }

        for category, pattern in file_patterns.items():
            match = re.search(pattern, llm_output, re.DOTALL)
            if match:
                new_content = match.group(1).strip()
                # 计算新增条目数
                old_count = original.get(category.value, "").count("### ")
                new_count = new_content.count("### ")
                items_added += max(0, new_count - old_count)

                self.store.write_file(category, new_content)
                updated_files.append(category.value)

        # 如果正则没匹配到（LLM 输出格式不同），尝试直接整体更新
        if not updated_files:
            # 回退策略：增量追加
            items_added = self._fallback_merge(llm_output)

        return {
            "updated_files": updated_files,
            "items_added": items_added,
        }

    def _fallback_merge(self, llm_output: str) -> int:
        """回退合并策略：尝试从 LLM 输出中提取新条目"""
        from src.core.models import KnowledgeItem
        import re

        items_added = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 检测 ### 标题块
        blocks = re.split(r"\n### ", llm_output)
        for block in blocks[1:]:
            lines = block.strip().split("\n")
            if not lines:
                continue
            title = lines[0].strip()

            # 根据关键词判断分类
            category = self._guess_category(title, block)

            item = KnowledgeItem(
                k_id=f"K-{now.replace('-', '').replace(':', '').replace(' ', '-')}",
                category=category.value,
                title=title,
                content="\n".join(lines[1:]).strip(),
                last_updated=now,
            )
            self.store.append_item(item)
            items_added += 1

        return items_added

    @staticmethod
    def _guess_category(title: str, content: str) -> KnowledgeCategory:
        """根据标题和内容猜测知识分类"""
        text = (title + " " + content).lower()
        decision_keywords = ["决定", "决策", "选择", "采用", "方案", "架构"]
        issue_keywords = ["待办", "待跟进", "疑问", "待确认", "待决定"]
        norm_keywords = ["规范", "流程", "约定", "标准", "规则"]
        personnel_keywords = ["负责", "职责", "角色", "分工", "人员"]

        if any(k in text for k in decision_keywords):
            return KnowledgeCategory.TECH_DECISIONS
        elif any(k in text for k in issue_keywords):
            return KnowledgeCategory.FOLLOW_UP
        elif any(k in text for k in norm_keywords):
            return KnowledgeCategory.PROJECT_NORMS
        elif any(k in text for k in personnel_keywords):
            return KnowledgeCategory.PERSONNEL
        return KnowledgeCategory.TECH_DECISIONS
