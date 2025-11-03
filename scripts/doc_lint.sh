#!/usr/bin/env bash
# Lint markdown documentation
set -euo pipefail

if ! command -v markdownlint >/dev/null 2>&1; then
    echo "⚠️  markdownlint not found. Install via: npm install -g markdownlint-cli"
    echo "   Continuing without linting..."
    exit 0
fi

echo "🔍 Linting markdown documentation..."
markdownlint docs/**/*.md --config .markdownlint.json || {
    echo "❌ Markdown linting failed"
    exit 1
}

echo "✅ All markdown files passed linting"

