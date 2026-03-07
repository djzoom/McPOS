"""
channels/sg/plugin.py — Sleep in Grace Channel Plugin

SG is a healing/ambient/sleep music channel:
- 474 instrumental tracks, 50 vocal tracks
- No BPM constraint
- Long crossfade (30s) between tracks
- 6-hour sessions default
- Instrumental-preferred (vocal_mix_ratio = 5%)
- Background video loops from sg/assets/video/
"""

from __future__ import annotations

import asyncio
import random
import subprocess
from datetime import datetime
from pathlib import Path

from mcpos.core.channel import ChannelPlugin, register_channel
from mcpos.models import EpisodeSpec, AssetPaths, StageResult, StageName, Track
from mcpos.audio.catalog import scan_sg_library
from mcpos.core.logging import log_info, log_warning, log_error


@register_channel
class SGPlugin(ChannelPlugin):
    """Sleep in Grace — Healing ambient sleep music channel."""

    @classmethod
    def channel_id_str(cls) -> str:
        return "sg"

    # ------------------------------------------------------------------
    # Library
    # ------------------------------------------------------------------

    def scan_library(self) -> list[Track]:
        vocal_root_str = self.config.extra.get("vocal_library", "")
        vocal_root = Path(vocal_root_str).expanduser() if vocal_root_str else None

        catalog_csv_str = self.config.extra.get("catalog_csv", "")
        catalog_csv = Path(catalog_csv_str).expanduser() if catalog_csv_str else None

        log_info(f"[sg] Scanning library: {self.config.library_root}")
        tracks = scan_sg_library(
            instrumental_root=self.config.library_root,
            vocal_root=vocal_root,
            catalog_csv=catalog_csv,
        )
        log_info(f"[sg] Library: {len(tracks)} tracks "
                 f"({sum(1 for t in tracks if t.vocal_class == 'instrumental')} instrumental, "
                 f"{sum(1 for t in tracks if t.vocal_class == 'vocal')} vocal)")
        return tracks

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_tracks(self, spec: EpisodeSpec, catalog: list[Track]) -> list[Track]:
        """
        Select tracks for one SG episode.

        Strategy:
        - vocal_mix_ratio (default 5%) = fraction of vocal tracks to include
        - Prefer instrumental; sprinkle in vocal tracks
        - Filter: duration 120s–1200s (2–20 min)
        - Fill to target_duration_min
        """
        target_min = spec.target_duration_min or self.config.target_duration_min
        target_sec = target_min * 60
        vocal_ratio = float(self.config.extra.get("vocal_mix_ratio", 0.05))

        # Split pool
        instrumental = [
            t for t in catalog
            if t.vocal_class in ("instrumental", None) and 120 <= t.duration_sec <= 1200
        ]
        vocal = [
            t for t in catalog
            if t.vocal_class == "vocal" and 120 <= t.duration_sec <= 1200
        ]

        if not instrumental:
            log_warning("[sg] No instrumental tracks found; using all tracks")
            instrumental = [t for t in catalog if 120 <= t.duration_sec <= 1200]

        random.shuffle(instrumental)
        random.shuffle(vocal)

        # Build selection: fill instrumental, inject vocal at vocal_ratio
        selected: list[Track] = []
        total_sec = 0.0
        vocal_idx = 0
        instr_idx = 0
        vocal_inject_every = max(1, round(1.0 / vocal_ratio)) if vocal_ratio > 0 else None

        while total_sec < target_sec:
            # Inject a vocal track periodically
            if (vocal_inject_every and vocal and
                    len(selected) > 0 and len(selected) % vocal_inject_every == 0 and
                    vocal_idx < len(vocal)):
                selected.append(vocal[vocal_idx])
                total_sec += vocal[vocal_idx].duration_sec
                vocal_idx += 1
            elif instr_idx < len(instrumental):
                selected.append(instrumental[instr_idx])
                total_sec += instrumental[instr_idx].duration_sec
                instr_idx += 1
            else:
                break  # exhausted pool

        log_info(f"[sg] Selected {len(selected)} tracks ({total_sec/60:.1f} min)")
        return selected

    # ------------------------------------------------------------------
    # Audio mix — SG crossfade mixer
    # ------------------------------------------------------------------

    def build_mix(self, tracks: list[Track], spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
        """
        Build SG mix using long crossfade (30s) between tracks via ffmpeg.

        Uses ffmpeg's acrossfade filter chained across all tracks.
        Output: paths.music_mix_mp3 when available, otherwise paths.final_mix_mp3.
        """
        started_at = datetime.now()
        mix_output = paths.music_mix_mp3 if getattr(paths, "music_mix_mp3", None) else paths.final_mix_mp3

        if mix_output.exists():
            log_info(f"[sg] Mix already exists: {mix_output}")
            return StageResult(
                stage=StageName.MIX, success=True,
                duration_seconds=0.0, key_asset_paths=[mix_output],
                started_at=started_at, finished_at=datetime.now(),
            )

        if not tracks:
            return StageResult(
                stage=StageName.MIX, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message="No tracks selected",
                started_at=started_at, finished_at=datetime.now(),
            )

        mix_output.parent.mkdir(parents=True, exist_ok=True)

        crossfade_sec = int(self.config.crossfade_sec)

        try:
            output_path = self._build_crossfade_mix(tracks, mix_output, crossfade_sec)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            log_info(f"[sg] Mix complete: {output_path} ({duration:.1f}s)")
            return StageResult(
                stage=StageName.MIX, success=True,
                duration_seconds=duration,
                key_asset_paths=[output_path],
                started_at=started_at, finished_at=finished_at,
            )
        except Exception as e:
            log_error(f"[sg] build_mix failed: {e}")
            return StageResult(
                stage=StageName.MIX, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message=str(e),
                started_at=started_at, finished_at=datetime.now(),
            )

    def _build_crossfade_mix(
        self,
        tracks: list[Track],
        output_path: Path,
        crossfade_sec: int = 30,
    ) -> Path:
        """
        Build a crossfaded mix using ffmpeg acrossfade filter.

        For N tracks, the filter chain is:
          [0][1]acrossfade=d=30[a01];
          [a01][2]acrossfade=d=30[a02];
          ...
          [a0(N-2)][N-1]acrossfade=d=30[out]
        """
        n = len(tracks)

        # Build ffmpeg command
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]

        for track in tracks:
            cmd += ["-i", str(track.path)]

        # Build filtergraph
        if n == 1:
            # Single track: just encode directly
            filter_complex = "[0:a]anull[out]"
        else:
            parts = []
            prev = "[0:a]"
            for i in range(1, n):
                curr_in = f"[{i}:a]"
                if i < n - 1:
                    curr_out = f"[cf{i}]"
                else:
                    curr_out = "[out]"
                parts.append(f"{prev}{curr_in}acrossfade=d={crossfade_sec}:c1=tri:c2=tri{curr_out}")
                prev = curr_out if i < n - 1 else prev
                # Correct the prev pointer
                if i < n - 1:
                    prev = f"[cf{i}]"
            filter_complex = ";".join(parts)

        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:a", "libmp3lame",
            "-b:a", "320k",
            "-ar", "44100",
            str(output_path),
        ]

        log_info(f"[sg] Running ffmpeg crossfade mix ({n} tracks, {crossfade_sec}s crossfade)...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr[-1000:]}")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"ffmpeg produced empty output: {output_path}")

        return output_path

    # ------------------------------------------------------------------
    # Video render — loop background video
    # ------------------------------------------------------------------

    def render_video(self, spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
        """
        Render SG video: loop a random background video over the audio mix.

        Video loops are in sg/assets/video/ (53 MP4 files, ~30s each).
        The audio is paths.final_mix_mp3; output is paths.youtube_mp4.
        """
        started_at = datetime.now()

        if paths.youtube_mp4.exists():
            log_info(f"[sg] Video already exists: {paths.youtube_mp4}")
            return StageResult(
                stage=StageName.RENDER, success=True,
                duration_seconds=0.0, key_asset_paths=[paths.youtube_mp4],
                started_at=started_at, finished_at=datetime.now(),
            )

        if not paths.final_mix_mp3.exists():
            return StageResult(
                stage=StageName.RENDER, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message="Mix audio not found; run MIX stage first",
                started_at=started_at, finished_at=datetime.now(),
            )

        # Pick a random video loop
        video_dir = self.config.assets_root / "video"
        video_loops = list(video_dir.glob("*.mp4")) if video_dir.exists() else []
        if not video_loops:
            return StageResult(
                stage=StageName.RENDER, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message=f"No video loops found in {video_dir}",
                started_at=started_at, finished_at=datetime.now(),
            )

        bg_video = random.choice(video_loops)
        paths.youtube_mp4.parent.mkdir(parents=True, exist_ok=True)

        try:
            output = self._render_looped_video(paths.final_mix_mp3, bg_video, paths.youtube_mp4)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()

            # Write render_complete flag
            paths.render_complete_flag.touch(exist_ok=True)

            log_info(f"[sg] Render complete: {output} ({duration:.1f}s)")
            return StageResult(
                stage=StageName.RENDER, success=True,
                duration_seconds=duration,
                key_asset_paths=[output],
                started_at=started_at, finished_at=finished_at,
            )
        except Exception as e:
            log_error(f"[sg] render_video failed: {e}")
            return StageResult(
                stage=StageName.RENDER, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message=str(e),
                started_at=started_at, finished_at=datetime.now(),
            )

    def _render_looped_video(
        self,
        audio_path: Path,
        bg_video: Path,
        output_path: Path,
    ) -> Path:
        """
        Loop bg_video to match audio_path duration, mux together.

        ffmpeg command:
          -stream_loop -1 -i {bg_video}  (loop video indefinitely)
          -i {audio_path}
          -shortest                       (stop at audio end)
          -c:v libx264 -crf 23 -preset fast
          -c:a aac -b:a 192k
          -movflags +faststart
        """
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-stream_loop", "-1", "-i", str(bg_video),
            "-i", str(audio_path),
            "-shortest",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path),
        ]

        log_info(f"[sg] Rendering video: bg={bg_video.name}, audio={audio_path.name}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=14400)  # 4h timeout

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg render failed: {result.stderr[-1000:]}")

        return output_path

    # ------------------------------------------------------------------
    # Text generation
    # ------------------------------------------------------------------

    async def generate_text_async(self, spec: EpisodeSpec, paths: AssetPaths, tracks: list[Track]) -> StageResult:
        """Generate YouTube title/description/tags via Claude API."""
        from mcpos.text.generator import generate_episode_text

        try:
            return await generate_episode_text(spec, paths, tracks)
        except Exception as e:
            log_error(f"[sg] generate_text failed: {e}")
            return StageResult(
                stage=StageName.TEXT_BASE, success=False,
                duration_seconds=0.0, key_asset_paths=[],
                error_message=str(e),
                started_at=datetime.now(), finished_at=datetime.now(),
            )

    def generate_text(self, spec: EpisodeSpec, paths: AssetPaths, tracks: list[Track]) -> StageResult:
        """
        Synchronous compatibility wrapper.

        The formal SG pipeline awaits `generate_text_async()` directly.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.generate_text_async(spec, paths, tracks))

        return StageResult(
            stage=StageName.TEXT_BASE,
            success=False,
            duration_seconds=0.0,
            key_asset_paths=[],
            error_message="generate_text() cannot run inside an active event loop; await generate_text_async() instead",
            started_at=datetime.now(),
            finished_at=datetime.now(),
        )
