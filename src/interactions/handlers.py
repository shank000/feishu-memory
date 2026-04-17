"""四种交互处理器: QA / 推送 / 摘要 / 决策追踪"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from src.core.models import KnowledgeCategory, SearchResults
from src.llm.provider import LLMProvider
from src.llm.prompts import ANSWER_QUESTION_PROMPT, ANSWER_QUESTION_SYSTEM, GENERATE_DIGEST_PROMPT, GENERATE_DIGEST_SYSTEM
from src.memory.knowledge_store import KnowledgeStore
from src.retrieval.parallel_search import ParallelSearchEngine


class QAHandler:
    """被动问答处理器"""

    def __init__(self, search_engine: ParallelSearchEngine, llm: LLMProvider):
        self.search_engine = search_engine
        self.llm = llm

    async def answer(self, query: str) -> dict:
        """回答用户问题

        Returns:
            {"answer": str, "sources": list, "layers_hit": list, "latency_ms": float}
        """
        # 1. 并行检索
        search_results = await self.search_engine.search(query)

        # 2. 构建上下文
        context = self._build_context(search_results)

        # 3. LLM 生成回答
        prompt = ANSWER_QUESTION_PROMPT.format(
            query=query,
            context=context,
        )
        answer_text = await self.llm.generate(prompt, ANSWER_QUESTION_SYSTEM)

        # 4. 提取来源信息
        sources = self._extract_sources(search_results)

        return {
            "answer": answer_text,
            "sources": sources,
            "layers_hit": search_results.layers_hit,
            "latency_ms": search_results.total_latency_ms,
        }

    def _build_context(self, results: SearchResults) -> str:
        """构建 LLM 上下文"""
        parts = []
        layer_names = {1: "L1-原始消息", 2: "L2-结构化事件", 3: "L3-知识库"}
        for r in results.results:
            layer_name = layer_names.get(r.layer, f"L{r.layer}")
            parts.append(
                f"[{layer_name}] {r.title}\n{r.content}\n"
            )
        return "\n---\n".join(parts) if parts else "未找到相关记忆"

    def _extract_sources(self, results: SearchResults) -> list[dict]:
        """提取来源信息"""
        sources = []
        seen_ids = set()
        for r in results.results:
            if r.source_id not in seen_ids:
                seen_ids.add(r.source_id)
                sources.append({
                    "layer": r.layer,
                    "id": r.source_id,
                    "title": r.title,
                })
        return sources


class PushHandler:
    """主动推送处理器"""

    def __init__(self, knowledge_store: KnowledgeStore, cooldown_hours: int = 24):
        self.knowledge_store = knowledge_store
        self.cooldown_hours = cooldown_hours
        self._push_history: dict[str, str] = {}  # k_id -> last_push_time

    def check_and_push(self) -> list[dict]:
        """检查开放议题并生成推送消息

        Returns:
            需要推送的议题列表
        """
        open_issues = self.knowledge_store.get_open_issues()
        now = datetime.now()
        push_list = []

        for issue in open_issues:
            # 检查冷却时间
            last_push = self._push_history.get(issue.k_id)
            if last_push:
                last_time = datetime.fromisoformat(last_push)
                if (now - last_time).total_seconds() < self.cooldown_hours * 3600:
                    continue

            # 生成推送消息
            message = self._format_push_message(issue)
            push_list.append(message)

            # 记录推送时间
            self._push_history[issue.k_id] = now.isoformat()

        return push_list

    def _format_push_message(self, issue) -> dict:
        """格式化推送消息"""
        assignee_str = f" (负责人: {issue.assignee})" if issue.assignee else ""
        deadline_str = f"\n截止日期: {issue.deadline}" if issue.deadline else ""

        return {
            "type": "active_push",
            "title": "待跟进议题提醒",
            "content": (
                f"议题: {issue.title}{assignee_str}\n"
                f"内容: {issue.content[:200]}{deadline_str}\n"
                f"状态: {issue.status}"
            ),
            "k_id": issue.k_id,
            "category": "待跟进议题",
        }


class DigestHandler:
    """定期摘要处理器"""

    def __init__(self, llm: LLMProvider, episode_store=None):
        self.llm = llm
        self.episode_store = episode_store

    async def generate_daily_digest(self, date_str: Optional[str] = None) -> dict:
        """生成日报"""
        date_val = date_str or datetime.now().strftime("%Y-%m-%d")

        if self.episode_store:
            episodes = self.episode_store.get_by_date(date_val)
        else:
            episodes = []

        if not episodes:
            return {
                "type": "daily_digest",
                "date": date_val,
                "content": f"{date_val} 无重要事件记录",
            }

        episodes_text = "\n".join(
            f"- [{ep.tags}] {ep.title}: {ep.summary}" for ep in episodes
        )

        prompt = GENERATE_DIGEST_PROMPT.format(
            period_type="日报",
            episodes=episodes_text,
            time_range=date_val,
        )
        content = await self.llm.generate(prompt, GENERATE_DIGEST_SYSTEM)

        return {
            "type": "daily_digest",
            "date": date_val,
            "content": content,
            "episodes_count": len(episodes),
        }

    async def generate_weekly_digest(self, week_start: str, week_end: str) -> dict:
        """生成周报"""
        if self.episode_store:
            episodes = []
            from datetime import timedelta
            start = datetime.strptime(week_start, "%Y-%m-%d")
            end = datetime.strptime(week_end, "%Y-%m-%d")
            current = start
            while current <= end:
                episodes.extend(self.episode_store.get_by_date(current.strftime("%Y-%m-%d")))
                current += timedelta(days=1)
        else:
            episodes = []

        episodes_text = "\n".join(
            f"- [{ep.date}] [{ep.tags}] {ep.title}: {ep.summary}" for ep in episodes
        )

        prompt = GENERATE_DIGEST_PROMPT.format(
            period_type="周报",
            episodes=episodes_text or "本周无重要事件",
            time_range=f"{week_start} ~ {week_end}",
        )
        content = await self.llm.generate(prompt, GENERATE_DIGEST_SYSTEM)

        return {
            "type": "weekly_digest",
            "week": f"{week_start} ~ {week_end}",
            "content": content,
            "episodes_count": len(episodes),
        }


class DecisionTracker:
    """决策追踪器 - 维护决策时间线"""

    def __init__(self, episode_store=None, knowledge_store: Optional[KnowledgeStore] = None):
        self.episode_store = episode_store
        self.knowledge_store = knowledge_store

    def get_timeline(self, query: Optional[str] = None) -> list[dict]:
        """获取决策时间线"""
        decisions = []

        # 从 Episode 层获取
        if self.episode_store:
            for ep in self.episode_store.get_by_tag("决策"):
                if not ep.is_active():
                    continue
                if query and query.lower() not in ep.title.lower():
                    continue
                decisions.append({
                    "date": ep.date,
                    "title": ep.title,
                    "summary": ep.summary,
                    "participants": ep.participants,
                    "source": f"Episode {ep.ep_id}",
                    "status": "有效" if ep.is_active() else "已失效",
                })

        # 从 Knowledge 层获取
        if self.knowledge_store:
            items = self.knowledge_store.get_all_items(KnowledgeCategory.TECH_DECISIONS)
            for item in items:
                if item.valid_until:
                    continue
                if query and query.lower() not in item.title.lower():
                    continue
                decisions.append({
                    "date": item.valid_from[:10] if item.valid_from else "",
                    "title": item.title,
                    "summary": item.content[:200],
                    "source": f"Knowledge {item.k_id}",
                    "status": "有效",
                })

        # 按日期排序
        decisions.sort(key=lambda d: d.get("date", ""), reverse=True)
        return decisions

    def format_timeline(self, decisions: list[dict]) -> str:
        """格式化决策时间线为 Markdown"""
        lines = ["# 决策时间线\n"]
        for d in decisions:
            lines.append(f"## [{d['date']}] {d['title']}")
            lines.append(f"- 摘要: {d['summary']}")
            if d.get("participants"):
                lines.append(f"- 参与人: {', '.join(d['participants'])}")
            lines.append(f"- 来源: {d['source']}")
            lines.append(f"- 状态: {d['status']}\n")
        return "\n".join(lines)
