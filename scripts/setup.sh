#!/bin/bash
# 飞书企业级记忆引擎 - 环境设置

set -e
cd "$(dirname "$0")/.."

echo "=== 飞书企业级记忆引擎 - 环境设置 ==="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

echo "Python: $(python3 --version)"

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt -q

# 创建必要目录
echo "创建目录..."
mkdir -p memory_store/raw memory_store/episodes memory_store/knowledge

echo "环境设置完成!"
echo ""
echo "运行 Demo:   bash scripts/run_demo.sh"
echo "启动服务:    python -m uvicorn src.server.app:app --reload --port 8000"
