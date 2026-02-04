#!/usr/bin/env python3
# coding: utf-8
"""
Rename images in images_pool/available by describing each image via OpenAI Vision.

Behavior:
- For each image: call OpenAI once with the image as input, ask for <=10-word English phrase.
- Slugify the phrase and rename the file accordingly.
- Writes a JSONL report to reports/ for audit/revert.

Safety:
- Skips images referenced by any existing recipe.json (to avoid breaking old episodes).
- Supports --dry-run and --limit for cost control.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _iter_images(dir_path: Path) -> list[Path]:
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    files = [p for p in dir_path.iterdir() if p.is_file() and p.suffix.lower() in exts]
    files.sort(key=lambda p: p.name.lower())
    return files


def _collect_referenced_images(channels_root: Path) -> set[str]:
    """
    Collect cover_image_filename / image_filename from existing recipe.json files.
    """
    referenced: set[str] = set()
    if not channels_root.exists():
        return referenced

    for recipe_path in channels_root.rglob("recipe.json"):
        try:
            payload = json.loads(recipe_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        name = payload.get("cover_image_filename") or payload.get("image_filename")
        if name and isinstance(name, str):
            referenced.add(name)
    return referenced


def _resize_to_jpeg_bytes(image_path: Path, max_edge: int = 512, quality: int = 72) -> bytes:
    try:
        from PIL import Image
    except Exception as e:
        raise RuntimeError("Pillow is required for vision renaming. Install with: pip install Pillow") from e

    with Image.open(image_path) as img:
        img = img.convert("RGB")
        w, h = img.size
        scale = min(1.0, float(max_edge) / float(max(w, h)))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)))
        out = Path("/tmp") / f"kat_img_{_now_tag()}.jpg"
        img.save(out, format="JPEG", quality=quality, optimize=True)
        data = out.read_bytes()
        try:
            out.unlink()
        except Exception:
            pass
        return data


def _clean_caption_to_words(text: str) -> list[str]:
    # Keep only letters/spaces, collapse whitespace.
    cleaned = re.sub(r"[^A-Za-z ]", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    words = cleaned.split()
    # Enforce <=10 words.
    if len(words) > 10:
        words = words[:10]
    # Remove immediate duplicates ("focus focus").
    out: list[str] = []
    for w in words:
        lw = w.lower()
        if out and out[-1].lower() == lw:
            continue
        out.append(w)
    return out


def _slugify(words: list[str]) -> str:
    if not words:
        return ""
    s = "_".join(w.lower() for w in words)
    s = re.sub(r"[^a-z_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _pick_unique_target(dir_path: Path, stem: str, suffix: str) -> Path:
    """
    Ensure we never overwrite an existing file.
    """
    candidate = dir_path / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate
    for i in range(2, 1000):
        cand = dir_path / f"{stem}_{i}{suffix}"
        if not cand.exists():
            return cand
    raise RuntimeError(f"Could not find unique filename for stem={stem}")


def _openai_caption_image(
    api_key: str,
    image_bytes: bytes,
    model: str,
    timeout: int,
) -> str:
    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError("openai python package is required. Install with: pip install openai") from e

    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:image/jpeg;base64,{b64}"

    client = OpenAI(api_key=api_key, timeout=timeout)
    system = "You write concise, literal image captions for file naming."
    user = (
        "Describe this image in ONE short English phrase of 3 to 10 words.\n"
        "Hard rules:\n"
        "- No more than 10 words\n"
        "- Letters and spaces only\n"
        "- No punctuation, no numbers, no emojis\n"
        "- Concrete content only (objects, setting, visible motifs)\n"
        "Return only the phrase."
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        max_tokens=48,
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(REPO_ROOT / "images_pool" / "available"))
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--sleep", type=float, default=0.2, help="Sleep seconds between API calls")
    ap.add_argument("--limit", type=int, default=0, help="Process at most N images (0 = all)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from mcpos.config import get_config, get_openai_api_key
    from mcpos.core.logging import log_info, log_warning

    dir_path = Path(args.dir).resolve()
    if not dir_path.exists():
        raise SystemExit(f"Directory not found: {dir_path}")

    api_key = get_openai_api_key()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set (or config/openai_api_key.txt missing)")

    cfg = get_config()
    referenced = _collect_referenced_images(cfg.channels_root)

    images = _iter_images(dir_path)
    if args.limit and args.limit > 0:
        images = images[: args.limit]

    report_dir = REPO_ROOT / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"vision_rename_images_{_now_tag()}.jsonl"

    log_info(f"Scanning: {dir_path}")
    log_info(f"Found {len(images)} image(s) to consider")
    log_info(f"Report: {report_path}")
    if args.dry_run:
        log_warning("DRY-RUN: no files will be renamed")

    renamed = 0
    skipped_referenced = 0
    skipped_errors = 0

    with report_path.open("w", encoding="utf-8") as f:
        for idx, img_path in enumerate(images, 1):
            if img_path.name in referenced:
                skipped_referenced += 1
                rec = {
                    "status": "skipped_referenced",
                    "path": str(img_path),
                    "filename": img_path.name,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                continue

            try:
                jpeg_bytes = _resize_to_jpeg_bytes(img_path)
                caption_raw = _openai_caption_image(
                    api_key=api_key,
                    image_bytes=jpeg_bytes,
                    model=args.model,
                    timeout=args.timeout,
                )
                words = _clean_caption_to_words(caption_raw)
                stem = _slugify(words)
                if not stem:
                    # Deterministic local fallback: reuse cleaned words from old filename stem.
                    stem = re.sub(r"[^a-z_]+", "_", img_path.stem.lower()).strip("_")[:80] or "untitled_image"

                target = _pick_unique_target(img_path.parent, stem, img_path.suffix.lower())

                rec = {
                    "status": "planned" if args.dry_run else "renamed",
                    "idx": idx,
                    "old": img_path.name,
                    "new": target.name,
                    "caption_raw": caption_raw,
                    "caption_words": words,
                    "model": args.model,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()

                if not args.dry_run:
                    img_path.rename(target)
                    renamed += 1

                if args.sleep > 0:
                    time.sleep(args.sleep)
            except Exception as e:
                skipped_errors += 1
                rec = {
                    "status": "error",
                    "idx": idx,
                    "path": str(img_path),
                    "filename": img_path.name,
                    "error": f"{type(e).__name__}: {e}",
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()

    log_info(f"Done. renamed={renamed}, skipped_referenced={skipped_referenced}, errors={skipped_errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

