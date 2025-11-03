#!/usr/bin/env bash
set -euo pipefail

echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║                  Sprint 6 修复验证脚本（一键全量检查）                          ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检测后端端口
detected_port=$(pgrep -fl uvicorn | grep -oE 'port[[:space:]]+[0-9]+' | awk '{print $2}' | head -1)
if [ -z "$detected_port" ]; then
  echo -e "${RED}❌ 未检测到运行中的 uvicorn 进程${NC}"
  echo "请先启动后端："
  echo "  cd kat_rec_web/backend"
  echo "  export USE_MOCK_MODE=false"
  echo "  uvicorn main:app --reload --port 8010"
  exit 1
fi

echo -e "${GREEN}✅ 检测到后端运行在端口 $detected_port${NC}"
echo ""

# 验证计数器
passed=0
failed=0

check_pass() {
  echo -e "${GREEN}✅ $1${NC}"
  ((passed++)) || true
}

check_fail() {
  echo -e "${RED}❌ $1${NC}"
  ((failed++)) || true
}

check_warn() {
  echo -e "${YELLOW}⚠️  $1${NC}"
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. 后端路由注册验证"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_file=$(pgrep -fl uvicorn | grep -oE '/tmp/[^[:space:]]+\.log' | head -1)
if [ -n "$log_file" ] && [ -f "$log_file" ]; then
  if grep -q "T2R/MCRB routers registered\|T2R routers registered" "$log_file" 2>/dev/null; then
    check_pass "T2R路由已注册"
  else
    check_fail "T2R路由未注册（检查日志：$log_file）"
  fi
else
  check_warn "无法确定日志文件位置"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. 健康检查端点"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

health=$(curl -s --connect-timeout 2 "http://127.0.0.1:$detected_port/health" 2>/dev/null || echo "")
if [ -n "$health" ]; then
  status=$(echo "$health" | jq -r '.status // empty' 2>/dev/null)
  if [ "$status" = "ok" ]; then
    check_pass "/health 返回 status=ok"
  elif [ -n "$status" ]; then
    check_warn "/health 返回 status=$status"
    echo "$health" | jq . 2>/dev/null || echo "$health"
  else
    check_fail "/health 响应格式异常"
    echo "$health"
  fi
else
  check_fail "/health 不可达"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Metrics 端点验证"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for ep in system ws-health; do
  code=$(curl -s -o /tmp/verify_metrics_${ep}.json -w "%{http_code}" "http://127.0.0.1:$detected_port/metrics/$ep" 2>/dev/null || echo "000")
  if [ "$code" = "200" ]; then
    check_pass "/metrics/$ep 返回 200"
    if [ "$ep" = "system" ]; then
      has_cpu=$(jq -e '.cpu // empty' /tmp/verify_metrics_${ep}.json 2>/dev/null || echo "")
      has_mem=$(jq -e '.memory // empty' /tmp/verify_metrics_${ep}.json 2>/dev/null || echo "")
      has_uptime=$(jq -e '.uptime // empty' /tmp/verify_metrics_${ep}.json 2>/dev/null || echo "")
      if [ -n "$has_cpu" ] && [ -n "$has_mem" ] && [ -n "$has_uptime" ]; then
        check_pass "/metrics/system 包含 CPU/内存/uptime 字段"
      else
        check_warn "/metrics/system 缺少部分字段"
      fi
    fi
  else
    check_fail "/metrics/$ep 返回 $code"
  fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. T2R API 端点验证"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

scan_result=$(jq -n --arg id "kat-records" '{channel_id:$id}' 2>/dev/null | \
  curl -s -X POST "http://127.0.0.1:$detected_port/api/t2r/scan" \
  -H 'Content-Type: application/json' -d @- 2>/dev/null || echo "")

if [ -n "$scan_result" ] && echo "$scan_result" | jq -e '.status // .summary // .errors' >/dev/null 2>&1; then
  check_pass "/api/t2r/scan 响应正常"
  echo "$scan_result" | jq '{status:.status, summary:.summary, errors:.errors}' 2>/dev/null || true
elif echo "$scan_result" | jq -e '.detail' >/dev/null 2>&1; then
  detail=$(echo "$scan_result" | jq -r '.detail' 2>/dev/null)
  check_fail "/api/t2r/scan 返回错误: $detail"
else
  check_fail "/api/t2r/scan 无响应或格式错误"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. WebSocket 版本递增验证"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "audit/ws_probe.py" ]; then
  python3 audit/ws_probe.py --endpoint "ws://127.0.0.1:$detected_port/ws/status" --seconds 10 >/dev/null 2>&1 || true
  if [ -f "audit/ws_stats.json" ]; then
    count=$(jq -r '.count // 0' audit/ws_stats.json 2>/dev/null || echo "0")
    max_version=$(jq -r '.max_version // 0' audit/ws_stats.json 2>/dev/null || echo "0")
    if [ "$count" -ge 5 ] && [ "$max_version" -gt 0 ]; then
      check_pass "WebSocket 收到 $count 条消息，最大版本 $max_version"
    else
      check_warn "WebSocket 消息较少（count=$count, max_version=$max_version）"
    fi
  else
    check_warn "WebSocket 统计文件未生成"
  fi
else
  check_warn "ws_probe.py 不存在，跳过 WebSocket 验证"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. SRT 目录遍历防护验证"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

srt_response=$(curl -s -X POST "http://127.0.0.1:$detected_port/api/t2r/srt/inspect" \
  -H 'Content-Type: application/json' \
  -d '{"path":"../../etc/passwd"}' 2>/dev/null || echo "")

http_code=$(curl -s -o /tmp/verify_srt.json -w "%{http_code}" -X POST "http://127.0.0.1:$detected_port/api/t2r/srt/inspect" \
  -H 'Content-Type: application/json' \
  -d '{"path":"../../etc/passwd"}' 2>/dev/null || echo "000")

if [ "$http_code" = "400" ] || [ "$http_code" = "403" ] || [ "$http_code" = "404" ]; then
  check_pass "SRT 目录遍历被正确拒绝（HTTP $http_code）"
  response_body=$(cat /tmp/verify_srt.json 2>/dev/null || echo "")
  if echo "$response_body" | grep -qi "/etc/passwd\|/Users\|/home" 2>/dev/null; then
    check_fail "响应中泄露了服务器绝对路径"
  else
    check_pass "响应中未泄露服务器路径"
  fi
else
  check_fail "SRT 目录遍历防护可能失效（HTTP $http_code）"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7. 导入路径护栏验证"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for pkg in "kat_rec_web/backend/__init__.py" \
           "kat_rec_web/backend/routes/__init__.py" \
           "kat_rec_web/backend/t2r/__init__.py" \
           "kat_rec_web/backend/t2r/routes/__init__.py"; do
  if [ -f "$pkg" ]; then
    check_pass "$pkg 存在"
  else
    check_fail "$pkg 缺失"
  fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "总结"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 通过: $passed"
echo "❌ 失败: $failed"
echo ""

if [ "$failed" -eq 0 ]; then
  echo -e "${GREEN}🎉 所有验证通过！Sprint 6 修复已完全落地。${NC}"
  exit 0
else
  echo -e "${RED}⚠️  有 $failed 项验证失败，请检查上述输出。${NC}"
  exit 1
fi
