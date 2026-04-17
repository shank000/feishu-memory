"""Demo 端到端运行器 - 一键启动完整演示流程"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


async def run_demo():
    """运行完整的 Demo 流程"""
    from src.core.config import Settings
    from src.core.operations import OperationEngine
    from src.collectors.collectors import SimCollector
    from src.llm.provider import MockLLMProvider
    from src.memory.raw_store import RawStore
    from src.memory.episode_store import EpisodeStore
    from src.memory.knowledge_store import KnowledgeStore
    from src.memory.extractor import EpisodeExtractor
    from src.memory.consolidator import KnowledgeConsolidator
    from src.retrieval.parallel_search import ParallelSearchEngine
    from src.interactions.handlers import QAHandler, PushHandler, DigestHandler, DecisionTracker
    from demo.simulate_data import generate_project_messages, save_messages_to_jsonl

    print("=" * 60)
    print("飞书企业级记忆引擎 - Demo 运行")
    print("=" * 60)

    # 1. 初始化
    print("\n[1/7] 初始化组件...")
    settings = Settings.get()
    # 不强制覆盖 mode，使用配置文件中的值

    raw_store = RawStore(settings.raw_dir)
    episode_store = EpisodeStore(settings.episodes_dir)
    knowledge_store = KnowledgeStore(settings.knowledge_dir)

    # 根据配置选择 LLM
    if settings.is_demo or not settings.llm_api_key:
        print("   使用 MockLLM (Demo模式)")
        from src.llm.provider import MockLLMProvider
        llm = MockLLMProvider()
    else:
        print(f"   使用真实 LLM: {settings.llm_model} @ {settings.llm_base_url}")
        from src.llm.provider import OpenAIProvider
        llm = OpenAIProvider(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    # 2. 生成模拟数据
    print("[2/7] 生成模拟飞书对话数据...")
    messages = generate_project_messages("Alpha", "2026-04-01", 14)
    count = save_messages_to_jsonl(messages, settings.raw_dir)
    print(f"   已生成 {count} 条消息")

    # 3. Episode 提取
    print("[3/7] 提取 Episodes...")
    extractor = EpisodeExtractor(llm)
    all_messages = raw_store.read_all()
    existing_episodes = episode_store.get_all_active()

    episodes = await extractor.extract(all_messages, existing_episodes, "2026-04-01")
    engine = OperationEngine(episode_store)
    added_ids = []
    for ep in episodes:
        result = engine.apply_operation(ep, existing_episodes)
        if result:
            episode_store.add(result)
            added_ids.append(result.ep_id)
    print(f"   提取了 {len(added_ids)} 个 Episodes")

    # 4. Knowledge 合并
    print("[4/7] 合并 Knowledge...")
    consolidator = KnowledgeConsolidator(llm, knowledge_store)
    all_episodes = episode_store.get_all_active()
    merge_result = await consolidator.consolidate(all_episodes)
    print(f"   更新了 {len(merge_result.get('updated_files', []))} 个知识文件")

    # 5. 检索测试
    print("[5/7] 测试并行检索...")
    search_engine = ParallelSearchEngine(raw_store, episode_store, knowledge_store, settings)

    test_queries = [
        "项目用了什么数据库？",
        "认证方案是什么？",
        "谁负责后端开发？",
        "监控方案定了没有？",
    ]

    for query in test_queries:
        results = await search_engine.search(query)
        print(f"   Q: {query}")
        print(f"   A: 命中层级 {results.layers_hit}, 耗时 {results.total_latency_ms:.0f}ms")
        if results.results:
            top = results.results[0]
            print(f"   Top: [L{top.layer}] {top.title}")

    # 6. 主动推送
    print("[6/7] 检查主动推送...")
    push_handler = PushHandler(knowledge_store)
    push_messages = push_handler.check_and_push()
    print(f"   待推送: {len(push_messages)} 条")
    for pm in push_messages:
        print(f"   - {pm['title']}: {pm['content'][:60]}")

    # 7. 决策时间线
    print("[7/7] 生成决策时间线...")
    tracker = DecisionTracker(episode_store, knowledge_store)
    decisions = tracker.get_timeline()
    print(f"   共 {len(decisions)} 条决策")
    for d in decisions:
        print(f"   - [{d['date']}] {d['title']}")

    # 统计
    print("\n" + "=" * 60)
    print("系统统计")
    print("=" * 60)
    print(f"Raw 层: {raw_store.stats()}")
    print(f"Episode 层: {episode_store.stats()}")
    print(f"Knowledge 层: {knowledge_store.stats()}")

    print("\nDemo 运行完成！启动 Web 服务请运行: python -m src.server.app")
    return True


if __name__ == "__main__":
    asyncio.run(run_demo())
