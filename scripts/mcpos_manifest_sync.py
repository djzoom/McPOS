#!/usr/bin/env python3
"""
Sync McPOS episode output into manifest + schedule_master.json.

Usage:
  python3 scripts/mcpos_manifest_sync.py <channel_id> <episode_id> [<episode_id> ...] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import re
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _atomic_write_json(path: Path, payload: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _to_schedule_date(episode_id: str) -> Optional[str]:
    match = re.search(r"(\d{8})", episode_id)
    return match.group(1) if match else None


def _pick_first_existing(base: Path, candidates: list[str]) -> Optional[Path]:
    for name in candidates:
        path = base / name
        if path.exists():
            return path
    return None


def _read_text_if_exists(path: Optional[Path]) -> Optional[str]:
    if not path or not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, payload: dict, dry_run: bool) -> None:
    if dry_run:
        return
    _atomic_write_json(path, payload)


def build_manifest(channel_id: str, episode_id: str, episode_dir: Path) -> dict:
    manifest_path = episode_dir / f"{episode_id}_manifest.json"
    manifest = _load_json(manifest_path)

    # Resolve assets
    video = _pick_first_existing(
        episode_dir,
        [
            f"{episode_id}_youtube.mp4",
            f"{episode_id}_final.mp4",
            f"{episode_id}.mp4",
        ],
    )
    cover = _pick_first_existing(
        episode_dir,
        [
            f"{episode_id}_cover.png",
            f"{episode_id}_cover.jpg",
            "cover.png",
            "cover.jpg",
        ],
    )
    title = _pick_first_existing(episode_dir, [f"{episode_id}_youtube_title.txt", "title.txt"])
    description = _pick_first_existing(episode_dir, [f"{episode_id}_youtube_description.txt", "description.txt"])
    tags = _pick_first_existing(episode_dir, [f"{episode_id}_youtube_tags.txt", "tags.txt"])
    subtitles = _pick_first_existing(episode_dir, [f"{episode_id}_youtube.srt", f"{episode_id}.srt"])
    playlist = _pick_first_existing(episode_dir, ["playlist.csv"])
    recipe = _pick_first_existing(episode_dir, ["recipe.json"])

    schedule_date = _to_schedule_date(episode_id)

    manifest.setdefault("episode_id", episode_id)
    manifest.setdefault("channel_id", channel_id)
    manifest.setdefault("created_at", datetime.utcnow().isoformat())
    manifest["updated_at"] = datetime.utcnow().isoformat()
    manifest["source"] = "mcpos"
    manifest["schema"] = "mcpos_manifest_v1"
    manifest["upload_ready"] = True
    if schedule_date:
        manifest["schedule_date"] = schedule_date

    paths = manifest.get("paths") or {}
    if video:
        paths["video"] = str(video)
    if cover:
        paths["cover"] = str(cover)
    if title:
        paths["title"] = str(title)
    if description:
        paths["description"] = str(description)
    if tags:
        paths["tags"] = str(tags)
    if subtitles:
        paths["subtitles"] = str(subtitles)
    if playlist:
        paths["playlist"] = str(playlist)
    if recipe:
        paths["recipe"] = str(recipe)
    manifest["paths"] = paths

    return manifest


def sync_schedule(channel_id: str, episode_id: str, manifest: dict, dry_run: bool) -> None:
    schedule_path = REPO_ROOT / "channels" / channel_id / "schedule_master.json"
    schedule = _load_json(schedule_path)
    episodes = schedule.get("episodes") or []

    entry = next((ep for ep in episodes if ep.get("episode_id") == episode_id), None)
    if not entry:
        # Create a minimal entry if missing
        episode_number = max([ep.get("episode_number", 0) for ep in episodes] or [0]) + 1
        entry = {
            "episode_id": episode_id,
            "episode_number": episode_number,
            "schedule_date": manifest.get("schedule_date"),
            "status": "pending",
            "title": None,
            "image_path": None,
            "output_file": None,
            "playlist_path": None,
            "tracks_used": [],
            "starting_track": None,
            "locked_at": None,
            "lock_reason": None,
        }
        episodes.append(entry)

    paths = manifest.get("paths") or {}
    if manifest.get("schedule_date") and not entry.get("schedule_date"):
        entry["schedule_date"] = manifest.get("schedule_date")
    if paths.get("video"):
        entry["output_file"] = paths["video"]
    if paths.get("cover"):
        entry["image_path"] = paths["cover"]
    if paths.get("playlist"):
        entry["playlist_path"] = paths["playlist"]

    # Optional title sync (only if empty)
    title_path = paths.get("title")
    if title_path and not entry.get("title"):
        title_text = _read_text_if_exists(Path(title_path))
        if title_text:
            entry["title"] = title_text

    schedule["episodes"] = episodes
    schedule["updated_at"] = datetime.utcnow().isoformat()
    _save_json(schedule_path, schedule, dry_run)


def sync_episode(channel_id: str, episode_id: str, dry_run: bool) -> None:
    episode_dir = REPO_ROOT / "channels" / channel_id / "output" / episode_id
    if not episode_dir.exists():
        raise FileNotFoundError(f"Episode output dir not found: {episode_dir}")

    manifest = build_manifest(channel_id, episode_id, episode_dir)
    manifest_path = episode_dir / f"{episode_id}_manifest.json"
    _save_json(manifest_path, manifest, dry_run)
    sync_schedule(channel_id, episode_id, manifest, dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync McPOS manifest to schedule_master.json")
    parser.add_argument("channel_id", help="Channel ID (e.g., kat)")
    parser.add_argument("episode_id", nargs="+", help="Episode ID(s) (e.g., kat_20260401)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files")
    args = parser.parse_args()

    errors = 0
    for episode_id in args.episode_id:
        try:
            sync_episode(args.channel_id, episode_id, args.dry_run)
            print(f"Synced: {args.channel_id}/{episode_id}")
        except Exception as exc:
            errors += 1
            print(f"Failed: {args.channel_id}/{episode_id} -> {exc}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
