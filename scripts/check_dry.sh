#!/usr/bin/env bash
# DRY (Don't Repeat Yourself) enforcement checks
# Ensures no duplicate event types, stores, or schemas are introduced

set -euo pipefail

echo "🔍 Running DRY compliance checks..."

# Single source of WS event types check
echo "  Checking WS event types are only in routes/websocket.py..."
ws_event_count=$(grep -r "t2r_.*" kat_rec_web/backend/routes/websocket.py 2>/dev/null | wc -l | tr -d ' ')
if [ "$ws_event_count" -lt 5 ]; then
    echo "❌ ERROR: Expected at least 5 T2R event types in routes/websocket.py"
    exit 1
fi

# Check no duplicate event type definitions elsewhere (allow schema.py for type definitions and routes using broadcast_t2r_event)
duplicate_events=$(grep -r "t2r_.*" kat_rec_web/backend 2>/dev/null | \
    grep -v "routes/websocket.py" | \
    grep -v "t2r/events/schema.py" | \
    grep -v "broadcast_t2r_event" | \
    grep -v "tests" | \
    grep -v "docs" | \
    grep -v "\.pyc" | \
    grep -v "__pycache__" | \
    grep -v "Literal\[" | \
    grep -v "from.*websocket" || true)
if [ -n "$duplicate_events" ]; then
    echo "❌ ERROR: Found T2R event types defined outside routes/websocket.py (excluding schema definitions and imports):"
    echo "$duplicate_events"
    exit 1
fi

# Check no new Zustand slices outside stores/
echo "  Checking Zustand slices are only in stores/..."
new_slices=$(grep -r "create<.*Slice\|createSlice" kat_rec_web/frontend 2>/dev/null | grep -v "/stores/" | grep -v "node_modules" | grep -v ".next" || true)
if [ -n "$new_slices" ]; then
    echo "❌ ERROR: Found Zustand slices outside stores/ directory:"
    echo "$new_slices"
    exit 1
fi

# Check no new API endpoints (only existing ones)
echo "  Checking no new API endpoints added..."
new_endpoints=$(grep -r "@router\.(get|post|put|delete)" kat_rec_web/backend/desktop 2>/dev/null || true)
if [ -n "$new_endpoints" ]; then
    echo "❌ ERROR: Found new API endpoints in desktop wrapper (should only use existing):"
    echo "$new_endpoints"
    exit 1
fi

# Check no new WS channels
echo "  Checking no new WS channels added..."
new_ws=$(grep -r "@router\.websocket\|router\.websocket" kat_rec_web/backend/desktop 2>/dev/null || true)
if [ -n "$new_ws" ]; then
    echo "❌ ERROR: Found new WebSocket channels in desktop wrapper (should only use existing):"
    echo "$new_ws"
    exit 1
fi

echo "✅ All DRY checks passed!"

