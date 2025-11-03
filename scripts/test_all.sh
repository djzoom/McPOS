#!/bin/bash
# 一键测试脚本：启动后端并测试 WebSocket

set -e

echo "🧪 Kat Rec WebSocket 完整测试"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 检查后端是否运行
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ 后端服务已在运行"
    BACKEND_RUNNING=true
else
    echo "⚠️  后端服务未运行"
    BACKEND_RUNNING=false
fi

# 如果后端未运行，提示启动
if [ "$BACKEND_RUNNING" = false ]; then
    echo ""
    echo "请先启动后端服务："
    echo ""
    echo "  方法 1: 使用启动脚本"
    echo "    bash scripts/start_backend.sh"
    echo ""
    echo "  方法 2: 手动启动"
    echo "    cd kat_rec_web/backend"
    echo "    export USE_MOCK_MODE=true"
    echo "    uvicorn main:app --reload --port 8000"
    echo ""
    echo "然后在新终端运行此脚本进行测试"
    exit 1
fi

# 等待服务就绪
echo "⏳ 等待服务就绪..."
sleep 2

# 测试健康检查
echo ""
echo "📡 测试健康检查..."
HEALTH=$(curl -s http://localhost:8000/health)
if echo "$HEALTH" | grep -q "status"; then
    echo "✅ 健康检查通过"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
else
    echo "❌ 健康检查失败"
    exit 1
fi

# 测试任务控制 API
echo ""
echo "🎮 测试任务控制 API..."
CONTROL_RESPONSE=$(curl -s -X POST http://localhost:8000/api/task/control \
  -H "Content-Type: application/json" \
  -d '{"action": "retry_failed", "channels": ["CH-006", "CH-009"]}')

if echo "$CONTROL_RESPONSE" | grep -q "status.*ok"; then
    echo "✅ 批量重试 API 正常"
    echo "$CONTROL_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$CONTROL_RESPONSE"
else
    echo "❌ 批量重试 API 异常"
    echo "$CONTROL_RESPONSE"
fi

# 测试 WebSocket
echo ""
echo "🔌 测试 WebSocket 连接..."
if command -v python3 &> /dev/null; then
    if python3 -c "import websockets" 2>/dev/null; then
        echo "   运行 WebSocket 客户端测试..."
        python3 "$PROJECT_ROOT/scripts/test_websocket_client.py" --test status
    else
        echo "⚠️  websockets 库未安装"
        echo "   安装: pip install websockets"
        echo ""
        echo "   或使用浏览器测试："
        echo "   打开浏览器控制台，运行："
        echo "   const ws = new WebSocket('ws://localhost:8000/ws/status')"
        echo "   ws.onmessage = (e) => console.log(JSON.parse(e.data))"
    fi
else
    echo "⚠️  Python 3 未安装或不在 PATH 中"
fi

echo ""
echo "✅ 测试完成！"
echo ""
echo "💡 提示："
echo "   - 查看详细测试指南: cat scripts/websocket_quick_test.md"
echo "   - 启动后端服务: bash scripts/start_backend.sh"
echo "   - 测试 WebSocket: python3 scripts/test_websocket_client.py"

