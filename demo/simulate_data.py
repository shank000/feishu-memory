"""模拟数据生成器 - 生成真实感的企业协作对话数据"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from src.core.models import Message, MessageSource


# 模拟人物
PERSONAS = {
    "张三": {"id": "ou_zhangsan", "role": "项目经理"},
    "李四": {"id": "ou_lisi", "role": "后端开发"},
    "王五": {"id": "ou_wangwu", "role": "前端开发"},
    "赵六": {"id": "ou_zhaoliu", "role": "基础设施"},
    "钱七": {"id": "ou_qianqi", "role": "测试工程师"},
}


def generate_project_messages(
    project_name: str = "Alpha",
    start_date: str = "2026-04-01",
    days: int = 14,
) -> list[Message]:
    """生成项目协作对话消息

    Args:
        project_name: 项目名称
        start_date: 开始日期
        days: 持续天数

    Returns:
        消息列表
    """
    messages = []
    base_date = datetime.strptime(start_date, "%Y-%m-%d")
    msg_counter = 0

    # Day 1: 项目启动 + 技术选型
    day1 = base_date
    day1_msgs = [
        (day1.replace(hour=9, minute=0), "张三", f"各位，项目{project_name}正式启动，我们需要先确定技术架构。大家有什么建议？"),
        (day1.replace(hour=9, minute=5), "李四", "我建议用微服务架构，Spring Cloud + Kubernetes，这样扩展性好"),
        (day1.replace(hour=9, minute=10), "王五", "考虑到团队规模和项目周期，我觉得单体架构更合适，先用Next.js做前端，Go做后端"),
        (day1.replace(hour=9, minute=15), "张三", "王五说得对，我们团队只有5个后端，微服务太重了。决定采用单体架构：前端Next.js + 后端Go"),
        (day1.replace(hour=9, minute=30), "张三", "确认分工：@李四 负责后端API开发，@王五 负责前端，@赵六 负责数据库和基础设施，@钱七 负责测试"),
        (day1.replace(hour=9, minute=35), "李四", "收到，后端API我来负责。数据库选什么？PostgreSQL还是MySQL？"),
        (day1.replace(hour=9, minute=40), "赵六", "推荐PostgreSQL，JSON支持和扩展性更好，适合我们的业务场景"),
        (day1.replace(hour=9, minute=45), "张三", "好，数据库用PostgreSQL"),
        (day1.replace(hour=10, minute=0), "钱七", "测试方面，我建议用Playwright做E2E，Go自带的testing做单元测试"),
    ]
    for ts, sender, content in day1_msgs:
        msg_counter += 1
        messages.append(Message(
            msg_id=f"msg_{msg_counter:04d}",
            chat_id=f"oc_{project_name.lower()}_core",
            sender_id=PERSONAS[sender]["id"],
            sender_name=sender,
            content=content,
            timestamp=ts.isoformat(),
            source=MessageSource.GROUP_CHAT,
            collected_at=datetime.now().isoformat(),
        ))

    # Day 2: 认证方案
    day2 = base_date + timedelta(days=1)
    day2_msgs = [
        (day2.replace(hour=10, minute=0), "李四", "关于认证方案，我们用JWT还是Session？"),
        (day2.replace(hour=10, minute=5), "王五", "JWT吧，前后端分离更方便，也支持移动端扩展"),
        (day2.replace(hour=10, minute=10), "赵六", "注意JWT的安全问题，密钥管理要做好，建议用RS256而非HS256"),
        (day2.replace(hour=10, minute=15), "张三", "同意，认证用JWT + RS256。赵六你来负责安全方案的制定"),
        (day2.replace(hour=14, minute=0), "李四", "API设计我们用REST还是gRPC？"),
        (day2.replace(hour=14, minute=5), "张三", "对外用REST，内部服务间如果后续拆分可以用gRPC，现在先用REST"),
    ]
    for ts, sender, content in day2_msgs:
        msg_counter += 1
        messages.append(Message(
            msg_id=f"msg_{msg_counter:04d}",
            chat_id=f"oc_{project_name.lower()}_core",
            sender_id=PERSONAS[sender]["id"],
            sender_name=sender,
            content=content,
            timestamp=ts.isoformat(),
            source=MessageSource.GROUP_CHAT,
            collected_at=datetime.now().isoformat(),
        ))

    # Day 3: 实时通知需求
    day3 = base_date + timedelta(days=2)
    day3_msgs = [
        (day3.replace(hour=9, minute=0), "王五", "产品经理发来了新需求，要求增加实时通知功能，这个怎么实现？"),
        (day3.replace(hour=9, minute=5), "李四", "可以用WebSocket，Go的goroutine处理起来很方便"),
        (day3.replace(hour=9, minute=10), "赵六", "WebSocket可以，但要注意连接管理和心跳机制"),
        (day3.replace(hour=9, minute=15), "张三", "实时通知用WebSocket方案。赵六，@你负责评估服务器资源需求，下周一之前给个方案"),
        (day3.replace(hour=9, minute=20), "赵六", "收到，我周四之前给出资源评估方案"),
    ]
    for ts, sender, content in day3_msgs:
        msg_counter += 1
        messages.append(Message(
            msg_id=f"msg_{msg_counter:04d}",
            chat_id=f"oc_{project_name.lower()}_core",
            sender_id=PERSONAS[sender]["id"],
            sender_name=sender,
            content=content,
            timestamp=ts.isoformat(),
            source=MessageSource.GROUP_CHAT,
            collected_at=datetime.now().isoformat(),
        ))

    # Day 4: 数据库变更 (关键冲突场景)
    day4 = base_date + timedelta(days=3)
    day4_msgs = [
        (day4.replace(hour=14, minute=0), "张三", "紧急通知：CTO要求我们改用MySQL，公司已采购MySQL企业版许可证，PostgreSQL不走了"),
        (day4.replace(hour=14, minute=5), "赵六", "啊？之前定的PostgreSQL，我已经开始搭环境了...MySQL的JSON支持不如PG"),
        (day4.replace(hour=14, minute=10), "张三", "没办法，这是上面的决定。赵六你调整一下，MySQL 8.0的JSON功能也够用了"),
        (day4.replace(hour=14, minute=15), "李四", "数据库从PostgreSQL改为MySQL，我这边API层也要调整SQL语法"),
    ]
    for ts, sender, content in day4_msgs:
        msg_counter += 1
        messages.append(Message(
            msg_id=f"msg_{msg_counter:04d}",
            chat_id=f"oc_{project_name.lower()}_core",
            sender_id=PERSONAS[sender]["id"],
            sender_name=sender,
            content=content,
            timestamp=ts.isoformat(),
            source=MessageSource.GROUP_CHAT,
            collected_at=datetime.now().isoformat(),
        ))

    # Day 5: 架构评审会议 (含会议结束标记)
    day5 = base_date + timedelta(days=4)
    day5_msgs = [
        (day5.replace(hour=10, minute=0), "张三", "今天下午3点开架构评审会议，大家准备一下"),
        (day5.replace(hour=10, minute=30), "王五", "前端框架我调研了一下，考虑到SEO需求和团队经验，还是用Next.js App Router"),
        (day5.replace(hour=11, minute=0), "李四", "后端目录结构我提议按DDD分层：handler/service/repository/model"),
        (day5.replace(hour=11, minute=30), "张三", "DDD分层同意。还有个问题：部署方案？Docker Compose还是直接K8s？"),
        (day5.replace(hour=11, minute=35), "赵六", "现阶段用Docker Compose就够了，上K8s太重，等业务量上来了再迁移"),
    ]
    for ts, sender, content in day5_msgs:
        msg_counter += 1
        is_meeting_end = False
        messages.append(Message(
            msg_id=f"msg_{msg_counter:04d}",
            chat_id=f"oc_{project_name.lower()}_core",
            sender_id=PERSONAS[sender]["id"],
            sender_name=sender,
            content=content,
            timestamp=ts.isoformat(),
            source=MessageSource.GROUP_CHAT,
            collected_at=datetime.now().isoformat(),
        ))

    # 会议结束标记
    msg_counter += 1
    messages.append(Message(
        msg_id=f"msg_{msg_counter:04d}",
        chat_id=f"oc_{project_name.lower()}_core",
        sender_id=PERSONAS["张三"]["id"],
        sender_name="张三",
        content="好，部署先用Docker Compose。今天的架构评审会议结束，谢谢大家！",
        timestamp=day5.replace(hour=15, minute=30).isoformat(),
        source=MessageSource.GROUP_CHAT,
        is_meeting_end=True,
        collected_at=datetime.now().isoformat(),
    ))

    # Day 7: 监控方案 (开放议题)
    day7 = base_date + timedelta(days=6)
    day7_msgs = [
        (day7.replace(hour=9, minute=0), "钱七", "监控方案还没定，我们需要决定用什么监控工具？Prometheus还是Datadog？"),
        (day7.replace(hour=9, minute=10), "赵六", "开源方案用Prometheus + Grafana就够了，Datadog要付费而且数据出境有合规问题"),
        (day7.replace(hour=9, minute=15), "张三", "监控工具先不急定，等赵六的WebSocket资源评估方案出来一起看"),
    ]
    for ts, sender, content in day7_msgs:
        msg_counter += 1
        messages.append(Message(
            msg_id=f"msg_{msg_counter:04d}",
            chat_id=f"oc_{project_name.lower()}_core",
            sender_id=PERSONAS[sender]["id"],
            sender_name=sender,
            content=content,
            timestamp=ts.isoformat(),
            source=MessageSource.GROUP_CHAT,
            collected_at=datetime.now().isoformat(),
        ))

    # Day 10: 监控方案确定 (关闭开放议题)
    day10 = base_date + timedelta(days=9)
    day10_msgs = [
        (day10.replace(hour=16, minute=0), "赵六", "WebSocket资源评估方案出来了：预估需要4核8G服务器2台，支持5000并发连接"),
        (day10.replace(hour=16, minute=10), "张三", "好，资源方案收到。监控方案也定了吧：用Prometheus + Grafana"),
    ]
    for ts, sender, content in day10_msgs:
        msg_counter += 1
        messages.append(Message(
            msg_id=f"msg_{msg_counter:04d}",
            chat_id=f"oc_{project_name.lower()}_core",
            sender_id=PERSONAS[sender]["id"],
            sender_name=sender,
            content=content,
            timestamp=ts.isoformat(),
            source=MessageSource.GROUP_CHAT,
            collected_at=datetime.now().isoformat(),
        ))

    # Day 14: 上线复盘 (含会议结束标记)
    day14 = base_date + timedelta(days=13)
    day14_msgs = [
        (day14.replace(hour=10, minute=0), "张三", "项目Alpha已成功上线！开个复盘会，总结一下经验教训"),
        (day14.replace(hour=10, minute=5), "李四", "最大教训是数据库中途从PostgreSQL换MySQL，浪费了2天时间"),
        (day14.replace(hour=10, minute=10), "王五", "前端方面，Next.js App Router选对了，SEO效果很好"),
        (day14.replace(hour=10, minute=15), "钱七", "测试方面，Playwright + Go testing的组合很高效，覆盖率达到了85%"),
        (day14.replace(hour=10, minute=20), "赵六", "Docker Compose部署方案验证通过，后续如果需要扩展可以平滑迁移K8s"),
    ]
    for ts, sender, content in day14_msgs:
        msg_counter += 1
        messages.append(Message(
            msg_id=f"msg_{msg_counter:04d}",
            chat_id=f"oc_{project_name.lower()}_core",
            sender_id=PERSONAS[sender]["id"],
            sender_name=sender,
            content=content,
            timestamp=ts.isoformat(),
            source=MessageSource.GROUP_CHAT,
            collected_at=datetime.now().isoformat(),
        ))

    # 复盘会议结束
    msg_counter += 1
    messages.append(Message(
        msg_id=f"msg_{msg_counter:04d}",
        chat_id=f"oc_{project_name.lower()}_core",
        sender_id=PERSONAS["张三"]["id"],
        sender_name="张三",
        content="感谢大家的辛苦付出！复盘会议到此结束",
        timestamp=day14.replace(hour=11, minute=0).isoformat(),
        source=MessageSource.GROUP_CHAT,
        is_meeting_end=True,
        collected_at=datetime.now().isoformat(),
    ))

    return messages


def save_messages_to_jsonl(messages: list[Message], output_dir: Path) -> int:
    """将消息保存为 JSONL 文件"""
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for msg in messages:
        day = msg.timestamp[:10]
        filepath = output_dir / day.replace("-", "/") / f"{day}.jsonl"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(msg.to_json() + "\n")
        count += 1
    return count


if __name__ == "__main__":
    # 生成Demo数据
    messages = generate_project_messages()
    output = Path(__file__).parent.parent / "memory_store" / "raw"
    count = save_messages_to_jsonl(messages, output)
    print(f"已生成 {count} 条消息到 {output}")
