#!/usr/bin/env bash
set -euo pipefail
BASE_URL=${BASE_URL:-http://localhost:8000}

step() { echo "\n== $1 =="; }

step "HEALTH"
curl -s "$BASE_URL/health" | jq '{status, mode, environment: {paths_valid: .environment.paths_valid}}'

step "METRICS SYSTEM"
curl -s "$BASE_URL/metrics/system" | jq '{cpu: .cpu_percent, mem_mb: .memory_mb, uptime: .uptime_sec, ws: .active_ws_connections}'

step "METRICS WS-HEALTH"
curl -s "$BASE_URL/metrics/ws-health" | jq '{active: .active_connections, status_count: .status_manager_count, events_count: .events_manager_count}'

step "PLAN (dry)"
curl -s -X POST "$BASE_URL/api/episodes/plan" -H 'Content-Type: application/json' -d '{"episode_id":"AUDIT-TEST-001"}' | jq '{status, recipe_json_path}'

step "RUN (dry_run)"
curl -s -X POST "$BASE_URL/api/episodes/run" -H 'Content-Type: application/json' -d '{"episode_id":"AUDIT-TEST-001","stages":["remix","render"],"dry_run":true}' | jq '{status, run_id, stages}'

step "FILES"
ls -l "$(cd "$(dirname "$0")/.." && pwd)/kat_rec_web/data" 2>/dev/null | head -10 || true
