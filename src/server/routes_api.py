"""REST API 路由 - 查询/存储/状态端点"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


# ── 请求模型 ──────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = None

class InjectMessagesRequest(BaseModel):
    messages: list[dict]

class ProcessRequest(BaseModel):
    force: bool = False

class MergeRequest(BaseModel):
    force: bool = False


# ── 查询接口 ──────────────────────────────────────────────

@router.post("/query")
async def query_memory(req: QueryRequest, request: Request):
    """主查询接口 - 并行检索三层记忆"""
    state = request.app.state.memory_state
    if not state or not state.qa_handler:
        raise HTTPException(500, "系统未初始化")

    result = await state.qa_handler.answer(req.query)
    return result


@router.get("/search")
async def search_memory(q: str, top_k: int = 5, request: Request = None):
    """搜索记忆 (返回原始检索结果)"""
    state = request.app.state.memory_state
    if not state or not state.search_engine:
        raise HTTPException(500, "系统未初始化")

    results = await state.search_engine.search(q, top_k)
    return {
        "query": results.query,
        "layers_hit": results.layers_hit,
        "latency_ms": results.total_latency_ms,
        "results": [
            {
                "layer": r.layer,
                "source_id": r.source_id,
                "title": r.title,
                "content": r.content[:300],
                "score": r.relevance_score,
            }
            for r in results.results
        ],
    }


# ── 数据注入接口 (Demo用) ────────────────────────────────

@router.post("/collect")
async def trigger_collect(request: Request):
    """手动触发数据采集"""
    state = request.app.state.memory_state
    if not state or not state.collector:
        raise HTTPException(500, "系统未初始化")

    since = state.trigger_engine.state.last_collect_time
    messages = await state.collector.collect_messages(since or None)

    count = state.raw_store.append(messages)
    now = datetime.now().isoformat()
    await state.collector.mark_collected(now)
    state.trigger_engine.mark_collected(now, count, any(m.is_meeting_end for m in messages))

    return {"collected": count, "timestamp": now}


@router.post("/inject")
async def inject_messages(req: InjectMessagesRequest, request: Request):
    """直接注入消息 (Demo模式)"""
    state = request.app.state.memory_state
    if not state:
        raise HTTPException(500, "系统未初始化")

    from src.core.models import Message, MessageSource

    messages = []
    for m in req.messages:
        msg = Message(
            msg_id=m.get("msg_id", f"inj_{len(messages):06d}"),
            chat_id=m.get("chat_id", "oc_demo"),
            sender_id=m.get("sender_id", ""),
            sender_name=m.get("sender_name", ""),
            content=m.get("content", ""),
            msg_type=m.get("msg_type", "text"),
            timestamp=m.get("timestamp", datetime.now().isoformat()),
            source=MessageSource.GROUP_CHAT,
            is_meeting_end=m.get("is_meeting_end", False),
            collected_at=datetime.now().isoformat(),
        )
        messages.append(msg)

    count = state.raw_store.append(messages)
    return {"injected": count}


# ── 处理触发接口 ──────────────────────────────────────────

@router.post("/process/episodes")
async def process_episodes(req: ProcessRequest, request: Request):
    """手动触发 Episode 提取"""
    state = request.app.state.memory_state
    if not state or not state.extractor:
        raise HTTPException(500, "系统未初始化")

    since = state.trigger_engine.state.last_episode_process_time
    new_messages = state.raw_store.read_new_since(since)

    if not new_messages and not req.force:
        return {"triggered": False, "reason": "无新消息"}

    # 提取 Episodes
    existing = state.episode_store.get_all_active()
    episodes = await state.extractor.extract(new_messages, existing)

    # 应用操作引擎
    from src.core.operations import OperationEngine
    engine = OperationEngine(state.episode_store)
    added = []
    for ep in episodes:
        result = engine.apply_operation(ep, existing)
        if result:
            state.episode_store.add(result)
            added.append(result.ep_id)
        # DELETE 操作由 mark_superseded 处理

    now = datetime.now().isoformat()
    state.trigger_engine.mark_episode_processed(now)

    return {
        "triggered": True,
        "messages_processed": len(new_messages),
        "episodes_created": len(added),
        "episode_ids": added,
    }


@router.post("/process/knowledge")
async def process_knowledge(req: MergeRequest, request: Request):
    """手动触发 Knowledge 合并"""
    state = request.app.state.memory_state
    if not state or not state.consolidator:
        raise HTTPException(500, "系统未初始化")

    since = state.trigger_engine.state.last_knowledge_merge_time
    new_episodes = state.episode_store.get_new_since(since)

    if not new_episodes and not req.force:
        return {"triggered": False, "reason": "无新Episode"}

    result = await state.consolidator.consolidate(new_episodes)

    now = datetime.now().isoformat()
    state.trigger_engine.mark_knowledge_merged(now)

    return {
        "triggered": True,
        "episodes_processed": len(new_episodes),
        **result,
    }


# ── 交互接口 ──────────────────────────────────────────────

@router.get("/push")
async def get_push_messages(request: Request):
    """获取主动推送消息"""
    state = request.app.state.memory_state
    if not state or not state.push_handler:
        raise HTTPException(500, "系统未初始化")

    messages = state.push_handler.check_and_push()
    return {"push_messages": messages}


@router.get("/digest/daily")
async def get_daily_digest(date: Optional[str] = None, request: Request = None):
    """获取日报"""
    state = request.app.state.memory_state
    if not state or not state.digest_handler:
        raise HTTPException(500, "系统未初始化")

    result = await state.digest_handler.generate_daily_digest(date)
    return result


@router.get("/digest/weekly")
async def get_weekly_digest(week_start: str, week_end: str, request: Request = None):
    """获取周报"""
    state = request.app.state.memory_state
    if not state or not state.digest_handler:
        raise HTTPException(500, "系统未初始化")

    result = await state.digest_handler.generate_weekly_digest(week_start, week_end)
    return result


@router.get("/decisions/timeline")
async def get_decision_timeline(q: Optional[str] = None, request: Request = None):
    """获取决策时间线"""
    state = request.app.state.memory_state
    if not state or not state.decision_tracker:
        raise HTTPException(500, "系统未初始化")

    decisions = state.decision_tracker.get_timeline(q)
    return {"decisions": decisions, "count": len(decisions)}


# ── 记忆查看接口 ──────────────────────────────────────────

@router.get("/memory/raw/{date}")
async def get_raw_memory(date: str, request: Request):
    """查看 Raw 层数据"""
    state = request.app.state.memory_state
    if not state or not state.raw_store:
        raise HTTPException(500, "系统未初始化")

    messages = state.raw_store.read_day(date)
    return {
        "date": date,
        "count": len(messages),
        "messages": [
            {
                "msg_id": m.msg_id,
                "sender": m.sender_name,
                "content": m.content[:200],
                "timestamp": m.timestamp,
                "is_meeting_end": m.is_meeting_end,
            }
            for m in messages
        ],
    }


@router.get("/memory/episodes")
async def get_episodes(tag: Optional[str] = None, active_only: bool = True, request: Request = None):
    """查看 Episodes"""
    state = request.app.state.memory_state
    if not state or not state.episode_store:
        raise HTTPException(500, "系统未初始化")

    if tag:
        episodes = state.episode_store.get_by_tag(tag)
    elif active_only:
        episodes = state.episode_store.get_all_active()
    else:
        episodes = state.episode_store.get_all()

    return {
        "count": len(episodes),
        "episodes": [
            {
                "ep_id": ep.ep_id,
                "date": ep.date,
                "title": ep.title,
                "tags": ep.tags,
                "operation": ep.operation,
                "summary": ep.summary[:150],
                "is_active": ep.is_active(),
            }
            for ep in episodes
        ],
    }


@router.get("/memory/knowledge/{category}")
async def get_knowledge(category: str, request: Request):
    """查看 Knowledge 层"""
    state = request.app.state.memory_state
    if not state or not state.knowledge_store:
        raise HTTPException(500, "系统未初始化")

    from src.core.models import KnowledgeCategory
    try:
        cat = KnowledgeCategory(category)
    except ValueError:
        raise HTTPException(400, f"无效分类: {category}")

    content = state.knowledge_store.read_file(cat)
    items = state.knowledge_store.get_all_items(cat)

    return {
        "category": category,
        "content": content,
        "items_count": len(items),
    }


# ── 系统状态 ──────────────────────────────────────────────

@router.get("/status")
async def get_status(request: Request):
    """系统状态"""
    state = request.app.state.memory_state
    if not state:
        return {"status": "not_initialized"}

    raw_stats = state.raw_store.stats() if state.raw_store else {}
    ep_stats = state.episode_store.stats() if state.episode_store else {}
    kn_stats = state.knowledge_store.stats() if state.knowledge_store else {}

    return {
        "status": "running",
        "mode": state.settings.mode if state.settings else "unknown",
        "layers": {
            "raw": raw_stats,
            "episodes": ep_stats,
            "knowledge": kn_stats,
        },
        "trigger_state": state.trigger_engine.state.__dict__ if state.trigger_engine else {},
    }
