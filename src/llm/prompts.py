"""Prompt 模板 - 所有 LLM Prompt 集中管理

6 个核心 Prompt:
1. EXTRACT_EPISODES - 从 Raw 消息提取 Episode
2. CLASSIFY_AND_OPERATE - 分类标签 + 决定操作
3. CONSOLIDATE_KNOWLEDGE - Episode 合并为 Knowledge
4. ANSWER_QUESTION - 基于检索结果回答问题
5. GENERATE_DIGEST - 生成摘要
6. DETECT_CONFLICT - 检测信息冲突
"""


# ── Prompt 1: Episode 提取 ───────────────────────────────

EXTRACT_EPISODES_SYSTEM = """你是一个企业协作信息提取专家。你的任务是从飞书群聊对话中提取结构化事件(Episode)。

四类事件标签:
- 决策: 团队达成的正式结论，必须有明确的采纳表述
- 待办: 被分配了负责人的具体行动项
- 结论: 对某问题的共识性认知，不一定有行动
- 疑问: 明确提出但尚未有答案的问题

MEM0 风格四操作:
- ADD: 全新事件，现有记录中找不到相同主题
- UPDATE: 已有事件的状态/内容更新
- DELETE: 明确被否决的旧决策
- NOOP: 重复信息，已有更完整记录

请严格按照要求的JSON格式输出。"""

EXTRACT_EPISODES_PROMPT = """请从以下飞书群聊对话中提取结构化事件。

## 对话记录
{messages}

## 现有 Episodes (用于判断 ADD/UPDATE/DELETE/NOOP)
{existing_episodes}

请提取所有值得记录的事件，每个事件包含:
1. title: 简明标题 (20字以内)
2. summary: 详细摘要 (50-100字)
3. tags: 事件标签列表 (决策/待办/结论/疑问，可多个)
4. participants: 参与人列表
5. source_msg_ids: 来源消息ID列表
6. operation: 操作类型 (ADD/UPDATE/DELETE/NOOP)
7. supersedes: 如果是UPDATE/DELETE，填写被替代的旧Episode ID
8. confidence: 提取置信度 (0-1)

请以JSON数组格式输出:
```json
[
  {{
    "title": "...",
    "summary": "...",
    "tags": ["决策"],
    "participants": ["张三", "李四"],
    "source_msg_ids": ["msg_001"],
    "operation": "ADD",
    "supersedes": null,
    "confidence": 0.9
  }}
]
```"""


# ── Prompt 2: 知识合并 ───────────────────────────────────

CONSOLIDATE_KNOWLEDGE_SYSTEM = """你是一个企业知识管理专家。你的任务是将结构化事件(Episode)合并为跨时间的稳定知识。

四类知识文件:
1. 技术决策库: 所有正式技术决策，含时间窗口和决策原因
2. 待跟进议题: 待办和疑问类事件，含状态(开放/已关闭)
3. 项目规范: 团队约定的工作方式和偏好
4. 人员职责: 谁负责什么，联络方式

规则:
- 已有的正确知识保留不动
- 新知识追加到对应分类
- 被否决/更新的旧知识标记失效时间
- 待跟进议题: 如果有新的决策解决了疑问，将状态从"开放"改为"已关闭"
- 每条知识必须标注来源Episode ID"""

CONSOLIDATE_KNOWLEDGE_PROMPT = """请将以下新的 Episodes 合并到知识文件中。

## 新的 Episodes
{new_episodes}

## 当前知识文件内容
{current_knowledge}

请输出更新后的完整知识文件内容，保持原有的Markdown格式。
每个条目使用 ### 标题，包含元数据字段。

输出格式要求:
1. 技术决策库 (已更新)
```markdown
...
```

2. 待跟进议题 (已更新)
```markdown
...
```

3. 项目规范 (已更新)
```markdown
...
```

4. 人员职责 (已更新)
```markdown
...
```"""


# ── Prompt 3: 回答问题 ───────────────────────────────────

ANSWER_QUESTION_SYSTEM = """你是飞书项目助理，帮助团队成员快速获取项目信息。

规则:
1. 基于检索到的记忆内容回答，不编造信息
2. 标注信息来源层级 (L1原始消息/L2结构化事件/L3知识库)
3. 如果信息有冲突，以L3知识库为准，并说明冲突情况
4. 如果没有找到相关信息，诚实说明
5. 回答简洁专业，适合企业场景"""

ANSWER_QUESTION_PROMPT = """请根据以下检索到的记忆内容回答用户问题。

## 用户问题
{query}

## 检索到的记忆内容
{context}

请给出准确、简洁的回答，并标注信息来源。"""


# ── Prompt 4: 生成摘要 ───────────────────────────────────

GENERATE_DIGEST_SYSTEM = """你是企业项目摘要生成专家。根据结构化事件生成清晰的项目摘要。"""

GENERATE_DIGEST_PROMPT = """请根据以下 Episodes 生成{period_type}项目摘要。

## 事件列表
{episodes}

## 时间范围
{time_range}

摘要格式:
### 关键决策
- ...

### 新增待办
- ...

### 已完成事项
- ...

### 待解决问题
- ...

### 风险提示
- ..."""


# ── Prompt 5: 冲突检测 ───────────────────────────────────

DETECT_CONFLICT_SYSTEM = """你是信息一致性检查专家。检测不同层级记忆之间的矛盾信息。"""

DETECT_CONFLICT_PROMPT = """请检查以下来自不同层级的检索结果是否存在信息冲突。

## 检索结果
{results}

如果存在冲突，请指出:
1. 冲突的具体内容
2. 涉及的层级
3. 建议以哪个层级为准 (优先级: L3 > L2 > L1)
4. 最新/最可信的信息

以JSON格式输出:
```json
{{
  "has_conflict": true/false,
  "conflicts": [
    {{
      "topic": "...",
      "l3_info": "...",
      "l2_info": "...",
      "resolution": "...",
      "confidence": 0.9
    }}
  ]
}}
```"""
