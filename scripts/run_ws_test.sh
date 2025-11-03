#!/bin/bash
# 运行 WebSocket 测试（自动安装依赖）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🧪 WebSocket 测试"
echo ""

# 检查后端是否运行
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ 后端服务未运行"
    echo "   请先启动: bash scripts/start_backend.sh"
    exit 1
fi

echo "✅ 后端服务运行中"
echo ""

# 检查并安装 websockets
if ! python3 -c "import websockets" 2>/dev/null; then
    echo "📦 安装 websockets 库..."
    if [ -f "$PROJECT_ROOT/.venv311/bin/activate" ]; then
        source "$PROJECT_ROOT/.venv311/bin/activate"
    fi
    pip install websockets -q
    echo "✅ websockets 已安装"
    echo ""
fi

# 运行测试
echo "🔌 运行 WebSocket 测试..."
echo ""
python3 "$SCRIPT_DIR/test_websocket_client.py" "$@"

