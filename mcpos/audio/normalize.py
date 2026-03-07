"""Deterministic loudness normalization for VO assets."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Optional

from .probe import probe_audio_duration
from ..vo.models import NormalizationStats


def _codec_args(output_path: Path) -> list[str]:
    suffix = output_path.suffix.lower()
    if suffix == ".mp3":
        return ["-c:a", "libmp3lame", "-b:a", "320k"]
    if suffix == ".wav":
        return ["-c:a", "pcm_s16le"]
    return ["-c:a", "aac", "-b:a", "192k"]


def _extract_loudnorm_json(stderr_text: str) -> dict[str, Any]:
    start = stderr_text.rfind("{")
    end = stderr_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(stderr_text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def normalize_vo_audio(
    audio_path: Path,
    target_lufs: float = -14.0,
    target_peak: float = -1.0,
    *,
    output_path: Optional[Path] = None,
) -> NormalizationStats:
    """Run two-pass loudnorm and replace/emit a normalized asset."""

    audio_path = Path(audio_path)
    output_path = Path(output_path or audio_path)
    suffix = output_path.suffix or ".wav"
    temp_output = output_path.with_name(f"{output_path.stem}.normalized.tmp{suffix}")

    first_pass = subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "info",
            "-i", str(audio_path),
            "-af", f"loudnorm=I={target_lufs}:TP={target_peak}:LRA=11:print_format=json",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if first_pass.returncode != 0:
        raise RuntimeError((first_pass.stderr or "loudnorm first pass failed")[-1000:])
    measured = _extract_loudnorm_json(first_pass.stderr)

    loudnorm_filter = (
        f"loudnorm=I={target_lufs}:TP={target_peak}:LRA=11:"
        f"measured_I={measured.get('input_i', '-24.0')}:"
        f"measured_LRA={measured.get('input_lra', '1.0')}:"
        f"measured_TP={measured.get('input_tp', '-2.0')}:"
        f"measured_thresh={measured.get('input_thresh', '-34.0')}:"
        f"offset={measured.get('target_offset', '0.0')}:"
        f"linear=true:print_format=json"
    )
    second_pass = subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "info",
            "-i", str(audio_path),
            "-af", loudnorm_filter,
            *_codec_args(output_path),
            str(temp_output),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if second_pass.returncode != 0:
        raise RuntimeError((second_pass.stderr or "loudnorm second pass failed")[-1000:])
    normalized = _extract_loudnorm_json(second_pass.stderr)

    temp_output.replace(output_path)
    return NormalizationStats(
        input_path=audio_path,
        output_path=output_path,
        target_lufs=target_lufs,
        target_peak=target_peak,
        input_i=float(measured.get("input_i")) if measured.get("input_i") else None,
        output_i=float(normalized.get("output_i")) if normalized.get("output_i") else None,
        metadata={
            "input": measured,
            "output": normalized,
            "duration_sec": probe_audio_duration(output_path),
        },
    )
