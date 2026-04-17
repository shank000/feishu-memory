# 记忆采集员操作规则

## HEARTBEAT 规则

每 30 分钟触发一次采集心跳:
1. 通过 Lark CLI 拉取各群聊新消息
2. 追加写入 raw/YYYY-MM/DD.jsonl
3. 更新 _meta.json 记录采集进度
4. 检测是否有会议结束标记

## 采集协议

### 首次部署
1. 执行历史消息全量导入
2. 记录导入完成时间戳
3. 之后只做增量采集

### 增量采集
1. 从 _meta.json 读取上次采集时间戳
2. 执行 `lark-cli im messages list --chat-id {chat_id} --start-time {last_ts}`
3. 解析输出，转换为内部 Message 格式
4. 追加写入对应日期的 JSONL 文件
5. 更新 _meta.json

### 会议结束标记
以下关键词出现时标记 is_meeting_end=true:
- 会议结束 / 会议已结束 / 散会
- 会议纪要
- meeting ended

### 错误处理
- API 限流: 等待 60 秒后重试
- 网络异常: 记录错误，下次心跳补采
- 数据格式异常: 跳过该消息，记录 warning
