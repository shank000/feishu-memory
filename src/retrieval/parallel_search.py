"""并行检索 - 三层并发搜索"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from src.core.config import Settings
from src.core.models import SearchResult, SearchResults
from src.memory.episode_store import EpisodeStore
from src.memory.knowledge_store import KnowledgeStore
from src.memory.raw_store import RawStore
from src.retrieval.ranker import ResultRanker
from src.retrieval.conflict_resolver import ConflictResolver


class ParallelSearchEngine:
    """三层并行检索引擎

    用户提问后，同时向三层发出检索请求，不串行等待。
    三层结果合并后按优先级排序。
    """

    def __init__(
        self,
        raw_store: RawStore,
        episode_store: EpisodeStore,
        knowledge_store: KnowledgeStore,
        settings: Settings,
    ):
        self.raw_store = raw_store
        self.episode_store = episode_store
        self.knowledge_store = knowledge_store
        self.settings = settings
        self.ranker = ResultRanker(settings)
        self.resolver = ConflictResolver()

    async def search(self, query: str, top_k: Optional[int] = None) -> SearchResults:
        """并行检索三层记忆

        Args:
            query: 用户查询
            top_k: 每层最大返回数

        Returns:
            合并后的检索结果
        """
        start_time = time.time()
        k = top_k or self.settings.retrieval_top_k

        # 并行搜索三层
        l1_task = self._search_raw(query, k)
        l2_task = self._search_episodes(query, k)
        l3_task = self._search_knowledge(query, k)

        l1_results, l2_results, l3_results = await asyncio.gather(
            l1_task, l2_task, l3_task
        )

        # 合并结果
        all_results = l1_results + l2_results + l3_results

        # 排序
        ranked = self.ranker.rank(all_results, query)

        # 冲突检测与解决
        resolved = self.resolver.resolve(ranked)

        # 确定命中的层级
        layers_hit = list(set(r.layer for r in resolved))

        latency = (time.time() - start_time) * 1000

        return SearchResults(
            query=query,
            results=resolved[:k * 2],  # 返回更多结果供上层选择
            layers_hit=sorted(layers_hit),
            total_latency_ms=latency,
        )

    async def _search_raw(self, query: str, top_k: int) -> list[SearchResult]:
        """搜索 L1 Raw 层"""
        results = []
        try:
            messages = self.raw_store.search(query, top_k)
            for msg in messages:
                results.append(SearchResult(
                    layer=1,
                    source_id=msg.msg_id,
                    title=f"{msg.sender_name} 的消息",
                    content=msg.content[:500],
                    relevance_score=0.5,  # 关键词匹配基础分
                    source={"sender": msg.sender_name, "time": msg.timestamp, "chat_id": msg.chat_id},
                    timestamp=msg.timestamp,
                ))
        except Exception as e:
            print(f"L1 search error: {e}")
        return results

    async def _search_episodes(self, query: str, top_k: int) -> list[SearchResult]:
        """搜索 L2 Episode 层"""
        results = []
        try:
            episodes = self.episode_store.search(query, top_k, only_active=True)
            for ep in episodes:
                results.append(SearchResult(
                    layer=2,
                    source_id=ep.ep_id,
                    title=ep.title,
                    content=ep.summary,
                    relevance_score=0.7,
                    source={
                        "tags": ep.tags,
                        "participants": ep.participants,
                        "date": ep.date,
                        "operation": ep.operation,
                    },
                    timestamp=ep.valid_from,
                ))
        except Exception as e:
            print(f"L2 search error: {e}")
        return results

    async def _search_knowledge(self, query: str, top_k: int) -> list[SearchResult]:
        """搜索 L3 Knowledge 层"""
        results = []
        try:
            items = self.knowledge_store.search(query, top_k)
            for item in items:
                results.append(SearchResult(
                    layer=3,
                    source_id=item.k_id,
                    title=item.title,
                    content=item.content[:500],
                    relevance_score=0.9,
                    source={
                        "category": item.category,
                        "status": item.status,
                        "source_ep_ids": item.source_ep_ids,
                    },
                    timestamp=item.last_updated,
                ))
        except Exception as e:
            print(f"L3 search error: {e}")
        return results
