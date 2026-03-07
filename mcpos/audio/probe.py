"""Centralized ffprobe helpers for audio assets."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def probe_audio(path: Path) -> dict[str, Any]:
    if not Path(path).exists():
        return {}
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except Exception:
        return {}
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

    fmt = payload.get("format") or {}
    streams = payload.get("streams") or []
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    return {
        "path": str(path),
        "duration_sec": float(fmt.get("duration", 0.0) or 0.0),
        "bit_rate": int(fmt.get("bit_rate", 0) or 0),
        "size_bytes": int(fmt.get("size", 0) or 0),
        "sample_rate": int(audio_stream.get("sample_rate", 0) or 0),
        "channels": int(audio_stream.get("channels", 0) or 0),
        "codec_name": audio_stream.get("codec_name"),
    }


def probe_audio_duration(path: Path | None) -> float:
    if not path:
        return 0.0
    return float(probe_audio(Path(path)).get("duration_sec", 0.0) or 0.0)
