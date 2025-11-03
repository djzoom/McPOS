#!/usr/bin/env bash
set -euo pipefail

# 一键生成 4K 静帧视频（本地环境）
# - 自动创建并使用 .venv
# - 安装依赖
# - 运行全流程（封面/歌单/混音/视频）
# - 完成后自动打开产出目录

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "🔧 Checking Python venv (.venv)..."
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

echo "📦 Installing dependencies..."
source .venv/bin/activate
python -m pip install -U pip >/dev/null 2>&1 || true
pip install -r requirements.txt

echo "🎬 Generating 4K cover, playlist, remix and video..."
PYTHONPATH="$REPO_DIR" python scripts/local_picker/create_mixtape.py --font_name Lora-Regular --fps 1

echo "✅ Done. Opening output folders..."
open output/video 2>/dev/null || true
open output/cover 2>/dev/null || true
open output/playlists 2>/dev/null || true

echo "📁 Output in: $REPO_DIR/output"

