#!/usr/bin/env bash
# Scan for unused exports in frontend TypeScript
set -euo pipefail

OUTPUT_FILE="audit/deadcode_frontend.txt"
mkdir -p audit

echo "🔍 Scanning frontend for unused exports..."

if ! command -v ts-prune >/dev/null 2>&1; then
    echo "⚠️  ts-prune not found. Install via: npm install -g ts-prune"
    echo "   Creating placeholder report..."
    echo "# Dead Code Scan - Frontend" > "$OUTPUT_FILE"
    echo "# Install ts-prune: npm install -g ts-prune" >> "$OUTPUT_FILE"
    echo "# Then run: ts-prune -p kat_rec_web/frontend/tsconfig.json" >> "$OUTPUT_FILE"
    exit 0
fi

cd kat_rec_web/frontend
ts-prune -p tsconfig.json > "../../$OUTPUT_FILE" 2>&1 || {
    echo "⚠️  Dead code scan completed (some findings expected)"
}
cd - >/dev/null

echo "✅ Dead code scan complete: $OUTPUT_FILE"
echo "   Review findings before removing code - some may be false positives"

