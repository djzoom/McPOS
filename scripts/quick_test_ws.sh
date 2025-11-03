#!/bin/bash
# 快速 WebSocket 测试（后端已在运行）

echo "🧪 快速 WebSocket 测试"
echo ""

# 检查后端是否运行
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ 后端服务未运行"
    echo "   请先启动: bash scripts/start_backend.sh"
    exit 1
fi

echo "✅ 后端服务运行中"
echo ""

# 测试批量重试 API
echo "📡 测试批量重试 API..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/task/control \
  -H "Content-Type: application/json" \
  -d '{"action": "retry_failed", "channels": ["CH-006", "CH-009"]}')

if echo "$RESPONSE" | grep -q "status.*ok"; then
    echo "✅ API 测试通过"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
else
    echo "❌ API 测试失败"
    echo "$RESPONSE"
fi

echo ""
echo "🔌 WebSocket 测试说明："
echo ""
echo "现在后端已运行，您可以在新终端运行："
echo ""
echo "  1. Python 测试（推荐）："
echo "     python3 scripts/test_websocket_client.py"
echo ""
echo "  2. 浏览器测试："
echo "     打开浏览器控制台（F12），运行："
echo "     const ws = new WebSocket('ws://localhost:8000/ws/status')"
echo "     ws.onmessage = (e) => console.log(JSON.parse(e.data))"
echo ""
echo "  3. 完整测试套件："
echo "     bash scripts/test_all.sh"
echo ""

