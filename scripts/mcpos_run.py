#!/usr/bin/env python3
"""
scripts/mcpos_run.py — McPOS CLI

Multi-channel YouTube content production CLI.

Commands:
    produce   Run production pipeline (init → render) for one or more episodes
    upload    Upload render-complete episodes to YouTube (quota-guarded)
    patrol    Monitor YouTube comments and post AI-generated replies
    status    Show production status across channels

Examples:
    python scripts/mcpos_run.py produce --channel kat --date 20260307
    python scripts/mcpos_run.py produce --channel kat --month 2026-03
    python scripts/mcpos_run.py produce --channel sg  --date 20260307
    python scripts/mcpos_run.py produce --all-channels --date 20260307
    python scripts/mcpos_run.py upload  --channel kat --ready
    python scripts/mcpos_run.py patrol  --all-channels --since 24
    python scripts/mcpos_run.py status  --all-channels
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure repo root is in Python path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mcpos.config import get_config
from mcpos.core.pipeline import run_episode_batch
from mcpos.core.scheduler import (
    discover_channels,
    get_episodes_for_day,
    get_episodes_for_month,
    get_incomplete_episodes,
    get_ready_to_upload,
)
from mcpos.adapters.filesystem import detect_episode_state_from_filesystem, build_asset_paths
from mcpos.models import EpisodeSpec


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _progress(result: dict, idx: int, total: int) -> None:
    status = result.get("status", "?")
    eid = result.get("episode_id", "?")
    icons = {"success": "✅", "skipped": "⏭", "failed": "❌", "error": "💥"}
    print(f"  [{idx:3d}/{total}] {icons.get(status, '?')} {eid} — {status}")


def _resolve_channels(args: argparse.Namespace) -> list[str]:
    """Return channel list from --channel or --all-channels flag."""
    if getattr(args, "all_channels", False):
        return discover_channels()
    if getattr(args, "channel", None):
        return [args.channel]
    return []


# ---------------------------------------------------------------------------
# produce
# ---------------------------------------------------------------------------

async def cmd_produce(args: argparse.Namespace) -> int:
    channels = _resolve_channels(args)
    if not channels:
        print("Error: specify --channel or --all-channels")
        return 1

    for channel_id in channels:
        if args.date:
            specs = get_episodes_for_day(channel_id, args.date)
        elif args.month:
            year, month = map(int, args.month.split("-"))
            specs = get_episodes_for_month(channel_id, year, month)
        elif args.incomplete:
            specs = get_incomplete_episodes(channel_id)
        else:
            print("Error: specify --date, --month, or --incomplete")
            return 1

        if not specs:
            print(f"[{channel_id}] No episodes to produce")
            continue

        dates = [s.date for s in specs if s.date]
        print(f"\n[{channel_id}] Producing {len(specs)} episode(s)...")

        results = await run_episode_batch(
            channel_id=channel_id,
            dates=dates,
            skip_completed=not args.force,
            progress_callback=_progress,
        )

        success = sum(1 for r in results if r["status"] == "success")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        failed  = sum(1 for r in results if r["status"] in ("failed", "error"))
        print(f"[{channel_id}] Done: ✅ {success}  ⏭ {skipped}  ❌ {failed}")

    return 0


# ---------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------

async def cmd_upload(args: argparse.Namespace) -> int:
    from mcpos.upload.oauth import ChannelOAuth
    from mcpos.upload.quota import QuotaGuard, QuotaExceeded, UPLOAD_COST
    from mcpos.adapters.uploader import upload_episode_video

    channels = _resolve_channels(args)
    if not channels:
        print("Error: specify --channel or --all-channels")
        return 1

    config = get_config()

    for channel_id in channels:
        if args.date:
            specs = get_episodes_for_day(channel_id, args.date)
        elif getattr(args, "ready", False):
            specs = get_ready_to_upload(channel_id)
        else:
            print("Error: specify --date or --ready")
            return 1

        if not specs:
            print(f"[{channel_id}] No episodes to upload")
            continue

        guard = QuotaGuard(
            channel_id=channel_id,
            budget=getattr(args, "quota_budget", None) or 3000,
            state_dir=config.channels_root / channel_id,
        )
        print(f"\n[{channel_id}] Quota remaining: {guard.remaining()} / {guard.budget}")

        uploaded = 0
        for spec in specs:
            try:
                guard.consume(UPLOAD_COST, dry_run=True)
            except QuotaExceeded as e:
                print(f"  ⛔ Quota exceeded: {e}")
                break

            paths = build_asset_paths(spec, config)
            print(f"  ⬆  Uploading {spec.episode_id}...")
            result = await upload_episode_video(spec, paths, config)

            if result.state == "uploaded":
                guard.consume(UPLOAD_COST)
                uploaded += 1
                print(f"  ✅ {spec.episode_id} → {result.video_id}")
            else:
                print(f"  ❌ {spec.episode_id}: {result.error}")

        print(f"[{channel_id}] Uploaded {uploaded}/{len(specs)}. Quota remaining: {guard.remaining()}")

    return 0


# ---------------------------------------------------------------------------
# patrol
# ---------------------------------------------------------------------------

async def cmd_patrol(args: argparse.Namespace) -> int:
    from mcpos.ops.comments import patrol_all_channels

    channels = _resolve_channels(args)
    config = get_config()
    if not channels:
        channels = discover_channels(config.channels_root)

    print(f"🔍 Patrolling comments: {', '.join(channels)}")
    results = await patrol_all_channels(
        channels_root=config.channels_root,
        channel_ids=channels,
        since_hours=getattr(args, "since", 24) or 24,
        dry_run=getattr(args, "dry_run", False),
    )

    total = sum(len(r) for r in results.values())
    print(f"\nPatrol complete: {total} comments handled")
    for cid, replies in results.items():
        print(f"  {cid}: {len(replies)} replies {'(dry run)' if args.dry_run else ''}")
    return 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    config = get_config()
    channels = _resolve_channels(args)
    if not channels:
        channels = discover_channels(config.channels_root)

    if not channels:
        print("No channels found")
        return 1

    for channel_id in channels:
        output_dir = config.channels_root / channel_id / "output"
        if not output_dir.exists():
            print(f"\n[{channel_id}] — no output directory")
            continue

        total = uploaded = ready = incomplete = 0
        for ep_dir in output_dir.iterdir():
            if not ep_dir.is_dir():
                continue
            eid = ep_dir.name
            total += 1
            if (ep_dir / f"{eid}_upload_complete.flag").exists():
                uploaded += 1
            elif (ep_dir / f"{eid}_render_complete.flag").exists():
                ready += 1
            else:
                incomplete += 1

        print(f"\n[{channel_id}] {total} episodes total")
        print(f"  ✅ Uploaded:    {uploaded}")
        print(f"  📦 Ready:       {ready}")
        print(f"  🔧 Incomplete:  {incomplete}")

    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcpos_run",
        description="McPOS — Multi-Channel Content Production CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- produce ----
    p = sub.add_parser("produce", help="Run production pipeline (init→render)")
    p.add_argument("--channel", help="Channel ID (kat / rbr / sg)")
    p.add_argument("--all-channels", action="store_true", help="All configured channels")
    p.add_argument("--date", help="Single date YYYYMMDD")
    p.add_argument("--month", help="Month YYYY-MM")
    p.add_argument("--incomplete", action="store_true", help="Resume all incomplete episodes")
    p.add_argument("--force", action="store_true", help="Re-run completed stages")

    # ---- upload ----
    p = sub.add_parser("upload", help="Upload ready episodes to YouTube")
    p.add_argument("--channel", help="Channel ID")
    p.add_argument("--all-channels", action="store_true")
    p.add_argument("--date", help="Single date YYYYMMDD")
    p.add_argument("--ready", action="store_true", help="Upload all render-complete episodes")
    p.add_argument("--quota-budget", type=int, help="Override daily quota budget")

    # ---- patrol ----
    p = sub.add_parser("patrol", help="Monitor and reply to YouTube comments")
    p.add_argument("--channel", help="Specific channel (default: all)")
    p.add_argument("--all-channels", action="store_true")
    p.add_argument("--since", type=int, default=24, help="Hours to look back (default: 24)")
    p.add_argument("--dry-run", action="store_true", help="Generate replies, don't post")

    # ---- status ----
    p = sub.add_parser("status", help="Show production status")
    p.add_argument("--channel", help="Specific channel")
    p.add_argument("--all-channels", action="store_true", help="All channels")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "produce":
        return asyncio.run(cmd_produce(args))
    elif args.command == "upload":
        return asyncio.run(cmd_upload(args))
    elif args.command == "patrol":
        return asyncio.run(cmd_patrol(args))
    elif args.command == "status":
        return cmd_status(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
