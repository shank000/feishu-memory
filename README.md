# 飞书企业级长程协作记忆引擎

基于飞书 OpenClaw + Lark CLI 的企业级记忆系统，解决跨部门协作中智能体"失忆"、信息断层问题。

## 架构概览

**三Agent三层架构**:

```
飞书数据 → Collector → L1 Raw → Memory → L2 Episodes → L3 Knowledge → Assistant → 用户
```

- **Collector Agent (记忆采集员)**: 通过 Lark CLI 采集飞书群聊/文档/日历数据
- **Memory Agent (记忆中枢)**: LLM驱动提炼 Episodes + 合并 Knowledge
- **Assistant Agent (项目助理)**: 三层并行检索 + 四种交互

### 三层记忆架构

| 层级 | 名称 | 内容 | 触发条件 |
|------|------|------|---------|
| L1 | Raw | 原始消息 (仅追加) | 每30分钟心跳 |
| L2 | Episodes | 四标签事件+四操作 | >20条消息/会议结束 |
| L3 | Knowledge | 技术决策/待跟进/规范/职责 | >10条Episode/每日定时 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行 Demo

```bash
# 一键 Demo 流程
python demo/simulate_run.py

# 或启动 Web 服务
python -m uvicorn src.server.app:app --reload --port 8000
# 浏览器访问 http://localhost:8000/demo/
```

### 3. 配置真实模式

修改 `config/settings.yaml`:
```yaml
mode: real
llm:
  provider: openai
  api_key: sk-your-key
  model: gpt-4o
```

## 项目结构

```
code/
├── config/           # YAML配置
├── agents/           # OpenClaw Agent工作区 (SOUL.md等)
├── memory_store/     # 三层文件存储 (raw/episodes/knowledge)
├── src/              # Python核心引擎
│   ├── core/         # 数据模型+配置+操作引擎+触发器
│   ├── collectors/   # 数据采集 (Lark CLI + 模拟器)
│   ├── memory/       # 三层存储+LLM提取+合并
│   ├── retrieval/    # 并行检索+排序+冲突解决
│   ├── interactions/ # QA/推送/摘要/决策追踪
│   ├── llm/          # LLM抽象层+Prompt模板
│   └── server/       # FastAPI+调度器
├── demo/             # Demo专用 (Web UI+模拟数据)
├── tests/            # 测试+评测
├── 白皮书.md          # 记忆定义与架构白皮书
└── 评测报告.md        # 自证评测报告
```

## 四种交互模式

1. **被动问答**: 被@时检索三层记忆回答
2. **主动推送**: 待跟进议题(开放状态)定时提醒
3. **定期摘要**: 日报/周报自动生成
4. **决策追踪**: 决策时间线视图

## 交付物

| 交付物 | 文件 | 说明 |
|--------|------|------|
| 白皮书 | `白皮书.md` | 记忆定义与架构文档 |
| 可运行Demo | `demo/simulate_run.py` + Web UI | 端到端演示 |
| 评测报告 | `评测报告.md` | 8项指标自证评测 |

## 技术栈

- **语言**: Python 3.12
- **Web框架**: FastAPI + Uvicorn
- **存储**: 文件系统 (JSONL/JSON/Markdown)
- **LLM**: OpenAI兼容API (支持GPT-4o/DeepSeek等)
- **调度**: APScheduler
- **飞书**: Lark CLI + OpenClaw Agent框架

## 核心创新

1. **MEM0风格四操作引擎**: ADD/UPDATE/DELETE/NOOP 处理信息重叠与矛盾
2. **三层并行检索**: asyncio.gather并发搜索，L3>L2>L1优先级排序
3. **待跟进议题驱动主动推送**: 状态字段(开放/已关闭)触发提醒
4. **时间有效性模型**: valid_from/valid_until 精确控制信息生命周期