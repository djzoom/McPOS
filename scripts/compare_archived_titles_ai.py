#!/usr/bin/env python3
# coding: utf-8
"""
Compare archived full YouTube titles vs regenerated titles (AI album-title + deterministic subtitle).

This script is designed for review: it samples N archived episodes under
channels/<channel>/output/Archived/**/recipe.json, reads the existing full title
from *_youtube_title.txt, regenerates a new album title using the current
ai_title_generator pipeline, then assembles a new full YouTube title using the
deterministic subtitle pool.

It intentionally does NOT print secrets. It will attempt to read OPENAI_API_KEY
from the environment first; if missing, it will parse a quoted value from
~/.zshrc (common local setup).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
from pathlib import Path
from random import SystemRandom
from typing import Any

from mcpos.adapters.ai_title_generator import generate_album_title
from mcpos.adapters.titlegen.youtube import _build_youtube_title
from mcpos.adapters.ai_title_generator import MAX_YT_TITLE_CHARS, MAX_YT_TITLE_BYTES


def _read_openai_api_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key

    # Local convenience: many users keep keys in ~/.zshrc but do not export them
    # for non-interactive shells. Parse quoted assignment without printing.
    zshrc = Path.home() / ".zshrc"
    if not zshrc.exists():
        return None
    try:
        text = zshrc.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    m = re.search(r'OPENAI_API_KEY\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_old_full_title(folder: Path) -> str:
    primary = folder / f"{folder.name}_youtube_title.txt"
    if primary.exists():
        return primary.read_text(encoding="utf-8").strip()
    matches = list(folder.glob("*_youtube_title.txt"))
    if matches:
        return matches[0].read_text(encoding="utf-8").strip()
    return ""


def _parse_rgb(data: dict[str, Any]) -> tuple[int, int, int]:
    rgb = (data.get("assets") or {}).get("theme_color_rgb")
    if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
        try:
            return (int(rgb[0]), int(rgb[1]), int(rgb[2]))
        except Exception:
            return (128, 128, 128)
    return (128, 128, 128)


async def _run(args: argparse.Namespace) -> tuple[Path, Path]:
    archived_root = Path(args.archived_root)
    recipe_paths = sorted(archived_root.rglob("recipe.json"))
    if not recipe_paths:
        raise SystemExit(f"No recipe.json found under {archived_root}")

    n = min(args.n, len(recipe_paths))
    rng = SystemRandom()
    sample = rng.sample(recipe_paths, k=n)
    sample.sort(key=lambda p: p.parent.name)  # stable review order

    api_key = _read_openai_api_key()
    if not api_key:
        raise SystemExit(
            "OPENAI_API_KEY not found in environment and could not be parsed from ~/.zshrc"
        )

    rows: list[dict[str, str]] = []
    for recipe_path in sample:
        folder = recipe_path.parent
        data = _read_json(recipe_path)

        schedule_date = str(data.get("schedule_date") or data.get("episode_id") or folder.name)
        cover_filename = str(data.get("cover_image_filename") or "")
        old_full_title = _read_old_full_title(folder)

        # Regenerate album title using current pipeline (single-shot model call).
        new_album = await generate_album_title(
            track_titles=[],
            image_filename=cover_filename,
            theme_color_rgb=_parse_rgb(data),
            episode_date=schedule_date,
            api_key=api_key,
            api_base=None,
            model=None,
            channel_id=args.channel,
            budget=None,
            seed_salt=args.seed_salt,
        )

        new_full_title = _build_youtube_title(
            new_album,
            f"{new_album}|{args.channel}",
            MAX_YT_TITLE_CHARS,
            MAX_YT_TITLE_BYTES,
        )

        rows.append(
            {
                "date": schedule_date,
                "cover_image_filename": cover_filename,
                "old_full_title": old_full_title,
                "new_full_title": new_full_title,
            }
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_full = out_dir / f"archived_title_compare_{n}_ai.csv"
    out_min = out_dir / f"archived_title_compare_{n}_ai_min.csv"

    with out_full.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["date", "cover_image_filename", "old_full_title", "new_full_title"]
        )
        writer.writeheader()
        writer.writerows(rows)

    with out_min.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["cover_image_filename", "old_full_title", "new_full_title"]
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "cover_image_filename": r["cover_image_filename"],
                    "old_full_title": r["old_full_title"],
                    "new_full_title": r["new_full_title"],
                }
            )

    return out_full, out_min


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="kat")
    ap.add_argument("--archived-root", default="channels/kat/output/Archived")
    ap.add_argument("-n", type=int, default=25)
    ap.add_argument("--out-dir", default="reports")
    ap.add_argument("--seed-salt", default="archived_compare_ai")
    args = ap.parse_args()

    out_full, out_min = asyncio.run(_run(args))
    print(out_min)
    print(out_full)


if __name__ == "__main__":
    main()

