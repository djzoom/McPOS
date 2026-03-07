"""
channels/kat/plugin.py — KAT LoFi Channel Plugin

Wraps the existing KAT production logic into the ChannelPlugin interface.
KAT is the primary channel: 846 tracks, 170 BPM target, vinyl SFX, 3h sessions.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcpos.core.channel import ChannelPlugin, ChannelConfig, register_channel
from mcpos.models import EpisodeSpec, AssetPaths, StageResult, StageName, Track
from mcpos.audio.catalog import scan_bpm_library
from mcpos.core.logging import log_info, log_warning, log_error

# Cache for scanned library (in-process, reset between runs)
_catalog_cache: Optional[list[Track]] = None
_catalog_cache_mtime: Optional[float] = None


@register_channel
class KatPlugin(ChannelPlugin):
    """KAT Records Studio — Lo-Fi Jazz-Hop channel."""

    @classmethod
    def channel_id_str(cls) -> str:
        return "kat"

    # ------------------------------------------------------------------
    # Library
    # ------------------------------------------------------------------

    def scan_library(self) -> list[Track]:
        global _catalog_cache, _catalog_cache_mtime

        library_root = self.config.library_root
        cache_csv = library_root.parent.parent / "catalog" / "kat_catalog_cache.csv"

        # Invalidate in-process cache if CSV changed
        if cache_csv.exists():
            mtime = cache_csv.stat().st_mtime
            if _catalog_cache is not None and _catalog_cache_mtime == mtime:
                return _catalog_cache
            _catalog_cache_mtime = mtime

        log_info(f"[kat] Scanning library: {library_root}")
        tracks = scan_bpm_library(library_root, cache_csv=cache_csv if cache_csv.exists() else None)
        log_info(f"[kat] Library: {len(tracks)} tracks")

        _catalog_cache = tracks
        return tracks

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_tracks(self, spec: EpisodeSpec, catalog: list[Track]) -> list[Track]:
        """
        Select tracks for one KAT episode.

        Strategy:
        1. Filter to tracks with duration 90s–600s (1.5–10 min)
        2. Exclude tracks used in the last 60 episodes (dedup)
        3. Random shuffle, fill until target duration reached
        """
        target_min = spec.target_duration_min or self.config.target_duration_min
        target_sec = target_min * 60

        # Collect recently used track paths (avoid repeats)
        used_paths = self._recent_track_paths(spec, lookback=60)

        # Filter candidates
        candidates = [
            t for t in catalog
            if 90 <= t.duration_sec <= 600
            and str(t.path) not in used_paths
        ]

        if not candidates:
            log_warning("[kat] No fresh candidates; using full catalog")
            candidates = [t for t in catalog if 90 <= t.duration_sec <= 600]

        random.shuffle(candidates)

        # Fill to target duration
        selected: list[Track] = []
        total_sec = 0.0
        for track in candidates:
            if total_sec >= target_sec:
                break
            selected.append(track)
            total_sec += track.duration_sec

        log_info(f"[kat] Selected {len(selected)} tracks ({total_sec/60:.1f} min)")
        return selected

    def _recent_track_paths(self, spec: EpisodeSpec, lookback: int = 60) -> set[str]:
        """Collect paths used in recent episodes by scanning playlist.csv files."""
        from mcpos.config import get_config

        config = get_config()
        output_dir = config.channels_root / spec.channel_id / "output"
        if not output_dir.exists():
            return set()

        used: set[str] = set()
        episode_dirs = sorted(output_dir.iterdir(), reverse=True)[:lookback]

        for ep_dir in episode_dirs:
            if ep_dir.name == spec.episode_id:
                continue
            playlist = ep_dir / "playlist.csv"
            if not playlist.exists():
                continue
            try:
                with playlist.open(encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        val = row.get("Value", "").strip()
                        if val and val.endswith(".mp3"):
                            used.add(val)
            except Exception:
                pass

        return used

    # ------------------------------------------------------------------
    # Audio mix
    # ------------------------------------------------------------------

    def build_mix(self, tracks: list[Track], spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
        """
        Delegate to the existing KAT mix engine (assets/mix.py).

        The existing engine reads playlist.csv from paths.playlist_csv.
        We write the playlist first, then invoke run_remix_for_episode.
        """
        import asyncio
        from mcpos.assets.mix import run_remix_for_episode

        started_at = datetime.now()

        if paths.final_mix_mp3.exists():
            log_info(f"[kat] Mix already exists: {paths.final_mix_mp3}")
            return StageResult(
                stage=StageName.MIX, success=True,
                duration_seconds=0.0, key_asset_paths=[paths.final_mix_mp3],
                started_at=started_at, finished_at=datetime.now(),
            )

        try:
            result = asyncio.get_event_loop().run_until_complete(
                run_remix_for_episode(spec, paths)
            )
            return result
        except Exception as e:
            log_error(f"[kat] build_mix failed: {e}")
            return StageResult(
                stage=StageName.MIX, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message=str(e),
                started_at=started_at, finished_at=datetime.now(),
            )

    # ------------------------------------------------------------------
    # Video render
    # ------------------------------------------------------------------

    def render_video(self, spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
        """Delegate to existing render engine."""
        import asyncio
        from mcpos.assets.render import run_render_for_episode

        started_at = datetime.now()
        try:
            result = asyncio.get_event_loop().run_until_complete(
                run_render_for_episode(spec, paths)
            )
            return result
        except Exception as e:
            log_error(f"[kat] render_video failed: {e}")
            return StageResult(
                stage=StageName.RENDER, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message=str(e),
                started_at=started_at, finished_at=datetime.now(),
            )

    # ------------------------------------------------------------------
    # Text generation
    # ------------------------------------------------------------------

    def generate_text(self, spec: EpisodeSpec, paths: AssetPaths, tracks: list[Track]) -> StageResult:
        """Generate YouTube title/description/tags via Claude API."""
        import asyncio
        from mcpos.text.generator import generate_episode_text

        started_at = datetime.now()
        try:
            result = asyncio.get_event_loop().run_until_complete(
                generate_episode_text(spec, paths, tracks)
            )
            return result
        except Exception as e:
            log_error(f"[kat] generate_text failed: {e}")
            return StageResult(
                stage=StageName.TEXT_BASE, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message=str(e),
                started_at=started_at, finished_at=datetime.now(),
            )
