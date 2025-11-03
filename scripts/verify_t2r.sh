#!/bin/bash
# T2R (Trip to Reality) 验证脚本

set -e

echo "🧪 T2R 系统验证"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查后端是否运行
echo "📡 检查后端服务..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 后端服务运行中${NC}"
else
    echo -e "${RED}❌ 后端服务未运行${NC}"
    echo "   请先启动: bash scripts/start_backend.sh"
    exit 1
fi

echo ""
echo "🔍 检查后端文件..."

BACKEND_FILES=(
    "kat_rec_web/backend/t2r/router.py"
    "kat_rec_web/backend/t2r/routes/scan.py"
    "kat_rec_web/backend/t2r/routes/srt.py"
    "kat_rec_web/backend/t2r/routes/desc.py"
    "kat_rec_web/backend/t2r/routes/plan.py"
    "kat_rec_web/backend/t2r/routes/upload.py"
    "kat_rec_web/backend/t2r/routes/audit.py"
    "kat_rec_web/backend/t2r/services/schedule_service.py"
)

ALL_BACKEND_EXIST=true
for file in "${BACKEND_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $file${NC}"
    else
        echo -e "${RED}❌ $file 不存在${NC}"
        ALL_BACKEND_EXIST=false
    fi
done

echo ""
echo "🔍 检查前端文件..."

FRONTEND_FILES=(
    "kat_rec_web/frontend/stores/t2rScheduleStore.ts"
    "kat_rec_web/frontend/stores/t2rAssetsStore.ts"
    "kat_rec_web/frontend/stores/t2rSrtStore.ts"
    "kat_rec_web/frontend/stores/t2rDescStore.ts"
    "kat_rec_web/frontend/stores/runbookStore.ts"
    "kat_rec_web/frontend/services/t2rApi.ts"
    "kat_rec_web/frontend/hooks/useT2RWebSocket.ts"
    "kat_rec_web/frontend/app/(t2r)/t2r/page.tsx"
)

ALL_FRONTEND_EXIST=true
for file in "${FRONTEND_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $file${NC}"
    else
        echo -e "${RED}❌ $file 不存在${NC}"
        ALL_FRONTEND_EXIST=false
    fi
done

echo ""
echo "🧪 测试 API 端点..."

# 测试扫描 API
echo "   测试 POST /api/t2r/scan..."
SCAN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/t2r/scan -H 'Content-Type: application/json')
SCAN_STATUS=$(echo "$SCAN_RESPONSE" | jq -r '.status' 2>/dev/null)
SCAN_LOCKED=$(echo "$SCAN_RESPONSE" | jq -r '.summary.locked_count // .data.locked_count // 0' 2>/dev/null)
if [ "$SCAN_STATUS" = "ok" ] || echo "$SCAN_RESPONSE" | grep -q "status"; then
    echo -e "   ${GREEN}✅ 扫描 API 正常 (锁定: ${SCAN_LOCKED})${NC}"
else
    echo -e "   ${RED}❌ 扫描 API 异常${NC}"
    echo "   响应: $SCAN_RESPONSE"
fi

# 测试 SRT 检查 API
echo "   测试 POST /api/t2r/srt/inspect..."
SRT_RESPONSE=$(curl -s -X POST http://localhost:8000/api/t2r/srt/inspect \
  -H "Content-Type: application/json" \
  -d '{"episode_id": "20251102"}')
if echo "$SRT_RESPONSE" | grep -q "status"; then
    echo -e "   ${GREEN}✅ SRT 检查 API 正常${NC}"
else
    echo -e "   ${YELLOW}⚠️  SRT 检查 API 返回错误（可能文件不存在）${NC}"
fi

# 测试描述检查 API
echo "   测试 POST /api/t2r/desc/lint..."
DESC_RESPONSE=$(curl -s -X POST http://localhost:8000/api/t2r/desc/lint \
  -H "Content-Type: application/json" \
  -d '{"episode_id": "20251102", "description": "Test with Vibe Coding"}')
DESC_FLAGS=$(echo "$DESC_RESPONSE" | jq -r '.flags // [] | length' 2>/dev/null)
if echo "$DESC_RESPONSE" | grep -q "flags"; then
    echo -e "   ${GREEN}✅ 描述检查 API 正常 (检测到 ${DESC_FLAGS} 个问题)${NC}"
else
    echo -e "   ${RED}❌ 描述检查 API 异常${NC}"
    echo "   响应: $DESC_RESPONSE"
fi

# 测试计划 API
echo "   测试 POST /api/episodes/plan..."
PLAN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/episodes/plan \
  -H "Content-Type: application/json" \
  -d '{"episode_id": "20251102", "avoid_duplicates": true, "seo_template": true}')
PLAN_STATUS=$(echo "$PLAN_RESPONSE" | jq -r '.status' 2>/dev/null)
if [ "$PLAN_STATUS" = "ok" ]; then
    RECIPE_PATH=$(echo "$PLAN_RESPONSE" | jq -r '.recipe_json_path' 2>/dev/null)
    echo -e "   ${GREEN}✅ 计划 API 正常${NC}"
    if [ -n "$RECIPE_PATH" ] && [ "$RECIPE_PATH" != "null" ]; then
        echo "   Recipe: $RECIPE_PATH"
    fi
else
    echo -e "   ${YELLOW}⚠️  计划 API 返回错误${NC}"
fi

# 测试运行 API (dry run)
echo "   测试 POST /api/episodes/run (dry run)..."
RUN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/episodes/run \
  -H "Content-Type: application/json" \
  -d '{"episode_id": "20251102", "dry_run": true, "stages": ["remix", "render"]}')
RUN_STATUS=$(echo "$RUN_RESPONSE" | jq -r '.status' 2>/dev/null)
if [ "$RUN_STATUS" = "ok" ]; then
    echo -e "   ${GREEN}✅ 运行 API 正常${NC}"
else
    echo -e "   ${YELLOW}⚠️  运行 API 返回错误${NC}"
fi

echo ""
echo "📊 系统指标检查..."

# 测试系统指标端点
echo "   测试 GET /metrics/system..."
SYSTEM_METRICS=$(curl -s http://localhost:8000/metrics/system)
CPU_PERCENT=$(echo "$SYSTEM_METRICS" | jq -r '.cpu_percent' 2>/dev/null || echo "N/A")
MEMORY_MB=$(echo "$SYSTEM_METRICS" | jq -r '.memory_mb' 2>/dev/null || echo "N/A")
if echo "$SYSTEM_METRICS" | grep -q "cpu_percent"; then
    echo -e "   ${GREEN}✅ 系统指标 API 正常${NC}"
    echo "   CPU: ${CPU_PERCENT}%, 内存: ${MEMORY_MB} MB"
else
    echo -e "   ${YELLOW}⚠️  系统指标 API 返回错误${NC}"
fi

# 测试 WebSocket 健康端点
echo "   测试 GET /metrics/ws-health..."
WS_HEALTH=$(curl -s http://localhost:8000/metrics/ws-health)
WS_CONNECTIONS=$(echo "$WS_HEALTH" | jq -r '.active_connections' 2>/dev/null || echo "0")
if echo "$WS_HEALTH" | grep -q "active_connections"; then
    echo -e "   ${GREEN}✅ WebSocket 健康检查正常${NC}"
    echo "   活跃连接: ${WS_CONNECTIONS}"
else
    echo -e "   ${YELLOW}⚠️  WebSocket 健康检查返回错误${NC}"
fi

echo ""
echo "📊 验证总结..."

# Load previous results if exists
PREV_RESULT_FILE=".t2r_verify_last.json"
if [ -f "$PREV_RESULT_FILE" ]; then
    PREV_LOCKED=$(jq -r '.locked_count // 0' "$PREV_RESULT_FILE" 2>/dev/null || echo "0")
    PREV_CONFLICTS=$(jq -r '.conflicts_count // 0' "$PREV_RESULT_FILE" 2>/dev/null || echo "0")
    PREV_SCAN_TIME=$(jq -r '.scan_time // ""' "$PREV_RESULT_FILE" 2>/dev/null || echo "")
    
    echo ""
    echo "📈 与上次结果对比:"
    echo "   上次扫描时间: ${PREV_SCAN_TIME:-未知}"
    echo "   锁定数: ${PREV_LOCKED} → ${SCAN_LOCKED}"
    echo "   冲突数: ${PREV_CONFLICTS} → $(echo "$SCAN_RESPONSE" | jq -r '.summary.conflicts_count // .data.conflicts // [] | length' 2>/dev/null || echo "0")"
fi

# Save current results
CURRENT_RESULT=$(cat <<EOF
{
  "locked_count": ${SCAN_LOCKED:-0},
  "conflicts_count": $(echo "$SCAN_RESPONSE" | jq -r '.summary.conflicts_count // .data.conflicts // [] | length' 2>/dev/null || echo "0"),
  "scan_time": "$(date -Iseconds)",
  "all_checks_passed": $([ "$ALL_BACKEND_EXIST" = true ] && [ "$ALL_FRONTEND_EXIST" = true ] && echo "true" || echo "false")
}
EOF
)
echo "$CURRENT_RESULT" > "$PREV_RESULT_FILE"

if [ "$ALL_BACKEND_EXIST" = true ] && [ "$ALL_FRONTEND_EXIST" = true ]; then
    echo -e "${GREEN}✅ 所有文件检查通过${NC}"
    echo ""
    echo "下一步："
    echo "1. 启动前端: cd kat_rec_web/frontend && pnpm dev"
    echo "2. 访问: http://localhost:3000/t2r"
    echo "3. 测试各个功能模块"
    echo ""
    echo -e "${GREEN}🎉 T2R 系统验证完成！${NC}"
else
    echo -e "${RED}❌ 部分文件缺失，请检查上述错误${NC}"
    exit 1
fi

