#!/usr/bin/env bash
set -euo pipefail
echo "Branch: $(git branch --show-current || echo '?')"
git log --oneline -5 --decorate || true

echo "---- docs / audit ----"
ls -lt docs 2>/dev/null | head || true
ls -lt audit 2>/dev/null | head || true

echo "---- markers ----"
miss=0
check() { [ -f "$1" ] && echo "OK   $1" || { echo "MISS $1"; miss=$((miss+1)); }; }
check kat_rec_web/backend/t2r/services/env_check.py
check kat_rec_web/backend/t2r/services/runbook_journal.py
check kat_rec_web/backend/t2r/services/retry_manager.py
check kat_rec_web/backend/t2r/routes/metrics.py
check kat_rec_web/backend/t2r/utils/atomic_write.py
check kat_rec_web/backend/t2r/utils/atomic_group.py
check kat_rec_web/docker-compose.yml
check docs/T2R_SPRINT5_COMPLETE.md
check docs/T2R_SPRINT6_COMPLETE.md
check docs/AUDIT_SPRINT6.md
check audit/ws_probe.py
echo "Missing: $miss"

echo "---- backend ----"
pgrep -fl uvicorn || echo "uvicorn not running"

detected_port=$(pgrep -fl uvicorn | grep -oE 'port[[:space:]]+[0-9]+' | awk '{print $2}' | head -1)
if [ -z "$detected_port" ]; then
  test_ports="8000 8010"
else
  test_ports="$detected_port"
fi

for port in $test_ports; do
  echo "检查端口 $port:"
  health=$(curl -s --connect-timeout 2 "http://127.0.0.1:$port/health" 2>/dev/null || echo "")
  if [ -n "$health" ]; then
    status=$(echo "$health" | jq -r '.status // empty' 2>/dev/null)
    if [ -n "$status" ]; then
      echo "  /health -> $status"
    else
      echo "  /health -> OK"
    fi
  else
    echo "  /health -> unreachable"
  fi
  
  for ep in system ws-health; do
    code=$(curl -s -o /tmp/_m_${port}_${ep}.json -w "%{http_code}" "http://127.0.0.1:$port/metrics/$ep" 2>/dev/null || echo "000")
    echo "  /metrics/$ep -> $code"
    [ "$code" = "200" ] && head -n 10 /tmp/_m_${port}_${ep}.json 2>/dev/null | jq . 2>/dev/null || true
  done
  
  scan_result=$(jq -n --arg id "kat-records" '{channel_id:$id}' 2>/dev/null | \
    curl -s -X POST "http://127.0.0.1:$port/api/t2r/scan" -H 'Content-Type: application/json' -d @- 2>/dev/null || echo "")
  if [ -n "$scan_result" ] && echo "$scan_result" | jq -e . >/dev/null 2>&1; then
    if echo "$scan_result" | jq -e '.status' >/dev/null 2>&1; then
      echo "  /api/t2r/scan -> OK"
      echo "$scan_result" | jq '{status:.status, summary:.summary, errors:.errors}' 2>/dev/null || echo "$scan_result"
    elif echo "$scan_result" | jq -e '.detail' >/dev/null 2>&1; then
      echo "  /api/t2r/scan -> 404"
    else
      echo "  /api/t2r/scan -> OK (响应格式未知)"
    fi
  elif echo "$scan_result" | jq -e '.detail' >/dev/null 2>&1; then
    echo "  /api/t2r/scan -> 404"
    echo "$scan_result" | jq -r '.detail' 2>/dev/null
  else
    echo "  /api/t2r/scan -> error (无响应)"
  fi
  echo ""
done
