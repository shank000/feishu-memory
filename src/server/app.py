"""FastAPI 主应用 - 将所有模块组装在一起"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.core.config import Settings
from src.core.models import TriggerState
from src.core.triggers import TriggerEngine
from src.collectors.collectors import SimCollector, LarkCollector, BaseCollector
from src.llm.provider import LLMProvider, OpenAIProvider, MockLLMProvider
from src.memory.episode_store import EpisodeStore
from src.memory.extractor import EpisodeExtractor
from src.memory.knowledge_store import KnowledgeStore
from src.memory.consolidator import KnowledgeConsolidator
from src.memory.raw_store import RawStore
from src.retrieval.parallel_search import ParallelSearchEngine
from src.interactions.handlers import QAHandler, PushHandler, DigestHandler, DecisionTracker
from src.server.scheduler import MemoryScheduler


# ── 全局组件 ──────────────────────────────────────────────

class AppState:
    """应用共享状态"""

    def __init__(self):
        self.settings: Optional[Settings] = None
        self.raw_store: Optional[RawStore] = None
        self.episode_store: Optional[EpisodeStore] = None
        self.knowledge_store: Optional[KnowledgeStore] = None
        self.llm: Optional[LLMProvider] = None
        self.collector: Optional[BaseCollector] = None
        self.extractor: Optional[EpisodeExtractor] = None
        self.consolidator: Optional[KnowledgeConsolidator] = None
        self.search_engine: Optional[ParallelSearchEngine] = None
        self.qa_handler: Optional[QAHandler] = None
        self.push_handler: Optional[PushHandler] = None
        self.digest_handler: Optional[DigestHandler] = None
        self.decision_tracker: Optional[DecisionTracker] = None
        self.trigger_engine: Optional[TriggerEngine] = None
        self.scheduler: Optional[MemoryScheduler] = None


state = AppState()


def create_app(config_dir: Optional[str] = None) -> FastAPI:
    """创建 FastAPI 应用"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """应用生命周期: 启动与关闭"""
        # 初始化
        init_components(config_dir)
        # 将状态挂载到 FastAPI app.state 上，供路由访问
        app.state.memory_state = state
        yield
        # 清理
        if state.scheduler:
            state.scheduler.shutdown()

    app = FastAPI(
        title="飞书企业级记忆引擎",
        description="基于三层记忆架构的企业协作记忆系统",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    from src.server.routes_api import router as api_router
    app.include_router(api_router, prefix="/api")

    # 静态文件 (Demo UI)
    ui_path = Path(__file__).parent.parent.parent / "demo" / "demo_ui"
    if ui_path.exists():
        app.mount("/demo", StaticFiles(directory=str(ui_path), html=True), name="demo_ui")

    return app


def init_components(config_dir: Optional[str] = None) -> None:
    """初始化所有组件"""
    # 配置
    state.settings = Settings.get(config_dir)
    s = state.settings

    # 存储
    state.raw_store = RawStore(s.raw_dir)
    state.episode_store = EpisodeStore(s.episodes_dir)
    state.knowledge_store = KnowledgeStore(s.knowledge_dir)

    # LLM
    if s.is_demo and not s.llm_api_key:
        state.llm = MockLLMProvider()
    else:
        state.llm = OpenAIProvider(
            api_key=s.llm_api_key,
            model=s.llm_model,
            base_url=s.llm_base_url,
            temperature=s.llm_temperature,
            max_tokens=s.llm_max_tokens,
        )

    # 采集器
    if s.is_demo:
        scenarios_path = Path(__file__).parent.parent.parent / "demo" / "demo_scenarios.yaml"
        state.collector = SimCollector(scenarios_path)
    else:
        state.collector = LarkCollector(s.feishu_config)

    # 处理器
    state.extractor = EpisodeExtractor(state.llm)
    state.consolidator = KnowledgeConsolidator(state.llm, state.knowledge_store)

    # 检索
    state.search_engine = ParallelSearchEngine(
        state.raw_store, state.episode_store, state.knowledge_store, s
    )

    # 交互处理器
    state.qa_handler = QAHandler(state.search_engine, state.llm)
    state.push_handler = PushHandler(state.knowledge_store, s.push_cooldown_hours)
    state.digest_handler = DigestHandler(state.llm, state.episode_store)
    state.decision_tracker = DecisionTracker(state.episode_store, state.knowledge_store)

    # 触发器
    state.trigger_engine = TriggerEngine(s)

    # 调度器
    state.scheduler = MemoryScheduler(state)


# 默认应用实例
app = create_app()
