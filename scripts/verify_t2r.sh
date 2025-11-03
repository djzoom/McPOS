#!/usr/bin/env bash
set -euo pipefail

API="http://127.0.0.1:8010"
WS="ws://127.0.0.1:8010"

echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║                  T2R API 端点验证脚本                                            ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""

errors=0

test_endpoint() {
  local name="$1"
  local method="$2"
  local endpoint="$3"
  local data="$4"
  local expected_code="${5:-200}"
  
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "测试: $name"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  if [ "$method" = "POST" ]; then
    response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$API$endpoint" \
      -H 'Content-Type: application/json' \
      -d "$data" 2>/dev/null || echo "ERROR\nHTTP_CODE:000")
  else
    response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$API$endpoint" 2>/dev/null || echo "ERROR\nHTTP_CODE:000")
  fi
  
  http_code=$(echo "$response" | grep "HTTP_CODE:" | sed 's/HTTP_CODE://')
  body=$(echo "$response" | sed '/HTTP_CODE:/d')
  
  if [ "$http_code" = "$expected_code" ]; then
    echo "✅ HTTP $http_code"
    echo "$body" | jq . 2>/dev/null | head -n 5 || echo "$body" | head -n 3
    return 0
  else
    echo "❌ HTTP $http_code (期望: $expected_code)"
    echo "$body" | jq -r '.detail // .error // .' 2>/dev/null || echo "$body" | head -n 3
    errors=$((errors + 1))
    return 1
  fi
}

echo "1) /api/t2r/scan"
test_endpoint "Scan (T2R)" "POST" "/api/t2r/scan" '{"channel_id":"kat-records"}' "200"
echo ""

echo "2) /api/mcrb/scan (alias)"
test_endpoint "Scan (MCRB alias)" "POST" "/api/mcrb/scan" '{"channel_id":"kat-records"}' "200"
echo ""

echo "3) /api/t2r/srt/inspect"
test_endpoint "SRT Inspect" "POST" "/api/t2r/srt/inspect" '{"episode_id":"test"}' "200"
echo ""

echo "4) /api/t2r/desc/lint"
test_endpoint "Desc Lint" "POST" "/api/t2r/desc/lint" '{"episode_id":"test","description":"test"}' "200"
echo ""

echo "5) /api/t2r/plan"
test_endpoint "Plan Episode" "POST" "/api/t2r/plan" '{"episode_id":"20251102"}' "200"
echo ""

echo "6) /api/t2r/run"
test_endpoint "Run Episode" "POST" "/api/t2r/run" '{"episode_id":"20251102","dry_run":true}' "200"
echo ""

echo "7) /api/t2r/upload/verify"
test_endpoint "Upload Verify" "POST" "/api/t2r/upload/verify" '{"episode_id":"test","video_id":"test123"}' "200"
echo ""

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $errors -eq 0 ]; then
  echo "✅ 所有端点验证通过"
  exit 0
else
  echo "❌ 有 $errors 个端点验证失败"
  exit 1
fi

