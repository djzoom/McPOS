#!/usr/bin/env bash
# Scan for dead code in backend Python
set -euo pipefail

OUTPUT_FILE="audit/deadcode_backend.txt"
mkdir -p audit

echo "🔍 Scanning backend for dead code..."

if ! command -v vulture >/dev/null 2>&1; then
    echo "⚠️  vulture not found. Install via: pip install vulture"
    echo "   Creating placeholder report..."
    echo "# Dead Code Scan - Backend" > "$OUTPUT_FILE"
    echo "# Install vulture: pip install vulture" >> "$OUTPUT_FILE"
    echo "# Then run: vulture kat_rec_web/backend --min-confidence 80" >> "$OUTPUT_FILE"
    exit 0
fi

# Scan with min confidence 80%
vulture kat_rec_web/backend --min-confidence 80 > "$OUTPUT_FILE" 2>&1 || {
    echo "⚠️  Dead code scan completed (some findings expected)"
}

echo "✅ Dead code scan complete: $OUTPUT_FILE"
echo "   Review findings before removing code - some may be false positives"

