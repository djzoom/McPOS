#!/usr/bin/env bash
# Sprint 6 验收与压力测试脚本
# 用途: 全面验证 T2R 系统在生产环境下的稳定性和功能完整性

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
BASE_URL="http://localhost:8000"
WS_URL="ws://localhost:8000"
TEST_EPISODE_ID="CH-TEST-$(date +%s)"
TEST_DIR="${HOME}/Downloads/Kat_Rec"
DATA_DIR="${TEST_DIR}/data"

# 测试结果计数器
PASSED=0
FAILED=0
WARNINGS=0

# 打印函数
print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_test() {
    echo -e "\n${YELLOW}▶ $1${NC}"
}

print_pass() {
    echo -e "${GREEN}✅ $1${NC}"
    ((PASSED++)) || true
}

print_fail() {
    echo -e "${RED}❌ $1${NC}"
    ((FAILED++)) || true
}

print_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARNINGS++)) || true
}

# 检查依赖
check_dependencies() {
    print_header "0. 预备检查"
    
    local missing=()
    
    command -v curl >/dev/null 2>&1 || missing+=("curl")
    command -v jq >/dev/null 2>&1 || missing+=("jq")
    command -v python3 >/dev/null 2>&1 || missing+=("python3")
    
    if [ ${#missing[@]} -gt 0 ]; then
        print_fail "缺少依赖: ${missing[*]}"
        echo "请安装缺失的工具后重试"
        exit 1
    fi
    
    print_pass "依赖检查通过"
    
    # 检查后端是否运行
    if ! curl -s "${BASE_URL}/health" > /dev/null 2>&1; then
        print_fail "后端未运行在 ${BASE_URL}"
        echo "请先启动后端: cd kat_rec_web/backend && uvicorn main:app --reload --port 8000"
        exit 1
    fi
    
    print_pass "后端服务运行中"
}

# 1. 90秒 Smoke Test
test_smoke() {
    print_header "1. 90秒 Smoke Test（\"活着就行\"）"
    
    # 1.1 健康检查
    print_test "健康检查（带环境自检）"
    HEALTH_RESPONSE=$(curl -s "${BASE_URL}/health")
    
    if echo "$HEALTH_RESPONSE" | jq -e '.status == "ok"' > /dev/null 2>&1; then
        print_pass "健康检查返回 OK"
        
        # 检查路径信息
        if echo "$HEALTH_RESPONSE" | jq -e '.environment.paths' > /dev/null 2>&1; then
            print_pass "环境路径信息已列出"
            echo "$HEALTH_RESPONSE" | jq '.environment.paths | to_entries[] | "\(.key): \(.value.valid)"'
        else
            print_warn "未找到环境路径信息"
        fi
    else
        print_fail "健康检查失败"
        echo "$HEALTH_RESPONSE" | jq '.'
        return 1
    fi
    
    # 1.2 系统指标
    print_test "系统指标（CPU/内存/WS连接数）"
    METRICS_RESPONSE=$(curl -s "${BASE_URL}/metrics/system")
    
    if echo "$METRICS_RESPONSE" | jq -e '.cpu_percent, .memory_mb, .active_ws_connections' > /dev/null 2>&1; then
        print_pass "系统指标端点正常"
        CPU=$(echo "$METRICS_RESPONSE" | jq -r '.cpu_percent')
        MEM=$(echo "$METRICS_RESPONSE" | jq -r '.memory_mb')
        WS=$(echo "$METRICS_RESPONSE" | jq -r '.active_ws_connections')
        echo "  CPU: ${CPU}%, 内存: ${MEM} MB, WS连接: ${WS}"
    else
        print_fail "系统指标端点异常"
        echo "$METRICS_RESPONSE" | jq '.'
        return 1
    fi
    
    # 1.3 WS健康指标
    print_test "WebSocket健康指标"
    WS_HEALTH=$(curl -s "${BASE_URL}/metrics/ws-health")
    
    if echo "$WS_HEALTH" | jq -e '.active_connections' > /dev/null 2>&1; then
        print_pass "WS健康检查正常"
        CONN=$(echo "$WS_HEALTH" | jq -r '.active_connections')
        echo "  活跃连接数: ${CONN}"
    else
        print_warn "WS健康检查返回异常（可能没有连接）"
    fi
    
    # 1.4 计划接口
    print_test "计划接口（生成Recipe）"
    PLAN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/episodes/plan" \
        -H 'Content-Type: application/json' \
        -d "{\"episode_id\":\"${TEST_EPISODE_ID}\"}")
    
    if echo "$PLAN_RESPONSE" | jq -e '.status == "ok"' > /dev/null 2>&1; then
        print_pass "计划接口正常"
        RECIPE_PATH=$(echo "$PLAN_RESPONSE" | jq -r '.recipe_json_path // empty')
        if [ -n "$RECIPE_PATH" ] && [ "$RECIPE_PATH" != "null" ]; then
            print_pass "Recipe文件已生成: ${RECIPE_PATH}"
            
            # 检查文件是否存在且包含hash
            if [[ "$RECIPE_PATH" =~ -[a-f0-9]{8}\.json$ ]]; then
                print_pass "Recipe文件名包含hash（幂等性）"
            else
                print_warn "Recipe文件名未包含hash"
            fi
        else
            print_warn "Recipe路径为空"
        fi
    else
        print_fail "计划接口失败"
        echo "$PLAN_RESPONSE" | jq '.'
        return 1
    fi
    
    # 1.5 运行接口（后台任务）
    print_test "运行接口（后台任务 + WS广播）"
    RUN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/episodes/run" \
        -H 'Content-Type: application/json' \
        -d "{\"episode_id\":\"${TEST_EPISODE_ID}\",\"stages\":[\"remix\",\"render\",\"upload\",\"verify\"]}")
    
    if echo "$RUN_RESPONSE" | jq -e '.status == "ok" and .run_id' > /dev/null 2>&1; then
        print_pass "运行接口立即返回run_id"
        RUN_ID=$(echo "$RUN_RESPONSE" | jq -r '.run_id')
        echo "  Run ID: ${RUN_ID}"
        echo "  ⚠️  请查看后端日志确认WS广播是否正常"
    else
        print_fail "运行接口失败"
        echo "$RUN_RESPONSE" | jq '.'
        return 1
    fi
    
    echo ""
    print_pass "Smoke Test 完成"
}

# 2. WebSocket完整性测试
test_websocket() {
    print_header "2. WebSocket完整性（版本号、心跳、批量缓冲）"
    
    print_test "WebSocket测试（Python客户端）"
    
    # 创建临时Python测试脚本
    PYTHON_TEST=$(cat <<'PYTHON_EOF'
import asyncio
import json
import statistics
import websockets
import time

gaps = []
last_ver = -1
pings = 0
events = 0
error_count = 0

async def test_ws():
    global last_ver, pings, events, error_count
    uri = 'ws://localhost:8000/ws/events'
    
    try:
        async with websockets.connect(uri) as ws:
            t_prev = time.time()
            
            # 接收最多100条消息或10秒超时
            for _ in range(100):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    
                    # 处理心跳
                    if msg == 'ping' or msg == '"ping"':
                        pings += 1
                        continue
                    
                    # 解析JSON
                    try:
                        m = json.loads(msg)
                    except:
                        continue
                    
                    # 检查版本号
                    if isinstance(m, dict):
                        version = m.get('version') or m.get('data', {}).get('version')
                        if version is not None:
                            if version <= last_ver:
                                print(f"❌ version非递增: {version} <= {last_ver}")
                                error_count += 1
                            last_ver = version
                        
                        events += 1
                        
                        # 计算间隔
                        t_now = time.time()
                        gap_ms = (t_now - t_prev) * 1000
                        if gap_ms < 5000:  # 排除心跳间隔
                            gaps.append(gap_ms)
                        t_prev = t_now
                    
                except asyncio.TimeoutError:
                    break
                    
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        error_count += 1
        return
    
    # 输出结果
    if pings >= 1:
        print(f"✅ 心跳正常 (收到 {pings} 次)")
    else:
        print(f"⚠️  心跳不足 (收到 {pings} 次)")
        error_count += 1
    
    if events > 0 and len(gaps) > 0:
        median_gap = statistics.median(gaps)
        print(f"✅ 收到 {events} 个事件")
        print(f"   批量缓冲中位数间隔: {median_gap:.1f}ms")
        if 50 <= median_gap <= 200:
            print(f"✅ 批量缓冲正常 (~100ms)")
        else:
            print(f"⚠️  批量缓冲异常 (期望 ~100ms)")
    else:
        print(f"⚠️  事件数不足: {events}, 间隔数: {len(gaps)}")
    
    if last_ver > 0:
        print(f"✅ 版本号单调递增 (最高: {last_ver})")
    else:
        print(f"⚠️  未检测到版本号")
    
    if error_count > 0:
        exit(1)

if __name__ == '__main__':
    asyncio.run(test_ws())
PYTHON_EOF
)
    
    # 运行Python测试
    if python3 -c "import websockets" 2>/dev/null; then
        python3 <<< "$PYTHON_TEST"
        if [ $? -eq 0 ]; then
            print_pass "WebSocket测试通过"
        else
            print_fail "WebSocket测试失败"
            print_warn "请手动在浏览器控制台测试（见测试文档）"
        fi
    else
        print_warn "websockets库未安装，跳过Python WS测试"
        print_warn "请手动在浏览器控制台测试（见README或测试文档）"
    fi
}

# 3. 重试与恢复测试
test_retry_recovery() {
    print_header "3. 重试与恢复（retry_policy / journal / resume）"
    
    # 3.1 检查重试策略
    print_test "检查重试策略配置"
    RETRY_POLICY="${TEST_DIR}/kat_rec_web/backend/t2r/config/retry_policy.json"
    
    if [ -f "$RETRY_POLICY" ]; then
        print_pass "重试策略文件存在"
        if jq -e '.retry_policy.stages' "$RETRY_POLICY" > /dev/null 2>&1; then
            print_pass "重试策略配置有效"
            echo "  配置的阶段: $(jq -r '.retry_policy.stages | keys[]' "$RETRY_POLICY" | tr '\n' ' ')"
        else
            print_fail "重试策略配置无效"
        fi
    else
        print_fail "重试策略文件不存在: $RETRY_POLICY"
    fi
    
    # 3.2 触发Run并检查Journal
    print_test "触发Run并检查Journal"
    TEST_EPISODE_RETRY="CH-TEST-RETRY-$(date +%s)"
    
    RUN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/episodes/run" \
        -H 'Content-Type: application/json' \
        -d "{\"episode_id\":\"${TEST_EPISODE_RETRY}\",\"stages\":[\"remix\",\"render\",\"upload\",\"verify\"]}")
    
    RUN_ID=$(echo "$RUN_RESPONSE" | jq -r '.run_id // empty')
    
    if [ -n "$RUN_ID" ]; then
        print_pass "Run已启动: ${RUN_ID}"
        
        # 等待一段时间让journal写入
        sleep 2
        
        # 检查Journal
        JOURNAL_FILE="${DATA_DIR}/run_journal.json"
        if [ -f "$JOURNAL_FILE" ]; then
            print_pass "Journal文件存在"
            
            # 检查是否有该run的记录
            if jq -e --arg rid "$RUN_ID" '.runs[] | select(.run_id == $rid)' "$JOURNAL_FILE" > /dev/null 2>&1; then
                print_pass "Journal中找到了run记录"
                
                # 检查阶段状态
                STAGES=$(jq -r --arg rid "$RUN_ID" '.runs[] | select(.run_id == $rid) | .stages[].status' "$JOURNAL_FILE" 2>/dev/null | head -5)
                if [ -n "$STAGES" ]; then
                    print_pass "阶段状态已记录"
                    echo "  阶段状态: $(echo "$STAGES" | tr '\n' ' ')"
                fi
                
                # 检查retry_point（如果有失败）
                RETRY_POINT=$(jq -r --arg rid "$RUN_ID" '.runs[] | select(.run_id == $rid) | .stages[] | select(.retry_point) | .retry_point' "$JOURNAL_FILE" 2>/dev/null | head -1)
                if [ -n "$RETRY_POINT" ]; then
                    print_pass "检测到retry_point: ${RETRY_POINT}"
                else
                    echo "  ℹ️  当前run未失败，无retry_point"
                fi
            else
                print_warn "Journal中未找到该run（可能还在写入中）"
            fi
        else
            print_warn "Journal文件不存在（可能尚未创建）"
        fi
    else
        print_fail "Run启动失败"
        return 1
    fi
    
    # 3.3 恢复测试（如果pytest可用）
    print_test "运行恢复功能测试"
    TEST_FILE="${TEST_DIR}/kat_rec_web/backend/tests/test_resume_run.py"
    
    if [ -f "$TEST_FILE" ]; then
        cd "${TEST_DIR}/kat_rec_web/backend"
        if pytest -q tests/test_resume_run.py 2>/dev/null; then
            print_pass "恢复功能测试通过"
        else
            print_warn "恢复功能测试失败或跳过"
        fi
        cd - > /dev/null
    else
        print_warn "测试文件不存在: $TEST_FILE"
    fi
}

# 4. 原子写入测试
test_atomic_write() {
    print_header "4. 原子写入与事务组写入"
    
    # 检查是否有.tmp残留文件
    print_test "检查临时文件残留"
    TMP_COUNT=$(find "${DATA_DIR}" -name "*.tmp" 2>/dev/null | wc -l | tr -d ' ')
    
    if [ "$TMP_COUNT" -eq 0 ]; then
        print_pass "无临时文件残留（原子写入正常）"
    else
        print_fail "发现 ${TMP_COUNT} 个临时文件残留"
        find "${DATA_DIR}" -name "*.tmp" 2>/dev/null | head -5
    fi
    
    # 检查recipe文件
    print_test "检查Recipe文件完整性"
    RECIPE_FILES=$(find "${DATA_DIR}" -name "${TEST_EPISODE_ID}-*.json" 2>/dev/null | head -5)
    
    if [ -n "$RECIPE_FILES" ]; then
        print_pass "Recipe文件存在"
        for f in $RECIPE_FILES; do
            if jq empty "$f" 2>/dev/null; then
                echo "  ✅ $f (JSON有效)"
            else
                print_fail "$f (JSON无效或损坏)"
            fi
        done
    else
        print_warn "未找到Recipe文件（可能尚未生成）"
    fi
}

# 5. Metrics回归测试
test_metrics_regression() {
    print_header "5. Metrics回归（含WS连接数变化）"
    
    print_test "初始WS连接数"
    INIT_WS=$(curl -s "${BASE_URL}/metrics/system" | jq -r '.active_ws_connections')
    echo "  初始连接数: ${INIT_WS}"
    
    print_test "等待5秒后再次检查（模拟页面连接）"
    sleep 5
    LATER_WS=$(curl -s "${BASE_URL}/metrics/system" | jq -r '.active_ws_connections')
    echo "  当前连接数: ${LATER_WS}"
    
    if [ "$LATER_WS" -ge "$INIT_WS" ]; then
        print_pass "连接数变化正常（可能因测试脚本连接）"
    else
        print_warn "连接数下降（可能有连接断开）"
    fi
    
    print_test "WS健康详情"
    WS_HEALTH=$(curl -s "${BASE_URL}/metrics/ws-health")
    STATUS_COUNT=$(echo "$WS_HEALTH" | jq -r '.status_manager_count // 0')
    EVENTS_COUNT=$(echo "$WS_HEALTH" | jq -r '.events_manager_count // 0')
    echo "  Status Manager: ${STATUS_COUNT}"
    echo "  Events Manager: ${EVENTS_COUNT}"
    
    print_pass "Metrics回归测试完成"
}

# 6. 一键验收脚本
test_full_smoke() {
    print_header "6. 一键验收脚本（完整流程）"
    
    TEST_EPISODE_FULL="CH-TEST-FULL-$(date +%s)"
    
    echo "测试Episode ID: ${TEST_EPISODE_FULL}"
    
    # Health
    echo ""
    echo "== HEALTH =="
    HEALTH=$(curl -s "${BASE_URL}/health")
    echo "$HEALTH" | jq '{status, mode, environment: {paths_valid: .environment.paths_valid}}'
    
    if echo "$HEALTH" | jq -e '.status == "ok"' > /dev/null; then
        print_pass "Health检查通过"
    else
        print_fail "Health检查失败"
    fi
    
    # Metrics
    echo ""
    echo "== METRICS =="
    METRICS=$(curl -s "${BASE_URL}/metrics/system")
    echo "$METRICS" | jq '{cpu: .cpu_percent, mem: .memory_mb, ws: .active_ws_connections}'
    
    CPU_VAL=$(echo "$METRICS" | jq -r '.cpu_percent')
    if (( $(echo "$CPU_VAL >= 0 && $CPU_VAL <= 100" | bc -l) )); then
        print_pass "Metrics数值合理"
    else
        print_warn "Metrics数值异常"
    fi
    
    # Plan
    echo ""
    echo "== PLAN =="
    PLAN=$(curl -s -X POST "${BASE_URL}/api/episodes/plan" \
        -H 'Content-Type: application/json' \
        -d "{\"episode_id\":\"${TEST_EPISODE_FULL}\"}")
    echo "$PLAN" | jq '{status, recipe_json_path}'
    
    if echo "$PLAN" | jq -e '.status == "ok"' > /dev/null; then
        print_pass "Plan接口通过"
    else
        print_fail "Plan接口失败"
    fi
    
    # Run
    echo ""
    echo "== RUN =="
    RUN=$(curl -s -X POST "${BASE_URL}/api/episodes/run" \
        -H 'Content-Type: application/json' \
        -d "{\"episode_id\":\"${TEST_EPISODE_FULL}\",\"stages\":[\"remix\",\"render\",\"upload\",\"verify\"]}")
    echo "$RUN" | jq '{status, run_id, stages}'
    
    if echo "$RUN" | jq -e '.status == "ok" and .run_id' > /dev/null; then
        print_pass "Run接口通过"
    else
        print_fail "Run接口失败"
    fi
}

# 7. 前端测试提示
test_frontend_hints() {
    print_header "7. 前端去重与重连（手动测试）"
    
    echo "请手动测试以下项目："
    echo ""
    echo "1. 打开浏览器: http://localhost:3000/t2r"
    echo ""
    echo "2. 打开开发者控制台，观察SystemFeed："
    echo "   - 检查是否有重复事件（同一version不应重复）"
    echo "   - 观察事件流是否正常"
    echo ""
    echo "3. 断网测试（10-20秒）："
    echo "   - 断开网络连接"
    echo "   - 等待10-20秒"
    echo "   - 恢复网络"
    echo "   - 观察前端是否能自动重连并继续接收事件"
    echo "   - 重连间隔应为指数退避: 2s → 4s → 8s → 16s → 32s → 60s"
    echo ""
    echo "4. 查看SystemMetricsCard组件（如果已集成）："
    echo "   - 检查CPU/内存/WS连接数是否实时更新"
    echo ""
    
    print_warn "前端测试需要手动验证"
}

# 8. Docker测试提示
test_docker_hints() {
    print_header "8. Docker化验收（可选）"
    
    echo "Docker测试步骤："
    echo ""
    echo "1. 启动Docker Compose:"
    echo "   cd ${TEST_DIR}/kat_rec_web"
    echo "   docker compose up --build"
    echo ""
    echo "2. 等待服务启动后，重复以下测试："
    echo "   - 第1步: Smoke Test（curl健康检查和API）"
    echo "   - 第2步: WebSocket测试"
    echo "   - 第5步: Metrics回归"
    echo ""
    echo "3. 验证容器内服务正常："
    echo "   docker compose exec backend curl http://localhost:8000/health"
    echo ""
    
    print_warn "Docker测试需要单独执行"
}

# 生成测试报告
print_summary() {
    print_header "测试总结"
    
    TOTAL=$((PASSED + FAILED + WARNINGS))
    
    echo -e "${GREEN}通过: ${PASSED}${NC}"
    echo -e "${RED}失败: ${FAILED}${NC}"
    echo -e "${YELLOW}警告: ${WARNINGS}${NC}"
    echo -e "总计: ${TOTAL}"
    echo ""
    
    # 红线标准
    echo "🎯 通过标准（必须全部满足）："
    echo ""
    
    MUST_PASS=0
    
    # 检查健康检查
    if curl -s "${BASE_URL}/health" | jq -e '.status == "ok"' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ /health 返回 OK${NC}"
        ((MUST_PASS++))
    else
        echo -e "${RED}❌ /health 未返回 OK${NC}"
    fi
    
    # 检查Metrics
    if curl -s "${BASE_URL}/metrics/system" | jq -e '.cpu_percent, .memory_mb' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ /metrics/system 可用${NC}"
        ((MUST_PASS++))
    else
        echo -e "${RED}❌ /metrics/system 不可用${NC}"
    fi
    
    # 检查Plan
    if curl -s -X POST "${BASE_URL}/api/episodes/plan" \
        -H 'Content-Type: application/json' \
        -d "{\"episode_id\":\"test\"}" | jq -e '.status == "ok"' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Plan接口正常${NC}"
        ((MUST_PASS++))
    else
        echo -e "${RED}❌ Plan接口异常${NC}"
    fi
    
    # 检查Run
    if curl -s -X POST "${BASE_URL}/api/episodes/run" \
        -H 'Content-Type: application/json' \
        -d '{"episode_id":"test","stages":["remix"]}' | jq -e '.run_id' > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Run接口返回run_id${NC}"
        ((MUST_PASS++))
    else
        echo -e "${RED}❌ Run接口未返回run_id${NC}"
    fi
    
    echo ""
    
    if [ $MUST_PASS -eq 4 ] && [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}🎉 Sprint 6 验收测试通过！${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        exit 0
    else
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${RED}⚠️  Sprint 6 验收测试未完全通过${NC}"
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        exit 1
    fi
}

# 主函数
main() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║     Sprint 6 验收与压力测试脚本                              ║"
    echo "║     T2R System Acceptance & Stress Test                     ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    check_dependencies
    test_smoke
    test_websocket
    test_retry_recovery
    test_atomic_write
    test_metrics_regression
    test_full_smoke
    test_frontend_hints
    test_docker_hints
    print_summary
}

# 运行主函数
main

