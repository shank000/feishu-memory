"""调度器 - APScheduler 定时触发"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler

if TYPE_CHECKING:
    from src.server.app import AppState


class MemoryScheduler:
    """定时任务调度器

    任务列表:
    - 采集心跳: 每30分钟 (collector heartbeat)
    - Episode提取: 条件触发 (>20条新消息 or 会议结束)
    - Knowledge合并: 每日02:00 or Episode>10
    - 摘要生成: 每日18:00
    - 主动推送扫描: 每日10:00
    """

    def __init__(self, app_state: AppState):
        self.state = app_state
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def _setup_jobs(self) -> None:
        """设置定时任务"""
        s = self.state.settings

        # 采集心跳
        self.scheduler.add_job(
            self._collect_heartbeat,
            "interval",
            minutes=s.collector_heartbeat_minutes,
            id="collect_heartbeat",
        )

        # Episode 条件检查 (每5分钟检查一次)
        self.scheduler.add_job(
            self._check_episode_trigger,
            "interval",
            minutes=5,
            id="episode_trigger_check",
        )

        # Knowledge 每日合并
        merge_hour, merge_min = map(int, s.knowledge_daily_schedule.split(":"))
        self.scheduler.add_job(
            self._knowledge_merge,
            "cron",
            hour=merge_hour,
            minute=merge_min,
            id="knowledge_daily_merge",
        )

        # 每日摘要
        digest_hour, digest_min = map(int, s.digest_daily_schedule.split(":"))
        self.scheduler.add_job(
            self._daily_digest,
            "cron",
            hour=digest_hour,
            minute=digest_min,
            id="daily_digest",
        )

        # 主动推送扫描
        push_hour, push_min = map(int, s.push_schedule.split(":"))
        self.scheduler.add_job(
            self._push_scan,
            "cron",
            hour=push_hour,
            minute=push_min,
            id="push_scan",
        )

    def start(self) -> None:
        """启动调度器"""
        self.scheduler.start()

    def shutdown(self) -> None:
        """关闭调度器"""
        self.scheduler.shutdown(wait=False)

    # ── 定时任务实现 ──────────────────────────────────────

    async def _collect_heartbeat(self) -> None:
        """采集心跳"""
        if not self.state.collector:
            return
        since = self.state.trigger_engine.state.last_collect_time
        messages = await self.state.collector.collect_messages(since or None)
        count = self.state.raw_store.append(messages)
        now = datetime.now().isoformat()
        await self.state.collector.mark_collected(now)
        self.state.trigger_engine.mark_collected(
            now, count, any(m.is_meeting_end for m in messages)
        )

    async def _check_episode_trigger(self) -> None:
        """检查 Episode 触发条件"""
        should, reason = self.state.trigger_engine.check_message_trigger(self.state.raw_store)
        if should:
            await self._process_episodes()

    async def _process_episodes(self) -> None:
        """执行 Episode 提取"""
        since = self.state.trigger_engine.state.last_episode_process_time
        new_messages = self.state.raw_store.read_new_since(since)

        if not new_messages:
            return

        existing = self.state.episode_store.get_all_active()
        episodes = await self.state.extractor.extract(new_messages, existing)

        from src.core.operations import OperationEngine
        engine = OperationEngine(self.state.episode_store)
        for ep in episodes:
            result = engine.apply_operation(ep, existing)
            if result:
                self.state.episode_store.add(result)

        now = datetime.now().isoformat()
        self.state.trigger_engine.mark_episode_processed(now)

    async def _knowledge_merge(self) -> None:
        """执行 Knowledge 合并"""
        since = self.state.trigger_engine.state.last_knowledge_merge_time
        new_episodes = self.state.episode_store.get_new_since(since)

        if not new_episodes:
            return

        await self.state.consolidator.consolidate(new_episodes)
        now = datetime.now().isoformat()
        self.state.trigger_engine.mark_knowledge_merged(now)

    async def _daily_digest(self) -> None:
        """生成每日摘要"""
        await self.state.digest_handler.generate_daily_digest()

    async def _push_scan(self) -> None:
        """主动推送扫描"""
        messages = self.state.push_handler.check_and_push()
        # 在实际系统中，这里会通过飞书机器人发送消息
        # Demo 模式下记录到日志
        for msg in messages:
            print(f"[主动推送] {msg['title']}: {msg['content'][:100]}")
