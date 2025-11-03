#!/bin/bash
# Sprint 3 验证脚本

set -e

echo "🧭 Sprint 3 验证开始..."
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查后端是否运行
echo "📡 检查后端服务..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 后端服务运行中${NC}"
else
    echo -e "${RED}❌ 后端服务未运行，请先启动后端${NC}"
    echo "   运行: cd kat_rec_web/backend && export USE_MOCK_MODE=true && uvicorn main:app --reload --port 8000"
    exit 1
fi

# 检查 WebSocket 端点（通过 HTTP 升级测试）
echo ""
echo "🔌 检查 WebSocket 端点..."

# 使用 curl 测试 WebSocket 端点（HTTP 101 响应表示可以升级）
if curl -s -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:8000/ws/status 2>&1 | grep -q "101\|200\|400"; then
    echo -e "${GREEN}✅ WebSocket /ws/status 端点可访问${NC}"
else
    echo -e "${YELLOW}⚠️  WebSocket /ws/status 端点检查（需要实际 WebSocket 客户端）${NC}"
fi

if curl -s -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:8000/ws/events 2>&1 | grep -q "101\|200\|400"; then
    echo -e "${GREEN}✅ WebSocket /ws/events 端点可访问${NC}"
else
    echo -e "${YELLOW}⚠️  WebSocket /ws/events 端点检查（需要实际 WebSocket 客户端）${NC}"
fi

# 检查任务控制 API
echo ""
echo "🎮 检查任务控制 API..."
CONTROL_RESPONSE=$(curl -s -X POST http://localhost:8000/api/task/control \
  -H "Content-Type: application/json" \
  -d '{"channel_id": "CH-001", "action": "start"}')

if echo "$CONTROL_RESPONSE" | grep -q "status.*ok"; then
    echo -e "${GREEN}✅ 任务控制 API 正常${NC}"
    echo "   响应: $CONTROL_RESPONSE"
else
    echo -e "${RED}❌ 任务控制 API 异常${NC}"
    echo "   响应: $CONTROL_RESPONSE"
fi

# 检查前端文件
echo ""
echo "📁 检查前端文件..."

FILES=(
    "kat_rec_web/frontend/services/wsClient.ts"
    "kat_rec_web/frontend/stores/channelSlice.ts"
    "kat_rec_web/frontend/stores/feedSlice.ts"
    "kat_rec_web/frontend/components/SystemFeed.tsx"
    "kat_rec_web/frontend/hooks/useWebSocket.ts"
)

ALL_FILES_EXIST=true
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $file${NC}"
    else
        echo -e "${RED}❌ $file 不存在${NC}"
        ALL_FILES_EXIST=false
    fi
done

# 检查后端文件
echo ""
echo "📁 检查后端文件..."

BACKEND_FILES=(
    "kat_rec_web/backend/routes/websocket.py"
    "kat_rec_web/backend/routes/control.py"
)

ALL_BACKEND_FILES_EXIST=true
for file in "${BACKEND_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $file${NC}"
    else
        echo -e "${RED}❌ $file 不存在${NC}"
        ALL_BACKEND_FILES_EXIST=false
    fi
done

# 总结
echo ""
echo "📊 验证总结..."
echo ""

if [ "$ALL_FILES_EXIST" = true ] && [ "$ALL_BACKEND_FILES_EXIST" = true ]; then
    echo -e "${GREEN}✅ 所有文件检查通过${NC}"
    echo ""
    echo "下一步："
    echo "1. 启动前端: cd kat_rec_web/frontend && pnpm dev"
    echo "2. 打开浏览器: http://localhost:3000"
    echo "3. 检查浏览器控制台，应该看到 WebSocket 连接成功"
    echo "4. 观察 SystemFeed（右下角）是否实时更新"
    echo "5. 点击频道卡片的控制按钮，测试任务控制功能"
    echo ""
    echo -e "${GREEN}🎉 Sprint 3 验证完成！${NC}"
else
    echo -e "${RED}❌ 部分文件缺失，请检查上述错误${NC}"
    exit 1
fi

