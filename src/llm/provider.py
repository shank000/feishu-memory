"""LLM 抽象层 - Provider 接口 + OpenAI 兼容实现"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx


class LLMProvider(ABC):
    """LLM 提供者抽象接口"""

    @abstractmethod
    async def generate(self, prompt: str, system: str = "") -> str:
        """生成文本"""
        ...

    @abstractmethod
    async def generate_json(self, prompt: str, system: str = "", schema: Optional[dict] = None) -> dict:
        """生成 JSON 输出"""
        ...


class OpenAIProvider(LLMProvider):
    """OpenAI 兼容的 LLM Provider

    支持 OpenAI、DeepSeek、本地 vLLM 等兼容 API
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(timeout=60.0)

    async def generate(self, prompt: str, system: str = "") -> str:
        """调用 LLM 生成文本"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        for attempt in range(3):
            try:
                resp = await self._client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise

        return ""

    async def generate_json(self, prompt: str, system: str = "", schema: Optional[dict] = None) -> dict:
        """调用 LLM 生成 JSON 输出"""
        json_prompt = prompt
        if not json_prompt.endswith("请以JSON格式输出。"):
            json_prompt += "\n\n请以JSON格式输出，不要包含markdown代码块标记。"

        text = await self.generate(json_prompt, system)

        # 清理输出，提取 JSON
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试找到 JSON 对象
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            return {"error": "Failed to parse LLM output as JSON", "raw": text}


class MockLLMProvider(LLMProvider):
    """模拟 LLM - 用于 Demo 模式无 API Key 场景

    从输入 prompt 中提取关键词，生成合理的模拟输出
    """

    # 关键词到 Episode 的映射规则
    EPISODE_PATTERNS = [
        (["单体架构", "Next.js", "Go", "架构"], {"title": "采用单体架构方案", "summary": "团队讨论后决定采用单体架构：前端Next.js + 后端Go，考虑团队规模不适合微服务", "tags": ["决策"]}),
        (["分工", "负责", "李四", "王五", "赵六", "钱七"], {"title": "确认团队分工", "summary": "李四负责后端API开发，王五负责前端，赵六负责数据库和基础设施，钱七负责测试", "tags": ["待办"]}),
        (["PostgreSQL", "数据库"], {"title": "数据库选型为PostgreSQL", "summary": "赵六推荐PostgreSQL，JSON支持和扩展性更好", "tags": ["决策"]}),
        (["MySQL", "改用", "CTO"], {"title": "数据库改为MySQL", "summary": "CTO要求改用MySQL企业版，数据库从PostgreSQL变更为MySQL", "tags": ["决策"], "operation": "UPDATE"}),
        (["JWT", "认证", "RS256"], {"title": "认证方案采用JWT+RS256", "summary": "认证使用JWT，密钥算法选用RS256，赵六负责安全方案制定", "tags": ["决策"]}),
        (["REST", "API", "gRPC"], {"title": "API风格选择REST", "summary": "对外使用REST API，内部服务间后续拆分时考虑gRPC", "tags": ["决策"]}),
        (["WebSocket", "实时通知"], {"title": "实时通知采用WebSocket", "summary": "实时通知功能使用WebSocket实现，Go的goroutine处理连接", "tags": ["决策"]}),
        (["Docker Compose", "部署"], {"title": "部署方案Docker Compose", "summary": "现阶段使用Docker Compose部署，等业务量上来再考虑K8s迁移", "tags": ["决策"]}),
        (["DDD", "分层", "目录"], {"title": "后端按DDD分层", "summary": "后端目录结构按DDD分层：handler/service/repository/model", "tags": ["决策"]}),
        (["监控", "Prometheus", "Grafana"], {"title": "监控方案确定Prometheus+Grafana", "summary": "监控使用Prometheus + Grafana开源方案，避免Datadog数据出境合规问题", "tags": ["决策"]}),
        (["Playwright", "测试"], {"title": "测试框架选择Playwright", "summary": "E2E测试使用Playwright，单元测试使用Go自带testing框架", "tags": ["决策"]}),
        (["Next.js App Router"], {"title": "前端选用Next.js App Router", "summary": "考虑SEO需求和团队经验，前端使用Next.js App Router", "tags": ["决策"]}),
        (["评估", "资源", "服务器"], {"title": "赵六评估服务器资源需求", "summary": "赵六负责评估WebSocket资源需求，周四之前给方案", "tags": ["待办"]}),
        (["代码规范", "Go", "风格"], {"title": "Go代码风格规范待定", "summary": "Go代码风格规范需要统一，尚未确定具体方案", "tags": ["疑问"]}),
        (["会议结束"], {"title": "架构评审会议结束", "summary": "架构评审会议结束，确认了部署方案和目录结构", "tags": ["结论"]}),
    ]

    async def generate(self, prompt: str, system: str = "") -> str:
        """根据输入内容生成合理的模拟输出"""
        # 知识合优先判断 (必须在 Episode 之前，因为知识合并的 prompt/system 也包含 Episode 关键词)
        if "合并" in prompt or "合并" in system or "consolidat" in prompt.lower() or "知识文件" in system:
            return self._generate_knowledge(prompt)
        elif "提取" in prompt or "extract" in prompt.lower() or "Episode" in system:
            return self._generate_episodes(prompt)
        elif "回答" in prompt or "answer" in prompt.lower() or "用户问题" in prompt:
            return self._generate_answer(prompt)
        elif "摘要" in prompt or "digest" in prompt.lower():
            return self._generate_digest(prompt)
        return "模拟LLM输出"

    def _generate_episodes(self, prompt: str) -> str:
        """生成模拟 Episode 提取结果"""
        episodes = []
        seen_titles = set()

        for keywords, template in self.EPISODE_PATTERNS:
            if any(kw in prompt for kw in keywords):
                title = template["title"]
                if title not in seen_titles:
                    seen_titles.add(title)
                    ep = {
                        "title": title,
                        "summary": template["summary"],
                        "tags": template.get("tags", ["决策"]),
                        "operation": template.get("operation", "ADD"),
                        "participants": ["张三", "李四", "王五", "赵六", "钱七"][:2],
                        "source_msg_ids": [],
                        "confidence": 0.9,
                    }
                    if template.get("operation") == "UPDATE":
                        ep["supersedes"] = "previous_decision"
                    episodes.append(ep)

        if not episodes:
            episodes = [{"title": "项目讨论", "summary": "团队进行了项目相关讨论", "tags": ["结论"], "operation": "ADD", "participants": [], "source_msg_ids": [], "confidence": 0.7}]

        return json.dumps(episodes, ensure_ascii=False)

    def _generate_knowledge(self, prompt: str) -> str:
        """生成模拟知识合并结果"""
        now = "2026-04-16"
        return f"""1. 技术决策库
```markdown
# 技术决策库

> 由记忆中枢自动维护，最后更新: {now}

---

### 采用单体架构方案
**ID**: K-tech-001
**生效时间**: 2026-04-01
**更新时间**: {now}
**来源Episode**: EP-001

前端Next.js + 后端Go单体架构，考虑团队规模不适合微服务

### 数据库选型为MySQL
**ID**: K-tech-002
**生效时间**: 2026-04-04
**更新时间**: {now}
**来源Episode**: EP-002

CTO要求改用MySQL企业版，数据库从PostgreSQL变更为MySQL。原PostgreSQL决策已失效

### 认证方案JWT+RS256
**ID**: K-tech-003
**生效时间**: 2026-04-02
**更新时间**: {now}
**来源Episode**: EP-003

认证使用JWT，密钥算法RS256

### API风格REST
**ID**: K-tech-004
**生效时间**: 2026-04-02
**更新时间**: {now}

对外使用REST API

### 实时通知WebSocket
**ID**: K-tech-005
**生效时间**: 2026-04-03
**更新时间**: {now}

实时通知使用WebSocket实现

### 部署方案Docker Compose
**ID**: K-tech-006
**生效时间**: 2026-04-05
**更新时间**: {now}

现阶段Docker Compose，后续迁移K8s

### 监控方案Prometheus+Grafana
**ID**: K-tech-007
**生效时间**: 2026-04-10
**更新时间**: {now}

监控使用Prometheus + Grafana开源方案
```

2. 待跟进议题
```markdown
# 待跟进议题

> 由记忆中枢自动维护，最后更新: {now}

---

### Go代码风格规范
**ID**: K-issue-001
**状态**: 开放
**负责人**: 张三
**更新时间**: {now}

Go代码风格规范需要统一，尚未确定具体方案

### 服务器资源评估
**ID**: K-issue-002
**状态**: 已关闭
**负责人**: 赵六
**截止日期**: 2026-04-10
**更新时间**: {now}

WebSocket资源评估：4核8G服务器2台，支持5000并发
```

3. 项目规范
```markdown
# 项目规范

> 由记忆中枢自动维护，最后更新: {now}

---

### 后端目录DDD分层
**ID**: K-norm-001
**更新时间**: {now}

handler/service/repository/model

### 测试框架
**ID**: K-norm-002
**更新时间**: {now}

E2E: Playwright, 单元: Go testing, 覆盖率目标85%
```

4. 人员职责
```markdown
# 人员职责

> 由记忆中枢自动维护，最后更新: {now}

---

### 项目经理: 张三
**ID**: K-role-001
**更新时间**: {now}

项目管理、架构决策、任务分配

### 后端开发: 李四
**ID**: K-role-002
**更新时间**: {now}

后端API开发、SQL调整

### 前端开发: 王五
**ID**: K-role-003
**更新时间**: {now}

前端Next.js开发

### 基础设施: 赵六
**ID**: K-role-004
**更新时间**: {now}

数据库、基础设施、安全方案、资源评估

### 测试: 钱七
**ID**: K-role-005
**更新时间**: {now}

E2E测试、单元测试、质量保障
```"""

    def _generate_answer(self, prompt: str) -> str:
        """生成模拟问答结果"""
        if "数据库" in prompt:
            return "根据记忆库记录，项目最初选择PostgreSQL，但后续CTO要求改用MySQL企业版，当前有效的决策是使用MySQL。[来源: L3知识库-技术决策库]"
        elif "认证" in prompt:
            return "项目使用JWT + RS256认证方案，密钥算法选择RS256而非HS256以提高安全性。[来源: L3知识库-技术决策库]"
        elif "谁" in prompt and "后端" in prompt:
            return "李四负责后端API开发。[来源: L3知识库-人员职责]"
        elif "部署" in prompt:
            return "现阶段使用Docker Compose部署，后续业务量增长后考虑迁移到K8s。[来源: L3知识库-技术决策库]"
        elif "监控" in prompt:
            return "监控方案已确定为Prometheus + Grafana开源方案，避免了Datadog的数据出境合规问题。[来源: L3知识库-技术决策库]"
        elif "架构" in prompt or "技术栈" in prompt:
            return "项目采用单体架构：前端Next.js App Router + 后端Go。数据库为MySQL。[来源: L3知识库-技术决策库]"
        elif "WebSocket" in prompt:
            return "实时通知功能使用WebSocket实现，Go的goroutine处理连接。认证统一通过JWT握手验证。[来源: L2/L3]"
        elif "赵六" in prompt:
            return "赵六负责数据库、基础设施、安全方案制定和资源评估。已完成WebSocket资源评估：4核8G服务器2台。[来源: L3知识库-人员职责]"
        elif "待办" in prompt or "待跟进" in prompt:
            return "当前待跟进议题：Go代码风格规范（开放状态，负责人张三）。已关闭议题：服务器资源评估。[来源: L3知识库-待跟进议题]"
        return "根据记忆库记录，项目Alpha采用单体架构(Next.js+Go)，MySQL数据库，JWT认证，Docker Compose部署，Prometheus+Grafana监控。[来源: L3知识库]"

    def _generate_digest(self, prompt: str) -> str:
        return """### 关键决策
- 采用单体架构: Next.js + Go
- 数据库从PostgreSQL改为MySQL
- 认证方案: JWT + RS256

### 新增待办
- 赵六评估服务器资源需求

### 已完成事项
- 架构评审会议

### 待解决问题
- Go代码风格规范待定
- 监控方案待定"""

    async def generate_json(self, prompt: str, system: str = "", schema: Optional[dict] = None) -> dict:
        text = await self.generate(prompt, system)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"result": text}
