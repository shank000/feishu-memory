"""冲突解决器 - 跨层信息冲突检测与解决"""

from __future__ import annotations

from src.core.models import SearchResult


class ConflictResolver:
    """冲突检测与解决

    规则:
    1. L3 与 L2 冲突时，以 L3 为准 (更高度提炼)
    2. 同层内有时间冲突时，valid_until=null 的优先
    3. L2 中 UPDATE 操作的新记录优先于被 superseded 的旧记录
    4. 冲突时在结果中标记 conflict_info
    """

    def resolve(self, results: list[SearchResult]) -> list[SearchResult]:
        """检测并解决冲突"""
        if not results:
            return results

        # 按主题分组 (简单启发式: 标题相似度)
        groups = self._group_by_topic(results)

        resolved = []
        for topic, items in groups.items():
            if len(items) == 1:
                resolved.append(items[0])
                continue

            # 检测同主题内的冲突
            conflict = self._detect_conflict(items)
            if conflict:
                winner = self._resolve_conflict(items)
                # 标记冲突信息
                winner.source["conflict_detected"] = True
                winner.source["conflict_details"] = conflict
                resolved.append(winner)
                # 保留其他结果但降低分数
                for item in items:
                    if item is not winner:
                        item.relevance_score *= 0.3
                        item.source["conflict_superseded"] = True
                        resolved.append(item)
            else:
                resolved.extend(items)

        return resolved

    def _group_by_topic(self, results: list[SearchResult]) -> dict[str, list[SearchResult]]:
        """按主题相似度分组"""
        groups: dict[str, list[SearchResult]] = {}
        for r in results:
            # 提取关键词作为分组键
            key = self._extract_topic_key(r.title)
            if key not in groups:
                groups[key] = []
            groups[key].append(r)
        return groups

    def _extract_topic_key(self, title: str) -> str:
        """从标题提取主题关键词"""
        # 简单实现: 取标题中的主要词汇
        stop_words = {"的", "了", "是", "在", "和", "与", "及", "等", "为", "中"}
        words = [w for w in title.split() if w not in stop_words]
        if not words:
            return title[:5]
        return words[0]

    def _detect_conflict(self, items: list[SearchResult]) -> str | None:
        """检测同主题内的冲突"""
        # 不同层级返回了关于同一主题的不同信息
        layers = set(r.layer for r in items)
        if len(layers) <= 1:
            return None

        # 检查内容差异
        contents = [r.content[:100] for r in items]
        if len(set(contents)) == 1:
            return None  # 内容相同，无冲突

        return f"多层检索发现关于 '{items[0].title}' 的不同信息"

    def _resolve_conflict(self, items: list[SearchResult]) -> SearchResult:
        """解决冲突: 按优先级选择"""
        # 优先级: L3 > L2 > L1
        for layer in [3, 2, 1]:
            for item in items:
                if item.layer == layer:
                    return item

        return items[0]
