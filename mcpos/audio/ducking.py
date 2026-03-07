"""Deterministic VO/music ducking and mixdown."""

from __future__ import annotations

import csv
import json
import math
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

from .probe import probe_audio_duration
from ..core.logging import log_warning
from ..vo.models import DuckingInterval, VOAsset, VOConfig, VOTimelineEntry


def _db_to_linear(db_value: float) -> float:
    return math.pow(10.0, db_value / 20.0)


def _volume_expr(intervals: Iterable[DuckingInterval]) -> str:
    expressions: list[str] = []
    for interval in intervals:
        duck_factor = _db_to_linear(interval.target_db)
        fade = max(0.001, interval.fade_sec)
        hold_start = interval.start_sec
        hold_end = interval.end_sec
        fade_down_start = max(0.0, hold_start - fade)
        fade_up_end = hold_end + fade
        expr = (
            f"if(lt(t,{fade_down_start:.3f}),1,"
            f"if(lt(t,{hold_start:.3f}),1-(1-{duck_factor:.6f})*(t-{fade_down_start:.3f})/{max(hold_start - fade_down_start, 0.001):.3f},"
            f"if(lt(t,{hold_end:.3f}),{duck_factor:.6f},"
            f"if(lt(t,{fade_up_end:.3f}),{duck_factor:.6f}+(1-{duck_factor:.6f})*(t-{hold_end:.3f})/{max(fade_up_end - hold_end, 0.001):.3f},1))))"
        )
        expressions.append(f"({expr})")
    return "*".join(expressions) if expressions else "1"


def _write_ducking_map(path: Path, intervals: list[DuckingInterval]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["segment_id", "start_sec", "end_sec", "target_db", "fade_sec", "source"])
        for interval in intervals:
            writer.writerow([
                interval.segment_id,
                f"{interval.start_sec:.3f}",
                f"{interval.end_sec:.3f}",
                f"{interval.target_db:.3f}",
                f"{interval.fade_sec:.3f}",
                interval.source,
            ])


def apply_ducking_and_mix(
    music_mix_path: Path,
    vo_assets: list[VOAsset],
    timeline_entries: list[VOTimelineEntry],
    vo_config: VOConfig,
    *,
    output_path: Path,
    ducking_map_path: Path,
    meta_json_path: Path,
) -> tuple[Path, Path, dict]:
    """Apply deterministic ducking and render a final mix."""

    music_mix_path = Path(music_mix_path)
    output_path = Path(output_path)
    ducking_map_path = Path(ducking_map_path)
    meta_json_path = Path(meta_json_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pairs = list(zip(vo_assets, timeline_entries, strict=False))
    if len(pairs) != len(vo_assets) or len(pairs) != len(timeline_entries):
        log_warning(
            "[audio/ducking] VO assets and timeline entries are misaligned; "
            f"mixing {len(pairs)} paired segment(s)"
        )

    intervals = [
        DuckingInterval(
            segment_id=entry.segment_id,
            start_sec=entry.start_sec,
            end_sec=entry.end_sec,
            target_db=vo_config.ducking_db,
            fade_sec=vo_config.fade_sec,
            source=entry.kind.value,
        )
        for _asset, entry in pairs
    ]
    _write_ducking_map(ducking_map_path, intervals)

    if not pairs:
        if music_mix_path.resolve() != output_path.resolve():
            shutil.copy2(music_mix_path, output_path)
        meta = {
            "degraded_to_music_only": True,
            "reason": "no_vo_assets",
            "interval_count": 0,
            "music_mix_path": str(music_mix_path),
            "final_mix_path": str(output_path),
        }
        meta_json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path, ducking_map_path, meta

    expr = _volume_expr(intervals)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(music_mix_path)]
    filters = [f"[0:a]volume='{expr}'[musicduck]"]
    mix_inputs = ["[musicduck]"]

    for idx, (asset, entry) in enumerate(pairs, start=1):
        cmd += ["-i", str(asset.path)]
        fade = max(0.1, min(vo_config.fade_sec, max(asset.duration_sec / 2.0, 0.1)))
        fade_out_start = max(0.0, asset.duration_sec - fade)
        delay_ms = max(0, int(round(entry.start_sec * 1000)))
        label = f"vo{idx}"
        filters.append(
            f"[{idx}:a]afade=t=in:st=0:d={fade:.3f},"
            f"afade=t=out:st={fade_out_start:.3f}:d={fade:.3f},"
            f"adelay={delay_ms}|{delay_ms}[{label}]"
        )
        mix_inputs.append(f"[{label}]")

    filters.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:normalize=0:duration=first[out]")
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[out]",
        "-c:a", "libmp3lame",
        "-b:a", "320k",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if result.returncode != 0:
        log_warning(f"[audio/ducking] Ducking failed, falling back to music-only mix: {result.stderr[-400:]}")
        shutil.copy2(music_mix_path, output_path)
        meta = {
            "degraded_to_music_only": True,
            "reason": "ducking_failed",
            "error": (result.stderr or "ffmpeg ducking failed")[-1000:],
            "interval_count": len(intervals),
            "expression": expr,
        }
        meta_json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path, ducking_map_path, meta

    meta = {
        "degraded_to_music_only": False,
        "interval_count": len(intervals),
        "expression": expr,
        "music_mix_duration_sec": probe_audio_duration(music_mix_path),
        "final_mix_duration_sec": probe_audio_duration(output_path),
        "final_mix_path": str(output_path),
    }
    meta_json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path, ducking_map_path, meta
