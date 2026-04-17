"""结果排序器 - 按优先级排序检索结果

优先级: L3 (密度最高) > L2 (上下文) > L1 (溯源)
"""

from __future__ import annotations

from src.core.config import Settings
from src.core.models import SearchResult


class ResultRanker:
    """检索结果排序器"""

    LAYER_WEIGHTS = {3: 1.0, 2: 0.7, 1: 0.4}

    def __init__(self, settings: Settings):
        self.settings = settings
        # 允许从配置覆盖权重
        self.weights = {
            3: settings.layer_weight_knowledge,
            2: settings.layer_weight_episode,
            1: settings.layer_weight_raw,
        }

    def rank(self, results: list[SearchResult], query: str = "") -> list[SearchResult]:
        """对检索结果排序

        排序规则:
        1. 层权重 × 相关性分数
        2. 同分时 L3 > L2 > L1
        3. 同层同分时按时间倒序
        """
        for r in results:
            layer_w = self.weights.get(r.layer, 0.5)
            r.relevance_score = layer_w * r.relevance_score

        return sorted(results, key=lambda r: (
            -r.relevance_score,
            -r.layer,  # 层级高的优先
            r.timestamp,  # 时间新的优先
        ))
