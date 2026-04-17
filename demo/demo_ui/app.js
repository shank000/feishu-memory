/* 飞书记忆引擎 Demo UI 交互逻辑 */

const API_BASE = '/api';
let currentLayer = 'raw';
let messagesInjected = 0;
const SCENARIOS = window.DEMO_SCENARIOS || null;

// ── 工具函数 ─────────────────────────────────────────────

async function api(method, path, body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(`${API_BASE}${path}`, opts);
    return resp.json();
}

function setLoading(el, loading) {
    if (loading) {
        el.innerHTML = '<div class="loading">处理中</div>';
    }
}

function formatTime(ts) {
    if (!ts) return '';
    return ts.substring(11, 16);
}

// ── 状态更新 ──────────────────────────────────────────────

async function updateStatus() {
    try {
        const status = await api('GET', '/status');
        document.getElementById('status-text').textContent =
            `Raw: ${status.layers?.raw?.total_messages || 0}条 | ` +
            `Episodes: ${status.layers?.episodes?.active_episodes || 0}个 | ` +
            `模式: ${status.mode || 'unknown'}`;
        document.getElementById('mode-badge').textContent =
            status.mode === 'demo' ? 'Demo Mode' : 'Real Mode';
    } catch (e) {
        console.error('Status update failed:', e);
    }
}

// ── 消息注入 ──────────────────────────────────────────────

async function injectMessages() {
    const chatEl = document.getElementById('chat-messages');
    chatEl.innerHTML = '<div class="loading">正在注入消息</div>';

    try {
        // 从内嵌场景数据注入
        const scenarios = getDemoScenarios();
        if (!scenarios || scenarios.length === 0) {
            chatEl.innerHTML = '<div class="system-msg">无可用场景数据</div>';
            return;
        }

        const result = await api('POST', '/inject', { messages: scenarios });
        messagesInjected += scenarios.length;

        // 显示注入的消息
        chatEl.innerHTML = '';
        scenarios.forEach(msg => {
            appendChatMessage(msg);
        });

        await updateStatus();
    } catch (e) {
        chatEl.innerHTML = `<div class="system-msg">注入失败: ${e.message}</div>`;
    }
}

function getDemoScenarios() {
    // 内嵌的Demo场景数据 (简化版，完整数据通过API注入)
    return [
        { sender_name: "张三", content: "各位，项目Alpha正式启动，我们需要先确定技术架构", timestamp: "2026-04-01T09:00:00" },
        { sender_name: "李四", content: "我建议用微服务架构，Spring Cloud + Kubernetes", timestamp: "2026-04-01T09:05:00" },
        { sender_name: "王五", content: "考虑到团队规模，单体架构更合适：前端Next.js + 后端Go", timestamp: "2026-04-01T09:10:00" },
        { sender_name: "张三", content: "决定采用单体架构：前端Next.js + 后端Go", timestamp: "2026-04-01T09:15:00" },
        { sender_name: "张三", content: "分工确认：李四负责后端，王五负责前端，赵六负责基础设施，钱七负责测试", timestamp: "2026-04-01T09:30:00" },
        { sender_name: "李四", content: "数据库选什么？PostgreSQL还是MySQL？", timestamp: "2026-04-01T09:35:00" },
        { sender_name: "赵六", content: "推荐PostgreSQL，JSON支持更好", timestamp: "2026-04-01T09:40:00" },
        { sender_name: "张三", content: "数据库用PostgreSQL", timestamp: "2026-04-01T09:45:00" },
        { sender_name: "张三", content: "紧急通知：CTO要求改用MySQL，公司已采购MySQL企业版许可证", timestamp: "2026-04-04T14:00:00" },
        { sender_name: "赵六", content: "之前定的PostgreSQL，MySQL的JSON支持不如PG", timestamp: "2026-04-04T14:05:00" },
        { sender_name: "张三", content: "没办法，数据库从PostgreSQL改为MySQL", timestamp: "2026-04-04T14:10:00" },
        { sender_name: "钱七", content: "监控方案还没定，Prometheus还是Datadog？", timestamp: "2026-04-07T09:00:00" },
        { sender_name: "张三", content: "监控工具先不急定，等WebSocket评估方案出来一起看", timestamp: "2026-04-07T09:15:00" },
        { sender_name: "张三", content: "好，监控用Prometheus + Grafana", timestamp: "2026-04-10T16:10:00" },
        { sender_name: "张三", content: "架构评审会议结束", timestamp: "2026-04-05T15:30:00", is_meeting_end: true },
    ];
}

function appendChatMessage(msg) {
    const chatEl = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = 'chat-msg' + (msg.is_meeting_end ? ' meeting-end' : '');
    div.innerHTML = `
        <div class="sender">${msg.sender_name}<span class="time">${formatTime(msg.timestamp)}</span></div>
        <div class="content">${msg.content}</div>
    `;
    chatEl.appendChild(div);
    chatEl.scrollTop = chatEl.scrollHeight;
}

// ── 智能问答 ──────────────────────────────────────────────

async function askQuestion(query) {
    const qaArea = document.getElementById('qa-area');

    // 显示用户问题
    const userDiv = document.createElement('div');
    userDiv.className = 'qa-msg user';
    userDiv.innerHTML = `<div class="label">用户</div><div class="content">${query}</div>`;
    qaArea.appendChild(userDiv);

    // 显示加载
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'qa-msg assistant';
    loadingDiv.innerHTML = '<div class="loading">思考中</div>';
    qaArea.appendChild(loadingDiv);
    qaArea.scrollTop = qaArea.scrollHeight;

    try {
        const result = await api('POST', '/query', { query });

        // 显示回答
        const sources = (result.sources || []).map(s => {
            const layerClass = `l${s.layer}`;
            const layerName = s.layer === 3 ? 'L3知识库' : s.layer === 2 ? 'L2事件' : 'L1原文';
            return `<span class="source-tag ${layerClass}">${layerName}: ${s.title}</span>`;
        }).join(' ');

        loadingDiv.innerHTML = `
            <div class="label">项目助理</div>
            <div class="content">${result.answer || '暂无相关记忆'}</div>
            ${sources ? `<div class="sources">来源: ${sources}</div>` : ''}
        `;
    } catch (e) {
        loadingDiv.innerHTML = `<div class="content" style="color:red">查询失败: ${e.message}</div>`;
    }

    qaArea.scrollTop = qaArea.scrollHeight;
}

// ── 记忆层查看 ────────────────────────────────────────────

async function loadLayer(layer) {
    currentLayer = layer;
    const content = document.getElementById('memory-content');

    // 更新Tab样式
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab[data-layer="${layer}"]`).classList.add('active');

    setLoading(content, true);

    try {
        if (layer === 'raw') {
            const status = await api('GET', '/status');
            const days = status.layers?.raw?.days || [];
            if (days.length === 0) {
                content.innerHTML = '<div class="system-msg">Raw层暂无数据</div>';
                return;
            }
            const dayData = await api('GET', `/memory/raw/${days[days.length - 1]}`);
            content.innerHTML = dayData.messages.map(m => `
                <div class="memory-item">
                    <div class="meta">
                        <span>${m.sender}</span>
                        <span>${m.timestamp?.substring(11,16) || ''}</span>
                        ${m.is_meeting_end ? '<span class="tag tag-decision">会议结束</span>' : ''}
                    </div>
                    <div>${m.content}</div>
                </div>
            `).join('');
        } else if (layer === 'episodes') {
            const data = await api('GET', '/memory/episodes');
            if (data.episodes.length === 0) {
                content.innerHTML = '<div class="system-msg">Episodes层暂无数据，请先触发提取</div>';
                return;
            }
            content.innerHTML = data.episodes.map(ep => `
                <div class="memory-item">
                    <div class="meta">
                        <span>${ep.ep_id}</span>
                        <span>${ep.date}</span>
                        ${ep.tags.map(t => `<span class="tag tag-${getTagClass(t)}">${t}</span>`).join('')}
                        <span class="tag tag-${ep.operation.toLowerCase()}">${ep.operation}</span>
                        ${ep.is_active ? '' : '<span style="color:red">已失效</span>'}
                    </div>
                    <div><strong>${ep.title}</strong></div>
                    <div style="color:#666;margin-top:4px">${ep.summary}</div>
                </div>
            `).join('');
        } else if (layer === 'knowledge') {
            content.innerHTML = '';
            for (const cat of ['技术决策库', '待跟进议题', '项目规范', '人员职责']) {
                try {
                    const data = await api('GET', `/memory/knowledge/${cat}`);
                    if (data.content && data.content.trim().length > 50) {
                        const section = document.createElement('div');
                        section.innerHTML = `
                            <h3 style="margin:12px 0 8px;color:var(--primary)">${cat} (${data.items_count}条)</h3>
                            <div style="white-space:pre-wrap;font-size:13px;line-height:1.6;padding:8px;background:var(--bg);border-radius:6px;max-height:300px;overflow-y:auto">${data.content}</div>
                        `;
                        content.appendChild(section);
                    }
                } catch (e) {}
            }
            if (!content.innerHTML) {
                content.innerHTML = '<div class="system-msg">Knowledge层暂无数据，请先触发合并</div>';
            }
        }
    } catch (e) {
        content.innerHTML = `<div class="system-msg">加载失败: ${e.message}</div>`;
    }
}

function getTagClass(tag) {
    const map = { '决策': 'decision', '待办': 'todo', '结论': 'conclusion', '疑问': 'question' };
    return map[tag] || 'decision';
}

// ── 操作执行 ──────────────────────────────────────────────

async function executeAction(action) {
    const qaArea = document.getElementById('qa-area');

    try {
        let result;
        switch (action) {
            case 'process-episodes':
                result = await api('POST', '/process/episodes', { force: true });
                showActionResult('Episode提取', result);
                break;
            case 'process-knowledge':
                result = await api('POST', '/process/knowledge', { force: true });
                showActionResult('Knowledge合并', result);
                break;
            case 'push':
                result = await api('GET', '/push');
                showActionResult('主动推送', result);
                break;
            case 'digest':
                result = await api('GET', '/digest/daily');
                showActionResult('每日摘要', result);
                break;
            case 'timeline':
                result = await api('GET', '/decisions/timeline');
                showActionResult('决策时间线', result);
                break;
            case 'auto-run':
                await autoRun();
                return;
        }
        loadLayer(currentLayer);
        updateStatus();
    } catch (e) {
        showActionResult('操作失败', { error: e.message });
    }
}

function showActionResult(title, result) {
    const qaArea = document.getElementById('qa-area');
    const div = document.createElement('div');
    div.className = 'qa-msg assistant';
    div.innerHTML = `
        <div class="label" style="color:var(--warning)">${title}</div>
        <div class="content"><pre>${JSON.stringify(result, null, 2)}</pre></div>
    `;
    qaArea.appendChild(div);
    qaArea.scrollTop = qaArea.scrollHeight;
}

async function autoRun() {
    const qaArea = document.getElementById('qa-area');
    const steps = [
        { name: '1. 注入消息', action: () => injectMessages() },
        { name: '2. 提取Episodes', action: () => api('POST', '/process/episodes', { force: true }) },
        { name: '3. 合并Knowledge', action: () => api('POST', '/process/knowledge', { force: true }) },
        { name: '4. 测试检索', action: () => askQuestion('项目用了什么数据库？') },
    ];

    for (const step of steps) {
        const div = document.createElement('div');
        div.className = 'qa-msg assistant';
        div.innerHTML = `<div class="label" style="color:var(--primary)">${step.name}</div><div class="loading">执行中</div>`;
        qaArea.appendChild(div);
        qaArea.scrollTop = qaArea.scrollHeight;

        try {
            await step.action();
            div.innerHTML = `<div class="label" style="color:var(--success)">${step.name} ✓</div>`;
        } catch (e) {
            div.innerHTML = `<div class="label" style="color:var(--danger)">${step.name} ✗</div><div>${e.message}</div>`;
        }
    }

    loadLayer(currentLayer);
    updateStatus();
}

// ── 事件绑定 ──────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    // 注入消息
    document.getElementById('btn-inject').addEventListener('click', injectMessages);

    // 采集
    document.getElementById('btn-collect').addEventListener('click', async () => {
        const result = await api('POST', '/collect');
        showActionResult('数据采集', result);
        updateStatus();
    });

    // 提问
    document.getElementById('btn-query').addEventListener('click', () => {
        const input = document.getElementById('qa-input');
        if (input.value.trim()) {
            askQuestion(input.value.trim());
            input.value = '';
        }
    });

    document.getElementById('qa-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && e.target.value.trim()) {
            askQuestion(e.target.value.trim());
            e.target.value = '';
        }
    });

    // Tab 切换
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => loadLayer(tab.dataset.layer));
    });

    // 快捷操作
    document.querySelectorAll('.btn-action').forEach(btn => {
        btn.addEventListener('click', () => executeAction(btn.dataset.action));
    });

    // 初始状态
    updateStatus();
});
