#!/usr/bin/env bash
set -euo pipefail

API_BASE="http://127.0.0.1:8010"

echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║                  后端API功能测试（GUI黄金路径验证）                            ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# 测试计数
passed=0
failed=0

test_endpoint() {
  local name="$1"
  local method="$2"
  local endpoint="$3"
  local data="$4"
  
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "测试: $name"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  if [ "$method" = "POST" ]; then
    response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$API_BASE$endpoint" \
      -H 'Content-Type: application/json' \
      -d "$data" 2>/dev/null || echo "ERROR\nHTTP_CODE:000")
  else
    response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$API_BASE$endpoint" 2>/dev/null || echo "ERROR\nHTTP_CODE:000")
  fi
  
  http_code=$(echo "$response" | grep "HTTP_CODE:" | sed 's/HTTP_CODE://')
  body=$(echo "$response" | sed '/HTTP_CODE:/d')
  
  if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
    echo "✅ HTTP $http_code"
    echo "$body" | jq . 2>/dev/null | head -n 20 || echo "$body" | head -n 5
    ((passed++)) || true
    return 0
  else
    echo "❌ HTTP $http_code"
    echo "$body" | jq -r '.detail // .error // .' 2>/dev/null || echo "$body" | head -n 3
    ((failed++)) || true
    return 1
  fi
}

# 1. SRT检查端点
test_endpoint \
  "SRT检查" \
  "POST" \
  "/api/t2r/srt/inspect" \
  '{"episode_id":"test-episode-001"}'

echo ""

# 2. Desc Lint端点
test_endpoint \
  "描述检查" \
  "POST" \
  "/api/t2r/desc/lint" \
  '{"episode_id":"test-episode-001","description":"Test description"}'

echo ""

# 3. Plan端点
test_endpoint \
  "生成计划" \
  "POST" \
  "/api/t2r/plan" \
  '{"episode_id":"test-episode-001","schedule_date":"2025-11-03"}'

echo ""

# 4. Run端点
test_endpoint \
  "执行Runbook" \
  "POST" \
  "/api/t2r/run" \
  '{"episode_id":"test-episode-001","run_id":"test-run-001"}'

echo ""

# 5. Upload Verify端点
test_endpoint \
  "上传验证" \
  "POST" \
  "/api/t2r/upload/verify" \
  '{"episode_id":"test-episode-001","video_id":"test-video-123","platform":"youtube"}'

echo ""

# 6. Audit端点
test_endpoint \
  "审计报告" \
  "GET" \
  "/api/t2r/audit?report_type=daily&start_date=2025-11-01&end_date=2025-11-03" \
  ""

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "总结: ✅ $passed 通过 | ❌ $failed 失败"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

