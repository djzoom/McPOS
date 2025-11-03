#!/bin/bash
# WebSocket 测试脚本

set -e

echo "🧪 WebSocket 测试脚本"
echo ""

# 检查后端是否运行
echo "📡 检查后端服务..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "\033[0;32m✅ 后端服务运行中\033[0m"
else
    echo -e "\033[0;31m❌ 后端服务未运行\033[0m"
    echo "   请先启动后端："
    echo "   cd kat_rec_web/backend"
    echo "   export USE_MOCK_MODE=true"
    echo "   uvicorn main:app --reload --port 8000"
    exit 1
fi

echo ""
echo "🔌 WebSocket 测试说明"
echo ""
echo "注意: curl 不能直接测试 WebSocket 连接"
echo ""
echo "推荐测试方法："
echo ""
echo "1️⃣ 使用 Python 脚本测试:"
echo "   python3 scripts/test_websocket_client.py"
echo ""
echo "2️⃣ 使用 wscat (需要安装):"
echo "   npm install -g wscat"
echo "   wscat -c ws://localhost:8000/ws/status"
echo ""
echo "3️⃣ 使用浏览器控制台:"
echo "   const ws = new WebSocket('ws://localhost:8000/ws/status')"
echo "   ws.onmessage = (e) => console.log(e.data)"
echo ""
echo "4️⃣ 运行测试套件:"
echo "   cd kat_rec_web/backend"
echo "   pytest tests/test_websocket_status.py -v"
echo ""

# 测试 API 端点（HTTP，不是 WebSocket）
echo "📡 测试任务控制 API..."
CONTROL_RESPONSE=$(curl -s -X POST http://localhost:8000/api/task/control \
  -H "Content-Type: application/json" \
  -d '{"action": "retry_failed", "channels": ["CH-006", "CH-009"]}')

if echo "$CONTROL_RESPONSE" | grep -q "status.*ok"; then
    echo -e "\033[0;32m✅ 批量重试 API 正常\033[0m"
    echo "   响应: $CONTROL_RESPONSE"
else
    echo -e "\033[0;31m❌ 批量重试 API 异常\033[0m"
    echo "   响应: $CONTROL_RESPONSE"
fi

echo ""
echo "✅ 测试完成"

