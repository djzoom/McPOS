#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
FRONTEND_DIR="$ROOT_DIR/kat_rec_web/frontend"
BACKEND_DIR="$ROOT_DIR/kat_rec_web/backend"
DOC_OUT="$ROOT_DIR/docs/ENTROPY_REPORT.md"
SIZE_TXT="$ROOT_DIR/docs/FRONTEND_SIZE.txt"

echo "== Entropy Report =="

echo "- Frontend node_modules size (before):"
if [ -d "$FRONTEND_DIR/node_modules" ]; then
  du -sh "$FRONTEND_DIR/node_modules" | tee "$SIZE_TXT"
else
  echo "node_modules not found" | tee "$SIZE_TXT"
fi

echo "- Top 20 biggest packages:"
if [ -d "$FRONTEND_DIR/node_modules" ]; then
  du -sh "$FRONTEND_DIR/node_modules"/* 2>/dev/null | sort -hr | head -20
else
  echo "(skipped)"
fi

echo "- Python freeze (backend minimal):"
if command -v python3 >/dev/null 2>&1; then
  (cd "$BACKEND_DIR" && python3 -m pip freeze | sort | sed 's/^/    /') || true
fi

echo "- File counts:"
BACKEND_COUNT=$(find "$BACKEND_DIR/t2r" -type f | wc -l | tr -d ' ' || echo 0)
FRONTEND_COUNT=$(find "$FRONTEND_DIR" -type f -name "*.{ts,tsx}" -o -name "*.ts" -o -name "*.tsx" 2>/dev/null | wc -l | tr -d ' ' || echo 0)
echo "  backend/t2r files: $BACKEND_COUNT"
echo "  frontend ts/tsx files: $FRONTEND_COUNT"

# Emit markdown summary
mkdir -p "$ROOT_DIR/docs"
{
  echo "# ENTROPY_REPORT"
  echo ""
  echo "## Frontend node_modules size"
  if [ -f "$SIZE_TXT" ]; then cat "$SIZE_TXT"; else echo "(no data)"; fi
  echo ""
  echo "## Top 20 biggest frontend packages"
  if [ -d "$FRONTEND_DIR/node_modules" ]; then
    du -sh "$FRONTEND_DIR/node_modules"/* 2>/dev/null | sort -hr | head -20 | sed 's/^/ - /'
  else
    echo "(node_modules missing)"
  fi
  echo ""
  echo "## Python dependency freeze (backend)"
  if command -v python3 >/dev/null 2>&1; then
    (cd "$BACKEND_DIR" && python3 -m pip freeze | sort | sed 's/^/ - /') || true
  fi
  echo ""
  echo "## File counts"
  echo "- backend/t2r files: $BACKEND_COUNT"
  echo "- frontend ts/tsx files: $FRONTEND_COUNT"
} > "$DOC_OUT"

echo "Saved report to $DOC_OUT"
