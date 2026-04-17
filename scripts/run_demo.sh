#!/bin/bash
# 飞书企业级记忆引擎 - 启动 Demo

set -e
cd "$(dirname "$0")/.."

echo "=== 飞书企业级记忆引擎 - Demo 模式 ==="
echo ""

# 确保依赖已安装
pip install -r requirements.txt -q 2>/dev/null

# 运行 Demo 流程
echo "运行 Demo 流程..."
python3 demo/simulate_run.py

echo ""
echo "Demo 流程完成！"
echo ""
echo "启动 Web 服务查看可视化界面:"
echo "  python3 -m uvicorn src.server.app:app --reload --port 8000"
echo ""
echo "浏览器访问: http://localhost:8000/demo/"
