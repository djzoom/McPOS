"""
mcpos/core/scheduler.py — Episode scheduling and discovery

Reads from:
  channels/<id>/schedule_master.json  — explicit schedule (optional)
  channels/<id>/output/               — filesystem scan (implicit)

Episode ID convention: {channel_id}_{YYYYMMDD}
"""

from __future__ import annotations

import json
import calendar
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

from ..models import EpisodeSpec
from ..config import get_config
from .logging import log_info, log_warning


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _date_range(start: date, end: date) -> list[str]:
    """Generate YYYYMMDD strings from start to end (inclusive)."""
    result = []
    current = start
    while current <= end:
        result.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return result


# ---------------------------------------------------------------------------
# Channel discovery
# ---------------------------------------------------------------------------

def discover_channels(channels_root: Optional[Path] = None) -> list[str]:
    """List channel IDs from the channels/ directory."""
    if channels_root is None:
        channels_root = get_config().channels_root
    if not channels_root.exists():
        return []
    return sorted(
        d.name for d in channels_root.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


# ---------------------------------------------------------------------------
# Episode scheduling
# ---------------------------------------------------------------------------

def get_episodes_for_day(channel_id: str, target_date: str) -> List[EpisodeSpec]:
    """
    Return EpisodeSpec(s) for a given day (YYYYMMDD).

    Checks channels/<id>/schedule_master.json first.
    Falls back to one episode per day: {channel_id}_{YYYYMMDD}.
    """
    config = get_config()
    schedule_file = config.channels_root / channel_id / "schedule_master.json"

    if schedule_file.exists():
        try:
            schedule = json.loads(schedule_file.read_text(encoding="utf-8"))
            day_entry = schedule.get(target_date)
            if day_entry:
                if isinstance(day_entry, list):
                    return [
                        EpisodeSpec(
                            channel_id=channel_id,
                            episode_id=e.get("episode_id", f"{channel_id}_{target_date}"),
                            date=target_date,
                        )
                        for e in day_entry
                    ]
                if isinstance(day_entry, dict):
                    return [EpisodeSpec(
                        channel_id=channel_id,
                        episode_id=day_entry.get("episode_id", f"{channel_id}_{target_date}"),
                        date=target_date,
                    )]
        except Exception as e:
            log_warning(f"[scheduler] Failed to read schedule_master.json: {e}")

    # Default: one episode per day
    return [EpisodeSpec(
        channel_id=channel_id,
        episode_id=f"{channel_id}_{target_date}",
        date=target_date,
    )]


def get_episodes_for_month(channel_id: str, year: int, month: int) -> List[EpisodeSpec]:
    """Return all episode specs for a given year/month."""
    _, last_day = calendar.monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)

    specs: List[EpisodeSpec] = []
    for date_str in _date_range(start, end):
        specs.extend(get_episodes_for_day(channel_id, date_str))
    return specs


# ---------------------------------------------------------------------------
# Episode discovery
# ---------------------------------------------------------------------------

def get_incomplete_episodes(channel_id: Optional[str] = None) -> List[EpisodeSpec]:
    """
    Scan output directories for episodes that haven't completed all core stages.

    Useful for resuming interrupted production runs.
    """
    from ..adapters.filesystem import detect_episode_state_from_filesystem, build_asset_paths

    config = get_config()
    channel_ids = [channel_id] if channel_id else discover_channels(config.channels_root)
    specs: List[EpisodeSpec] = []

    for cid in channel_ids:
        output_dir = config.channels_root / cid / "output"
        if not output_dir.exists():
            continue

        for episode_dir in sorted(output_dir.iterdir()):
            if not episode_dir.is_dir():
                continue
            episode_id = episode_dir.name
            parts = episode_id.split("_")
            ep_date = parts[-1] if len(parts) > 1 and len(parts[-1]) == 8 else None

            spec = EpisodeSpec(channel_id=cid, episode_id=episode_id, date=ep_date)
            paths = build_asset_paths(spec, config)
            state = detect_episode_state_from_filesystem(spec, paths)

            if not state.is_core_complete():
                specs.append(spec)
                log_info(f"[scheduler] Incomplete: {episode_id}")

    return specs


def get_ready_to_upload(channel_id: Optional[str] = None) -> List[EpisodeSpec]:
    """
    Return episodes that are render-complete but not yet uploaded.

    Condition: render_complete.flag exists AND upload_complete.flag does NOT exist.
    """
    config = get_config()
    channel_ids = [channel_id] if channel_id else discover_channels(config.channels_root)
    specs: List[EpisodeSpec] = []

    for cid in channel_ids:
        output_dir = config.channels_root / cid / "output"
        if not output_dir.exists():
            continue

        for episode_dir in sorted(output_dir.iterdir()):
            if not episode_dir.is_dir():
                continue
            episode_id = episode_dir.name
            parts = episode_id.split("_")
            ep_date = parts[-1] if len(parts) > 1 and len(parts[-1]) == 8 else None

            render_flag = episode_dir / f"{episode_id}_render_complete.flag"
            upload_flag = episode_dir / f"{episode_id}_upload_complete.flag"

            if render_flag.exists() and not upload_flag.exists():
                specs.append(EpisodeSpec(
                    channel_id=cid, episode_id=episode_id, date=ep_date,
                ))

    return specs
