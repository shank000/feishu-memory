"""核心数据模型 - 三层记忆架构的数据结构定义"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


# ── 枚举类型 ──────────────────────────────────────────────

class TagType(str, Enum):
    """Episode 四类事件标签"""
    DECISION = "决策"    # 团队达成的正式结论
    TODO = "待办"        # 被分配了负责人的行动项
    CONCLUSION = "结论"  # 共识性认知
    QUESTION = "疑问"    # 尚未有答案的问题


class OpType(str, Enum):
    """MEM0 风格四操作"""
    ADD = "ADD"          # 全新事件
    UPDATE = "UPDATE"    # 已有事件状态/内容更新
    DELETE = "DELETE"    # 被否决的旧决策，标记删除
    NOOP = "NOOP"        # 重复信息，跳过


class MessageSource(str, Enum):
    """消息来源"""
    GROUP_CHAT = "group_chat"
    DOC = "doc"
    CALENDAR = "calendar"
    MINUTES = "minutes"


class KnowledgeCategory(str, Enum):
    """知识层四类文件"""
    TECH_DECISIONS = "技术决策库"
    FOLLOW_UP = "待跟进议题"
    PROJECT_NORMS = "项目规范"
    PERSONNEL = "人员职责"


class IssueStatus(str, Enum):
    """待跟进议题状态"""
    OPEN = "开放"
    CLOSED = "已关闭"


# ── Layer 1: Raw Message ─────────────────────────────────

@dataclass
class Message:
    """飞书原始消息 - Layer 1"""
    msg_id: str
    chat_id: str
    sender_id: str
    sender_name: str
    content: str
    msg_type: str = "text"
    timestamp: str = ""          # ISO 8601
    parent_id: Optional[str] = None
    source: MessageSource = MessageSource.GROUP_CHAT
    source_url: Optional[str] = None  # 飞书消息链接
    is_meeting_end: bool = False  # 会议结束标记
    collected_at: str = ""       # 采集时间

    def to_json(self) -> str:
        d = asdict(self)
        d["source"] = self.source.value
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> Message:
        d = json.loads(data)
        if "source" in d and isinstance(d["source"], str):
            d["source"] = MessageSource(d["source"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Layer 2: Episode ─────────────────────────────────────

@dataclass
class Episode:
    """结构化事件 - Layer 2"""
    ep_id: str                     # EP-YYYY-MMDD-NNN
    date: str                      # YYYY-MM-DD
    title: str                     # 事件标题
    summary: str                   # LLM 生成的摘要
    tags: list[str] = field(default_factory=list)  # TagType values
    source_msg_ids: list[str] = field(default_factory=list)  # 指向 L1
    participants: list[str] = field(default_factory=list)
    operation: str = OpType.ADD.value
    supersedes: Optional[str] = None   # 被UPDATE/DELETE的旧Episode ID
    valid_from: str = ""            # ISO 8601
    valid_until: Optional[str] = None  # None=当前有效
    confidence: float = 1.0
    created_at: str = ""

    def is_active(self) -> bool:
        """当前有效 (valid_until 为 None)"""
        return self.valid_until is None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> Episode:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, data: str) -> Episode:
        return cls.from_dict(json.loads(data))


# ── Layer 3: Knowledge Item ──────────────────────────────

@dataclass
class KnowledgeItem:
    """知识条目 - Layer 3"""
    k_id: str
    category: str              # KnowledgeCategory value
    title: str
    content: str               # Markdown 内容
    source_ep_ids: list[str] = field(default_factory=list)  # 指向 L2
    status: str = ""           # IssueStatus, 仅用于待跟进议题
    valid_from: str = ""
    valid_until: Optional[str] = None
    last_updated: str = ""
    assignee: Optional[str] = None  # 负责人 (待办/议题)
    deadline: Optional[str] = None  # 截止日期

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> KnowledgeItem:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── 检索结果 ─────────────────────────────────────────────

@dataclass
class SearchResult:
    """检索结果条目"""
    layer: int                 # 1=Raw, 2=Episode, 3=Knowledge
    source_id: str             # 消息/Episode/知识 ID
    title: str
    content: str
    relevance_score: float
    source: dict = field(default_factory=dict)  # 原始数据引用
    timestamp: str = ""


@dataclass
class SearchResults:
    """三层并行检索的合并结果"""
    query: str
    results: list[SearchResult] = field(default_factory=list)
    layers_hit: list[int] = field(default_factory=list)
    total_latency_ms: float = 0.0


# ── 触发状态 ─────────────────────────────────────────────

@dataclass
class TriggerState:
    """触发器状态追踪"""
    last_collect_time: str = ""
    last_episode_process_time: str = ""
    last_knowledge_merge_time: str = ""
    new_message_count_since_process: int = 0
    new_episode_count_since_merge: int = 0
    meeting_end_detected: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> TriggerState:
        return cls(**json.loads(data))
