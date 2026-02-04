#!/usr/bin/env python3
# coding: utf-8
"""
Plan stage: allocate covers + generate album titles (AI) + write planned YouTube title.

New Kat Rec workflow (main trunk):
- Create episode folders first.
- Randomly pick covers from images_pool/available (do NOT move to used yet).
- Copy a per-episode cover into the episode folder.
- Generate album title (single-shot AI, strict: no fallback).
- Rename the per-episode cover copy to the album title (slug).
- Write recipe.json skeleton containing:
  - cover_image_filename (episode-local cover copy)
  - cover_source_filename (original filename in images_pool/available)
  - album_title
  - assets.theme_color_rgb
- Write <episode_id>_youtube_title.txt using deterministic subtitle selection (no AI).

After upload succeeds, uploader will move cover_source_filename from available -> used.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from mcpos.config import get_config, get_openai_api_key  # noqa: E402
from mcpos.core.logging import log_info, log_warning, log_error  # noqa: E402
from mcpos.adapters.color_extractor import extract_theme_color  # noqa: E402
from mcpos.adapters.ai_title_generator import (  # noqa: E402
    EpisodeBudget,
    generate_album_title,
    MAX_YT_TITLE_BYTES,
    MAX_YT_TITLE_CHARS,
)
from mcpos.adapters.titlegen.youtube import _build_youtube_title  # noqa: E402


def _date_to_iso(date_yyyymmdd: str) -> str:
    if len(date_yyyymmdd) == 8 and date_yyyymmdd.isdigit():
        return f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
    return date_yyyymmdd


def _slugify_album_title_for_filename(title: str) -> str:
    """
    Make a filesystem-safe slug for cover filename.
    Keep it deterministic and ASCII.
    """
    t = (title or "").strip().lower()
    t = re.sub(r"[^a-z0-9]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    return t or "untitled"


def _find_episode_cover_candidates(episode_dir: Path, episode_id: str) -> list[Path]:
    """
    Find candidate cover source images already in episode_dir.
    Exclude generated cover outputs (<episode_id>_cover.png).
    """
    candidates: list[Path] = []
    for p in episode_dir.glob("*.png"):
        if p.name == f"{episode_id}_cover.png":
            continue
        candidates.append(p)
    return candidates


def _load_reserved_cover_sources(channel_id: str) -> set[str]:
    """
    Reserved = already referenced as cover_source_filename in any recipe.json under:
      channels/<channel_id>/output/**
    """
    cfg = get_config()
    output_root = cfg.channels_root / channel_id / "output"
    reserved: set[str] = set()
    if not output_root.exists():
        return reserved
    for recipe_path in output_root.rglob("recipe.json"):
        try:
            payload = json.loads(recipe_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        src = (
            payload.get("cover_source_filename")
            or payload.get("cover_image_source_filename")
            or payload.get("cover_image_original_filename")
        )
        if isinstance(src, str) and src.strip():
            reserved.add(src.strip())
    return reserved


def _pick_cover_from_available(
    available_paths: list[Path],
    reserved_sources: set[str],
    used_pool_names: set[str],
    *,
    rng_seed: Optional[int] = None,
) -> Path:
    """
    Deterministic randomness is not required here; we just need "not sequential".
    Use SystemRandom-like shuffle behavior by hashing filenames if rng_seed provided.
    """
    candidates = [
        p for p in available_paths
        if p.name not in reserved_sources and p.name not in used_pool_names
    ]
    if not candidates:
        raise RuntimeError("No available cover images left after reserved/used filtering.")

    if rng_seed is None:
        import random

        rng = random.SystemRandom()
        return rng.choice(candidates)

    # Deterministic pick path for reproducibility in tests/dry runs.
    ranked = sorted(candidates, key=lambda p: hash((p.name, rng_seed)))
    return ranked[0]


def _write_recipe_plan_skeleton(
    recipe_path: Path,
    *,
    episode_id: str,
    channel_id: str,
    date_yyyymmdd: str,
    cover_image_filename: str,
    cover_source_filename: str,
    album_title: str,
    theme_color_rgb: tuple[int, int, int],
) -> None:
    existing: dict = {}
    if recipe_path.exists():
        try:
            existing = json.loads(recipe_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    payload = dict(existing)
    payload.setdefault("created_at", datetime.now().isoformat())
    payload["episode_id"] = episode_id
    payload["channel_id"] = channel_id
    payload["schedule_date"] = _date_to_iso(date_yyyymmdd)
    payload["date"] = date_yyyymmdd
    payload["cover_image_filename"] = cover_image_filename
    payload["cover_source_filename"] = cover_source_filename
    payload["album_title"] = album_title

    assets = payload.get("assets")
    if not isinstance(assets, dict):
        assets = {}
    assets["theme_color_rgb"] = list(theme_color_rgb)
    payload["assets"] = assets

    plan = payload.get("plan")
    if not isinstance(plan, dict):
        plan = {}
    plan["planned_at"] = datetime.now().isoformat()
    plan["planned_by"] = "plan_month_covers_titles.py"
    payload["plan"] = plan

    recipe_path.parent.mkdir(parents=True, exist_ok=True)
    recipe_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_youtube_title_file(
    title_path: Path,
    *,
    channel_id: str,
    album_title: str,
) -> str:
    seed = f"{album_title}|{channel_id}"
    youtube_title = _build_youtube_title(album_title, seed, MAX_YT_TITLE_CHARS, MAX_YT_TITLE_BYTES)
    title_path.parent.mkdir(parents=True, exist_ok=True)
    title_path.write_text(youtube_title, encoding="utf-8")
    return youtube_title


@dataclass
class PlanResult:
    episode_id: str
    date: str
    cover_source_filename: str
    cover_copy_filename: str
    album_title: str
    youtube_title: str


async def plan_range(
    channel_id: str,
    dates: list[str],
    *,
    force: bool = False,
) -> list[PlanResult]:
    cfg = get_config()
    api_key = get_openai_api_key()
    if not api_key or not api_key.strip():
        raise RuntimeError("OPENAI_API_KEY not set; plan stage requires AI album title generation.")

    available_paths = sorted(cfg.images_pool_available.glob("*.png"))
    used_pool_names = {p.name for p in cfg.images_pool_used.glob("*.png")}
    reserved_sources = _load_reserved_cover_sources(channel_id)

    results: list[PlanResult] = []

    for date_yyyymmdd in dates:
        episode_id = f"{channel_id}_{date_yyyymmdd}"
        episode_dir = cfg.channels_root / channel_id / "output" / episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)

        recipe_path = episode_dir / "recipe.json"
        title_path = episode_dir / f"{episode_id}_youtube_title.txt"

        if not force and recipe_path.exists():
            try:
                existing = json.loads(recipe_path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
            if existing.get("album_title") and existing.get("cover_image_filename") and title_path.exists():
                log_info(f"[plan] Skip already planned: {episode_id}")
                continue

        # If episode already has a local cover candidate, treat it as the copy source.
        local_candidates = _find_episode_cover_candidates(episode_dir, episode_id)
        cover_source_path: Optional[Path] = None
        cover_source_filename: Optional[str] = None
        cover_copy_path: Optional[Path] = None

        if local_candidates and not force:
            # Use the newest file as the intended cover copy (user may have manually placed it).
            local_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            cover_copy_path = local_candidates[0]
            cover_source_filename = cover_copy_path.name
            cover_source_path = cfg.images_pool_available / cover_source_filename
            log_info(f"[plan] Using existing episode-local cover copy: {episode_id} -> {cover_copy_path.name}")
        else:
            picked = _pick_cover_from_available(
                available_paths,
                reserved_sources=reserved_sources,
                used_pool_names=used_pool_names,
            )
            cover_source_path = picked
            cover_source_filename = picked.name

            cover_copy_path = episode_dir / cover_source_filename
            if cover_copy_path.exists():
                # Avoid accidental overwrite; keep a deterministic suffix.
                cover_copy_path = episode_dir / f"cover_{cover_source_filename}"
            shutil.copy2(cover_source_path, cover_copy_path)
            log_info(f"[plan] Copied cover for {episode_id}: {cover_source_filename} -> {cover_copy_path.name}")

        assert cover_copy_path is not None
        assert cover_source_path is not None
        assert cover_source_filename is not None

        # Extract theme color from the episode-local copy (same pixels).
        try:
            theme_rgb = extract_theme_color(cover_copy_path)
        except Exception as e:
            raise RuntimeError(f"[plan] Failed to extract theme color for {episode_id}: {e}") from e

        # AI album title: single-shot, strict (no fallback).
        budget = EpisodeBudget(max_calls=1)
        album_title = await generate_album_title(
            track_titles=[],
            image_filename=cover_source_filename,
            theme_color_rgb=theme_rgb,
            episode_date=_date_to_iso(date_yyyymmdd),
            api_key=api_key,
            channel_id=channel_id,
            budget=budget,
        )

        # Rename cover copy to album-title slug.
        slug = _slugify_album_title_for_filename(album_title)
        target_name = f"{slug}{cover_copy_path.suffix.lower()}"
        target_path = episode_dir / target_name
        if target_path.exists() and target_path.resolve() != cover_copy_path.resolve():
            # Ensure uniqueness within episode dir.
            i = 2
            while True:
                cand = episode_dir / f"{slug}_{i}{cover_copy_path.suffix.lower()}"
                if not cand.exists():
                    target_path = cand
                    target_name = cand.name
                    break
                i += 1

        if cover_copy_path.resolve() != target_path.resolve():
            cover_copy_path.rename(target_path)
            cover_copy_path = target_path

        youtube_title = _write_youtube_title_file(title_path, channel_id=channel_id, album_title=album_title)

        _write_recipe_plan_skeleton(
            recipe_path,
            episode_id=episode_id,
            channel_id=channel_id,
            date_yyyymmdd=date_yyyymmdd,
            cover_image_filename=cover_copy_path.name,
            cover_source_filename=cover_source_filename,
            album_title=album_title,
            theme_color_rgb=theme_rgb,
        )

        reserved_sources.add(cover_source_filename)

        results.append(
            PlanResult(
                episode_id=episode_id,
                date=date_yyyymmdd,
                cover_source_filename=cover_source_filename,
                cover_copy_filename=cover_copy_path.name,
                album_title=album_title,
                youtube_title=youtube_title,
            )
        )

        log_info(f"[plan] Planned {episode_id}: {album_title} ({cover_copy_path.name})")

    return results


def _build_dates(year: int, month: int, start_day: int, end_day: int) -> list[str]:
    import calendar

    _, last_day = calendar.monthrange(year, month)
    if start_day < 1 or start_day > last_day:
        raise ValueError(f"start_day out of range: {start_day} (last_day={last_day})")
    if end_day < start_day:
        raise ValueError(f"end_day must be >= start_day: {end_day} < {start_day}")
    if end_day > last_day:
        end_day = last_day
    return [f"{year:04d}{month:02d}{d:02d}" for d in range(start_day, end_day + 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan covers + titles for a month range (Plan stage)")
    parser.add_argument("channel_id", help="channel id, e.g. kat")
    parser.add_argument("year", type=int, help="year, e.g. 2026")
    parser.add_argument("month", type=int, help="month (1-12)")
    parser.add_argument("--start-day", type=int, default=1, help="start day (default: 1)")
    parser.add_argument("--end-day", type=int, default=31, help="end day inclusive (default: 31)")
    parser.add_argument("--force", action="store_true", help="overwrite/replan even if recipe/title exist")
    args = parser.parse_args()

    dates = _build_dates(args.year, args.month, args.start_day, args.end_day)

    import asyncio

    try:
        results = asyncio.run(plan_range(args.channel_id, dates, force=args.force))
    except KeyboardInterrupt:
        log_warning("[plan] Interrupted by user")
        raise SystemExit(130)
    except Exception as e:
        log_error(f"[plan] Failed: {e}")
        raise SystemExit(1)

    if not results:
        print("No episodes planned (already planned).")
        return

    print("\nPlanned episodes:")
    for r in results:
        print(f"- {r.episode_id}: {r.album_title} | {r.cover_copy_filename} (src={r.cover_source_filename})")


if __name__ == "__main__":
    main()

