"""
channels/rbr/plugin.py — Run Baby Run Channel Plugin

RBR is a running music channel:
- 468 tracks, BPM-stretch to target BPM
- DJ set style (hard cuts with beat alignment)
- 1–3h sessions
- Uses RunBabyRun audio engine via subprocess
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcpos.core.channel import ChannelPlugin, ChannelConfig, register_channel
from mcpos.models import EpisodeSpec, AssetPaths, StageResult, StageName, Track
from mcpos.audio.catalog import scan_bpm_library
from mcpos.core.logging import log_info, log_warning, log_error

# Path to RunBabyRun repo
RBR_REPO = Path("~/Downloads/RunBabyRun/code").expanduser()


@register_channel
class RBRPlugin(ChannelPlugin):
    """Run Baby Run — BPM-locked running music channel."""

    @classmethod
    def channel_id_str(cls) -> str:
        return "rbr"

    # ------------------------------------------------------------------
    # Library
    # ------------------------------------------------------------------

    def scan_library(self) -> list[Track]:
        library_root = self.config.library_root
        # Use RunBabyRun's catalog cache if available
        cache_csv = RBR_REPO / "output" / "work" / "catalog" / "rbr_catalog_cache.csv"

        log_info(f"[rbr] Scanning library: {library_root}")
        tracks = scan_bpm_library(
            library_root,
            cache_csv=cache_csv if cache_csv.exists() else None,
        )
        log_info(f"[rbr] Library: {len(tracks)} tracks")
        return tracks

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_tracks(self, spec: EpisodeSpec, catalog: list[Track]) -> list[Track]:
        """
        Select tracks within BPM tolerance of target_bpm.

        Tracks are selected by BPM proximity. If BPM info is missing,
        all tracks are considered candidates.
        """
        target_bpm = spec.target_bpm or self.config.target_bpm or 170
        bpm_tol = int(self.config.extra.get("bpm_tolerance", 5))
        target_min = spec.target_duration_min or self.config.target_duration_min
        target_sec = target_min * 60

        # Filter by BPM range
        candidates = [
            t for t in catalog
            if t.bpm is None or abs(t.bpm - target_bpm) <= bpm_tol
        ]

        if not candidates:
            log_warning(f"[rbr] No tracks in BPM range {target_bpm}±{bpm_tol}; using all")
            candidates = list(catalog)

        # Filter by duration
        candidates = [t for t in candidates if 60 <= t.duration_sec <= 600]
        random.shuffle(candidates)

        # Fill to target
        selected: list[Track] = []
        total_sec = 0.0
        for track in candidates:
            if total_sec >= target_sec:
                break
            selected.append(track)
            total_sec += track.duration_sec

        log_info(f"[rbr] Selected {len(selected)} tracks ({total_sec/60:.1f} min, BPM={target_bpm})")
        return selected

    # ------------------------------------------------------------------
    # Audio mix — delegate to RunBabyRun engine
    # ------------------------------------------------------------------

    def build_mix(self, tracks: list[Track], spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
        """
        Build RBR mix by calling the RunBabyRun CLI.

        RunBabyRun handles: BPM stretch, crossfade alignment, Intro/Outro packaging.
        Output is placed in paths.final_mix_mp3.
        """
        started_at = datetime.now()

        if paths.final_mix_mp3.exists():
            log_info(f"[rbr] Mix already exists: {paths.final_mix_mp3}")
            return StageResult(
                stage=StageName.MIX, success=True,
                duration_seconds=0.0, key_asset_paths=[paths.final_mix_mp3],
                started_at=started_at, finished_at=datetime.now(),
            )

        target_bpm = spec.target_bpm or self.config.target_bpm or 170
        target_min = spec.target_duration_min or self.config.target_duration_min

        # Write track list to a temp file for RBR CLI
        track_list_path = paths.episode_output_dir / "rbr_track_list.txt"
        track_list_path.parent.mkdir(parents=True, exist_ok=True)
        track_list_path.write_text(
            "\n".join(str(t.path) for t in tracks),
            encoding="utf-8",
        )

        # Call RBR CLI
        rbr_script = RBR_REPO / "scripts" / "rbr_constant_bpm_mix.py"
        if not rbr_script.exists():
            # Fallback: use a simple concatenation mix
            log_warning("[rbr] RunBabyRun script not found; using simple concatenation mix")
            return self._simple_concat_mix(tracks, paths, started_at)

        cmd = [
            sys.executable, str(rbr_script),
            "--bpm", str(target_bpm),
            "--minutes", str(target_min),
            "--input-dir", str(self.config.library_root),
            "--output", str(paths.final_mix_mp3),
        ]

        log_info(f"[rbr] Running RBR CLI: bpm={target_bpm}, min={target_min}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True,
                timeout=7200,
                cwd=str(RBR_REPO),
            )
            if result.returncode != 0:
                raise RuntimeError(f"RBR CLI failed: {result.stderr[-500:]}")

            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            log_info(f"[rbr] Mix complete ({duration:.1f}s)")
            return StageResult(
                stage=StageName.MIX, success=True,
                duration_seconds=duration,
                key_asset_paths=[paths.final_mix_mp3],
                started_at=started_at, finished_at=finished_at,
            )
        except Exception as e:
            log_error(f"[rbr] build_mix failed: {e}")
            return StageResult(
                stage=StageName.MIX, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message=str(e),
                started_at=started_at, finished_at=datetime.now(),
            )

    def _simple_concat_mix(
        self, tracks: list[Track], paths: AssetPaths, started_at: datetime
    ) -> StageResult:
        """Fallback: simple ffmpeg concatenation without BPM stretch."""
        if not tracks:
            return StageResult(
                stage=StageName.MIX, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message="No tracks to mix",
                started_at=started_at, finished_at=datetime.now(),
            )

        # Write concat list
        concat_list = paths.episode_output_dir / "concat_list.txt"
        lines = [f"file '{t.path}'" for t in tracks]
        concat_list.write_text("\n".join(lines), encoding="utf-8")

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c:a", "libmp3lame", "-b:a", "320k",
            str(paths.final_mix_mp3),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if result.returncode != 0:
            return StageResult(
                stage=StageName.MIX, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message=result.stderr[-500:],
                started_at=started_at, finished_at=datetime.now(),
            )

        finished_at = datetime.now()
        return StageResult(
            stage=StageName.MIX, success=True,
            duration_seconds=(finished_at - started_at).total_seconds(),
            key_asset_paths=[paths.final_mix_mp3],
            started_at=started_at, finished_at=finished_at,
        )

    # ------------------------------------------------------------------
    # Video render
    # ------------------------------------------------------------------

    def render_video(self, spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
        """
        Render RBR video: static cover image over audio mix.

        Uses ffmpeg to combine cover.png + final_mix.mp3 → youtube.mp4.
        """
        started_at = datetime.now()

        if paths.youtube_mp4.exists():
            log_info(f"[rbr] Video already exists: {paths.youtube_mp4}")
            return StageResult(
                stage=StageName.RENDER, success=True,
                duration_seconds=0.0, key_asset_paths=[paths.youtube_mp4],
                started_at=started_at, finished_at=datetime.now(),
            )

        if not paths.final_mix_mp3.exists():
            return StageResult(
                stage=StageName.RENDER, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message="Mix audio not found",
                started_at=started_at, finished_at=datetime.now(),
            )

        if not paths.cover_png.exists():
            return StageResult(
                stage=StageName.RENDER, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message="Cover image not found",
                started_at=started_at, finished_at=datetime.now(),
            )

        paths.youtube_mp4.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-i", str(paths.cover_png),
            "-i", str(paths.final_mix_mp3),
            "-shortest",
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-tune", "stillimage",
            str(paths.youtube_mp4),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=14400)
            if result.returncode != 0:
                raise RuntimeError(result.stderr[-500:])

            paths.render_complete_flag.touch(exist_ok=True)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            log_info(f"[rbr] Render complete ({duration:.1f}s)")
            return StageResult(
                stage=StageName.RENDER, success=True,
                duration_seconds=duration,
                key_asset_paths=[paths.youtube_mp4],
                started_at=started_at, finished_at=finished_at,
            )
        except Exception as e:
            log_error(f"[rbr] render_video failed: {e}")
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
            log_error(f"[rbr] generate_text failed: {e}")
            return StageResult(
                stage=StageName.TEXT_BASE, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message=str(e),
                started_at=started_at, finished_at=datetime.now(),
            )
