#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "[dev] ensure venv..."
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

echo "[dev] install deps..."
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt

echo "[dev] run tests..."
python -m pytest -q

echo "[dev] build cover + playlist..."
python scripts/local_picker/create_mixtape.py --seed 20251030 --font_name Lora-Regular --output_name dev_preview_cover.png || true

echo "[dev] done. Outputs in ./output"

