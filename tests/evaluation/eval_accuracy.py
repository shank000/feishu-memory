"""自证评测脚本 - 8项指标评测"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class Evaluator:
    """自证评测引擎"""

    def __init__(self):
        self.datasets_dir = Path(__file__).parent / "datasets"
        self.results = {}

    def load_golden_episodes(self) -> list[dict]:
        path = self.datasets_dir / "golden_episodes.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def load_golden_queries(self) -> list[dict]:
        path = self.datasets_dir / "golden_queries.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def eval_episode_extraction(self, extracted: list[dict], golden: list[dict]) -> dict:
        """指标1: Episode 提取准确性 (Precision/Recall/F1)"""
        if not golden:
            return {"precision": 0, "recall": 0, "f1": 0, "note": "无黄金数据"}

        matched = 0
        for g in golden:
            for e in extracted:
                # 简单匹配: 关键词重叠
                keywords = g.get("source_keywords", [])
                if any(kw in e.get("title", "") or kw in e.get("summary", "") for kw in keywords):
                    matched += 1
                    break

        precision = matched / max(len(extracted), 1)
        recall = matched / max(len(golden), 1)
        f1 = 2 * precision * recall / max(precision + recall, 0.001)

        return {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "matched": matched,
            "extracted": len(extracted),
            "golden": len(golden),
        }

    def eval_tag_classification(self, extracted: list[dict], golden: list[dict]) -> dict:
        """指标2: 标签分类准确性"""
        if not golden:
            return {"accuracy": 0, "note": "无黄金数据"}

        correct = 0
        total = 0
        for g in golden:
            for e in extracted:
                keywords = g.get("source_keywords", [])
                if any(kw in e.get("title", "") for kw in keywords):
                    total += 1
                    g_tags = set(g.get("tags", []))
                    e_tags = set(e.get("tags", []))
                    if g_tags & e_tags:  # 有交集
                        correct += 1
                    break

        accuracy = correct / max(total, 1)
        return {
            "accuracy": round(accuracy, 3),
            "correct": correct,
            "total": total,
        }

    def eval_operation_correctness(self, extracted: list[dict], golden: list[dict]) -> dict:
        """指标3: 操作正确性"""
        if not golden:
            return {"accuracy": 0, "note": "无黄金数据"}

        correct = 0
        total = 0
        by_op = {}

        for g in golden:
            expected_op = g.get("operation", "ADD")
            for e in extracted:
                keywords = g.get("source_keywords", [])
                if any(kw in e.get("title", "") for kw in keywords):
                    total += 1
                    actual_op = e.get("operation", "ADD")
                    if actual_op == expected_op:
                        correct += 1
                    by_op[expected_op] = by_op.get(expected_op, {"correct": 0, "total": 0})
                    by_op[expected_op]["total"] += 1
                    if actual_op == expected_op:
                        by_op[expected_op]["correct"] += 1
                    break

        accuracy = correct / max(total, 1)
        return {
            "accuracy": round(accuracy, 3),
            "correct": correct,
            "total": total,
            "by_operation": by_op,
        }

    def eval_knowledge_quality(self, knowledge_content: str, golden_episodes: list[dict]) -> dict:
        """指标4: 知识合并质量 (简单关键词覆盖)"""
        if not golden_episodes or not knowledge_content:
            return {"coverage": 0, "note": "无数据"}

        covered = 0
        total_keywords = set()
        for g in golden_episodes:
            for kw in g.get("source_keywords", []):
                total_keywords.add(kw)
                if kw in knowledge_content:
                    covered += 1

        coverage = covered / max(len(total_keywords), 1)
        return {
            "coverage": round(coverage, 3),
            "covered_keywords": covered,
            "total_keywords": len(total_keywords),
        }

    def eval_retrieval_accuracy(self, query_results: list[dict]) -> dict:
        """指标5: 检索准确性 (MRR)"""
        if not query_results:
            return {"mrr": 0, "recall_at_5": 0, "note": "无查询结果"}

        mrr_sum = 0
        recall_at_5 = 0

        for qr in query_results:
            expected = qr.get("expected_answer_contains", [])
            results = qr.get("actual_results", [])

            found_relevant = False
            for rank, r in enumerate(results, 1):
                content = r.get("content", "").lower()
                if any(kw.lower() in content for kw in expected):
                    mrr_sum += 1.0 / rank
                    found_relevant = True
                    break

            # Recall@5
            top5 = results[:5]
            found_in_top5 = any(
                any(kw.lower() in r.get("content", "").lower() for kw in expected)
                for r in top5
            )
            if found_in_top5:
                recall_at_5 += 1

        n = max(len(query_results), 1)
        return {
            "mrr": round(mrr_sum / n, 3),
            "recall_at_5": round(recall_at_5 / n, 3),
            "queries_tested": len(query_results),
        }

    def eval_conflict_resolution(self, query_results: list[dict]) -> dict:
        """指标6: 冲突解决准确性"""
        conflict_queries = [q for q in query_results if q.get("should_resolve_conflict")]
        if not conflict_queries:
            return {"accuracy": 1.0, "note": "无冲突场景"}

        correct = 0
        for q in conflict_queries:
            expected = q.get("expected_answer_contains", [])
            actual_answer = q.get("actual_answer", "").lower()
            if any(kw.lower() in actual_answer for kw in expected):
                correct += 1

        return {
            "accuracy": round(correct / max(len(conflict_queries), 1), 3),
            "conflict_scenarios": len(conflict_queries),
            "correctly_resolved": correct,
        }

    def eval_push_timeliness(self, push_messages: list[dict], open_issues: list[dict]) -> dict:
        """指标7: 主动推送时效性"""
        if not open_issues:
            return {"coverage": 1.0, "note": "无开放议题"}

        pushed_ids = {p.get("k_id") for p in push_messages}
        open_ids = {i.get("k_id") for i in open_issues}
        covered = len(pushed_ids & open_ids)

        return {
            "coverage": round(covered / max(len(open_ids), 1), 3),
            "open_issues": len(open_ids),
            "pushed": len(pushed_ids),
            "covered": covered,
        }

    def eval_latency(self, latencies: list[float]) -> dict:
        """指标8: 端到端延迟"""
        if not latencies:
            return {"p50": 0, "p95": 0, "note": "无延迟数据"}

        latencies.sort()
        n = len(latencies)
        p50 = latencies[n // 2]
        p95 = latencies[int(n * 0.95)] if n > 1 else latencies[0]

        return {
            "p50_ms": round(p50, 1),
            "p95_ms": round(p95, 1),
            "samples": n,
            "avg_ms": round(sum(latencies) / n, 1),
        }

    def run_full_evaluation(self) -> dict:
        """运行完整评测"""
        print("=" * 60)
        print("飞书企业级记忆引擎 - 自证评测")
        print("=" * 60)

        golden_episodes = self.load_golden_episodes()
        golden_queries = self.load_golden_queries()

        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "golden_data": {
                "episodes": len(golden_episodes),
                "queries": len(golden_queries),
            },
            "metrics": {},
        }

        # 模拟评测结果 (实际需要运行系统后填写)
        print("\n[指标1] Episode提取准确性")
        results["metrics"]["episode_extraction"] = self.eval_episode_extraction(
            [], golden_episodes  # 空列表=需运行系统后填入
        )
        print(f"  F1: {results['metrics']['episode_extraction'].get('f1', 'N/A')}")

        print("\n[指标2] 标签分类准确性")
        results["metrics"]["tag_classification"] = self.eval_tag_classification(
            [], golden_episodes
        )
        print(f"  Accuracy: {results['metrics']['tag_classification'].get('accuracy', 'N/A')}")

        print("\n[指标3] 操作正确性")
        results["metrics"]["operation_correctness"] = self.eval_operation_correctness(
            [], golden_episodes
        )
        print(f"  Accuracy: {results['metrics']['operation_correctness'].get('accuracy', 'N/A')}")

        print("\n[指标4] 知识合并质量")
        results["metrics"]["knowledge_quality"] = self.eval_knowledge_quality(
            "", golden_episodes
        )
        print(f"  Coverage: {results['metrics']['knowledge_quality'].get('coverage', 'N/A')}")

        print("\n[指标5] 检索准确性")
        results["metrics"]["retrieval_accuracy"] = self.eval_retrieval_accuracy([])
        print(f"  MRR: {results['metrics']['retrieval_accuracy'].get('mrr', 'N/A')}")

        print("\n[指标6] 冲突解决准确性")
        results["metrics"]["conflict_resolution"] = self.eval_conflict_resolution([])
        print(f"  Accuracy: {results['metrics']['conflict_resolution'].get('accuracy', 'N/A')}")

        print("\n[指标7] 主动推送时效性")
        results["metrics"]["push_timeliness"] = self.eval_push_timeliness([], [])
        print(f"  Coverage: {results['metrics']['push_timeliness'].get('coverage', 'N/A')}")

        print("\n[指标8] 端到端延迟")
        results["metrics"]["latency"] = self.eval_latency([])
        print(f"  P50: {results['metrics']['latency'].get('p50_ms', 'N/A')}ms")

        # 保存结果
        output_path = Path(__file__).parent.parent.parent / "评测报告.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n评测结果已保存到: {output_path}")

        return results


if __name__ == "__main__":
    evaluator = Evaluator()
    evaluator.run_full_evaluation()
