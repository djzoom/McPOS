#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
IMG_DIR="$ROOT_DIR/assets/design/images"
N="${1:-}"

if [ -z "$N" ]; then
  echo "Usage: batch_generate_covers.sh <N>"
  exit 1
fi

if ! [[ "$N" =~ ^[0-9]+$ ]]; then
  echo "N must be a positive integer"
  exit 1
fi

COUNT=$(find "$IMG_DIR" -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' \) | wc -l | tr -d ' ')
if [ -z "$COUNT" ] || [ "$COUNT" -eq 0 ]; then
  echo "No images found in $IMG_DIR"
  exit 1
fi

if [ "$N" -gt "$COUNT" ]; then
  echo "Requested N=$N exceeds image count $COUNT"
  exit 2
fi

# Build list of N unique images (randomized) using Python for portability
python - "$IMG_DIR" "$N" <<'PY' > "$ROOT_DIR/.batch_images.txt"
import glob,random,os,sys
img_dir = sys.argv[1]
n = int(sys.argv[2])
imgs = []
for ext in ("*.png","*.jpg"):
    imgs.extend(glob.glob(os.path.join(img_dir, ext)))
random.shuffle(imgs)
print("\n".join(imgs[:n]))
PY

ix=0
while IFS= read -r img; do
  ix=$((ix+1))
  echo "[batch] ($ix/$N) -> $img"
  PYTHONPATH="$ROOT_DIR" python "$ROOT_DIR/scripts/local_picker/create_mixtape.py" \
    --image "$img" --font_name Lora-Regular --no-remix
done < "$ROOT_DIR/.batch_images.txt"

rm -f "$ROOT_DIR/.batch_images.txt"

echo "Batch completed: $N covers generated."

