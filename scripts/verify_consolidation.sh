#!/usr/bin/env bash
# Verify consolidation changes
set -euo pipefail

echo "🔍 Verifying consolidation changes..."

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"

# 1) Health & Metrics
echo ""
echo "1) Health & Metrics"
echo "   Checking /health..."
if curl -sf "$BACKEND_URL/health" | jq -e '.status == "ok"' >/dev/null 2>&1; then
    echo "   ✅ /health returns 200 with status: ok"
else
    echo "   ⚠️  /health check failed or returned non-ok status"
    curl -s "$BACKEND_URL/health" | jq '.' || true
fi

echo "   Checking /metrics/system..."
if curl -sf "$BACKEND_URL/metrics/system" | jq -e '.uptime_sec' >/dev/null 2>&1; then
    echo "   ✅ /metrics/system returns uptime"
else
    echo "   ⚠️  /metrics/system check failed"
fi

echo "   Checking /metrics/ws-health..."
if curl -sf "$BACKEND_URL/metrics/ws-health" | jq -e '.active_connections' >/dev/null 2>&1; then
    echo "   ✅ /metrics/ws-health returns connection count"
    curl -sf "$BACKEND_URL/metrics/ws-health" | jq '{connections: .active_connections, status_buffer: .status_manager.current_buffer_size, events_buffer: .events_manager.current_buffer_size}' || true
else
    echo "   ⚠️  /metrics/ws-health check failed"
fi

# 2) Alias routes
echo ""
echo "2) Alias routes (/api/t2r/* and /api/mcrb/*)"
for ep in "scan" "srt/inspect"; do
    echo "   Testing $ep..."
    if curl -sf -X POST "$BACKEND_URL/api/t2r/$ep" -H 'Content-Type: application/json' -d '{}' >/dev/null 2>&1; then
        echo "      ✅ /api/t2r/$ep works"
    else
        echo "      ⚠️  /api/t2r/$ep failed (may be expected for some endpoints)"
    fi
    
    if curl -sf -X POST "$BACKEND_URL/api/mcrb/$ep" -H 'Content-Type: application/json' -d '{}' >/dev/null 2>&1; then
        echo "      ✅ /api/mcrb/$ep works (alias)"
    else
        echo "      ⚠️  /api/mcrb/$ep failed (may be expected for some endpoints)"
    fi
done

# 3) WS quick probe
echo ""
echo "3) WebSocket quick probe (10s)"
if [ -f "audit/ws_probe.py" ]; then
    timeout 12 python3 audit/ws_probe.py 2>/dev/null || true
    if [ -f "audit/ws_stats.json" ]; then
        COUNT=$(jq -r '.message_count // 0' audit/ws_stats.json)
        MAX_V=$(jq -r '.max_version // 0' audit/ws_stats.json)
        MIN_V=$(jq -r '.min_version // 0' audit/ws_stats.json)
        echo "   Messages received: $COUNT"
        echo "   Version range: $MIN_V → $MAX_V"
        if [ "$COUNT" -ge 5 ] && [ "$MAX_V" -gt "$MIN_V" ]; then
            echo "   ✅ WS probe passed (≥5 messages, version increasing)"
        else
            echo "   ⚠️  WS probe: need ≥5 messages with increasing version"
        fi
    fi
else
    echo "   ⚠️  audit/ws_probe.py not found, skipping WS probe"
fi

# 4) Build/Export
echo ""
echo "4) Frontend Build/Export"
if [ -d "kat_rec_web/frontend" ]; then
    cd kat_rec_web/frontend
    if pnpm build >/dev/null 2>&1; then
        echo "   ✅ Frontend build succeeded"
    else
        echo "   ⚠️  Frontend build failed"
    fi
    
    if pnpm export >/dev/null 2>&1; then
        if [ -d "out" ]; then
            echo "   ✅ Frontend export succeeded (out/ directory exists)"
        else
            echo "   ⚠️  Frontend export succeeded but out/ not found"
        fi
    else
        echo "   ⚠️  Frontend export failed"
    fi
    cd - >/dev/null
else
    echo "   ⚠️  Frontend directory not found"
fi

# 5) Atomic IO spot check
echo ""
echo "5) Atomic IO spot check"
if grep -r "open(.*'w')" kat_rec_web/backend/t2r 2>/dev/null | grep -v ".pyc" | grep -v "__pycache__" | head -5; then
    echo "   ⚠️  Found potential non-atomic file writes (review above)"
else
    echo "   ✅ No obvious non-atomic writes found in t2r/"
fi

echo ""
echo "✅ Consolidation verification complete"

